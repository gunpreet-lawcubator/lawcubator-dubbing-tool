import os
import threading
import traceback
import uuid
from dataclasses import dataclass, field

from . import video_retime, video_utils
from .alignment import align_transcript_to_audio, transcribe_full_via_scribe
from .assemble import assemble_track, compose_final_audio, fit_segment_to_duration
from .subtitles import write_ass
from .translate import translate_segments
from .tts import generate_tts

STEPS = [
    "extracting_audio",
    "transcribing",
    "aligning",
    "translating",
    "generating_tts",
    "time_aligning",
    "retiming_video",
    "assembling",
    "mixing_bgm",
    "muxing_video",
    "done",
]


@dataclass
class Job:
    job_id: str
    status: str = "queued"
    step: str = ""
    error: str = ""
    segments_preview: list = field(default_factory=list)
    output_audio_path: str = ""
    output_audio_url: str = ""
    output_video_path: str = ""
    flagged_segments: list = field(default_factory=list)
    resolutions: dict = field(default_factory=dict)
    _resume_event: threading.Event = field(default_factory=threading.Event, repr=False)
    # Retained after completion so subtitle text can be edited and re-burned
    # (rebuild subtitles.ass + re-mux) without re-running the expensive
    # transcribe/translate/TTS/retime steps. Not exposed via /api/status.
    segments: list = field(default_factory=list, repr=False)
    video_to_mux_path: str = ""
    video_audio_path: str = ""
    video_width: int = 0
    video_height: int = 0
    is_cjk: bool = False
    subtitle_style: dict = field(default_factory=dict, repr=False)
    subtitles_enabled: bool = False
    subtitle_path: str = ""


_jobs: dict[str, Job] = {}


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def has_active_jobs() -> bool:
    return any(j.status not in ("done", "error") for j in _jobs.values())


def start_job(
    video_path: str,
    transcript_path: str,
    language_code: str,
    language_name: str,
    voice_id: str,
    is_cjk: bool,
    translation_model: str,
    output_dir: str,
    sync_mode: str = "video",
    logo_intro_path: str | None = None,
    main_bgm_path: str | None = None,
    main_bgm_start_mode: str = "after_intro",
    main_bgm_start_seconds: float = 0.0,
    logo_intro_fade_in: float = 0.5,
    logo_intro_fade_out: float = 1.5,
    logo_intro_volume_pct: float = 100,
    main_bgm_fade_in: float = 4.0,
    main_bgm_fade_out: float = 4.0,
    main_bgm_volume_pct: float = 12,
    operator_notes: str = "",
    subtitles_enabled: bool = True,
    subtitle_font_size_pct: float = 0.039,
    subtitle_text_color: str = "#FFFFFF",
    subtitle_background_color: str = "#000000",
    subtitle_background_opacity: float = 100,
    subtitle_margin_v_pct: float = 0.056,
    subtitle_margin_lr_pct: float = 0.0625,
    subtitle_padding_x_pct: float = 0.6,
    subtitle_padding_y_pct: float = 0.35,
    subtitle_corner_radius_pct: float = 0.35,
    subtitle_max_lines_per_cue: int = 2,
) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id=job_id, status="running")
    _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_pipeline,
        args=(
            job, video_path, transcript_path, language_code, language_name, voice_id, is_cjk,
            translation_model, output_dir,
            sync_mode,
            logo_intro_path, main_bgm_path, main_bgm_start_mode, main_bgm_start_seconds,
            logo_intro_fade_in, logo_intro_fade_out, logo_intro_volume_pct,
            main_bgm_fade_in, main_bgm_fade_out, main_bgm_volume_pct,
            operator_notes,
            subtitles_enabled, subtitle_font_size_pct, subtitle_text_color,
            subtitle_background_color, subtitle_background_opacity,
            subtitle_margin_v_pct, subtitle_margin_lr_pct,
            subtitle_padding_x_pct, subtitle_padding_y_pct, subtitle_corner_radius_pct,
            subtitle_max_lines_per_cue,
        ),
        daemon=True,
    )
    thread.start()
    return job_id


def resolve_job(job_id: str, resolutions: dict) -> bool:
    """Called by POST /api/resolve/{job_id} once Ashin has picked how to
    handle each flagged out-of-range segment. Wakes the blocked pipeline
    thread (see the `needs_review` pause in _run_pipeline) to continue.
    Returns False if the job wasn't actually waiting (already resolved, or
    never flagged) so the endpoint can reject a double-submit with a 409.
    """
    job = get_job(job_id)
    if job is None or job.status != "needs_review":
        return False
    job.resolutions = resolutions
    job.status = "running"
    job._resume_event.set()
    return True


