"""
Text overlay generation — 中央配置・インパクト重視スタイル
"""
import logging
import math
from pathlib import Path
from typing import List, Tuple

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

_BOLD_PATHS = [
    FONTS_DIR / "NotoSansJP-Bold.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

_REGULAR_PATHS = [
    FONTS_DIR / "NotoSansJP-Regular.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]

# Legacy alias
DEFAULT_FONT_PATHS = _BOLD_PATHS


def _get_font(size: int, bold: bool = True):
    if not PIL_AVAILABLE:
        return None
    for p in (_BOLD_PATHS if bold else _REGULAR_PATHS):
        try:
            return ImageFont.truetype(str(p), size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _text_size(draw, text: str, font) -> Tuple[int, int]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return len(text) * 30, 40


def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
    lines = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            test = current + ch
            try:
                w = draw.textbbox((0, 0), test, font=font)[2]
            except Exception:
                w = len(test) * 30
            if w <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def _natural_break(text: str) -> str:
    """日本語テキストを最も自然な位置で一度だけ改行"""
    if "\n" in text:
        return text
    if len(text) <= 14:
        return text

    mid = len(text) // 2
    break_after = "。、！？…ー〜・）」』"
    particles = "はがをにでともへ"

    # 句読点・記号を中心から探す
    for r in range(0, mid + 1):
        for i in [mid - r, mid + r]:
            if 0 < i < len(text) - 1 and text[i] in break_after:
                return text[:i + 1] + "\n" + text[i + 1:]

    # 助詞の後ろを中心から探す
    for r in range(0, mid + 1):
        for i in [mid - r, mid + r]:
            if 0 < i < len(text) - 1 and text[i] in particles:
                return text[:i + 1] + "\n" + text[i + 1:]

    # 最終手段: 中央で分割
    return text[:mid] + "\n" + text[mid:]


def _draw_shadow_text(draw, x: int, y: int, text: str, font,
                      fill=(255, 255, 255, 255), shadow_offset: int = 3,
                      shadow_alpha: int = 160):
    """ソフトシャドウ付きテキスト"""
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font,
              fill=(0, 0, 0, shadow_alpha))
    draw.text((x, y), text, font=font, fill=fill)


def _draw_left_bracket(draw, x_center: int, y_top: int, y_bottom: int,
                        curve_depth: int = 16, color=(255, 255, 255, 190), width: int = 3):
    """曲線の縦ブラケット ( 型"""
    n, height = 30, y_bottom - y_top
    pts = []
    for i in range(n + 1):
        t = i / n
        bow = curve_depth * math.sin(math.pi * t)
        pts.append((x_center - bow, y_top + t * height))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=width)


def _make_clip(img, duration: float, position):
    """RGBA PIL画像からmoviepyクリップを作成（透明度対応）"""
    if not NUMPY_AVAILABLE:
        return None
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(float) / 255.0
    clip = ImageClip(rgb, ismask=False)
    mask = ImageClip(alpha, ismask=True)
    return clip.set_mask(mask).set_duration(duration).set_position(position)


# ─────────────────────────────────────────────────────────────────────────────
# Hook overlay（0〜3秒）— 画面中央・大きくインパクト
# ─────────────────────────────────────────────────────────────────────────────

def create_hook_overlay(text: str, duration: float = 3.0, font_size: int = 72,
                        solution_text: str = None, topic: str = None,
                        points_count: int = None):
    """
    text          : フック文（中央に大きく表示）
    solution_text : サブテキスト（フックの下に中サイズで表示）
    topic         : トピック（ヘッダーに ＼ topic ／ で表示）
    """
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    header_font = _get_font(36, bold=False)
    hook_font = _get_font(74, bold=True)
    sub_font = _get_font(52, bold=False)

    pad_x = 56
    max_w = CANVAS_W - pad_x * 2

    # ── テンポラリ draw でサイズ計測 ────────────────────────────────
    tmp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)

    # ヘッダー行: ＼ topic ／
    header_text = f"＼ {topic} ／" if topic else ""
    header_lines = _wrap_text(header_text, header_font, max_w, td) if header_text else []

    # メインフック（自然な位置で改行）
    hook_broken = _natural_break(text)
    hook_lines = _wrap_text(hook_broken, hook_font, max_w, td)

    # サブテキスト
    sub_lines: List[str] = []
    if solution_text:
        sub_broken = _natural_break(solution_text)
        sub_lines = _wrap_text(sub_broken, sub_font, max_w, td)

    # ── 画像サイズ計算 ───────────────────────────────────────────────
    h_lh = 48   # header line height
    k_lh = 86   # hook line height
    s_lh = 64   # sub line height
    pad_top = 44
    pad_inner = 20  # header→hook の間隔
    pad_sub = 28    # hook→sub の間隔
    pad_bottom = 44

    img_h = (pad_top
             + len(header_lines) * h_lh + (pad_inner if header_lines else 0)
             + len(hook_lines) * k_lh
             + (pad_sub + len(sub_lines) * s_lh if sub_lines else 0)
             + pad_bottom)

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景パネル（ダーク半透明）
    draw.rounded_rectangle([0, 0, CANVAS_W, img_h], radius=0, fill=(8, 8, 8, 210))
    # 上下の黄色アクセントライン
    draw.rectangle([0, 0, CANVAS_W, 4], fill=(255, 210, 0, 255))
    draw.rectangle([0, img_h - 4, CANVAS_W, img_h], fill=(255, 210, 0, 255))

    # ── ヘッダー描画 ─────────────────────────────────────────────────
    y = pad_top
    for line in header_lines:
        w, _ = _text_size(draw, line, header_font)
        _draw_shadow_text(draw, (CANVAS_W - w) // 2, y, line, header_font,
                          fill=(200, 200, 200, 200), shadow_offset=2, shadow_alpha=100)
        y += h_lh
    if header_lines:
        y += pad_inner

    # ── メインフック描画（中央・大きく） ─────────────────────────────
    for line in hook_lines:
        w, _ = _text_size(draw, line, hook_font)
        _draw_shadow_text(draw, (CANVAS_W - w) // 2, y, line, hook_font,
                          fill=(255, 255, 255, 255), shadow_offset=4, shadow_alpha=180)
        y += k_lh

    # ── サブテキスト描画 ─────────────────────────────────────────────
    if sub_lines:
        y += pad_sub
        for line in sub_lines:
            w, _ = _text_size(draw, line, sub_font)
            _draw_shadow_text(draw, (CANVAS_W - w) // 2, y, line, sub_font,
                              fill=(240, 240, 240, 220), shadow_offset=3, shadow_alpha=150)
            y += s_lh

    # 画面中央に配置（やや上寄り）
    y_pos = max(40, (CANVAS_H - img_h) // 2 - 80)
    return _make_clip(img, duration, (0, y_pos))


# ─────────────────────────────────────────────────────────────────────────────
# Body overlay（3〜12秒）— 中央配置・ブラケットリスト
# ─────────────────────────────────────────────────────────────────────────────

def create_body_overlay(points: List[str], start_time: float = 3.0,
                        font_size: int = 52, video_duration: float = 15.0):
    """全ポイントを中央に一括表示・左ブラケット付き"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return []

    font = _get_font(font_size, bold=False)
    padding_left = 106
    max_w = CANVAS_W - padding_left - 40

    all_lines_by_point: List[List[str]] = []
    for point in points:
        tmp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        # ポイントも自然な改行を適用
        broken = _natural_break(point)
        all_lines_by_point.append(_wrap_text(f"・{broken}", font, max_w, td))

    line_h = font_size + 18
    point_gap = 16
    total_h = sum(len(ls) * line_h for ls in all_lines_by_point) + point_gap * len(all_lines_by_point)
    img_h = total_h + 50

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 左ブラケット
    _draw_left_bracket(draw, x_center=58, y_top=16, y_bottom=img_h - 16,
                       curve_depth=15, color=(255, 255, 255, 190), width=3)

    y = 16
    for lines in all_lines_by_point:
        for line in lines:
            _draw_shadow_text(draw, padding_left, y, line, font,
                              fill=(255, 255, 255, 245), shadow_offset=3)
            y += line_h
        y += point_gap

    body_duration = max(1.0, video_duration - start_time - 3.0)

    # 画面中央やや上に配置
    y_pos = max(40, (CANVAS_H - img_h) // 2 - 40)
    clip = _make_clip(img, body_duration, (0, y_pos))
    clip = clip.set_start(start_time).crossfadein(0.4)
    return [clip]


# ─────────────────────────────────────────────────────────────────────────────
# CTA overlay（最後3秒）
# ─────────────────────────────────────────────────────────────────────────────

def create_cta_overlay(text: str, start_offset_from_end: float = 3.0,
                       font_size: int = 50, video_duration: float = 15.0):
    """CTA: ダークバー + 黄色アクセントライン（画面下部）"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    font = _get_font(font_size, bold=True)
    max_w = CANVAS_W - 80

    tmp = Image.new("RGBA", (CANVAS_W, 100), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    lines = _wrap_text(text, font, max_w, td)

    line_h = font_size + 14
    img_h = line_h * len(lines) + 56

    img = Image.new("RGBA", (CANVAS_W, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, CANVAS_W, img_h], fill=(10, 10, 10, 215))
    draw.rectangle([0, 0, CANVAS_W, 5], fill=(255, 210, 0, 255))
    draw.rectangle([0, img_h - 5, CANVAS_W, img_h], fill=(255, 210, 0, 255))

    y = 26
    for line in lines:
        w, _ = _text_size(draw, line, font)
        _draw_shadow_text(draw, (CANVAS_W - w) // 2, y, line, font,
                          fill=(255, 255, 255, 255), shadow_offset=3)
        y += line_h

    cta_start = max(0.0, video_duration - start_offset_from_end)
    clip = _make_clip(img, video_duration - cta_start, (0, int(CANVAS_H * 0.74)))
    clip = clip.set_start(cta_start).crossfadein(0.4)
    return clip
