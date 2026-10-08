import math

from pydub import AudioSegment

from .video_utils import get_duration, time_stretch

# This is now a *residual* fine-tuning pass, not the primary corrector — the
# heavy lifting happens earlier via ElevenLabs' own speed setting (see
# orchestrator.py), which paces speech naturally instead of digitally
# stretching it. Kept at the original wide bound as a rarely-exercised safety
# net rather than a working limit: with the speed pass absorbing most of the
# gap upfront, real residual tempos land well under this in practice.
MIN_TEMPO = 0.7
MAX_TEMPO = 1.4


def fit_segment_to_duration(raw_path: str, stretched_path: str, target_duration: float) -> dict:
    """Time-stretches raw_path so it fits target_duration, clamped to a safe
    range so we never distort the voice into something unnatural.

    Returns diagnostics: raw_duration (untouched TTS output length),
    tempo_needed (the uncapped ratio required to hit target_duration exactly),
    and tempo_applied (the clamped factor actually used). When tempo_needed
    exceeds the clamp range, tempo_applied differs from it and the segment
    will over/undershoot target_duration even after stretching.
    """
    actual_duration = get_duration(raw_path)
    if actual_duration <= 0:
        return {"raw_duration": actual_duration, "tempo_needed": 1.0, "tempo_applied": 1.0}

    tempo_needed = actual_duration / target_duration
    tempo_applied = max(MIN_TEMPO, min(MAX_TEMPO, tempo_needed))
    time_stretch(raw_path, stretched_path, tempo_applied)
    return {
        "raw_duration": actual_duration,
        "tempo_needed": tempo_needed,
        "tempo_applied": tempo_applied,
    }


def assemble_track(segments: list, total_duration_seconds: float, output_path: str) -> None:
    """Places each segment's final audio at its original start time on a
    silent base track spanning the full video duration.
    """
    total_ms = int(total_duration_seconds * 1000)
    base = AudioSegment.silent(duration=total_ms)

    for seg in segments:
        if not seg.final_audio_path:
            continue
        clip = AudioSegment.from_file(seg.final_audio_path)
        position_ms = max(0, int(seg.start * 1000))
        base = base.overlay(clip, position=position_ms)

    base.export(output_path, format="mp3")


def _volume_pct_to_db(pct: float) -> float:
    """0-100 percent (100 = original file volume) to a pydub-compatible dB
    gain. log10(0) is undefined, so 0% (fully muted) is handled separately
    rather than computed.
    """
    if pct <= 0:
        return -120.0  # inaudible; avoids a log10(0) domain error
    return 20 * math.log10(pct / 100)


def compose_final_audio(
    voice_path: str,
    logo_intro_path: str | None,
    main_bgm_path: str | None,
    video_duration: float,
    logo_intro_fade_in: float,
    logo_intro_fade_out: float,
    logo_intro_volume_pct: float,
    main_bgm_start: float,
    main_bgm_fade_in: float,
    main_bgm_fade_out: float,
    main_bgm_volume_pct: float,
    output_path: str,
) -> None:
    """Layers up to three audio tiers onto the dubbed voice track: a short
    branded logo-intro jingle at the very start, and a main background music
    bed that kicks in at main_bgm_start (either right after the intro, or at
    an operator-chosen timestamp) and plays through to the end of the video
    (or its own natural end, whichever comes first — it is not looped).

    voice_path already spans the full video_duration (silence-padded), so
    that's the base every other layer gets overlaid onto. Either music path
    can be None to skip that tier entirely (e.g. operator picked "none").
    """
    base = AudioSegment.from_file(voice_path)

    if logo_intro_path:
        intro = AudioSegment.from_file(logo_intro_path)
        fade_in_ms = int(max(0, logo_intro_fade_in) * 1000)
        fade_out_ms = int(max(0, logo_intro_fade_out) * 1000)
        intro = intro.fade_in(fade_in_ms).fade_out(fade_out_ms) + _volume_pct_to_db(logo_intro_volume_pct)
        base = base.overlay(intro, position=0)

    if main_bgm_path:
        available_ms = int(max(0, video_duration - main_bgm_start) * 1000)
        if available_ms > 0:
            bgm = AudioSegment.from_file(main_bgm_path)[:available_ms]
            fade_in_ms = int(max(0, main_bgm_fade_in) * 1000)
            fade_out_ms = int(max(0, main_bgm_fade_out) * 1000)
            bgm = bgm.fade_in(fade_in_ms).fade_out(fade_out_ms) + _volume_pct_to_db(main_bgm_volume_pct)
            base = base.overlay(bgm, position=int(max(0, main_bgm_start) * 1000))

    base.export(output_path, format="mp3")
