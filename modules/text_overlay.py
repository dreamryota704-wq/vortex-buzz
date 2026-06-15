"""
Text overlay generation for short videos using Pillow and moviepy.
Creates hook, body, and CTA text overlays as ImageClip composited onto video.
"""
import logging
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not installed. Text overlays will not work.")

try:
    from moviepy.editor import ImageClip, VideoClip
    from moviepy.video.VideoClip import ImageClip as MpyImageClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

# Canvas size for 9:16 video
CANVAS_W, CANVAS_H = 1080, 1920

# Default font path (falls back to PIL default if not found)
FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"
DEFAULT_FONT_PATHS = [
    FONTS_DIR / "NotoSansJP-Bold.ttf",
    FONTS_DIR / "NotoSansJP-Regular.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def _get_font(size: int):
    """Load the best available Japanese font at the given size."""
    if not PIL_AVAILABLE:
        return None
    for font_path in DEFAULT_FONT_PATHS:
        try:
            return ImageFont.truetype(str(font_path), size)
        except (IOError, OSError):
            continue
    # Fallback to PIL default (no Japanese support but won't crash)
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _wrap_text(text: str, font, max_width: int, draw: "ImageDraw.Draw") -> List[str]:
    """Wrap text to fit within max_width pixels."""
    lines = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue
        words = list(paragraph)  # Split into individual characters for CJK
        current_line = ""
        for char in words:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
    return lines


def _create_text_image(
    text: str,
    font_size: int,
    text_color: Tuple[int, int, int, int],
    shadow_color: Tuple[int, int, int, int],
    bg_color: Optional[Tuple[int, int, int, int]],
    canvas_w: int = CANVAS_W,
    padding: int = 60,
    shadow_offset: int = 3,
) -> "Image.Image":
    """
    Render text to a transparent RGBA image with optional background and shadow.
    Returns the image at native canvas width with auto-computed height.
    """
    font = _get_font(font_size)
    # First pass: measure text
    temp_img = Image.new("RGBA", (canvas_w, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp_img)
    max_text_w = canvas_w - padding * 2
    lines = _wrap_text(text, font, max_text_w, draw)

    line_heights = []
    for line in lines:
        if line:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_heights.append(bbox[3] - bbox[1])
        else:
            line_heights.append(font_size)

    line_spacing = int(font_size * 0.3)
    total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1)
    img_h = total_text_h + padding * 2

    # Second pass: draw
    img = Image.new("RGBA", (canvas_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if bg_color:
        draw.rectangle([0, 0, canvas_w, img_h], fill=bg_color)

    y = padding
    for i, line in enumerate(lines):
        if not line:
            y += line_heights[i] if i < len(line_heights) else font_size
            continue
        # Center each line
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (canvas_w - text_w) // 2

        # Draw shadow
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            line,
            font=font,
            fill=shadow_color,
        )
        # Draw main text
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_heights[i] + line_spacing

    return img


def create_hook_overlay(text: str, duration: float = 3.0, font_size: int = 72):
    """
    Create hook text overlay for the first `duration` seconds of the video.
    White bold text with black shadow, centered on screen.

    Args:
        text: Hook text string
        duration: Duration in seconds (default 3)
        font_size: Font size in pixels (default 72)

    Returns:
        moviepy ImageClip positioned at center-top of frame
    """
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        logger.warning("PIL or moviepy not available, returning None for hook overlay")
        return None

    img = _create_text_image(
        text=text,
        font_size=font_size,
        text_color=(255, 255, 255, 255),
        shadow_color=(0, 0, 0, 200),
        bg_color=(0, 0, 0, 120),
        padding=50,
        shadow_offset=4,
    )

    img_array = _pil_to_array(img)
    clip = ImageClip(img_array, ismask=False)
    clip = clip.set_duration(duration)

    # Position: vertically centered in upper 40% of frame
    x_pos = 0
    y_pos = int(CANVAS_H * 0.2) - img.height // 2
    y_pos = max(50, y_pos)

    clip = clip.set_position((x_pos, y_pos))
    return clip


def create_body_overlay(
    points: List[str],
    start_time: float = 3.0,
    font_size: int = 56,
    video_duration: float = 15.0,
):
    """
    Create body text overlays with sequential fade-in for each bullet point.

    Args:
        points: List of text strings (each is a bullet point)
        start_time: When the body overlay section begins (seconds)
        font_size: Font size for body text
        video_duration: Total video duration (needed to compute per-point timing)

    Returns:
        List of moviepy ImageClip objects
    """
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        logger.warning("PIL or moviepy not available, returning [] for body overlay")
        return []

    clips = []
    body_duration = video_duration - start_time - 3.0  # Reserve last 3s for CTA
    if body_duration <= 0:
        body_duration = video_duration - start_time
    per_point = body_duration / max(len(points), 1)

    for i, point in enumerate(points):
        bullet_text = f"・{point}"
        img = _create_text_image(
            text=bullet_text,
            font_size=font_size,
            text_color=(255, 255, 255, 255),
            shadow_color=(0, 0, 0, 180),
            bg_color=None,
            padding=40,
            shadow_offset=3,
        )
        img_array = _pil_to_array(img)
        clip = ImageClip(img_array, ismask=False)

        point_start = start_time + i * per_point
        point_duration = body_duration - i * per_point
        clip = clip.set_start(point_start).set_duration(point_duration)

        # Fade in over 0.3 seconds
        clip = clip.crossfadein(0.3)

        # Stack points vertically: center of screen, offset by index
        y_pos = int(CANVAS_H * 0.4) + i * (font_size + 30)
        clip = clip.set_position((0, y_pos))
        clips.append(clip)

    return clips


def create_cta_overlay(
    text: str,
    start_offset_from_end: float = 3.0,
    font_size: int = 60,
    video_duration: float = 15.0,
):
    """
    Create CTA overlay for the last `start_offset_from_end` seconds.
    Uses highlighted yellow/orange background for visibility.

    Args:
        text: CTA text string (may contain newlines)
        start_offset_from_end: Seconds from end to show CTA (default 3)
        font_size: Font size (default 60)
        video_duration: Total video duration

    Returns:
        moviepy ImageClip for the CTA section
    """
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        logger.warning("PIL or moviepy not available, returning None for CTA overlay")
        return None

    img = _create_text_image(
        text=text,
        font_size=font_size,
        text_color=(30, 30, 30, 255),
        shadow_color=(200, 150, 0, 160),
        bg_color=(255, 210, 0, 230),  # Yellow/orange highlight
        padding=40,
        shadow_offset=2,
    )

    img_array = _pil_to_array(img)
    clip = ImageClip(img_array, ismask=False)

    cta_start = max(0.0, video_duration - start_offset_from_end)
    cta_duration = video_duration - cta_start
    clip = clip.set_start(cta_start).set_duration(cta_duration)

    # Position: bottom area of screen
    y_pos = int(CANVAS_H * 0.75)
    clip = clip.set_position((0, y_pos))

    return clip


def _pil_to_array(img: "Image.Image"):
    """Convert PIL RGBA image to numpy array (RGB + alpha handled)."""
    import numpy as np
    # Convert to RGBA then back to RGB for moviepy compatibility
    if img.mode == "RGBA":
        # Composite on black background for moviepy (which doesn't support alpha directly)
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[3])
        return np.array(bg)
    return np.array(img.convert("RGB"))
