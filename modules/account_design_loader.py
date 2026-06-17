"""
account_design_loader.py
account_design.md を解析して毎日の動画コンテンツ（hook・body・topic）を返す。
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
# パーサー: TikTok5枚構成パターン
# ─────────────────────────────────────────────

def _parse_tiktok_patterns(md_text: str) -> list:
    """
    account_design.md の「TikTok動画構成」セクションからパターンを抽出。
    各パターン: {"name": str, "hook": str, "body_points": [str]}
    """
    patterns = []

    # ### パターンN「...」 で区切る
    blocks = re.split(r'###\s+パターン\d+', md_text)

    for block in blocks[1:]:
        # パターン名
        name_match = re.match(r'\s*「(.+?)」', block)
        name = name_match.group(1) if name_match else "パターン"

        # ```...``` ブロックを取得
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
                    # ＼...／ を除去して純粋なテキストを取り出す
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
            in_block = False  # 次の```を待つ
        if '```' in line:
            in_block = not in_block
            continue
        if in_block:
            m = re.match(r'\d+\.\s+(.+)', line.strip())
            if m:
                pain_words.append(m.group(1).strip())

    return pain_words


# ─────────────────────────────────────────────
# フック抽出: hook_templates.txt 代替として使える1枚目テキスト
# ─────────────────────────────────────────────

def load_hooks_for_account(account: str, knowledge_dir: Path) -> list:
    """
    account_design.md の各パターンの1枚目テキスト（hook）を一覧で返す。
    hook_generator.py の候補プールに追加される。
    """
    text = _load_text(knowledge_dir / account / "account_design.md")
    if not text:
        return []
    patterns = _parse_tiktok_patterns(text)
    return [p["hook"] for p in patterns if p["hook"]]


# ─────────────────────────────────────────────
# メイン API: 今日のコンテンツを返す
# ─────────────────────────────────────────────

def pick_daily_content(account: str, knowledge_dir: Path, weekday: int) -> Optional[dict]:
    """
    account_design.md から今日の曜日に合ったコンテンツを返す。

    Returns:
        {"topic": str, "info": str, "hook_hint": str} or None
        - topic    : 痛み語（TikTokトピックキーワード）
        - info     : 「・〇〇\n・〇〇」形式のボディテキスト
        - hook_hint: 1枚目フックの参考テキスト（hook_generatorが使う）
    """
    text = _load_text(knowledge_dir / account / "account_design.md")
    if not text:
        return None

    patterns = _parse_tiktok_patterns(text)
    pain_words = _parse_pain_words(text)

    if not patterns:
        return None

    # 曜日でパターンをローテーション（5パターン → 7曜日をmod）
    pattern = patterns[weekday % len(patterns)]

    # トピック: 痛み語リストから曜日ローテーション
    if pain_words:
        topic = pain_words[weekday % len(pain_words)]
    else:
        topic = pattern["name"]

    # ボディテキスト: パターンのbody_pointsを「・」形式に
    if pattern["body_points"]:
        info = "\n".join(f"・{p}" for p in pattern["body_points"])
    else:
        info = f"・{topic}について詳しく解説\n・プロフィールリンクから詳細を確認"

    return {
        "topic": topic,
        "info": info,
        "hook_hint": pattern["hook"],
    }