def update_subtitles(job_id: str, edits: list[dict]) -> bool:
    """Applies edited subtitle text to a completed job, rebuilds
    subtitles.ass, and re-mux onto the already-produced video+audio —
    visual-only, no re-transcription/translation/TTS/retiming. Returns
    False if the job isn't in a state this applies to (caller returns
    404/400 as appropriate).
    """
    job = get_job(job_id)
    if job is None or job.status != "done" or not job.subtitles_enabled:
        return False

    for edit in edits:
        index = edit["index"]
        if 0 <= index < len(job.segments):
            job.segments[index].translated_text = edit["text"]
            if index < len(job.segments_preview):
                job.segments_preview[index]["translated"] = edit["text"]

    write_ass(
        job.segments, job.video_width, job.video_height, job.is_cjk, job.subtitle_path,
        **job.subtitle_style,
    )
    video_utils.mux_video_with_audio(
        job.video_to_mux_path, job.video_audio_path, job.output_video_path,
        subtitle_path=job.subtitle_path,
    )
    return True


def _set_step(job: Job, step: str) -> None:
    job.step = step


def _run_pipeline(
    job: Job,
    video_path: str,
    transcript_path: str,
    language_code: str,
    language_name: str,
    voice_id: str,
    is_cjk: bool,
    translation_model: str,
    output_dir: str,
    sync_mode: str = "video",
    logo_intro_path: str | None = None,
    main_bgm_path: str | None = None,
    main_bgm_start_mode: str = "after_intro",
    main_bgm_start_seconds: float = 0.0,
    logo_intro_fade_in: float = 0.5,
    logo_intro_fade_out: float = 1.5,
    logo_intro_volume_pct: float = 100,
    main_bgm_fade_in: float = 4.0,
    main_bgm_fade_out: float = 4.0,
    main_bgm_volume_pct: float = 12,
    operator_notes: str = "",
    subtitles_enabled: bool = True,
    subtitle_font_size_pct: float = 0.039,
    subtitle_text_color: str = "#FFFFFF",
    subtitle_background_color: str = "#000000",
    subtitle_background_opacity: float = 100,
    subtitle_margin_v_pct: float = 0.056,
    subtitle_margin_lr_pct: float = 0.0625,
    subtitle_padding_x_pct: float = 0.6,
    subtitle_padding_y_pct: float = 0.35,
    subtitle_corner_radius_pct: float = 0.35,
    subtitle_max_lines_per_cue: int = 2,
) -> None:
    try:
        job_dir = os.path.join(output_dir, job.job_id)
        segments_dir = os.path.join(job_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)

        _set_step(job, "extracting_audio")
        english_audio_path = os.path.join(job_dir, "english_audio.wav")
        video_utils.extract_audio(video_path, english_audio_path)

        # No human-written script available: ElevenLabs Scribe v2's own
        # output stands in for one, but still goes through the same
        # sentence-splitting + fuzzy alignment a human transcript would,
        # rather than trusting ASR segment boundaries directly.
        _set_step(job, "transcribing")
        generated_text, asr_words = transcribe_full_via_scribe(english_audio_path)

        _set_step(job, "aligning")
        segments = align_transcript_to_audio(generated_text, asr_words)
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(generated_text)

        _set_step(job, "translating")
        translations = translate_segments(
            [seg.text for seg in segments], language_code, language_name, model=translation_model,
            operator_notes=operator_notes,
        )
        for seg, translated in zip(segments, translations):
            seg.translated_text = translated["display"]
            seg.speech_text = translated["speech"]

        _set_step(job, "generating_tts")
        if sync_mode == "audio":
            # First pass at neutral speed, then measure. If it doesn't fit
            # its slot within a small margin, regenerate once at a speed
            # ElevenLabs itself paces to (natural prosody) rather than
            # reaching straight for digital time-stretching, which is a
            # cruder fix reserved for whatever small gap remains after this.
            # Only useful in audio-mode: it exists to shrink how much the
            # audio needs to be atempo-stretched afterward. In video-mode
            # there's no audio-side gap to close — the video absorbs all of
            # it — so nudging ElevenLabs' pace here would only cost an extra
            # API call for no benefit, and pure default-speed generation is
            # the most natural-sounding audio available anyway.
            REGEN_THRESHOLD_HIGH = 1.05
            REGEN_THRESHOLD_LOW = 1 / REGEN_THRESHOLD_HIGH
            for i, seg in enumerate(segments):
                raw_path = os.path.join(segments_dir, f"raw_{i:03d}.mp3")
                generate_tts(seg.speech_text, raw_path, voice_id)

                target_duration = seg.end - seg.start
                first_pass_duration = video_utils.get_duration(raw_path)
                tempo_needed = first_pass_duration / target_duration if target_duration > 0 else 1.0

                if tempo_needed > REGEN_THRESHOLD_HIGH or tempo_needed < REGEN_THRESHOLD_LOW:
                    regen_path = os.path.join(segments_dir, f"raw_{i:03d}_regen.mp3")
                    generate_tts(seg.speech_text, regen_path, voice_id, speed=tempo_needed)
                    seg.raw_audio_path = regen_path
                    seg.speed_used = max(0.7, min(1.2, tempo_needed))
                    seg.regenerated = True
                else:
                    seg.raw_audio_path = raw_path
        else:
            for i, seg in enumerate(segments):
                raw_path = os.path.join(segments_dir, f"raw_{i:03d}.mp3")
                generate_tts(seg.speech_text, raw_path, voice_id)
                seg.raw_audio_path = raw_path

        _set_step(job, "time_aligning")
        video_to_mux = video_path
        if sync_mode == "audio":
            for i, seg in enumerate(segments):
                target_duration = seg.end - seg.start
                stretched_path = os.path.join(segments_dir, f"stretched_{i:03d}.mp3")
                diagnostics = fit_segment_to_duration(seg.raw_audio_path, stretched_path, target_duration)
                seg.final_audio_path = stretched_path
                seg.raw_duration = diagnostics["raw_duration"]
                seg.tempo_needed = diagnostics["tempo_needed"]
                seg.tempo_applied = diagnostics["tempo_applied"]
                seg.audio_clamped = round(seg.tempo_needed, 3) != round(seg.tempo_applied, 3)
        else:
            factor_infos = video_retime.compute_video_factors(segments)
            flagged = [f for f in factor_infos if not f["in_range"]]
            if flagged:
                job.flagged_segments = [
                    {
                        "index": f["index"],
                        "english": segments[f["index"]].text,
                        "translated": segments[f["index"]].translated_text,
                        "factor": round(f["factor"], 3),
                        "direction": "longer" if f["factor"] > video_retime.MAX_VIDEO_FACTOR else "shorter",
                    }
                    for f in flagged
                ]
                job.status = "needs_review"
                job._resume_event.clear()
                job._resume_event.wait()

            # Resolve every segment's video factor + final audio, applying
            # any operator choices for the flagged (out-of-range) ones.
            # In-range segments need no decision: their video simply
            # retimes to the natural TTS length, audio untouched.
            video_factors_by_index = {}
            for f in factor_infos:
                i = f["index"]
                seg = segments[i]
                seg.raw_duration = f["raw_duration"]
                seg.tempo_needed = f["factor"]
                if f["in_range"]:
                    video_factors_by_index[i] = f["factor"]
                    seg.final_audio_path = seg.raw_audio_path
                    seg.tempo_applied = 1.0
                    continue

                choice = job.resolutions.get(str(i), "drift")
                clamped = max(video_retime.MIN_VIDEO_FACTOR, min(video_retime.MAX_VIDEO_FACTOR, f["factor"]))
                if choice == "fallback_audio":
                    target_duration = seg.end - seg.start
                    stretched_path = os.path.join(segments_dir, f"stretched_{i:03d}.mp3")
                    diagnostics = fit_segment_to_duration(seg.raw_audio_path, stretched_path, target_duration)
                    seg.final_audio_path = stretched_path
                    seg.tempo_applied = diagnostics["tempo_applied"]
                    seg.audio_clamped = round(diagnostics["tempo_needed"], 3) != round(diagnostics["tempo_applied"], 3)
                    video_factors_by_index[i] = 1.0
                elif choice == "residual_audio":
                    residual_target = (seg.end - seg.start) * clamped
                    stretched_path = os.path.join(segments_dir, f"stretched_{i:03d}.mp3")
                    diagnostics = fit_segment_to_duration(seg.raw_audio_path, stretched_path, residual_target)
                    seg.final_audio_path = stretched_path
                    seg.tempo_applied = diagnostics["tempo_applied"]
                    seg.audio_clamped = round(diagnostics["tempo_needed"], 3) != round(diagnostics["tempo_applied"], 3)
                    video_factors_by_index[i] = clamped
                else:  # "drift"
                    seg.final_audio_path = seg.raw_audio_path
                    seg.tempo_applied = 1.0
                    video_factors_by_index[i] = clamped

            _set_step(job, "retiming_video")
            video_work_dir = os.path.join(job_dir, "video_segments")
            video_to_mux, measured_durations = video_retime.retime_video(
                video_path, segments, video_factors_by_index, video_work_dir,
            )

            # New cumulative timeline from *measured* (not theoretical)
            # segment durations — untouched gaps between segments keep
            # their original length, only the spoken spans move.
            cursor = 0.0
            for i, seg in enumerate(segments):
                gap = seg.orig_start - (segments[i - 1].orig_end if i > 0 else 0.0)
                new_start = cursor + gap
                new_end = new_start + measured_durations[i]
                seg.start = new_start
                seg.end = new_end
                cursor = new_end

        _set_step(job, "assembling")
        total_duration = video_utils.get_duration(video_to_mux)
        output_audio_path = os.path.join(job_dir, "dubbed_audio.mp3")
        assemble_track(segments, total_duration, output_audio_path)

        # The voiceover-only track above stays as-is for the review player
        # (comparing voice clarity/sync shouldn't have music competing with
        # it). Logo-intro jingle + main BGM are only layered into the final
        # downloadable video's audio, produced separately here.
        video_audio_path = output_audio_path
        if logo_intro_path or main_bgm_path:
            _set_step(job, "mixing_bgm")
            mixed_audio_path = os.path.join(job_dir, "mixed_audio.mp3")
            if main_bgm_start_mode == "custom":
                main_bgm_start = main_bgm_start_seconds
            elif logo_intro_path:
                main_bgm_start = video_utils.get_duration(logo_intro_path)
            else:
                main_bgm_start = 0.0
            compose_final_audio(
                output_audio_path, logo_intro_path, main_bgm_path, total_duration,
                logo_intro_fade_in, logo_intro_fade_out, logo_intro_volume_pct,
                main_bgm_start, main_bgm_fade_in, main_bgm_fade_out, main_bgm_volume_pct,
                mixed_audio_path,
            )
            video_audio_path = mixed_audio_path

        subtitle_path = None
        if subtitles_enabled:
            subtitle_path = os.path.join(job_dir, "subtitles.ass")
            video_width, video_height = video_utils.get_video_dimensions(video_path)
            write_ass(
                segments, video_width, video_height, is_cjk, subtitle_path,
                font_size_pct=subtitle_font_size_pct,
                text_color=subtitle_text_color,
                background_color=subtitle_background_color,
                background_opacity=subtitle_background_opacity,
                margin_v_pct=subtitle_margin_v_pct,
                margin_lr_pct=subtitle_margin_lr_pct,
                padding_x_pct=subtitle_padding_x_pct,
                padding_y_pct=subtitle_padding_y_pct,
                corner_radius_pct=subtitle_corner_radius_pct,
                max_lines_per_cue=subtitle_max_lines_per_cue,
            )

        _set_step(job, "muxing_video")
        output_video_path = os.path.join(job_dir, "dubbed_video.mp4")
        video_utils.mux_video_with_audio(video_to_mux, video_audio_path, output_video_path, subtitle_path=subtitle_path)

        job.output_audio_path = output_audio_path
        job.output_video_path = output_video_path
        job.segments = segments
        job.video_to_mux_path = video_to_mux
        job.video_audio_path = video_audio_path
        job.video_width = video_width if subtitles_enabled else 0
        job.video_height = video_height if subtitles_enabled else 0
        job.is_cjk = is_cjk
        job.subtitles_enabled = subtitles_enabled
        job.subtitle_path = subtitle_path or ""
        job.subtitle_style = {
            "font_size_pct": subtitle_font_size_pct,
            "text_color": subtitle_text_color,
            "background_color": subtitle_background_color,
            "background_opacity": subtitle_background_opacity,
            "margin_v_pct": subtitle_margin_v_pct,
            "margin_lr_pct": subtitle_margin_lr_pct,
            "padding_x_pct": subtitle_padding_x_pct,
            "padding_y_pct": subtitle_padding_y_pct,
            "corner_radius_pct": subtitle_corner_radius_pct,
            "max_lines_per_cue": subtitle_max_lines_per_cue,
        }
        job.segments_preview = [
            {
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
                "orig_start": round(float(seg.orig_start), 2),
                "orig_end": round(float(seg.orig_end), 2),
                "english": seg.text,
                "translated": seg.translated_text,
                "speech_text": seg.speech_text,
                "target_duration": round(float(seg.orig_end) - float(seg.orig_start), 2),
                "raw_duration": round(float(seg.raw_duration), 2),
                "tempo_needed": round(float(seg.tempo_needed), 3),
                "tempo_applied": round(float(seg.tempo_applied), 3),
                "clamped": bool(seg.audio_clamped),
                "speed_used": round(float(seg.speed_used), 3),
                "regenerated": bool(seg.regenerated),
                "video_factor": round(float(seg.end - seg.start) / float(seg.orig_end - seg.orig_start), 3)
                if sync_mode == "video" and (seg.orig_end - seg.orig_start) > 0
                else None,
            }
            for seg in segments
        ]

        _set_step(job, "done")
        job.status = "done"
    except Exception as e:
        job.status = "error"
        job.error = f"{e}\n{traceback.format_exc()}"
