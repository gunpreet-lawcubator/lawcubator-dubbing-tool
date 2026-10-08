"""Per-language glossary overrides for translation.

Each file at backend/glossary/<language_code>.json is a simple English-term ->
approved-translation map. Entries here are injected into every translation
prompt for that language, so a correction made once (e.g. after a native
speaker flags a mistranslated word) sticks for every future video instead of
being re-discovered each time.
"""
import json
import os

_GLOSSARY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "glossary")


def load_glossary(language_code: str) -> dict:
    path = os.path.join(_GLOSSARY_DIR, f"{language_code}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
