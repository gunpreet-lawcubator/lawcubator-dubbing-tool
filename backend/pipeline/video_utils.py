import json
import os
import subprocess


def get_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def get_video_dimensions(video_path: str) -> tuple[int, int]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def get_video_fps(video_path: str) -> float:
    """Needed so every intermediate clip in video_retime.py's cut+retime
    step shares an identical frame rate — the ffmpeg concat demuxer's
    `-c copy` join requires bit-identical stream parameters across pieces.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "json", video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    rate = json.loads(result.stdout)["streams"][0]["r_frame_rate"]
    num, _, den = rate.partition("/")
    return float(num) / float(den or 1)


def extract_audio(video_path: str, output_wav_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-ac", "1", "-ar", "16000",
            output_wav_path,
        ],
        check=True, capture_output=True,
    )


def mux_video_with_audio(video_path: str, audio_path: str, output_path: str, subtitle_path: str | None = None) -> None:
    """Combines the original video's picture with a replacement audio track
    (the dubbed track, optionally already mixed with background music),
    dropping the original English audio.

    If subtitle_path is given (a .ass file — see subtitles.write_ass, which
    bakes in its own styling), burns it into the video as open captions
    (requires an ffmpeg build with libass — the plain `ffmpeg` Homebrew
    formula doesn't include it, `ffmpeg-full` does). Video is otherwise
    stream-copied (no re-encode) when there are no subtitles to burn in,
    since only the audio is changing; burning subtitles forces a re-encode
    because it's a pixel-level video filter.

    The subprocess runs with cwd set to the subtitle file's directory and
    references it by bare filename — ffmpeg's filter-string mini-language
    parses on ':' and can choke on spaces/colons in absolute paths otherwise
    (this project's own path has spaces in it).
    """
    cwd = None
    video_arg = video_path
    audio_arg = audio_path
    subtitle_filename = None
    if subtitle_path:
        cwd = os.path.dirname(subtitle_path)
        video_arg = os.path.relpath(video_path, cwd)
        audio_arg = os.path.relpath(audio_path, cwd)
        subtitle_filename = os.path.basename(subtitle_path)
        output_path = os.path.relpath(output_path, cwd)

    cmd = ["ffmpeg", "-y", "-i", video_arg, "-i", audio_arg]
    if subtitle_filename:
        cmd += ["-vf", f"ass={subtitle_filename}"]
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac"]
    else:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac"]
    cmd += ["-shortest", output_path]

    subprocess.run(cmd, check=True, capture_output=True, cwd=cwd)


def time_stretch(input_path: str, output_path: str, tempo: float) -> None:
    """Speed up/slow down audio to hit a target tempo factor.
    ffmpeg's atempo filter only accepts 0.5-2.0 per instance, so chain it
    for factors outside that range.
    """
    filters = []
    t = tempo
    while t > 2.0:
        filters.append("atempo=2.0")
        t /= 2.0
    while t < 0.5:
        filters.append("atempo=0.5")
        t /= 0.5
    filters.append(f"atempo={t:.4f}")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", ",".join(filters),
            output_path,
        ],
        check=True, capture_output=True,
    )
