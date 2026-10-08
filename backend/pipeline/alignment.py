"""Every video is transcribed via ElevenLabs Scribe v2 (no human-written
script — the ASR text itself becomes the transcript). This module splits
that transcript into sentences and fuzzy-aligns their words against Scribe's
word-level timestamps to recover a (start, end) time range per sentence.
"""
import re
from dataclasses import dataclass, field

from .tts import transcribe_with_scribe


@dataclass
class Segment:
    text: str
    start: float
    end: float
    translated_text: str = ""
    speech_text: str = ""
    raw_audio_path: str = ""
    final_audio_path: str = ""
    raw_duration: float = 0.0
    tempo_needed: float = 1.0
    tempo_applied: float = 1.0
    speed_used: float = 1.0
    regenerated: bool = False
    # Only meaningful for an actual audio atempo stretch (audio-mode, or the
    # residual_audio/fallback_audio review resolutions in video-mode) — True
    # when the needed stretch exceeded assemble.py's safe clamp range.
    audio_clamped: bool = False
    # Original (pre-video-retiming) timing — video-mode overwrites
    # start/end with the new retimed timeline, but keeps these so the UI
    # can still show how far a segment drifted from the source video.
    orig_start: float = 0.0
    orig_end: float = 0.0


def transcribe_full_via_scribe(audio_path: str) -> tuple[str, list[dict]]:
    """Returns a continuous punctuated transcript plus word-level timestamps
    from ElevenLabs Scribe v2, so the result can go through the same
    sentence-splitting + align_transcript_to_audio() path a human script
    would (re-split into clean grammatical sentences rather than trusting
    Scribe's own acoustic-pause-based segment boundaries, which often split
    mid-sentence or merge multiple sentences together).
    """
    result = transcribe_with_scribe(audio_path)
    words = [
        {"word": w["text"], "start": w["start"], "end": w["end"]}
        for w in result.get("words", [])
        if w.get("type") == "word"
    ]
    # Scribe's full text can include inline audio-event tags like "[music]" —
    # strip those before treating it as the transcript to translate.
    text = re.sub(r"\[[^\]]*\]", "", result.get("text", ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text, words


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _normalize(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def align_transcript_to_audio(transcript_text: str, asr_words: list[dict]) -> list[Segment]:
    """Maps each sentence of transcript_text to a (start, end) time range
    by fuzzy-aligning its words against the ASR word sequence.
    """
    sentences = split_sentences(transcript_text)

    # Flatten transcript into a single normalized word list, tracking which
    # sentence each word belongs to.
    ref_tokens: list[str] = []
    ref_sentence_idx: list[int] = []
    for s_idx, sentence in enumerate(sentences):
        for raw_word in sentence.split():
            norm = _normalize(raw_word)
            if norm:
                ref_tokens.append(norm)
                ref_sentence_idx.append(s_idx)

    asr_tokens = [_normalize(w["word"]) for w in asr_words]

    matcher_blocks = _sequence_matching_blocks(ref_tokens, asr_tokens)

    # ref_idx -> (start_time, end_time) for exactly-matched words.
    ref_time: dict[int, tuple[float, float]] = {}
    for ref_start, asr_start, size in matcher_blocks:
        for k in range(size):
            asr_word = asr_words[asr_start + k]
            ref_time[ref_start + k] = (asr_word["start"], asr_word["end"])

    n = len(ref_tokens)
    interpolated_start = _interpolate(n, ref_time, which=0)
    interpolated_end = _interpolate(n, ref_time, which=1)

    segments: list[Segment] = []
    for s_idx, sentence in enumerate(sentences):
        word_indices = [i for i, si in enumerate(ref_sentence_idx) if si == s_idx]
        if not word_indices:
            continue
        start = interpolated_start[word_indices[0]]
        end = interpolated_end[word_indices[-1]]
        if end <= start:
            end = start + 0.5
        segments.append(Segment(text=sentence, start=start, end=end, orig_start=start, orig_end=end))

    return segments


def _sequence_matching_blocks(ref_tokens: list[str], asr_tokens: list[str]):
    import difflib
    matcher = difflib.SequenceMatcher(None, ref_tokens, asr_tokens, autojunk=False)
    return [(b.a, b.b, b.size) for b in matcher.get_matching_blocks() if b.size > 0]


def _interpolate(n: int, ref_time: dict[int, tuple[float, float]], which: int) -> list[float]:
    known_indices = sorted(ref_time.keys())
    values = [0.0] * n
    if not known_indices:
        return values

    for idx in known_indices:
        values[idx] = ref_time[idx][which]

    # Fill before first known point.
    first = known_indices[0]
    for i in range(first):
        values[i] = values[first]

    # Fill after last known point.
    last = known_indices[-1]
    for i in range(last + 1, n):
        values[i] = values[last]

    # Linearly interpolate gaps between consecutive known points.
    for a, b in zip(known_indices, known_indices[1:]):
        if b - a <= 1:
            continue
        va, vb = values[a], values[b]
        span = b - a
        for i in range(a + 1, b):
            frac = (i - a) / span
            values[i] = va + (vb - va) * frac

    return values
