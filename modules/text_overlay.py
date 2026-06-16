"""
Text overlay generation — リファレンススタイル（＼...／ + バブル + ブラケットリスト）
"""
import logging
import math
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

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

CANVAS_W, CANVAS_H = 1080, 1920

FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_BOLD_FONT_PATHS = [
    FONTS_DIR / "NotoSansJP-Bold.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

_REGULAR_FONT_PATHS = [
    FONTS_DIR / "NotoSansJP-Regular.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]

# Legacy alias kept for external imports
DEFAULT_FONT_PATHS = _BOLD_FONT_PATHS


def _get_font(size: int, bold: bool = True):
    if not PIL_AVAILABLE:
        return None
    paths = _BOLD_FONT_PATHS if bold else _REGULAR_FONT_PATHS
    for p in paths:
        try:
            return ImageFont.truetype(str(p), size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


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


def _draw_shadow_text(draw, x: int, y: int, text: str, font,
                      fill=(255, 255, 255, 255), shadow_offset: int = 3,
                      shadow_alpha: int = 160):
    """ソフトシャドウ付きテキスト（縁取りなし）"""
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font,
              fill=(0, 0, 0, shadow_alpha))
    draw.text((x, y), text, font=font, fill=fill)


def _draw_left_bracket(draw, x_center: int, y_top: int, y_bottom: int,
                        curve_depth: int = 18, color=(255, 255, 255, 200), width: int = 3):
    """左側の丸みのある縦ブラケット（ ( 型）を描画"""
    n = 30
    height = y_bottom - y_top
    points = []
    for i in range(n + 1):
        t = i / n
        y = y_top + t * height
        bow = curve_depth * math.sin(math.pi * t)
        x = x_center - bow
        points.append((x, y))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=color, width=width)


def _make_clip(img, duration: float, position):
    """RGBA PILイメージからmoviepyクリップを作成（透明度対応）"""
    if not NUMPY_AVAILABLE:
        return None
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(float) / 255.0
    clip = ImageClip(rgb, ismask=False)
    mask = ImageClip(alpha, ismask=True)
    clip = clip.set_mask(mask).set_duration(duration).set_position(position)
    return clip


# ─────────────────────────────────────────────────────────────────────────────
# Hook overlay（0〜3秒）
# リファレンス: 上部 ＼...／ アドレシング + 中央ダークバブル
# ─────────────────────────────────────────────────────────────────────────────

def create_hook_overlay(text: str, duration: float = 3.0, font_size: int = 72,
                        solution_text: str = None, topic: str = None,
                        points_count: int = None):
    """
    text          : フック文（＼...／で表示）
    solution_text : バブル内に表示する価値提案（body_points[0]推奨）
    topic         : トピックキーワード（solution_textがない場合の代替）
    """
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    header_font = _get_font(38, bold=False)
    bubble_font = _get_font(60, bold=True)

    img = Image.new("RGBA", (CANVAS_W, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── 上部: ＼ text ／ ────────────────────────────────────────────────
    header = f"＼ {text} ／"
    header_lines = _wrap_text(header, header_font, CANVAS_W - 80, draw)
    y = 28
    for line in header_lines:
        w, _ = _text_size(draw, line, header_font)
        x = (CANVAS_W - w) // 2
        _draw_shadow_text(draw, x, y, line, header_font,
                          fill=(255, 255, 255, 215), shadow_offset=2, shadow_alpha=140)
        y += 52

    # ── バブルテキスト ───────────────────────────────────────────────────
    if solution_text:
        bubble_text = solution_text
    elif topic and points_count:
        bubble_text = f"{topic}\n{points_count}つのポイント"
    elif topic:
        bubble_text = topic
    else:
        bubble_text = text

    bubble_lines = _wrap_text(bubble_text, bubble_font, CANVAS_W - 140, draw)
    line_h = 82
    pad_y = 38
    bubble_w = CANVAS_W - 80
    bubble_h = len(bubble_lines) * line_h + pad_y * 2
    bx, by = 40, y + 18

    draw.rounded_rectangle(
        [bx, by, bx + bubble_w, by + bubble_h],
        radius=30, fill=(12, 12, 12, 215)
    )

    ty = by + pad_y
    for line in bubble_lines:
        w, _ = _text_size(draw, line, bubble_font)
        tx = (CANVAS_W - w) // 2
        _draw_shadow_text(draw, tx, ty, line, bubble_font,
                          fill=(255, 255, 255, 255), shadow_offset=3)
        ty += line_h

    return _make_clip(img, duration, (0, int(CANVAS_H * 0.07)))


# ─────────────────────────────────────────────────────────────────────────────
# Body overlay（3〜12秒）
# リファレンス: 左縦ブラケット + 箇条書き全件一括表示
# ─────────────────────────────────────────────────────────────────────────────

def create_body_overlay(points: List[str], start_time: float = 3.0,
                        font_size: int = 52, video_duration: float = 15.0):
    """全ポイントを一括表示、左ブラケット付き"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return []

    font = _get_font(font_size, bold=False)
    padding_left = 108
    max_w = CANVAS_W - padding_left - 40

    all_lines_by_point: List[List[str]] = []
    for point in points:
        temp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
        td = ImageDraw.Draw(temp)
        all_lines_by_point.append(_wrap_text(f"・{point}", font, max_w, td))

    line_h = font_size + 18
    point_gap = 14
    total_h = sum(len(ls) * line_h for ls in all_lines_by_point) + point_gap * len(all_lines_by_point)
    img_h = total_h + 60

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 左ブラケット
    _draw_left_bracket(draw, x_center=60, y_top=20, y_bottom=img_h - 20,
                       curve_depth=16, color=(255, 255, 255, 200), width=3)

    # テキスト
    y = 18
    for lines in all_lines_by_point:
        for line in lines:
            _draw_shadow_text(draw, padding_left, y, line, font,
                              fill=(255, 255, 255, 245), shadow_offset=3)
            y += line_h
        y += point_gap

    body_duration = max(1.0, video_duration - start_time - 3.0)
    clip = _make_clip(img, body_duration, (0, int(CANVAS_H * 0.33)))
    clip = clip.set_start(start_time).crossfadein(0.4)
    return [clip]


# ─────────────────────────────────────────────────────────────────────────────
# CTA overlay（最後3秒）
# リファレンス: ダークバー + 黄色アクセントライン
# ─────────────────────────────────────────────────────────────────────────────

def create_cta_overlay(text: str, start_offset_from_end: float = 3.0,
                       font_size: int = 50, video_duration: float = 15.0):
    """CTA: ダーク半透明バー + 黄色アクセント"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    font = _get_font(font_size, bold=True)
    max_w = CANVAS_W - 80

    temp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
    draw_temp = ImageDraw.Draw(temp)
    lines = _wrap_text(text, font, max_w, draw_temp)

    line_h = font_size + 14
    img_h = line_h * len(lines) + 56

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, CANVAS_W, img_h], fill=(10, 10, 10, 210))
    draw.rectangle([0, 0, CANVAS_W, 5], fill=(255, 210, 0, 255))
    draw.rectangle([0, img_h - 5, CANVAS_W, img_h], fill=(255, 210, 0, 255))

    y = 26
    for line in lines:
        w, _ = _text_size(draw, line, font)
        x = (CANVAS_W - w) // 2
        _draw_shadow_text(draw, x, y, line, font,
                          fill=(255, 255, 255, 255), shadow_offset=3)
        y += line_h

    cta_start = max(0.0, video_duration - start_offset_from_end)
    clip = _make_clip(img, video_duration - cta_start, (0, int(CANVAS_H * 0.74)))
    clip = clip.set_start(cta_start).crossfadein(0.4)
    return clip
