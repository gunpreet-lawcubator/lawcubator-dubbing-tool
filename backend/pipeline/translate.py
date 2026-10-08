import json
import os
import re

from openai import OpenAI

from .glossary import load_glossary

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    return _client


def _build_system_prompt(language_name: str, num_sentences: int, glossary: dict, operator_notes: str = "") -> str:
    glossary_block = ""
    if glossary:
        lines = "\n".join(f'- "{en}" -> "{target}"' for en, target in glossary.items())
        glossary_block = (
            "\n\nUse these exact translations whenever these English terms appear, "
            f"regardless of how you would otherwise translate them:\n{lines}"
        )

    notes_block = ""
    if operator_notes.strip():
        notes_block = (
            "\n\nIMPORTANT — operator-provided corrections for this specific video. These come "
            "from a human reviewer and take priority over your own judgment or the source "
            f"transcript's wording wherever they conflict:\n{operator_notes.strip()}"
        )

    return (
        f"You are a professional translator for corporate employee training videos, translating "
        f"English into {language_name}.\n\n"
        f"You will be given the full script of a training video as a numbered list of sentences, "
        f"in order. Translate ALL of them together, using the full script as context so that:\n"
        f"- Word choice reflects the actual meaning in context (this is workplace/HR/compliance "
        f"training content, not academic material) rather than a literal word-by-word translation.\n"
        f"- The same recurring terms, names, and phrases are translated the same way every time "
        f"they appear.\n"
        f"- Tone and formality stay consistent across the whole script.\n\n"
        f"Register: use natural, everyday spoken {language_name} — the way a professional would "
        f"actually talk in an Indian workplace. Do NOT use overly formal, literary, or heavily "
        f"Sanskritized/\"shuddh\" vocabulary. Keep common English business/tech words "
        f"(e.g. email, password, login, dashboard, OTP, HR, server) in English if that is how "
        f"they would naturally be said out loud, rather than translating them into obscure native "
        f"equivalents. Preserve product/company names as proper nouns, untranslated.\n\n"
        f"Two versions per sentence — this is the important part: for each sentence, produce a "
        f"'display' version and a 'speech' version. They should be identical in wording — same "
        f"language, same translation — except for how English acronyms/abbreviations are cased, "
        f"because the two versions serve different purposes:\n"
        f"- 'display' is what viewers will READ as an on-screen subtitle: write acronyms in "
        f"whatever form is most widely recognized in real-world writing, however that's "
        f"conventionally styled (e.g. \"PoSH\", \"NASA\", \"HR\", \"CEO\") — go by what's actually "
        f"widely used and adopted, not a fixed capitalization rule.\n"
        f"- 'speech' is what gets fed to a text-to-speech engine, which infers whether to say an "
        f"acronym as one word or spell it out letter-by-letter FROM ITS CASING: ALL CAPS is read "
        f"letter-by-letter (\"HR\" -> H-R, \"CEO\" -> C-E-O, \"OTP\" -> O-T-P, \"NASA\" -> N-A-S-A), "
        f"while Title Case is read as a single spoken word (\"Posh\" -> \"posh\", \"Nasa\" -> "
        f"\"nasa\"). For 'speech', judge each acronym by how people actually say it out loud in "
        f"real life — go by common real-world pronunciation, not by guessing from the letters — "
        f"and case it so the TTS engine says it correctly: most acronyms (HR, CEO, IT, KYC, GST, "
        f"OTP) are genuinely spoken letter-by-letter and should stay ALL CAPS in 'speech', but "
        f"acronyms that are widely spoken as one word should be written in Title Case in 'speech' "
        f"instead — even when their 'display' form is styled differently (e.g. \"PoSH\", "
        f"\"NASA\"). This content is aimed at Indian workplaces, so pay particular attention to "
        f"Indian institutions/regulators commonly said as a word rather than spelled out — e.g. "
        f"POSH (said \"posh\"), SEBI (said \"say-bee\"), ISRO (said \"iss-ro\") — the same way "
        f"NASA is said \"nasa\" — versus ones genuinely spelled out like HR, KYC, GST, PAN, TDS. "
        f"When unsure, default to how a native Indian English speaker would actually say the term "
        f"out loud in conversation. Only ever change casing for this — never insert hyphens, "
        f"periods, or spaces between letters, and never change the words themselves between the "
        f"two versions.\n\n"
        f"Pacing: each translation will be spoken aloud and time-fitted into the same time slot "
        f"as its English original, so keep it roughly proportional in length and speaking time — "
        f"avoid padded, roundabout, or unnecessarily wordy phrasing. When a shorter, equally "
        f"natural way to say the same thing is available, prefer it."
        f"{glossary_block}"
        f"{notes_block}\n\n"
        f"Some input sentences may themselves contain quotation marks (e.g. quoted dialogue). "
        f"When that happens, make sure any quotation marks inside a translated string are valid "
        f"JSON — i.e. escaped as \\\" — so the overall response stays parseable.\n\n"
        f'Respond with ONLY a JSON object of the form {{"translations": [...]}} containing exactly '
        f"{num_sentences} objects, one per input sentence in the same order, each of the form "
        f'{{"display": "...", "speech": "..."}}. No markdown, no code fences, no commentary — '
        f"just the raw JSON object."
    )


