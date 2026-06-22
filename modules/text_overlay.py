"""
text_overlay.py — スタイリッシュ・中央揃え・5枚スライド構成
・フック: W9(最太)大フォント + レタースペーシング + アクセントライン
・ボディ: W6(ヘッダー) / W2(コンテンツ) の強弱コントラスト
・CTA: W7 ミディアム太め
・全テキスト中央揃え / ブランク行でグループ分け自動フォントサイズ
"""
import logging
from pathlib import Path
from typing import List, Tuple, Optional

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

# macOS: W9(最太)〜W0(最細) まで全部対応
_BLACK_PATHS = [
    FONTS_DIR / "NotoSansJP-Black.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
_BOLD_PATHS = [
    FONTS_DIR / "NotoSansJP-Bold.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
]
_MEDIUM_PATHS = [
    FONTS_DIR / "NotoSansJP-Medium.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
_THIN_PATHS = [
    FONTS_DIR / "NotoSansJP-Light.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W2.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Light.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Light.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-DemiLight.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
_REGULAR_PATHS = [
    FONTS_DIR / "NotoSansJP-Regular.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


# ─── ユーティリティ ───────────────────────────────────────────

def _get_font(size: int, weight: str = "bold"):
    """weight: "black" | "bold" | "medium" | "regular" | "thin" """
    if not PIL_AVAILABLE:
        return None
    paths_map = {
        "black":   _BLACK_PATHS,
        "bold":    _BOLD_PATHS,
        "medium":  _MEDIUM_PATHS,
        "regular": _REGULAR_PATHS,
        "thin":    _THIN_PATHS,
    }
    for p in paths_map.get(weight, _BOLD_PATHS):
        try:
            return ImageFont.truetype(str(p), size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _text_w(draw, text: str, font) -> int:
    try:
        return draw.textbbox((0, 0), text, font=font)[2]
    except Exception:
        return len(text) * 28


def _text_size(draw, text: str, font) -> Tuple[int, int]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return len(text) * 28, 40


def _draw_shadow(draw, x: int, y: int, text: str, font,
                 fill=(255, 255, 255, 255), shadow_offset: int = 4,
                 shadow_alpha: int = 180):
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font,
              fill=(0, 0, 0, shadow_alpha))
    draw.text((x, y), text, font=font, fill=fill)


def _draw_spaced(draw, x: int, y: int, text: str, font,
                 fill=(255, 255, 255, 255), spacing: int = 3,
                 shadow_offset: int = 4, shadow_alpha: int = 180):
    """1文字ずつ描画してレタースペーシングを追加する"""
    cx = x
    for char in text:
        _draw_shadow(draw, cx, y, char, font, fill=fill,
                     shadow_offset=shadow_offset, shadow_alpha=shadow_alpha)
        w, _ = _text_size(draw, char, font)
        cx += w + spacing


def _spaced_text_width(draw, text: str, font, spacing: int = 3) -> int:
    total = 0
    for i, char in enumerate(text):
        w, _ = _text_size(draw, char, font)
        total += w
        if i < len(text) - 1:
            total += spacing
    return total


def _auto_fit_font_spaced(draw, text: str, start_size: int, max_w: int,
                          weight: str = "black", spacing: int = 2):
    """レタースペーシング込みでテキストが max_w に収まる最大フォントサイズを返す。"""
    size = start_size
    while size > 18:
        font = _get_font(size, weight)
        if font is None:
            break
        if _spaced_text_width(draw, text, font, spacing) <= max_w:
            return font, size
        size -= 2
    return _get_font(max(18, size), weight), max(18, size)


def _make_clip(img, duration: float, position):
    if not NUMPY_AVAILABLE:
        return None
    arr = np.array(img.convert("RGBA"))
    rgb   = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(float) / 255.0
    clip = ImageClip(rgb, ismask=False)
    mask = ImageClip(alpha, ismask=True)
    return clip.set_mask(mask).set_duration(duration).set_position(position)


def _wrap_to_width(draw, text: str, font, max_w: int) -> List[str]:
    """
    テキストをmax_w(px)以内に収まるよう1文字ずつ折り返す。
    既存の改行は維持する。
    """
    result = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            result.append("")
            continue
        if font is None or _text_w(draw, raw_line, font) <= max_w:
            result.append(raw_line)
            continue
        # 文字単位で折り返し
        current = ""
        for char in raw_line:
            test = current + char
            if _text_w(draw, test, font) > max_w:
                if current:
                    result.append(current)
                current = char
            else:
                current = test
        if current:
            result.append(current)
    return result if result else [text]


# ─── 文字化け防止: 特殊記号を・に統一 ────────────────────────

import re as _re

def _normalize_bullets(text: str) -> str:
    """
    ✅ ① → ■ □ などフォントによって文字化けしやすい記号を・に統一する。
    行頭の記号のみ対象（本文中の記号はそのまま）。
    """
    lines = []
    for line in text.splitlines():
        # 行頭の特殊記号 + スペースを ・ に変換
        normalized = _re.sub(
            r'^[\s]*[✅✓✔☑□■▶▷◆◇→⇒★☆①②③④⑤⑥⑦⑧⑨⑩]\s*',
            '・',
            line
        )
        lines.append(normalized)
    return "\n".join(lines)


# ─── グループ分割 ────────────────────────────────────────────

def _split_groups(text: str) -> List[List[str]]:
    """ブランク行でテキストをグループに分割。各グループは空でない行のリスト。"""
    groups: List[List[str]] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
        else:
            if current:
                groups.append(current)
                current = []
    if current:
        groups.append(current)
    return groups


# ─── スライドレンダラー ──────────────────────────────────────

def _render_slide(
    text: str,
    slide_role: str = "body",  # "hook" | "body" | "cta"
) -> Optional[Image.Image]:
    """
    スライドテキストを1枚のRGBA画像に描画。

    slide_role:
      "hook" → W9 大フォント(76px) + レタースペーシング + アクセントライン
      "body" → グループ1: W6 header(54px) / 中間: W2 content(42px) / 最後: W2 footer(34px dimmer)
      "cta"  → W7 medium(50px) + 余白大
    """
    if not PIL_AVAILABLE:
        return None

    # 文字化け防止: ✅①→ 等を・に統一
    text = _normalize_bullets(text)

    groups = _split_groups(text)
    if not groups:
        return None

    BLANK_GAP      = 28
    PANEL_PAD_V    = 60
    LETTER_SPACING = 2   # hook のレタースペーシング px
    MAX_TEXT_W     = 920  # テキスト最大幅(px)。CANVAS_W=1080 から左右80pxマージン

    # ── フォント・スタイル割り当て ───────────────────────────
    if slide_role == "hook":
        styles = [("large", g) for g in groups]
    elif slide_role == "cta":
        styles = [("cta", g) for g in groups]
    else:
        if len(groups) == 1:
            styles = [("header", groups[0])]
        elif len(groups) == 2:
            styles = [("header", groups[0]), ("content", groups[1])]
        else:
            styles = (
                [("header", groups[0])]
                + [("content", g) for g in groups[1:-1]]
                + [("footer", groups[-1])]
            )

    # ── フォントマップ（縮小版）: (font, line_height, color) ──
    FONT_MAP = {
        "large":   (_get_font(58, "black"),   76,  (255, 255, 255, 255)),
        "header":  (_get_font(44, "bold"),    60,  (255, 255, 255, 255)),
        "content": (_get_font(34, "thin"),    50,  (245, 245, 245, 255)),
        "footer":  (_get_font(28, "thin"),    42,  (210, 210, 210, 220)),
        "cta":     (_get_font(42, "medium"),  58,  (255, 255, 255, 255)),
    }

    # ── 全行を (role, font, lh, color, text) に展開 ──────────
    # 仮描画用ドロー（幅計算のため）
    _tmp_canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    _tmp_draw   = ImageDraw.Draw(_tmp_canvas)

    rendered_lines: List[Tuple] = []

    for role, grp_lines in styles:
        font, lh, color = FONT_MAP[role]

        if rendered_lines:
            rendered_lines.append((None, None, BLANK_GAP, None, None))

        for raw_line in grp_lines:
            if role == "large":
                # hookは折り返しなし: フォントサイズを自動縮小して1行に収める
                if raw_line.strip():
                    fit_font, fit_size = _auto_fit_font_spaced(
                        _tmp_draw, raw_line, 58, MAX_TEXT_W, "black", LETTER_SPACING
                    )
                    fit_lh = max(lh, int(fit_size * 1.35))
                    rendered_lines.append((role, fit_font, fit_lh, color, raw_line))
            else:
                # body/cta は従来通り折り返し
                wrapped = _wrap_to_width(_tmp_draw, raw_line, font, MAX_TEXT_W)
                for sub in wrapped:
                    rendered_lines.append((role, font, lh, color, sub if sub.strip() else None))

    # ── 描画サイズ計算 ────────────────────────────────────────
    total_h = sum(lh for (_, _, lh, _, _) in rendered_lines)
    panel_w = CANVAS_W
    panel_h = min(total_h + PANEL_PAD_V * 2, CANVAS_H - 160)  # 画面はみ出し防止

    # アクセントラインの高さ（hookのみ）
    ACCENT_H = 4 if slide_role == "hook" else 0

    # ── キャンバスとパネル ────────────────────────────────────
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))

    y_panel = max(80, (CANVAS_H - panel_h - ACCENT_H) // 2)

    # hookのアクセントライン（上部に細いカラーライン）
    if slide_role == "hook":
        accent_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        draw_a = ImageDraw.Draw(accent_layer)
        accent_y = y_panel - ACCENT_H - 12
        # 白いアクセントライン（中央に短め）
        line_w = 80
        lx = (CANVAS_W - line_w) // 2
        draw_a.rectangle([(lx, accent_y), (lx + line_w, accent_y + ACCENT_H)],
                         fill=(255, 255, 255, 200))
        canvas = Image.alpha_composite(canvas, accent_layer)

    # グラデーションパネル（よりダークでシネマティック）
    panel = Image.new("RGBA", (panel_w, panel_h + ACCENT_H), (0, 0, 0, 0))
    draw_p = ImageDraw.Draw(panel)
    for py in range(panel_h + ACCENT_H):
        # フックは深い黒、ボディ・CTAは少し透明に
        base_alpha = 210 if slide_role == "hook" else 185
        ratio = 1.0 - (py / (panel_h + ACCENT_H)) * 0.15
        alpha = int(base_alpha * ratio)
        draw_p.line([(0, py), (panel_w, py)], fill=(8, 8, 12, alpha))
    canvas.paste(panel, (0, y_panel), panel)

    # ── テキスト描画（中央揃え）──────────────────────────────
    y = y_panel + PANEL_PAD_V
    draw = ImageDraw.Draw(canvas)

    for (role, font, lh, color, text_line) in rendered_lines:
        if text_line is None:
            y += lh
            continue

        if role == "large":
            # フック: レタースペーシング付き中央揃え
            total_w = _spaced_text_width(draw, text_line, font, LETTER_SPACING)
            x = (CANVAS_W - total_w) // 2
            _draw_spaced(draw, x, y, text_line, font,
                         fill=color, spacing=LETTER_SPACING,
                         shadow_offset=5, shadow_alpha=200)
        else:
            w, _ = _text_size(draw, text_line, font)
            x = (CANVAS_W - w) // 2
            _draw_shadow(draw, x, y, text_line, font,
                         fill=color, shadow_offset=4, shadow_alpha=180)
        y += lh

    return canvas


# ─── 公開API ─────────────────────────────────────────────────

def create_hook_overlay(text: str, duration: float = 3.0, font_size: int = 68,
                        solution_text: str = None, topic: str = None,
                        points_count: int = None):
    """フックスライド（最初の1枚）"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    slide_text = text
    if topic and topic not in text:
        slide_text = f"{text}\n\n〜 {topic} 〜"

    canvas = _render_slide(slide_text, slide_role="hook")
    if canvas is None:
        return None

    clip = _make_clip(canvas, duration, (0, 0))
    if clip:
        clip = clip.crossfadein(0.3)
    return clip


def create_body_overlay(points: List[str], start_time: float = 3.0,
                        font_size: int = 52, video_duration: float = 15.0,
                        dur_each: float = None):
    """
    ボディスライド群（中間）。
    points の各要素が1枚のスライドテキスト（改行・ブランク行込みの完全フォーマット）。
    """
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE or not points:
        return []

    if dur_each is None:
        cta_reserve = 3.0
        total = video_duration - start_time - cta_reserve
        dur_each = max(1.5, total / max(len(points), 1))

    clips = []
    for i, slide_text in enumerate(points):
        t_start = start_time + i * dur_each
        if t_start >= video_duration - 1.5:
            break
        actual_dur = min(dur_each, video_duration - t_start)
        if actual_dur < 0.5:
            break

        canvas = _render_slide(slide_text, slide_role="body")
        if canvas is None:
            continue

        clip = _make_clip(canvas, actual_dur, (0, 0))
        if clip:
            clip = clip.set_start(t_start).crossfadein(0.3)
            clips.append(clip)

    return clips


def create_cta_overlay(text: str, start_offset_from_end: float = 5.0,
                       font_size: int = 44, video_duration: float = 20.0):
    """CTAスライド（最後の5秒）"""
    if not PIL_AVAILABLE or not MOVIEPY_AVAILABLE:
        return None

    canvas = _render_slide(text, slide_role="cta")
    if canvas is None:
        return None

    cta_start = max(0.0, video_duration - start_offset_from_end)
    duration   = video_duration - cta_start

    clip = _make_clip(canvas, duration, (0, 0))
    if clip:
        clip = clip.set_start(cta_start).crossfadein(0.5)
    return clip
