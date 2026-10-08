import os

import requests

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"

# ElevenLabs rejects voice_settings.speed outside this range (confirmed via the API's own
# validation error), so any computed speed must be clamped to it before sending.
SPEED_MIN = 0.7
SPEED_MAX = 1.2

def _get_api_key() -> str:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set in .env")
    return api_key


def list_voices() -> list[dict]:
    resp = requests.get(
        f"{ELEVENLABS_BASE_URL}/v2/voices",
        headers={"xi-api-key": _get_api_key()},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("voices", [])


def generate_tts(
    text: str,
    output_path: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    speed: float = 1.0,
) -> None:
    """speed asks ElevenLabs' own model to pace its delivery faster/slower
    (natural prosody), as opposed to digitally time-stretching audio after
    the fact. The API only accepts 0.7-1.2, so out-of-range values are
    clamped rather than left to error.
    """
    clamped_speed = max(SPEED_MIN, min(SPEED_MAX, speed))
    resp = requests.post(
        f"{ELEVENLABS_BASE_URL}/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": _get_api_key(),
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": clamped_speed},
        },
        timeout=120,
    )
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)


def transcribe_with_scribe(audio_path: str) -> dict:
    """Speech-to-text via ElevenLabs Scribe v2. Used when there's no
    human-written transcript to fall back on — meaningfully more accurate
    than local Whisper on domain-specific terms (verified directly: it
    correctly transcribed "lakhs or crores" where Whisper heard "lacks or
    crawls" on the same audio), for a fraction of a cent per minute.
    """
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{ELEVENLABS_BASE_URL}/v1/speech-to-text",
            headers={"xi-api-key": _get_api_key()},
            data={"model_id": "scribe_v2", "timestamps_granularity": "word"},
            files={"file": f},
            timeout=300,
        )
    resp.raise_for_status()
    return resp.json()
