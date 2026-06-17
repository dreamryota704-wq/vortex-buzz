"""
account_design_loader.py
account_design.md を解析して毎日の動画コンテンツ（hook・body・topic）を返す。
新フォーマット: VIDEO_PATTERN_N / SLIDE_1〜5 を優先。
旧フォーマット: ```コードブロック``` パターンにフォールバック。
"""
import re
import random
from pathlib import Path
from typing import Optional


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────
# パーサー: 新フォーマット VIDEO_PATTERN/SLIDE_N
# ─────────────────────────────────────────────

def _parse_video_patterns(md_text: str) -> list:
    """
    新フォーマット VIDEO_PATTERN_N「...」 の SLIDE_1〜5 を抽出。
    Returns: [{"name": str, "slides": [str x 5]}]
    各 slides[i] は SLIDE_{i+1} の整形済みテキスト（改行・ブランク行込み）。
    """
    patterns = []
    blocks = re.split(r'###\s+VIDEO_PATTERN_\d+', md_text)

    for block in blocks[1:]:
        name_match = re.match(r'\s*「(.+?)」', block)
        name = name_match.group(1) if name_match else "パターン"

        # SLIDE_N: を区切りとして split
        slide_parts = re.split(r'\nSLIDE_(\d+):', block)
        # slide_parts = [pre, num, content, num, content, ...]

        slide_dict: dict[int, str] = {}
        for idx in range(1, len(slide_parts), 2):
            if idx + 1 < len(slide_parts):
                slide_num = int(slide_parts[idx])
                content = slide_parts[idx + 1]
                # パターン境界（---）か末尾で切る
                content = re.split(r'\n---', content)[0].strip()
                slide_dict[slide_num] = content

        if slide_dict and 1 in slide_dict:
            slides = [slide_dict.get(i, "") for i in range(1, 6)]
            patterns.append({"name": name, "slides": slides})

    return patterns


# ─────────────────────────────────────────────
# パーサー: 旧フォーマット TikTok5枚構成パターン
# ─────────────────────────────────────────────

def _parse_tiktok_patterns(md_text: str) -> list:
    """
    account_design.md の「TikTok動画構成」セクションからパターンを抽出。
    各パターン: {"name": str, "hook": str, "body_points": [str]}
    """
    patterns = []

    blocks = re.split(r'###\s+パターン\d+', md_text)

    for block in blocks[1:]:
        name_match = re.match(r'\s*「(.+?)」', block)
        name = name_match.group(1) if name_match else "パターン"

        code_match = re.search(r'```\n(.*?)```', block, re.DOTALL)
        if not code_match:
            continue
        code = code_match.group(1)

        hook = ""
        body_lines = []
        current_card = 0

        for line in code.splitlines():
            card_match = re.match(r'^(\d)枚[:：]\s*(.*)', line.strip())
            if card_match:
                current_card = int(card_match.group(1))
                content = card_match.group(2).strip()
                if current_card == 1:
                    inner = re.sub(r'[＼\\](.+?)[／/]', r'\1', content)
                    hook = inner if inner != content else content
                elif 2 <= current_card <= 4:
                    clean = re.sub(r'^[・□✕✓①②③④⑤\-◆▶]\s*', '', content).strip()
                    if clean:
                        body_lines.append(clean)
            else:
                stripped = line.strip()
                if stripped and 2 <= current_card <= 4:
                    clean = re.sub(r'^[・□✕✓①②③④⑤\-◆▶]\s*', '', stripped).strip()
                    if clean and not clean.startswith('#'):
                        body_lines.append(clean)

        if hook:
            patterns.append({
                "name": name,
                "hook": hook,
                "body_points": body_lines[:5],
            })

    return patterns


# ─────────────────────────────────────────────
# パーサー: 痛み語リスト
# ─────────────────────────────────────────────

def _parse_pain_words(md_text: str) -> list:
    """
    account_design.md の「痛み語リスト」コードブロックを抽出。
    "1.  上司が怖い" 形式をパース。
    """
    pain_words = []
    in_block = False

    for line in md_text.splitlines():
        if '痛み語リスト' in line:
            in_block = False
        if '```' in line:
            in_block = not in_block
            continue
        if in_block:
            m = re.match(r'\d+\.\s+(.+)', line.strip())
            if m:
                pain_words.append(m.group(1).strip())

    return pain_words


# ─────────────────────────────────────────────
# フック抽出: hook_generator.py 向け
# ─────────────────────────────────────────────

def load_hooks_for_account(account: str, knowledge_dir: Path) -> list:
    """
    account_design.md の各パターンの1枚目テキスト（hook）を一覧で返す。
    新フォーマットは SLIDE_1、旧フォーマットは 1枚目テキスト。
    """
    text = _load_text(knowledge_dir / account / "account_design.md")
    if not text:
        return []

    # 新フォーマット優先
    video_patterns = _parse_video_patterns(text)
    if video_patterns:
        return [p["slides"][0] for p in video_patterns if p["slides"][0]]

    # 旧フォーマットフォールバック
    patterns = _parse_tiktok_patterns(text)
    return [p["hook"] for p in patterns if p["hook"]]


# ─────────────────────────────────────────────
# メイン API: 今日のコンテンツを返す
# ─────────────────────────────────────────────

def pick_daily_content(account: str, knowledge_dir: Path, weekday: int) -> Optional[dict]:
    """
    account_design.md から今日の曜日に合ったコンテンツを返す。

    新フォーマット（VIDEO_PATTERN）が存在する場合:
        {"topic", "info", "hook_hint", "slides": [s1,s2,s3,s4,s5]}
        slides[0] = SLIDE_1 (フック)
        slides[1] = SLIDE_2 (共感)
        slides[2] = SLIDE_3 (整理)
        slides[3] = SLIDE_4 (選択肢)
        slides[4] = SLIDE_5 (CTA)

    旧フォーマットの場合:
        {"topic", "info", "hook_hint"}  ← slides キーなし
    """
    text = _load_text(knowledge_dir / account / "account_design.md")
    if not text:
        return None

    pain_words = _parse_pain_words(text)

    # ── 新フォーマット優先 ──────────────────────────
    video_patterns = _parse_video_patterns(text)
    if video_patterns:
        pattern = video_patterns[weekday % len(video_patterns)]
        slides = pattern["slides"]
        topic = pain_words[weekday % len(pain_words)] if pain_words else pattern["name"]

        return {
            "topic": topic,
            "info": "\n".join(s for s in slides[1:4] if s),  # 旧呼び出し元向けフォールバック
            "hook_hint": slides[0],
            "slides": slides,
        }

    # ── 旧フォーマットフォールバック ────────────────
    patterns = _parse_tiktok_patterns(text)
    if not patterns:
        return None

    pattern = patterns[weekday % len(patterns)]
    topic = pain_words[weekday % len(pain_words)] if pain_words else pattern["name"]

    if pattern["body_points"]:
        info = "\n".join(f"・{p}" for p in pattern["body_points"])
    else:
        info = f"・{topic}について詳しく解説\n・プロフィールリンクから詳細を確認"

    return {
        "topic": topic,
        "info": info,
        "hook_hint": pattern["hook"],
    }
