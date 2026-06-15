"""
Video editing operations using moviepy.
Handles cropping, cutting, color filters, BGM, and export.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency when moviepy is not installed
try:
    from moviepy.editor import (
        VideoFileClip,
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
    )
    import moviepy.video.fx.all as vfx
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("moviepy not installed. Video editing functions will not work.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


def _require_moviepy():
    if not MOVIEPY_AVAILABLE:
        raise RuntimeError(
            "moviepy is not installed. Run: pip install moviepy==1.0.3"
        )


def crop_vertical(clip):
    """
    Crop video to 9:16 aspect ratio (1080x1920), centered horizontally.

    Args:
        clip: moviepy VideoClip

    Returns:
        Cropped VideoClip at 1080x1920
    """
    _require_moviepy()

    target_w, target_h = 1080, 1920
    src_w, src_h = clip.size

    # Calculate crop dimensions
    target_ratio = target_w / target_h  # 9:16 = 0.5625
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Source is wider than 9:16 — crop width
        new_w = int(src_h * target_ratio)
        x1 = (src_w - new_w) // 2
        y1 = 0
        cropped = clip.crop(x1=x1, y1=y1, x2=x1 + new_w, y2=src_h)
    else:
        # Source is taller than 9:16 — crop height
        new_h = int(src_w / target_ratio)
        x1 = 0
        y1 = (src_h - new_h) // 2
        cropped = clip.crop(x1=x1, y1=y1, x2=src_w, y2=y1 + new_h)

    # Resize to exact 1080x1920
    resized = cropped.resize((target_w, target_h))
    return resized


def cut_to_duration(clip, max_seconds: float = 15.0):
    """
    Trim clip to at most max_seconds.

    Args:
        clip: moviepy VideoClip
        max_seconds: Maximum duration in seconds (default 15)

    Returns:
        Trimmed VideoClip
    """
    _require_moviepy()

    if clip.duration > max_seconds:
        return clip.subclip(0, max_seconds)
    return clip


def apply_color_filter(clip, filter_type: str):
    """
    Apply a color grading filter to the clip.

    filter_type options:
        "cool"  — blue tint (cooler color temperature)
        "warm"  — orange/yellow tint (warmer color temperature)
        "sharp" — increased contrast + slight saturation boost
        "clean" — neutral / no modification

    Args:
        clip: moviepy VideoClip
        filter_type: One of "cool", "warm", "sharp", "clean"

    Returns:
        Color-filtered VideoClip
    """
    _require_moviepy()

    if not NUMPY_AVAILABLE:
        logger.warning("numpy not available, skipping color filter")
        return clip

    filter_type = (filter_type or "clean").lower()

    if filter_type == "clean":
        return clip

    def make_filter(ft):
        def color_filter(frame):
            img = frame.astype(np.float32)
            if ft == "cool":
                # Boost blue, reduce red slightly
                img[:, :, 0] = np.clip(img[:, :, 0] * 0.9, 0, 255)   # R -10%
                img[:, :, 2] = np.clip(img[:, :, 2] * 1.15, 0, 255)  # B +15%
            elif ft == "warm":
                # Boost red/green, reduce blue
                img[:, :, 0] = np.clip(img[:, :, 0] * 1.15, 0, 255)  # R +15%
                img[:, :, 1] = np.clip(img[:, :, 1] * 1.05, 0, 255)  # G +5%
                img[:, :, 2] = np.clip(img[:, :, 2] * 0.85, 0, 255)  # B -15%
            elif ft == "sharp":
                # Increase contrast: stretch values away from 128
                img = np.clip((img - 128) * 1.3 + 128, 0, 255)
            return img.astype(np.uint8)
        return color_filter

    return clip.fl_image(make_filter(filter_type))


def add_bgm(clip, bgm_path: str, volume_db: float = -15.0):
    """
    Mix background music into the clip at the specified dB level.

    Args:
        clip: moviepy VideoClip (with or without existing audio)
        bgm_path: Path to BGM audio file (.mp3, .wav, etc.)
        volume_db: BGM volume in dB relative to original (default -15 dB)

    Returns:
        VideoClip with mixed audio
    """
    _require_moviepy()

    bgm_path = Path(bgm_path)
    if not bgm_path.exists():
        logger.warning(f"BGM file not found: {bgm_path}. Skipping BGM.")
        return clip

    # Convert dB to linear multiplier
    linear_vol = 10 ** (volume_db / 20.0)

    bgm = AudioFileClip(str(bgm_path))
    # Loop or trim BGM to match video duration
    if bgm.duration < clip.duration:
        # Loop BGM
        loops = int(clip.duration / bgm.duration) + 1
        from moviepy.audio.AudioClip import concatenate_audioclips
        bgm = concatenate_audioclips([bgm] * loops)
    bgm = bgm.subclip(0, clip.duration).volumex(linear_vol)

    if clip.audio is not None:
        mixed = CompositeAudioClip([clip.audio, bgm])
        return clip.set_audio(mixed)
    else:
        return clip.set_audio(bgm)


def export_video(clip, output_path: str, metadata: dict = None):
    """
    Export video as MP4 and save metadata as JSON sidecar file.

    Args:
        clip: moviepy VideoClip
        output_path: Output file path (e.g. output/account_A/20240101_120000.mp4)
        metadata: Optional dict to save as JSON sidecar (.json alongside .mp4)
    """
    _require_moviepy()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting video to {output_path}")
    clip.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=30,
        preset="fast",
        logger=None,  # suppress moviepy progress bar (use our own)
    )

    # Save metadata sidecar
    if metadata is not None:
        meta_path = output_path.with_suffix(".json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Metadata saved to {meta_path}")

    return output_path
