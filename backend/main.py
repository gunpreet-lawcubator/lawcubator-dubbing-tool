import json
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import auth  # noqa: E402
import updater  # noqa: E402
from pipeline.orchestrator import get_job, has_active_jobs, resolve_job, start_job, update_subtitles  # noqa: E402
from pipeline.voices import find_voice, load_voices, save_voices, slugify  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
INPUT_DIR = os.path.join(PROJECT_DIR, "input")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".m4v")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac")
BGM_DIR = os.path.join(INPUT_DIR, "bgm")
LOGO_INTRO_DIR = os.path.join(BGM_DIR, "logo_intro")
MAIN_BGM_DIR = os.path.join(BGM_DIR, "main")
PLATFORM_CONFIG_PATH = os.path.join(BASE_DIR, "platform_config.json")

UPLOAD_CATEGORY_DIRS = {
    "video": INPUT_DIR,
    "logo_intro": LOGO_INTRO_DIR,
    "main_bgm": MAIN_BGM_DIR,
}
UPLOAD_CATEGORY_EXTENSIONS = {
    "video": VIDEO_EXTENSIONS,
    "logo_intro": AUDIO_EXTENSIONS,
    "main_bgm": AUDIO_EXTENSIONS,
}

# All routed through the one OpenRouter key. Estimated cost is per minute of
# video's worth of narration, based on real OpenRouter pricing — see chat for
# the calculation. Non-"preview" models only, since preview models can change
# or get deprecated without notice.
TRANSLATION_MODELS = [
    {"id": "deepseek/deepseek-chat", "label": "DeepSeek (current default)", "est_cost_per_min_inr": 0.07},
    {"id": "openai/gpt-5.1", "label": "ChatGPT (GPT-5.1)", "est_cost_per_min_inr": 0.63},
    {"id": "google/gemini-2.5-pro", "label": "Gemini (2.5 Pro)", "est_cost_per_min_inr": 0.63},
    {"id": "google/gemini-3.6-flash", "label": "Gemini (3.6 Flash)", "est_cost_per_min_inr": 0.50},
]
TRANSLATION_MODEL_IDS = {m["id"] for m in TRANSLATION_MODELS}

app = FastAPI(title="Lawcubator Multi-Language Video Pipeline (local prototype)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)


_OPEN_PATHS = ("/api/auth-status", "/api/login")


@app.middleware("http")
async def password_gate(request: Request, call_next):
    path = request.url.path
    protected = path.startswith("/api/") or path.startswith("/media/")
    if (
        protected
        and request.method != "OPTIONS"
        and path not in _OPEN_PATHS
        and auth.auth_required()
        and not auth.is_authenticated(request.cookies.get(auth.COOKIE_NAME))
    ):
        return JSONResponse({"detail": "Login required"}, status_code=401)
    return await call_next(request)


class LoginRequest(BaseModel):
    password: str


@app.get("/api/auth-status")
def auth_status(request: Request):
    required = auth.auth_required()
    return {"auth_required": required, "authenticated": (not required) or auth.is_authenticated(request.cookies.get(auth.COOKIE_NAME))}


@app.post("/api/login")
def login(req: LoginRequest, response: Response):
    if not auth.auth_required():
        return {"status": "ok"}
    if not auth.verify_password(req.password):
        raise HTTPException(401, "Wrong password")
    response.set_cookie(auth.COOKIE_NAME, auth.session_token(), max_age=30 * 24 * 3600, httponly=True, samesite="lax")
    return {"status": "ok"}


@app.get("/api/update-check")
def update_check():
    return updater.check()


@app.post("/api/update")
def update_now():
    if has_active_jobs():
        raise HTTPException(409, "A dub is still in progress. Wait for it to finish, then update.")
    try:
        version = updater.apply_update()
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"status": "restarting", "version": version}

for _dir in (INPUT_DIR, OUTPUT_DIR, LOGO_INTRO_DIR, MAIN_BGM_DIR):
    os.makedirs(_dir, exist_ok=True)

app.mount("/media/input", StaticFiles(directory=INPUT_DIR), name="input")
app.mount("/media/output", StaticFiles(directory=OUTPUT_DIR), name="output")


