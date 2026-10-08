"""The operator-managed list of target languages + ElevenLabs voices, backed
by backend/voices.json. This is the single source of truth for what shows up
in the "Target language" dropdown — replaces what used to be a hardcoded
dict in main.py plus per-language ELEVENLABS_VOICE_ID_* env vars.

Each entry: {"code": str, "label": str, "voice_id": str, "is_cjk": bool}.
`code` is generated server-side (see slugify()) from whatever label the
operator types — they only ever provide a label and a voice ID.
"""
import json
import os
import re

_VOICES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voices.json")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(label: str, existing_codes: set[str]) -> str:
    base = _SLUG_RE.sub("-", label.strip().lower()).strip("-") or "language"
    code = base
    n = 2
    while code in existing_codes:
        code = f"{base}-{n}"
        n += 1
    return code


def load_voices() -> list[dict]:
    if not os.path.isfile(_VOICES_PATH):
        return []
    with open(_VOICES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_voices(voices: list[dict]) -> None:
    with open(_VOICES_PATH, "w", encoding="utf-8") as f:
        json.dump(voices, f, indent=2)
        f.write("\n")


def find_voice(code: str) -> dict | None:
    return next((v for v in load_voices() if v["code"] == code), None)