_HYPHENATED_ACRONYM = re.compile(r"(?<![A-Za-z])[A-Z](?:-[A-Z])+(?![A-Za-z])")


def _collapse_hyphenated_acronyms(text: str) -> str:
    """The model sometimes hyphenates letter-by-letter acronyms ("H-R") even
    though it's told to use casing only — tested directly, ElevenLabs reads
    "H-R" and "HR" as the same duration either way, so it's not a
    pronunciation bug, but it's an unnecessary inconsistency worth
    normalizing away rather than trusting prompt-following alone.
    """
    return _HYPHENATED_ACRONYM.sub(lambda m: m.group(0).replace("-", ""), text)


def _parse_translations(raw: str, expected_count: int) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Translation model did not return valid JSON: {e}\nRaw response: {raw[:500]}") from e

    if isinstance(data, dict):
        data = data.get("translations")
    if not isinstance(data, list):
        raise RuntimeError(f"Expected a JSON object with a 'translations' array, got: {raw[:500]}")

    if len(data) != expected_count:
        raise RuntimeError(
            f"Translation count mismatch: sent {expected_count} sentences, got {len(data)} back.\n"
            f"Raw response: {raw[:500]}"
        )

    # Defensive: if the model ever returns a plain string instead of the
    # {display, speech} object, treat it as both — better than crashing.
    normalized = []
    for item in data:
        if isinstance(item, str):
            normalized.append({"display": item, "speech": _collapse_hyphenated_acronyms(item)})
        else:
            display = item.get("display", "")
            speech = item.get("speech", display)
            normalized.append({"display": display, "speech": _collapse_hyphenated_acronyms(speech)})
    return normalized


def translate_segments(
    sentences: list[str],
    target_language_code: str,
    language_name: str,
    model: str = "deepseek/deepseek-chat",
    operator_notes: str = "",
) -> list[dict]:
    """Translates all sentences of a video's transcript in a single call, so
    the model has the full script as context (for word-sense disambiguation
    and consistent terminology) instead of translating each sentence blind.

    target_language_code is only used to look up an optional glossary file
    (backend/glossary/<code>.json) — language_name (e.g. "Hindi") is what
    actually goes into the prompt, resolved by the caller from the voice
    registry rather than a hardcoded map here.

    Returns one {"display": str, "speech": str} dict per sentence — "display"
    is what's shown as a subtitle (conventional written form, e.g. "PoSH"),
    "speech" is what's fed to the TTS engine (pronunciation-cueing casing,
    e.g. "Posh" so it's said as one word instead of spelled out).
    """
    if not sentences:
        return []

    glossary = load_glossary(target_language_code)
    system_prompt = _build_system_prompt(language_name, len(sentences), glossary, operator_notes)
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))

    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": numbered},
        ],
    )
    raw = response.choices[0].message.content.strip()
    return _parse_translations(raw, len(sentences))
