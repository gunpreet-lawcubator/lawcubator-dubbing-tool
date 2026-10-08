"""Burned-in (open caption) subtitle generation.

Writes a self-contained .ass file — explicit PlayResX/PlayResY plus a fully
specified style — rather than relying on ffmpeg's `subtitles` filter to
convert a plain .srt on the fly with `force_style` overrides. That combo was
tested directly and turned out unreliable here: font size and margins ended
up scaled against an assumed low-res subtitle canvas instead of the actual
video resolution, and the caption background box didn't render at all until
BorderStyle=3 was paired with a nonzero Outline (which becomes the box's
padding in that mode, not a text outline). Baking an explicit style into a
real .ass file sidesteps all of that ambiguity.

Line wrapping and the caption background are both hand-rolled rather than
left to libass defaults:
- libass's own word-wrap only breaks at whitespace, so it never wraps CJK
  text (no spaces between characters) — verified directly, a long Chinese
  line just ran off both edges of the frame uncut. Long lines are wrapped
  here instead, breaking between CJK characters but never inside a run of
  Latin characters (an embedded acronym like "POSH" must stay whole — an
  earlier version wrapped purely by character count and split it into
  "POS"/"H" across two lines, reported directly from real output).
- ASS's native BorderStyle=3 box only draws sharp corners — there's no style
  parameter for corner radius. A rounded box is instead hand-drawn per cue
  using ASS vector drawing commands (bezier-approximated corners), as its
  own lower-layer dialogue line sized to fit the wrapped text, with the
  actual text drawn in a separate line on top.

A segment's wrapped text can exceed max_lines_per_cue (a long sentence
otherwise producing one oversized static box covering much of the frame) —
when it does, the lines are chunked into multiple sequential cues spread
proportionally (by character count) across the segment's own [start, end]
window, rather than shown all at once. This is a display-timing split for
readability, not word-level speech alignment.
"""

import re

_BEZIER_CIRCLE_CONSTANT = 0.552

_CJK_CHAR = re.compile(r"[㐀-鿿豈-﫿]")
_TOKEN_PATTERN = re.compile(r"[㐀-鿿豈-﫿]|\s+|[^㐀-鿿豈-﫿\s]+")


