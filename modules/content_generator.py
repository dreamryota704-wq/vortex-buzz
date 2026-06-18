"""
content_generator.py
Claude APIを使ってアカウントのペルソナに基づき毎回違う5枚スライドを生成する。
"""
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# .env を読み込む
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ─── ペルソナ設定（アカウント別）───────────────────────────────

PERSONA_MAP = {
    "account_A": {
        "name": "キャリア爆上げチャンネル",
        "character": "33歳・元大手メーカー勤務。転職2回で年収450万→730万。数字とロジックで話す断定的なスタイル。",
        "tone": "断定的・テンポが速い。「現実を言います」「これを知らないと損」「〜しないとヤバい」",
        "target": "年収が上がらない20〜40代・転職したいが動けない人",
        "theme": "転職・年収アップ・転職エージェント活用",
        "cta": "プロフィールのリンクから年収アップ転職ロードマップを確認してください",
    },
    "account_B": {
        "name": "退職・転職サポート局",
        "character": "28歳・元接客業。パワハラで退職代行を使い退職→IT企業に転職。共感重視・友達感覚。",
        "tone": "柔らかく温かい。「だよね」「わかるよ」「大丈夫だよ」「無理しないでね」",
        "target": "仕事辞めたいけど言えない20〜35歳",
        "theme": "退職代行・退職後の不安解消・転職の第一歩",
        "cta": "プロフィールのリンクから退職代行の比較・選び方を確認してみてね",
    },
    "taishoku_oa": {
        "name": "あかり｜退職日記",
        "character": "25歳・元IT企業OL。毎朝泣きながら出勤していたが退職代行で退職。感受性が高く自分の弱さをさらけ出せる。",
        "tone": "日記調・モノローグ。「正直に言うと」「あのころの私に教えてあげたい」「泣いてていいよ」",
        "target": "職場ストレスでボロボロになりかけている20代女性",
        "theme": "限界OLの体験談・退職代行・逃げていい許可",
        "cta": "プロフィールのリンクから退職前にやることリストを確認してみてね",
    },
    "taishoku_ob": {
        "name": "りょう｜退職代行の話",
        "character": "29歳・元製造業。残業月80時間・残業代未払い・パワハラから労組の退職代行で即日退職。感情より事実で話す。",
        "tone": "ロジカル・ファクトベース。「事実を言います」「実際どうだったか話します」「感情論より現実を見て」",
        "target": "ブラック企業にいる20〜30代男性",
        "theme": "退職代行の仕組み解説・ブラック企業脱出・残業代未払い",
        "cta": "プロフィールのリンクから退職代行の比較・費用を確認できます",
    },
    "taishoku_couple": {
        "name": "夫婦で退職した話",
        "character": "夫35歳(元営業・長時間労働)と妻32歳(元医療事務・育児と仕事の両立限界)が同時期に退職。子あり・ローンあり。",
        "tone": "夫婦掛け合い・本音ベース。「うちの場合は〜」「夫がさ〜」「二人で決めたこと」",
        "target": "共働き夫婦・子育て世代でどちらかが辞めたいと思っている30代",
        "theme": "夫婦での退職体験・家計リアル・子ありでも辞められた理由",
        "cta": "プロフィールのリンクから退職前の準備チェックリストを確認してみて",
    },
}

# ─── スライド生成プロンプト ───────────────────────────────────

def _build_prompt(persona: dict, pain_word: str, account: str = "") -> str:
    if account == "account_A":
        return _build_prompt_career(persona, pain_word)
    return _build_prompt_taishoku(persona, pain_word)


def _build_prompt_career(persona: dict, pain_word: str) -> str:
    """account_A（転職・年収アップ系）向けプロンプト"""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ】{pain_word}

【出力形式】必ず以下の形式のみ出力。余計な説明は不要。

SLIDE_1:
（フック：2〜3行。「＼〜／」形式か断定一文。視聴者が「自分のことだ」と止まる言葉）

SLIDE_2:
（現実・問題提起ヘッダー1行）

