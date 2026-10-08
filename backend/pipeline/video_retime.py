"""Video-side sync mode: instead of time-stretching TTS audio (atempo) to
fit each segment's original English slot, retime the *video* to match the
TTS audio's natural, untouched duration.

`tempo_needed = raw_TTS_duration / original_target_duration` (already
computed for the audio-stretch path) drives both mechanisms with the same
number, just fed into inverted-convention filters: atempo=F shrinks/grows
audio by dividing its duration by F, while setpts=F*PTS shrinks/grows video
by multiplying its duration by F. Verified by hand: target=5s, raw=7s ->
F=1.4 -> atempo=1.4 shrinks 7s to 5s; setpts=1.4*PTS grows the 5s clip to
7s. Same scalar, both land on the matching duration.

Building the retimed video is three separate steps, each trusting measured
ffprobe output over theoretical math (setpts doesn't always land on an
exact frame count):
1. compute_video_factors() - pure, no I/O.
2. retime_video() - cuts the source into untouched "gap" clips (before/
   between/after segments, preserving visual continuity outside speech)
   and retimed "segment" clips, each its own small ffmpeg call so one bad
   segment doesn't blow up a multi-minute render. Joined via the ffmpeg
   concat demuxer, not a single giant filter graph, so pieces stay
   independently debuggable.
"""
import os
import subprocess

from . import video_utils

MIN_VIDEO_FACTOR = 0.6
MAX_VIDEO_FACTOR = 1.6


def compute_video_factors(segments: list) -> list[dict]:
    """For each segment, the setpts factor its video clip would need to
    match its TTS audio's natural duration, and whether that falls inside
    the safe clamp range.
    """
    results = []
    for i, seg in enumerate(segments):
        target_duration = seg.end - seg.start
        raw_duration = video_utils.get_duration(seg.raw_audio_path)
        factor = raw_duration / target_duration if target_duration > 0 else 1.0
        results.append(
            {
                "index": i,
                "factor": factor,
                "raw_duration": raw_duration,
                "target_duration": target_duration,
                "in_range": MIN_VIDEO_FACTOR <= factor <= MAX_VIDEO_FACTOR,
            }
        )
    return results


def _cut_and_retime(video_path: str, start: float, end: float, factor: float, fps: float, output_path: str) -> None:
    # Seek on the input (not a trim filter): the trim filter decodes from the
    # start of the file for every piece, which is quadratic on long videos.
    vf = f"setpts=(PTS-STARTPTS)*{factor:.6f}"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", video_path,
            "-vf", vf, "-an",
            "-r", f"{fps:.5f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            output_path,
        ],
        check=True, capture_output=True,
    )


def retime_video(video_path: str, segments: list, factors_by_index: dict, work_dir: str, on_progress=None) -> tuple[str, list[float]]:
    """Cuts+retimes the video per factors_by_index (already clamped/resolved
    by the caller), preserving untouched gaps between segments, and
    concatenates the result into one video file.

    Returns (retimed_video_path, measured_segment_durations) where the
    durations are ffprobe'd from the actual retimed clips, in segment
    order - the orchestrator uses these (not the theoretical factor*target
    math) to build the new cumulative timeline for audio/subtitles/BGM.
    """
    os.makedirs(work_dir, exist_ok=True)
    fps = video_utils.get_video_fps(video_path)
    total_duration = video_utils.get_duration(video_path)

    total_pieces = len(segments)
    probe = 0.0
    for seg in segments:
        total_pieces += seg.start > probe
        probe = seg.end
    total_pieces += probe < total_duration

    def tick():
        if on_progress:
            on_progress(len(pieces), total_pieces)

    pieces: list[str] = []
    segment_piece_indices: list[int] = []
    cursor = 0.0
    for i, seg in enumerate(segments):
        if seg.start > cursor:
            gap_path = os.path.join(work_dir, f"gap_{i:03d}.mp4")
            _cut_and_retime(video_path, cursor, seg.start, 1.0, fps, gap_path)
            pieces.append(gap_path)
            tick()

        seg_path = os.path.join(work_dir, f"seg_{i:03d}.mp4")
        _cut_and_retime(video_path, seg.start, seg.end, factors_by_index[i], fps, seg_path)
        pieces.append(seg_path)
        segment_piece_indices.append(len(pieces) - 1)
        tick()
        cursor = seg.end

    if cursor < total_duration:
        gap_path = os.path.join(work_dir, f"gap_{len(segments):03d}.mp4")
        _cut_and_retime(video_path, cursor, total_duration, 1.0, fps, gap_path)
        pieces.append(gap_path)
        tick()

    measured_durations = [video_utils.get_duration(pieces[idx]) for idx in segment_piece_indices]

    filelist_path = os.path.join(work_dir, "concat_list.txt")
    with open(filelist_path, "w", encoding="utf-8") as f:
        for p in pieces:
            f.write(f"file '{os.path.abspath(p)}'\n")

    output_path = os.path.join(work_dir, "retimed_video.mp4")
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", filelist_path,
            "-c", "copy", output_path,
        ],
        check=True, capture_output=True,
    )
    return output_path, measured_durations