class ProcessRequest(BaseModel):
    video_filename: str
    language_code: str = "hi"
    translation_model: str = "deepseek/deepseek-chat"
    sync_mode: str = "video"  # "video" | "audio"
    logo_intro_filename: str | None = None
    main_bgm_filename: str | None = None
    main_bgm_start_mode: str = "after_intro"  # "after_intro" | "custom"
    main_bgm_start_seconds: float = 0.0
    logo_intro_fade_in: float | None = None
    logo_intro_fade_out: float | None = None
    logo_intro_volume_pct: float | None = None
    main_bgm_fade_in: float | None = None
    main_bgm_fade_out: float | None = None
    main_bgm_volume_pct: float | None = None
    operator_notes: str = ""
    subtitles_enabled: bool | None = None
    subtitle_font_size_pct: float | None = None
    subtitle_text_color: str | None = None
    subtitle_background_color: str | None = None
    subtitle_background_opacity: float | None = None
    subtitle_margin_v_pct: float | None = None
    subtitle_margin_lr_pct: float | None = None
    subtitle_padding_x_pct: float | None = None
    subtitle_padding_y_pct: float | None = None
    subtitle_corner_radius_pct: float | None = None
    subtitle_max_lines_per_cue: int | None = None


def _load_platform_config() -> dict:
    with open(PLATFORM_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_audio_dir(directory: str) -> list[dict]:
    if not os.path.isdir(directory):
        return []
    rel = os.path.relpath(directory, INPUT_DIR)
    return [
        {"filename": name, "url": f"/media/input/{rel}/{name}"}
        for name in sorted(os.listdir(directory))
        if name.lower().endswith(AUDIO_EXTENSIONS)
    ]


@app.get("/api/videos")
def list_videos():
    videos = []
    for name in sorted(os.listdir(INPUT_DIR)):
        if not name.lower().endswith(VIDEO_EXTENSIONS):
            continue
        base, _ext = os.path.splitext(name)
        transcript_name = f"{base}.txt"
        has_transcript = os.path.isfile(os.path.join(INPUT_DIR, transcript_name))
        videos.append(
            {
                "filename": name,
                "url": f"/media/input/{name}",
                "has_transcript": has_transcript,
                "transcript_filename": transcript_name if has_transcript else None,
            }
        )
    return {"videos": videos}


@app.get("/api/languages")
def list_languages():
    return {"languages": [{"code": v["code"], "label": v["label"]} for v in load_voices()]}


class VoiceRequest(BaseModel):
    label: str
    voice_id: str
    is_cjk: bool = False


@app.get("/api/voices")
def list_voices_endpoint():
    return {"voices": load_voices()}


@app.post("/api/voices")
def add_voice(req: VoiceRequest):
    if not req.label.strip():
        raise HTTPException(400, "Language name can't be empty")
    if not req.voice_id.strip():
        raise HTTPException(400, "ElevenLabs voice ID can't be empty")

    voices = load_voices()
    code = slugify(req.label, {v["code"] for v in voices})
    entry = {"code": code, "label": req.label.strip(), "voice_id": req.voice_id.strip(), "is_cjk": req.is_cjk}
    voices.append(entry)
    save_voices(voices)
    return entry


@app.put("/api/voices/{code}")
def update_voice(code: str, req: VoiceRequest):
    voices = load_voices()
    entry = next((v for v in voices if v["code"] == code), None)
    if entry is None:
        raise HTTPException(404, f"Unknown language code: {code}")
    entry["label"] = req.label.strip()
    entry["voice_id"] = req.voice_id.strip()
    entry["is_cjk"] = req.is_cjk
    save_voices(voices)
    return entry


@app.delete("/api/voices/{code}")
def delete_voice(code: str):
    voices = load_voices()
    remaining = [v for v in voices if v["code"] != code]
    if len(remaining) == len(voices):
        raise HTTPException(404, f"Unknown language code: {code}")
    save_voices(remaining)
    return {"status": "deleted"}


@app.get("/api/translation-models")
def list_translation_models():
    return {"models": TRANSLATION_MODELS}


@app.get("/api/bg-music")
def list_bg_music():
    return {"tracks": _list_audio_dir(MAIN_BGM_DIR)}


@app.get("/api/logo-intro-music")
def list_logo_intro_music():
    return {"tracks": _list_audio_dir(LOGO_INTRO_DIR)}


@app.get("/api/platform-config")
def get_platform_config():
    return _load_platform_config()


@app.get("/api/notes/{video_filename}")
def get_notes(video_filename: str):
    base, _ext = os.path.splitext(video_filename)
    notes_path = os.path.join(INPUT_DIR, f"{base}_notes.txt")
    if not os.path.isfile(notes_path):
        return {"notes": ""}
    with open(notes_path, "r", encoding="utf-8") as f:
        return {"notes": f.read()}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), category: str = Form(...)):
    if category not in UPLOAD_CATEGORY_DIRS:
        raise HTTPException(400, f"Unknown upload category: {category}")

    allowed_extensions = UPLOAD_CATEGORY_EXTENSIONS[category]
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            400,
            f"Unsupported file type for {category}: {file.filename} "
            f"(expected one of {', '.join(allowed_extensions)})",
        )

    target_dir = UPLOAD_CATEGORY_DIRS[category]
    os.makedirs(target_dir, exist_ok=True)

    name = os.path.basename(file.filename)
    dest_path = os.path.join(target_dir, name)
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(name)
        name = f"{base}_{uuid.uuid4().hex[:6]}{ext}"
        dest_path = os.path.join(target_dir, name)

    contents = await file.read()
    with open(dest_path, "wb") as f:
        f.write(contents)

    return {"filename": name}