def _format_timestamp(seconds: float) -> str:
    cs_total = round(seconds * 100)
    hours, cs_total = divmod(cs_total, 360_000)
    minutes, cs_total = divmod(cs_total, 6_000)
    secs, cs = divmod(cs_total, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _hex_to_ass_color(hex_color: str, opacity_pct: float = 100) -> str:
    """Converts a "#RRGGBB" color + 0-100 opacity percent into ASS's
    "&HAABBGGRR" hex format: byte order reversed to BGR, and alpha inverted
    from the usual convention (00 = fully opaque, FF = fully transparent).
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    alpha = round((100 - max(0, min(100, opacity_pct))) / 100 * 255)
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Wraps at CJK-character boundaries and whitespace, but never inside a
    run of non-CJK characters (Latin words/acronyms stay atomic regardless
    of script). Works for pure-CJK, pure-Latin, and mixed text alike.
    """
    tokens = _TOKEN_PATTERN.findall(text)
    lines: list[str] = []
    current = ""
    for tok in tokens:
        if tok.isspace() and not current:
            continue  # never start a line with whitespace
        if len(tok) > max_chars:
            # Pathological case: a single token alone exceeds a full line
            # (e.g. a very long URL) — hard-break just that token.
            if current.strip():
                lines.append(current.rstrip())
                current = ""
            for i in range(0, len(tok), max_chars):
                chunk = tok[i : i + max_chars]
                if i + max_chars < len(tok):
                    lines.append(chunk)
                else:
                    current = chunk
            continue
        if current and len(current) + len(tok) > max_chars:
            lines.append(current.rstrip())
            current = "" if tok.isspace() else tok
        else:
            current += tok
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def _split_wrapped_lines(wrapped: list[str], max_lines_per_cue: int) -> list[list[str]]:
    if max_lines_per_cue <= 0 or len(wrapped) <= max_lines_per_cue:
        return [wrapped]
    return [wrapped[i : i + max_lines_per_cue] for i in range(0, len(wrapped), max_lines_per_cue)]


def _distribute_cue_timing(chunks: list[list[str]], start: float, end: float) -> list[tuple[float, float]]:
    """Splits [start, end] across chunks proportionally by character count
    per chunk (more text -> more display time). The last chunk's end is
    pinned exactly to `end` so timings never leave a rounding gap.
    """
    total_chars = sum(sum(len(l) for l in chunk) for chunk in chunks) or 1
    duration = end - start
    timings = []
    cursor = start
    for i, chunk in enumerate(chunks):
        share = sum(len(l) for l in chunk) / total_chars
        chunk_end = end if i == len(chunks) - 1 else cursor + duration * share
        timings.append((cursor, chunk_end))
        cursor = chunk_end
    return timings


def _rounded_rect_path(width: float, height: float, radius: float) -> str:
    """ASS drawing-mode path (relative to a top-left origin at (0,0)) for a
    rounded rectangle, corners approximated with cubic beziers.
    """
    k = radius * _BEZIER_CIRCLE_CONSTANT
    r = radius
    w, h = width, height
    return (
        f"m {r} 0 "
        f"l {w - r} 0 "
        f"b {w - r + k} 0 {w} {r - k} {w} {r} "
        f"l {w} {h - r} "
        f"b {w} {h - r + k} {w - r + k} {h} {w - r} {h} "
        f"l {r} {h} "
        f"b {r - k} {h} 0 {h - r + k} 0 {h - r} "
        f"l 0 {r} "
        f"b 0 {r - k} {r - k} 0 {r} 0"
    )


def write_ass(
    segments: list,
    video_width: int,
    video_height: int,
    is_cjk: bool,
    output_path: str,
    font_size_pct: float = 0.039,
    text_color: str = "#FFFFFF",
    background_color: str = "#000000",
    background_opacity: float = 100,
    margin_v_pct: float = 0.056,
    margin_lr_pct: float = 0.0625,
    padding_x_pct: float = 0.6,
    padding_y_pct: float = 0.35,
    corner_radius_pct: float = 0.35,
    max_lines_per_cue: int = 2,
) -> None:
    """One or more cues per pipeline segment (see module docstring for the
    long-sentence splitting behavior), at the segment's own timestamps.
    Style is fully parameterized but every default here matches the look
    this file always had, so an unstyled call is unchanged. Sized
    proportionally to the actual video resolution so it looks right
    regardless of source dimensions.
    """
    font_size = round(video_height * font_size_pct)
    margin_v = round(video_height * margin_v_pct)
    margin_lr = round(video_width * margin_lr_pct)

    char_width = font_size * (1.0 if is_cjk else 0.55)
    wrap_width_px = video_width - 2 * margin_lr
    max_chars_per_line = max(4, int(wrap_width_px / char_width))

    line_height = font_size * 1.35
    pad_x = font_size * padding_x_pct
    pad_y = font_size * padding_y_pct
    corner_radius = font_size * corner_radius_pct

    text_ass_color = _hex_to_ass_color(text_color, 100)
    box_ass_color = _hex_to_ass_color(background_color, background_opacity)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Unicode MS,{font_size},{text_ass_color},&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,{margin_lr},{margin_lr},{margin_v},1
Style: Box,Arial Unicode MS,{font_size},{box_ass_color},&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    for seg in segments:
        wrapped = _wrap_text(seg.translated_text.strip(), max_chars_per_line)
        chunks = _split_wrapped_lines(wrapped, max_lines_per_cue)
        timings = _distribute_cue_timing(chunks, seg.start, seg.end)

        for chunk, (chunk_start, chunk_end) in zip(chunks, timings):
            widest_chars = max(len(l) for l in chunk)
            box_width = widest_chars * char_width + 2 * pad_x
            box_height = len(chunk) * line_height + 2 * pad_y

            box_x = (video_width - box_width) / 2
            box_y = video_height - margin_v - box_height

            start_ts = _format_timestamp(chunk_start)
            end_ts = _format_timestamp(chunk_end)

            path = _rounded_rect_path(box_width, box_height, corner_radius)
            lines.append(
                f"Dialogue: 0,{start_ts},{end_ts},Box,,0,0,0,,"
                f"{{\\an7\\pos({box_x:.1f},{box_y:.1f})\\p1}}{path}{{\\p0}}\n"
            )

            text = "\\N".join(chunk)
            text_x = box_x + box_width / 2
            text_y = box_y + box_height / 2
            lines.append(
                f"Dialogue: 1,{start_ts},{end_ts},Default,,0,0,0,,"
                f"{{\\an5\\pos({text_x:.1f},{text_y:.1f})}}{text}\n"
            )

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
