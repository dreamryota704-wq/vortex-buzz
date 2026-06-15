"""
Text overlay generation — TikTok スタイル（黒縁取り・大きな文字）
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

try:
    from moviepy.editor import ImageClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

CANVAS_W, CANVAS_H = 1080, 1920

FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"
DEFAULT_FONT_PATHS = [
    FONTS_DIR / "NotoSansJP-Bold.ttf",
    FONTS_DIR / "NotoSansJP-Regular.ttf",
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # Ubuntu (GitHub Actions)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
]


def _get_font(size: int):
    if not PIL_AVAILABLE:
        return None
    for font_path in DEFAULT_FONT_PATHS:
        try:
            return ImageFont.truetype(str(font_path), size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _draw_stroked_text(draw, x: int, y: int, text: str, font, fill, stroke_color, stroke_width: int = 6):
    """テキストを縁取り付きで描画（TikTokスタイル）"""
    # 縁取り: 上下左右斜め8方向に同じテキストを描画
    for dx in range(-stroke_width, stroke_width + 1, max(1, stroke_width // 3)):
        for dy in range(-stroke_width, stroke_width + 1, max(1, stroke_width // 3)):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
    lines = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue
        current_line = ""
        for char in list(paragraph):
            test_line = current_line + char
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
            except Exception:
                w = len(test_line) * 30
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
    return lines


def _text_size(draw, text: str, font) -> Tuple[int, int]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return len(text) * 30, 40


def _pil_to_array(img):
    import numpy as np
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[3])
        return np.array(bg)
    return np.array(img.convert("RGB"))


# ─────────────────────────────────────────────────────────────────────────────
# Hook overlay（0〜3秒: 画面上部に大きく表示）
# ─────────────────────────────────────────────────────────────────────────────

def create_hook_overlay(text: str, duration: float = 3.0, font_size: int = 90):
    """フック文: 大きな白文字 + 黒縁取り、半透明グラデーション背景"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    font = _get_font(font_size)
    padding_x = 60
    max_w = CANVAS_W - padding_x * 2

    # テキスト計測
    temp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp)
    lines = _wrap_text(text, font, max_w, draw)

    line_h = font_size + 10
    total_h = line_h * len(lines) + 60
    img_h = total_h + 80

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))

    # 半透明グラデーション背景
    for y in range(img_h):
        alpha = int(160 * (1 - abs(y - img_h / 2) / (img_h / 2)) + 80)
        alpha = min(200, max(60, alpha))
        for x in range(CANVAS_W):
            img.putpixel((x, y), (0, 0, 0, alpha))

    draw = ImageDraw.Draw(img)

    y = 40
    for line in lines:
        w, _ = _text_size(draw, line, font)
        x = (CANVAS_W - w) // 2
        _draw_stroked_text(draw, x, y, line, font,
                           fill=(255, 255, 255, 255),
                           stroke_color=(0, 0, 0, 255),
                           stroke_width=8)
        y += line_h

    clip = ImageClip(_pil_to_array(img), ismask=False)
    clip = clip.set_duration(duration)

    y_pos = int(CANVAS_H * 0.12)
    clip = clip.set_position((0, y_pos))
    return clip


# ─────────────────────────────────────────────────────────────────────────────
# Body overlay（3〜12秒: 箇条書き、順番に表示）
# ─────────────────────────────────────────────────────────────────────────────

def create_body_overlay(points: List[str], start_time: float = 3.0,
                        font_size: int = 68, video_duration: float = 15.0):
    """本文: 白文字 + 黒縁取り、ポイントごとに順番に表示"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return []

    font = _get_font(font_size)
    clips = []
    body_duration = video_duration - start_time - 3.0
    if body_duration <= 0:
        body_duration = video_duration - start_time
    per_point = body_duration / max(len(points), 1)

    for i, point in enumerate(points):
        text = f"✅ {point}"
        padding_x = 50
        max_w = CANVAS_W - padding_x * 2

        temp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
        draw_temp = ImageDraw.Draw(temp)
        lines = _wrap_text(text, font, max_w, draw_temp)

        line_h = font_size + 12
        img_h = line_h * len(lines) + 40
        img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))

        # 左端にアクセントライン
        for y in range(img_h):
            for x in range(8):
                img.putpixel((x, y), (255, 220, 0, 220))

        draw = ImageDraw.Draw(img)
        y = 20
        for line in lines:
            _draw_stroked_text(draw, padding_x, y, line, font,
                               fill=(255, 255, 255, 255),
                               stroke_color=(0, 0, 0, 255),
                               stroke_width=6)
            y += line_h

        clip = ImageClip(_pil_to_array(img), ismask=False)
        point_start = start_time + i * per_point
        point_duration = body_duration - i * per_point
        clip = clip.set_start(point_start).set_duration(point_duration)
        clip = clip.crossfadein(0.3)

        y_pos = int(CANVAS_H * 0.42) + i * (img_h + 20)
        clip = clip.set_position((0, y_pos))
        clips.append(clip)

    return clips


# ─────────────────────────────────────────────────────────────────────────────
# CTA overlay（最後3秒: 黄色背景で目立つCTA）
# ─────────────────────────────────────────────────────────────────────────────

def create_cta_overlay(text: str, start_offset_from_end: float = 3.0,
                       font_size: int = 72, video_duration: float = 15.0):
    """CTA: 黄色背景 + 黒文字 + 縁取り、画面下部に大きく表示"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    font = _get_font(font_size)
    padding_x = 40
    max_w = CANVAS_W - padding_x * 2

    temp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
    draw_temp = ImageDraw.Draw(temp)
    lines = _wrap_text(text, font, max_w, draw_temp)

    line_h = font_size + 14
    img_h = line_h * len(lines) + 70

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))

    # 鮮やかな黄色背景
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, CANVAS_W, img_h], radius=20,
                            fill=(255, 220, 0, 240))
    # 上下に黒ライン
    draw.rectangle([0, 0, CANVAS_W, 6], fill=(0, 0, 0, 255))
    draw.rectangle([0, img_h - 6, CANVAS_W, img_h], fill=(0, 0, 0, 255))

    y = 35
    for line in lines:
        w, _ = _text_size(draw, line, font)
        x = (CANVAS_W - w) // 2
        _draw_stroked_text(draw, x, y, line, font,
                           fill=(20, 20, 20, 255),
                           stroke_color=(255, 255, 255, 180),
                           stroke_width=4)
        y += line_h

    clip = ImageClip(_pil_to_array(img), ismask=False)
    cta_start = max(0.0, video_duration - start_offset_from_end)
    clip = clip.set_start(cta_start).set_duration(video_duration - cta_start)
    clip = clip.crossfadein(0.4)

    y_pos = int(CANVAS_H * 0.72)
    clip = clip.set_position((0, y_pos))
    return clip