@app.post("/api/process")
def process_video(req: ProcessRequest):
    voice_entry = find_voice(req.language_code)
    if voice_entry is None:
        raise HTTPException(400, f"Unsupported language_code: {req.language_code}")
    if req.translation_model not in TRANSLATION_MODEL_IDS:
        raise HTTPException(400, f"Unsupported translation_model: {req.translation_model}")
    if req.main_bgm_start_mode not in ("after_intro", "custom"):
        raise HTTPException(400, f"Unsupported main_bgm_start_mode: {req.main_bgm_start_mode}")
    if req.sync_mode not in ("video", "audio"):
        raise HTTPException(400, f"Unsupported sync_mode: {req.sync_mode}")

    video_path = os.path.join(INPUT_DIR, req.video_filename)
    if not os.path.isfile(video_path):
        raise HTTPException(404, f"Video not found: {req.video_filename}")

    base, _ext = os.path.splitext(req.video_filename)
    # Every video always gets a fresh auto-generated transcript (Scribe),
    # written here and overwriting any prior one for the same filename.
    transcript_path = os.path.join(INPUT_DIR, f"{base}.txt")

    platform_config = _load_platform_config()

    logo_intro_path = None
    if req.logo_intro_filename:
        logo_intro_path = os.path.join(LOGO_INTRO_DIR, req.logo_intro_filename)
        if not os.path.isfile(logo_intro_path):
            raise HTTPException(404, f"Logo intro music file not found: {req.logo_intro_filename}")

    main_bgm_path = None
    if req.main_bgm_filename:
        main_bgm_path = os.path.join(MAIN_BGM_DIR, req.main_bgm_filename)
        if not os.path.isfile(main_bgm_path):
            raise HTTPException(404, f"Main background music file not found: {req.main_bgm_filename}")

    # Persist operator notes for this video so they're pre-filled next time
    # this same video is processed, without Ashin needing to remember to
    # re-type or save them separately.
    notes_path = os.path.join(INPUT_DIR, f"{base}_notes.txt")
    if req.operator_notes.strip():
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write(req.operator_notes)

    job_id = start_job(
        video_path, transcript_path, req.language_code,
        voice_entry["label"], voice_entry["voice_id"], voice_entry["is_cjk"],
        req.translation_model, OUTPUT_DIR,
        sync_mode=req.sync_mode,
        logo_intro_path=logo_intro_path,
        main_bgm_path=main_bgm_path,
        main_bgm_start_mode=req.main_bgm_start_mode,
        main_bgm_start_seconds=req.main_bgm_start_seconds,
        logo_intro_fade_in=req.logo_intro_fade_in if req.logo_intro_fade_in is not None else platform_config["logo_intro_fade_in"],
        logo_intro_fade_out=req.logo_intro_fade_out if req.logo_intro_fade_out is not None else platform_config["logo_intro_fade_out"],
        logo_intro_volume_pct=req.logo_intro_volume_pct if req.logo_intro_volume_pct is not None else platform_config["logo_intro_volume_pct"],
        main_bgm_fade_in=req.main_bgm_fade_in if req.main_bgm_fade_in is not None else platform_config["main_bgm_fade_in"],
        main_bgm_fade_out=req.main_bgm_fade_out if req.main_bgm_fade_out is not None else platform_config["main_bgm_fade_out"],
        main_bgm_volume_pct=req.main_bgm_volume_pct if req.main_bgm_volume_pct is not None else platform_config["main_bgm_volume_pct"],
        operator_notes=req.operator_notes,
        subtitles_enabled=req.subtitles_enabled if req.subtitles_enabled is not None else platform_config["subtitles_enabled"],
        subtitle_font_size_pct=req.subtitle_font_size_pct if req.subtitle_font_size_pct is not None else platform_config["subtitle_font_size_pct"],
        subtitle_text_color=req.subtitle_text_color if req.subtitle_text_color is not None else platform_config["subtitle_text_color"],
        subtitle_background_color=req.subtitle_background_color if req.subtitle_background_color is not None else platform_config["subtitle_background_color"],
        subtitle_background_opacity=req.subtitle_background_opacity if req.subtitle_background_opacity is not None else platform_config["subtitle_background_opacity"],
        subtitle_margin_v_pct=req.subtitle_margin_v_pct if req.subtitle_margin_v_pct is not None else platform_config["subtitle_margin_v_pct"],
        subtitle_margin_lr_pct=req.subtitle_margin_lr_pct if req.subtitle_margin_lr_pct is not None else platform_config["subtitle_margin_lr_pct"],
        subtitle_padding_x_pct=req.subtitle_padding_x_pct if req.subtitle_padding_x_pct is not None else platform_config["subtitle_padding_x_pct"],
        subtitle_padding_y_pct=req.subtitle_padding_y_pct if req.subtitle_padding_y_pct is not None else platform_config["subtitle_padding_y_pct"],
        subtitle_corner_radius_pct=req.subtitle_corner_radius_pct if req.subtitle_corner_radius_pct is not None else platform_config["subtitle_corner_radius_pct"],
        subtitle_max_lines_per_cue=req.subtitle_max_lines_per_cue if req.subtitle_max_lines_per_cue is not None else platform_config["subtitle_max_lines_per_cue"],
    )
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job_id")

    result = {
        "job_id": job.job_id,
        "status": job.status,
        "step": job.step,
        "error": job.error,
    }
    if job.status == "needs_review":
        result["flagged_segments"] = job.flagged_segments
    if job.status == "done":
        result["audio_url"] = f"/media/output/{job.job_id}/dubbed_audio.mp3"
        result["video_url"] = f"/media/output/{job.job_id}/dubbed_video.mp4"
        result["segments"] = job.segments_preview
        result["subtitles_enabled"] = job.subtitles_enabled
    return result


