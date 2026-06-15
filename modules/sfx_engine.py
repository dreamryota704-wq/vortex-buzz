"""
Sound effects (SFX) engine.
Mixes SFX events into a video clip at specified timestamps.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

try:
    from moviepy.editor import AudioFileClip, CompositeAudioClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("moviepy not installed. SFX engine will not work.")

# Default SFX directory relative to buzz_system root
DEFAULT_SFX_DIR = Path(__file__).parent.parent / "assets" / "sfx"

# Supported SFX types and their filenames
SFX_FILENAMES = {
    "whoosh": "whoosh.mp3",
    "ding": "ding.mp3",
    "pop": "pop.mp3",
    "swoosh": "swoosh.mp3",
    "chime": "chime.mp3",
    "drum": "drum.mp3",
    "tap": "tap.mp3",
}

DEFAULT_VOLUME_DB = -15.0


def _db_to_linear(db: float) -> float:
    """Convert dB to linear amplitude multiplier."""
    return 10 ** (db / 20.0)


def add_sfx(
    clip,
    sfx_dir: str = None,
    events: List[Dict[str, Any]] = None,
    default_volume_db: float = DEFAULT_VOLUME_DB,
):
    """
    Mix sound effects into a video clip at specified event times.

    Args:
        clip: moviepy VideoClip with or without existing audio
        sfx_dir: Directory containing SFX audio files. Defaults to assets/sfx/
        events: List of event dicts with keys:
                  - "time": float, time in seconds to play the SFX
                  - "type": str, one of "whoosh", "ding", "pop", "swoosh"
                  - "volume_db": float (optional), override default volume
        default_volume_db: Default volume for SFX in dB (default -15)

    Returns:
        VideoClip with SFX mixed in. Returns original clip if no SFX loaded.
    """
    if not MOVIEPY_AVAILABLE:
        logger.warning("moviepy not available, skipping SFX")
        return clip

    if not events:
        return clip

    sfx_dir = Path(sfx_dir) if sfx_dir else DEFAULT_SFX_DIR

    audio_clips = []

    # Keep existing audio
    if clip.audio is not None:
        audio_clips.append(clip.audio)

    loaded_count = 0
    for event in events:
        event_time = float(event.get("time", 0))
        sfx_type = event.get("type", "ding")
        vol_db = float(event.get("volume_db", default_volume_db))

        # Skip events outside video duration
        if event_time >= clip.duration:
            logger.debug(f"SFX event at {event_time}s is past video duration {clip.duration}s, skipping")
            continue

        # Resolve file path
        filename = SFX_FILENAMES.get(sfx_type, f"{sfx_type}.mp3")
        sfx_path = sfx_dir / filename

        if not sfx_path.exists():
            logger.debug(f"SFX file not found: {sfx_path}, skipping event at {event_time}s")
            continue

        try:
            sfx_clip = AudioFileClip(str(sfx_path))
            # Trim SFX if it would extend past video duration
            max_sfx_duration = clip.duration - event_time
            if sfx_clip.duration > max_sfx_duration:
                sfx_clip = sfx_clip.subclip(0, max_sfx_duration)

            # Apply volume
            linear_vol = _db_to_linear(vol_db)
            sfx_clip = sfx_clip.volumex(linear_vol).set_start(event_time)
            audio_clips.append(sfx_clip)
            loaded_count += 1
            logger.debug(f"Loaded SFX '{sfx_type}' at t={event_time}s ({vol_db}dB)")
        except Exception as e:
            logger.warning(f"Failed to load SFX '{sfx_type}' from {sfx_path}: {e}")
            continue

    if loaded_count == 0:
        logger.info("No SFX files found/loaded, returning original clip")
        return clip

    mixed_audio = CompositeAudioClip(audio_clips)
    mixed_audio = mixed_audio.set_duration(clip.duration)
    return clip.set_audio(mixed_audio)


def get_default_sfx_events(video_duration: float = 15.0) -> List[Dict[str, Any]]:
    """
    Return a default set of SFX events for a standard short video.
    Useful as a starting point when no specific events are specified.

    Args:
        video_duration: Total video duration in seconds

    Returns:
        List of event dicts
    """
    events = [
        {"time": 0.0, "type": "whoosh", "volume_db": -18},    # Video start
        {"time": 3.0, "type": "ding", "volume_db": -15},       # Transition to body
        {"time": video_duration - 3.0, "type": "swoosh", "volume_db": -15},  # CTA appear
    ]
    # Add pop sounds between body points (evenly distributed between 3s and CTA)
    body_start = 3.0
    body_end = video_duration - 3.0
    if body_end > body_start + 2:
        mid = (body_start + body_end) / 2
        events.append({"time": mid, "type": "pop", "volume_db": -18})

    return events
