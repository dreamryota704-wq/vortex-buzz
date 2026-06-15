"""
Hook text generator for short videos.
Loads persona configs and winning hooks to produce engaging video hooks.
"""
import random
import re
from pathlib import Path
from typing import List, Optional

import yaml


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _fill_placeholders(template: str, topic: str, amount: str = "10万", days: str = "30日") -> str:
    """Fill common placeholders in a hook template string."""
    result = template
    result = result.replace("{topic}", topic)
    result = result.replace("{amount}", amount)
    result = result.replace("{days}", days)
    result = result.replace("{benefit}", f"{topic}で{amount}稼ぐ方法")
    return result


def _filter_avoid_words(text: str, avoid_words: List[str]) -> str:
    """Remove or replace words from the avoid list."""
    for word in avoid_words:
        text = text.replace(word, "")
    return text.strip()


# ---------------------------------------------------------------------------
# Hook templates per tone (fallback when no knowledge base file exists)
# ---------------------------------------------------------------------------

BUILTIN_HOOK_TEMPLATES = {
    "aggressive": [
        "【衝撃】{topic}で月{amount}稼ぐ方法、今すぐ教えます",
        "{topic}やらないと確実に損します【知らないと怖い】",
        "これを知らずに{topic}を始めると失敗します",
        "月{amount}稼いだ僕が{topic}の真実を暴露します",
        "【緊急】{topic}で稼げない人の共通点3つ",
        "99%の人が知らない{topic}の攻略法",
        "{topic}で失敗する人がやってる致命的なミス",
        "え、まだ{topic}やってないの？今すぐ見て",
        "【保存必須】{topic}で月{amount}への最短ルート",
        "これだけやれば{topic}で絶対に変わります",
    ],
    "friendly": [
        "ねえ、{topic}って実は簡単なの知ってた？",
        "{topic}で月{amount}稼いだ方法、こっそり教えちゃいます",
        "正直に言います、{topic}って○○すれば誰でもできます",
        "{topic}を始めて{days}後の変化がすごかった話",
        "友達に教えたら感謝された{topic}のコツ",
        "これ知ってたら{topic}もっと楽しくなるよ",
        "{topic}初心者が最初に絶対やるべきこと",
        "実は{topic}って難しくないんだよね〜",
        "{topic}でうまくいく人には共通点があります",
        "「{topic}って難しそう」と思ってるあなたへ",
    ],
    "empathy": [
        "仕事辞めたいのに言えない…そのまま続けますか？",
        "私も去年まで{topic}で毎日泣いてた",
        "もう限界かも…って思ったあの頃の自分に言いたいこと",
        "仕事に行きたくない朝、あなたは一人じゃないです",
        "「辞めたい」を言えない人に知ってほしいこと",
        "逃げることは悪いことじゃない、って誰かに言ってほしかった",
        "毎日しんどいのに「頑張れ」って言われても…",
        "あなたが今感じてる「限界」は本物です",
        "心が壊れる前に、知ってほしいことがあります",
        "職場のストレスで眠れてないあなたへ",
    ],
    "factual": [
        "{topic}の実態、数字で見ると驚きます",
        "知らないと損する{topic}の法律知識",
        "{topic}を利用した人の{days}後のデータ",
        "【データ公開】{topic}の成功率と失敗パターン",
        "{topic}に関する誤解、正しい情報をお伝えします",
        "{topic}の費用・流れ・注意点を3分で解説",
        "【完全解説】{topic}を使う前に知るべき5つのこと",
        "{topic}のリアルな口コミを集めてみた結果",
        "専門家が教える{topic}の正しい使い方",
        "{topic}のデメリットも正直に話します",
    ],
    "warm": [
        "二人で乗り越えた{topic}の話、聞いてください",
        "夫婦で経験した{topic}、あなたの参考になれば",
        "正直しんどかった。でも{topic}を選んで良かった理由",
        "私たちが{topic}について話し合った結果",
        "二人が{topic}を決めるまでの本音トーク",
        "夫婦で同じ悩みを抱えてた私たちの話",
        "二人で決めた選択を、後悔していません",
        "{topic}について彼と話したら予想外の展開に",
        "パートナーと一緒に乗り越えた経験談です",
        "二人のリアルな声、聞いてもらえますか",
    ],
    "curiosity": [
        "なぜ{topic}で稼げる人と稼げない人に分かれるのか",
        "{topic}の意外な真実、知ってますか？",
        "ほとんどの人が知らない{topic}の裏側",
        "プロが絶対に教えない{topic}の本当の方法",
        "え、{topic}ってこんなに簡単だったの？",
        "{topic}について調べたら衝撃の事実が出てきた",
        "実は{topic}って○○だったって知ってた？",
        "この事実を知ってから{topic}の見方が変わった",
        "「{topic}って怪しくないの？」に本気で答えます",
        "{topic}を3ヶ月やってみてわかったこと",
    ],
    "number_and_fact": [
        "月{amount}稼ぐために必要な{days}間の行動とは",
        "{topic}を始めた人の97%が知らない事実",
        "たった{days}で{amount}稼いだ{topic}の具体的な方法",
        "{topic}で稼げる人は何が違うのか、3つの数字で解説",
        "【実績公開】{topic}{days}の収益がこれ",
        "月{amount}稼いだ人が最初にやった3つのこと",
        "0円スタートで{days}後に{amount}になった話",
        "{topic}で稼げるまでの平均期間、知ってますか？",
        "月{amount}の壁を超えた人だけが知っている事実",
        "【数字公開】{topic}の正直なリターンはこれ",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_hook(
    account_name: str,
    topic: str,
    hook_tone: str,
    knowledge_base_path: Path,
    amount: str = "10万",
    days: str = "30日",
) -> str:
    """
    Generate a hook text for the given account and topic.

    Args:
        account_name: Account identifier (e.g. account_A)
        topic: Video topic keyword
        hook_tone: Tone style (aggressive, friendly, empathy, factual, warm, curiosity, number_and_fact)
        knowledge_base_path: Path to knowledge/{account}/ directory
        amount: Money amount placeholder value
        days: Days placeholder value

    Returns:
        Hook text string
    """
    persona = _load_yaml(knowledge_base_path / "persona.yaml")
    avoid_words = persona.get("avoid_words", [])
    hook_style = persona.get("hook_style", hook_tone)

    # Try to load winning hooks from knowledge base
    winning_hooks_text = _load_text(knowledge_base_path / "winning_hooks.md")
    winning_templates = []
    if winning_hooks_text:
        # Extract lines that look like templates (containing {topic} or similar)
        for line in winning_hooks_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-") and len(line) > 10:
                winning_templates.append(line)

    # Load templates file if it exists
    template_file_text = _load_text(knowledge_base_path / "templates" / "hook_templates.txt")
    file_templates = []
    if template_file_text:
        for line in template_file_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("//"):
                file_templates.append(line)

    # Also load shared tone-specific templates
    shared_dir = knowledge_base_path.parent.parent / "shared" / "templates"
    tone_file_map = {
        "aggressive": "hook_aggressive.txt",
        "friendly": "hook_friendly.txt",
        "curiosity": "hook_curious.txt",
        "empathy": "hook_empathy.txt",
        "factual": "hook_factual.txt",
        "warm": "hook_warm.txt",
        "number_and_fact": "hook_number.txt",
    }
    shared_tone_file = shared_dir / tone_file_map.get(hook_style, "hook_friendly.txt")
    shared_templates = []
    if shared_tone_file.exists():
        for line in _load_text(shared_tone_file).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                shared_templates.append(line)

    # Priority: winning_templates > file_templates > shared_templates > builtin
    candidate_pool = (
        winning_templates[:5]
        + file_templates[:10]
        + shared_templates[:10]
        + BUILTIN_HOOK_TEMPLATES.get(hook_style, BUILTIN_HOOK_TEMPLATES["friendly"])
    )

    if not candidate_pool:
        candidate_pool = BUILTIN_HOOK_TEMPLATES["friendly"]

    selected_template = random.choice(candidate_pool)
    hook_text = _fill_placeholders(selected_template, topic, amount, days)
    hook_text = _filter_avoid_words(hook_text, avoid_words)

    return hook_text


def generate_text_points(info_text: str) -> List[str]:
    """
    Parse the --info argument (newline-separated or ・-separated bullet points).

    Args:
        info_text: Raw info string, e.g. "・副業で月10万\n・初期費用0円"

    Returns:
        List of text point strings
    """
    points = []
    # Split by newline first
    raw_lines = info_text.replace("\\n", "\n").splitlines()
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        # Remove leading bullet characters
        line = re.sub(r"^[・•\-\*]\s*", "", line)
        if line:
            points.append(line)

    # If no newlines, try splitting by ・
    if len(points) <= 1 and "・" in info_text:
        parts = info_text.split("・")
        points = [p.strip() for p in parts if p.strip()]

    return points


def generate_cta(account_name: str, funnel_config: dict, cta_type: str) -> str:
    """
    Generate CTA text based on type (organic or conversion).

    Args:
        account_name: Account identifier
        funnel_config: Full funnels.yaml config dict (not just one funnel)
        cta_type: "organic" or "conversion"

    Returns:
        CTA text string
    """
    cta_rotation = funnel_config.get("cta_rotation", {})

    if cta_type == "organic":
        pool = cta_rotation.get("organic_cta_pool", [
            "👍 参考になったら保存して",
            "🔔 フォローして最新情報をゲット",
            "💬 コメントで教えて",
            "📌 後で見返したいなら保存がおすすめ",
        ])
        return random.choice(pool)

    elif cta_type == "conversion":
        conversion_cta = cta_rotation.get("conversion_cta", {})
        line1 = conversion_cta.get("line1", "詳しくはプロフィールのリンクから👆")
        line2 = conversion_cta.get("line2", "無料で確認できます")
        return f"{line1}\n{line2}"

    # Fallback
    return "詳しくはプロフィールのリンクから👆"