class ResolveRequest(BaseModel):
    resolutions: dict[str, str]


@app.post("/api/resolve/{job_id}")
def resolve(job_id: str, req: ResolveRequest):
    valid_choices = {"drift", "residual_audio", "fallback_audio"}
    invalid = set(req.resolutions.values()) - valid_choices
    if invalid:
        raise HTTPException(400, f"Unknown resolution choice(s): {', '.join(invalid)}")
    if not resolve_job(job_id, req.resolutions):
        raise HTTPException(409, "Job is not currently waiting for review")
    return {"status": "resumed"}


class SubtitleEdit(BaseModel):
    index: int
    text: str


class SubtitleEditRequest(BaseModel):
    segments: list[SubtitleEdit]


@app.post("/api/jobs/{job_id}/subtitles")
def edit_subtitles(job_id: str, req: SubtitleEditRequest):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job_id")
    if job.status != "done":
        raise HTTPException(400, "Job hasn't finished yet")
    if not job.subtitles_enabled:
        raise HTTPException(400, "Subtitles were disabled for this job — nothing to edit")

    edits = [{"index": e.index, "text": e.text} for e in req.segments]
    update_subtitles(job_id, edits)
    return {"status": "updated"}


# Local single-machine distribution (e.g. for Ashin): if a built frontend is
# sitting next to this backend, serve it from this same process so there's
# only one thing to run. Mounted last so it never shadows the /api and
# /media routes above. Absent in normal local dev, where Vite's own dev
# server serves the frontend on its own port instead.
FRONTEND_DIST_DIR = os.path.join(PROJECT_DIR, "frontend", "dist")
class _NoCacheHtmlStaticFiles(StaticFiles):
    # index.html points at hashed bundle names; if the browser caches it, it
    # keeps loading the old bundle after an update. Hashed assets cache fine.
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response


if os.path.isdir(FRONTEND_DIST_DIR):
    app.mount("/", _NoCacheHtmlStaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