・（現実・事実1）
・（現実・事実2）
・（現実・事実3）

（コメンタリー1〜2行：「あなたのせいじゃない」「会社の構造の問題」のような締め）

SLIDE_3:
（データ・根拠ヘッダー1行）

・（数字や事実1）
・（数字や事実2）
・（数字や事実3）

SLIDE_4:
（解決策・アクションヘッダー1行）

・（今すぐできること1）
・（今すぐできること2）
・（今すぐできること3）

（コメンタリー1〜2行：行動を後押しする一言）

SLIDE_5:
（視聴者を励ます1〜2行。「動こうとしているあなたは正しい」「変われる」などポジティブな一言）
（フォロー促進CTA：「毎日〜を発信中」「フォローして一緒に〜」の形式で）

【重要なルール】
・✅ ① → ■ などの記号は絶対に使わない。箇条書きは・（中点）のみ
・各グループは空行で区切る
・ペルソナの口調を徹底する（断定的・テンポ速め・数字とロジック重視）
・SLIDE_1〜SLIDE_5 のラベルのみ出力
"""


def _build_prompt_taishoku(persona: dict, pain_word: str) -> str:
    """退職代行系アカウント向けプロンプト"""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}

【出力形式】必ず以下の形式のみ出力。余計な説明は不要。

SLIDE_1:
（フック：2〜3行。視聴者が「自分のことだ」と止まる言葉）

SLIDE_2:
（共感ヘッダー1行）

・（共感ポイント1）
・（共感ポイント2）
・（共感ポイント3）

（コメンタリー1〜2行：「弱いんじゃない」「環境がおかしいだけ」のような締め）

SLIDE_3:
（整理・解決ヘッダー1行）

・（アクション1）
・（アクション2）
・（アクション3）

（コメンタリー1〜2行：行動を後押しする一言）

SLIDE_4:
（選択肢ヘッダー1行）

民間  → （特徴・向いている人）
労組  → （特徴・向いている人）
弁護士 → （特徴・向いている人）

（コメンタリー1〜2行：選び方のポイント）

SLIDE_5:
（視聴者を励ます1〜2行。「逃げることは正しい」「あなたは一人じゃない」などポジティブな一言）
（フォロー促進CTA：「毎日〜を発信中」「フォローして一緒に〜」の形式で）

【重要なルール】
・✅ ① → ■ などの記号は絶対に使わない。箇条書きは・（中点）のみ
・各グループは空行で区切る
・ペルソナの口調を徹底する
・SLIDE_1〜SLIDE_5 のラベルのみ出力
"""

# ─── Claude API 呼び出し ─────────────────────────────────────

def generate_slides_with_claude(account: str, pain_word: str) -> list:
    """
    Claude APIでペルソナに基づいた5枚スライドを生成して返す。
    Returns: [slide1_text, slide2_text, slide3_text, slide4_text, slide5_text]
    """
    persona = PERSONA_MAP.get(account)
    if not persona:
        logger.warning(f"[content_generator] ペルソナ未定義: {account}")
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[content_generator] ANTHROPIC_API_KEY が設定されていません")
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = _build_prompt(persona, pain_word, account=account)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # 速くて安い
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        logger.info(f"[content_generator] Claude生成完了: {account} / {pain_word}")

        return _parse_slides(raw)

    except Exception as e:
        logger.error(f"[content_generator] Claude APIエラー: {e}")
        return []


def _parse_slides(raw: str) -> list:
    """Claude出力からSLIDE_1〜SLIDE_5を抽出してリストで返す。"""
    # 行頭・文中どちらでも SLIDE_N: を検出
    parts = re.split(r'(?:^|\n)SLIDE_(\d+):', raw)
    # parts = [before, num, content, num, content, ...]

    slide_dict: dict = {}
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            num = int(parts[i])
            content = parts[i + 1].strip()
            slide_dict[num] = content

    slides = [slide_dict.get(n, "") for n in range(1, 6)]
    return slides if any(slides) else []
