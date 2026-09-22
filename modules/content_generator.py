"""
content_generator.py
Claude APIを使ってアカウントのペルソナに基づき毎回違う5枚スライドを生成する。
"""
import os
import re
import hashlib
import logging
from datetime import datetime
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
        "character": "33歳男性・元大手メーカー勤務。転職2回で年収450万→730万に上げた。感情より数字とロジックで話す。同じ悩みでも「年収・市場価値・転職戦略」の角度で切る。",
        "tone": "断定的・テンポが速い。「現実を言います」「これを知らないと損」「〜しないとヤバい」。他の人が共感で語るところをデータで語る。",
        "target": "年収が上がらない20〜40代・転職したいが動けない人",
        "theme": "転職・年収アップ・転職エージェント活用",
        "cta": "プロフィールのリンクから年収アップ転職ロードマップを確認してください",
        "unique_angle": "どんなテーマでも「年収・転職・市場価値」の視点に変換して語る。感情的な共感はしない。",
    },
    "account_B": {
        "name": "退職・転職サポート局",
        "character": "28歳女性・元接客業。パワハラで退職代行を使って退職→IT企業に転職成功。同じ悩みでも「あなたは悪くない・一緒に考えよう」の友達目線で語る。",
        "tone": "柔らかく温かい。「だよね」「わかるよ」「大丈夫だよ」「無理しないでね」。寄り添い系で優しく背中を押す。",
        "target": "仕事辞めたいけど言えない20〜35歳",
        "theme": "退職代行・退職後の不安解消・転職の第一歩",
        "cta": "プロフィールのリンクから退職代行の比較・選び方を確認してみてね",
        "unique_angle": "どんなテーマでも「あなたは一人じゃない・私も同じだった」の共感から入る。友達に話すような柔らかい言葉で。",
    },
    "taishoku_oa": {
        "name": "あかり｜退職日記",
        "character": "25歳女性・元IT企業OL。毎朝泣きながら出勤していたが退職代行で退職。自分の弱さと感情をそのままさらけ出す日記スタイル。",
        "tone": "日記調・モノローグ。「正直に言うと」「あのころの私に教えてあげたい」「泣いてていいよ」「私もそうだった」。",
        "target": "職場ストレスでボロボロになりかけている20代女性",
        "theme": "限界OLの体験談・退職代行・逃げていい許可",
        "cta": "プロフィールのリンクから退職前にやることリストを確認してみてね",
        "unique_angle": "どんなテーマでも自分の実体験・感情を日記のように語る。「私が〜だったとき」「あのとき気づいたこと」の一人称で。",
    },
    "taishoku_ob": {
        "name": "りょう｜退職代行の話",
        "character": "29歳男性・元製造業。残業月80時間・残業代未払い・パワハラを経験し労組の退職代行で即日退職。感情ではなく事実と仕組みで語る。",
        "tone": "ロジカル・ファクトベース。「事実を言います」「実際どうだったか話します」「感情論より現実を見て」。冷静で淡々とした語り口。",
        "target": "ブラック企業にいる20〜30代男性",
        "theme": "退職代行の仕組み解説・ブラック企業脱出・残業代未払い",
        "cta": "プロフィールのリンクから退職代行の比較・費用を確認できます",
        "unique_angle": "どんなテーマでも「法的事実・仕組み・具体的な手順」で語る。感情的な言葉は使わず、男性が納得できる現実ベースで。",
    },
    "career_young": {
        "name": "たくや｜20代転職リアル",
        "character": "25歳男性・元メーカー勤務。手取り18万・地方転勤辞令で限界→転職エージェント活用→3ヶ月でホワイト転職成功。年収350万→720万（２倍以上）に上昇。同世代に等身大の本音で語る。",
        "tone": "等身大・本音ベース。「俺も同じだった」「正直に言う」「20代のうちに動かないと後悔する」。説教くさくなく、友達目線で数字と実体験を組み合わせる。",
        "target": "低年収・地方転勤・ブラック環境で悩む20代男性",
        "theme": "20代の転職・年収アップ・転職エージェント活用・ホワイト転職・非公開求人",
        "cta": "20代限定のキャリア相談↓プロフリンクから非公開求人・優遇ルートあるよ",
        "unique_angle": "どんなテーマでも「手取り18万だったころの俺」「地方転勤辞令から逃げた25歳」の視点から語る。同世代の友達が話すような等身大の言葉で、数字と実体験を必ず入れる。",
    },
    "taishoku_couple": {
        "name": "夫婦で退職した話",
        "character": "夫35歳(元営業・長時間労働)と妻32歳(元医療事務・育児と仕事の両立が限界)が同時期に退職。子あり・住宅ローンあり。二人の視点で語る。",
        "tone": "夫婦掛け合い・本音ベース。「うちの場合は〜」「夫がさ〜」「二人で決めたこと」「子どもがいても辞められた」。",
        "target": "共働き夫婦・子育て世代でどちらかが辞めたいと思っている30代",
        "theme": "夫婦での退職体験・家計リアル・子ありでも辞められた理由",
        "cta": "プロフィールのリンクから退職前の準備チェックリストを確認してみて",
        "unique_angle": "どんなテーマでも「夫婦二人の視点」「子あり・ローンありの現実」から語る。片方だけでなく夫婦両方の気持ちを入れる。",
    },
    "chatlady_yui": {
        "name": "ゆい｜在宅のお仕事日記",
        "character": "23歳女性・元アパレル/飲食のフリーター。掛け持ちバイトで収入が不安定だったが、チャットレディの仕事に出会い、事務所のサポートで収入も生活も安定した。",
        "tone": "日記調・共感ベース。「正直に言うと」「あのころの私と同じ人へ」「特別なことは何もしてない」。素朴で飾らない語り口。煽りすぎない。",
        "target": "シフト制バイトで収入が不安定な20代女性・在宅の仕事に興味があるが不安な人",
        "theme": "チャットレディ・在宅の仕事・事務所サポート・収入の安定",
        "cta": "LINEで話だけ聞いてみて。詳細はプロフィールのリンクから",
        "unique_angle": "どんなテーマでも「収入が不安定だった頃の自分」「事務所に入ってからの安心感（レスポンスの速さ・入金の安心感）」の実体験から語る。時々「稼げるようになって手に入った生活」の具体描写も入れて憧れを作るが、金額の連呼はしない。",
    },
    "chatlady_miku": {
        "name": "みく｜シンママの在宅仕事日記",
        "character": "28歳女性・シングルマザー（子ども1人）。パート収入だけで生活していたが、チャットレディの仕事に出会い、事務所のサポートで子どもとの時間を守りながら収入が安定した。",
        "tone": "日記調・共感ベース。「正直、綺麗事だけじゃやっていけなかった」「子どものために」「同じシンママの人へ」。しっかり者だが本音も見せる。煽りすぎない。",
        "target": "シングルマザーで子どもとの時間を大切にしながら収入を安定させたい20〜30代女性",
        "theme": "チャットレディ・在宅の仕事・事務所サポート・シングルマザーの生活安定",
        "cta": "LINEで話だけ聞いてみて。詳細はプロフィールのリンクから",
        "unique_angle": "どんなテーマでも「パート収入だけで不安だった頃の自分」「子どもとの時間を守りながら事務所のサポート（レスポンスの速さ・入金の安心感）を受けている今」の実体験から語る。学校行事・保育園のお迎え・急な出費など子育て特有の具体名詞を必ず入れる。時々「子どもに我慢させなくなった生活」の具体描写も入れる。",
    },
    "chatlady_marina": {
        "name": "まりな｜主婦の在宅お小遣い稼ぎ日記",
        "character": "34歳女性・専業主婦。夫の収入だけでは教育費・将来が不安だったが、チャットレディの仕事に出会い、事務所のサポートで家計にゆとりが出た。",
        "tone": "日記調・共感ベース。「正直、旦那には言えなかったけど」「主婦の本音を言うと」「同じ主婦の人へ」。落ち着いた現実派。煽りすぎない。",
        "target": "パート収入だけでは生活が苦しい、家事育児と両立できる在宅の仕事を探している30〜40代主婦",
        "theme": "チャットレディ・在宅の仕事・事務所サポート・家計の安定",
        "cta": "LINEで話だけ聞いてみて。詳細はプロフィールのリンクから",
        "unique_angle": "どんなテーマでも「夫の収入だけで不安だった頃の自分」「家計にゆとりができた今の事務所のサポート（レスポンスの速さ・入金の安心感）」の実体験から語る。家計簿・教育費・パートとの両立など主婦特有の具体名詞を必ず入れる。時々「家計に我慢がなくなった生活」の具体描写も入れる。",
    },
}

# ─── スライド生成プロンプト ───────────────────────────────────

def _build_prompt(persona: dict, pain_word: str, account: str = "", hook_hint: str = "") -> str:
    if account == "account_A":
        return _build_prompt_career(persona, pain_word, hook_hint)
    if account == "taishoku_ob":
        return _build_prompt_taishoku_ob(persona, pain_word, hook_hint)
    if account == "account_B":
        return _build_prompt_account_b(persona, pain_word, hook_hint)
    if account == "taishoku_oa":
        return _build_prompt_taishoku_oa(persona, pain_word, hook_hint)
    if account == "taishoku_couple":
        return _build_prompt_taishoku_couple(persona, pain_word, hook_hint)
    if account == "career_young":
        return _build_prompt_career_young(persona, pain_word, hook_hint)
    if account == "chatlady_yui":
        return _build_prompt_chatlady_yui(persona, pain_word, hook_hint)
    if account == "chatlady_miku":
        return _build_prompt_chatlady_miku(persona, pain_word, hook_hint)
    if account == "chatlady_marina":
        return _build_prompt_chatlady_marina(persona, pain_word, hook_hint)
    return _build_prompt_taishoku(persona, pain_word, hook_hint)


def _unique_angle_line(persona: dict) -> str:
    angle = persona.get("unique_angle", "")
    return f"【このアカウント固有の切り口】{angle}" if angle else ""


def _pick_shared_hook(account: str, iteration: int = 0) -> str:
    """共通フックリストから日時+アカウント+iterationのシードでランダムに1つ選ぶ。"""
    path = Path(__file__).parent.parent / "knowledge" / "shared" / "hooks_strong.md"
    if not path.exists():
        return ""
    hooks = [
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("##")
    ]
    if not hooks:
        return ""
    seed_str = f"{datetime.now().strftime('%Y-%m-%d')}-{account}-hook-{iteration}"
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return hooks[h % len(hooks)]


def _build_prompt_career(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """account_A（転職・年収アップ系）向けプロンプト"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナとテーマで、5枚スライド動画のテキストを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【今日のテーマ】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【参考フォーマット（このスタイルで生成すること）】

SLIDE_1:
＼転職で年収が上がった人の現実／

SLIDE_2:
転職者の平均アップ額：約67万円
転職1回目の成功率：約68%
エージェント利用者の内定率：非利用者の約2倍

SLIDE_3:
転職しない人の現実
・同じ会社に3年いると市場価値が下がりはじめる
・40代になると転職先の選択肢が減る

SLIDE_4:
動くなら早い方がいい
今すぐできること：無料でエージェントに登録する

SLIDE_5:
数字は嘘をつかない
動いた人だけが現実を変えられます
転職のリアルを毎日発信中
フォローして一緒に変わっていこう

---

【出力ルール】
・上の参考フォーマットと同じ長さ・構成で、今日のテーマに合わせた内容を作る
・SLIDE_1：「＼〜／」形式の短いフック1行
・SLIDE_2：数字・データを3行並べる（ヘッダーなし or 1行ヘッダー）
・SLIDE_3：ヘッダー1行＋・箇条書き2〜3行
・SLIDE_4：ヘッダー1行＋アクション1〜2行（短く）
・SLIDE_5：視聴者を励ます1〜2行 ＋「毎日〜発信中 / フォローして〜」形式のCTA
・✅ ① → ■ などの記号は使わない。箇条書きは・のみ
・余計な説明・コメントは不要。テキストのみ出力

【最重要】このアカウントのペルソナ（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_taishoku_ob(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """taishoku_ob（ロジカル男性・ファクトベース）向けプロンプト — SLIDE_1は＼〜／形式"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【参考フォーマット（このスタイルで生成すること）】

SLIDE_1:
＼退職届を受け取らない会社の話／

SLIDE_2:
法律上、退職は2週間前に申告すれば成立します。
・会社が拒否しても退職は有効
・退職届を受け取らないのは違法行為
・強引に引き止めるのもハラスメント

SLIDE_3:
それでも辞められないなら

・退職代行サービスを使う
・内容証明郵便で退職届を送る
・労働基準監督署に相談する

SLIDE_4:
退職代行の選び方

民間  → 費用安い・交渉不可
労組  → 団体交渉できる・残業代請求も可
弁護士 → 法的トラブルにも対応・費用高め

SLIDE_5:
事実を知れば、逃げ道は必ずある
同じ悩みを持つ人へ毎日情報を発信中
フォローして一緒に抜け出そう

---

【出力ルール】
・SLIDE_1：必ず「＼〜／」形式の1行フック。テーマに沿った断定的な一言
・SLIDE_2：事実・法律・データを箇条書き（・のみ使用）
・SLIDE_3：具体的な行動リスト
・SLIDE_4：選択肢の比較（民間/労組/弁護士）
・SLIDE_5：視聴者を励ます1〜2行 ＋ フォローCTA
・✅ ① → ■ などの記号は絶対使わない。・のみ
・SLIDE_1〜SLIDE_5 のラベルのみ出力

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_account_b(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """account_B（共感・呼びかけ診断系）向けプロンプト — SLIDE_1は「〜な人、正直に言っていい？」形式"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【参考フォーマット（このスタイルで生成すること）】

SLIDE_1:
毎朝仕事行くの怖い人、正直に言っていい？

SLIDE_2:
それ、あなたが弱いんじゃないよ

・怖くて当然の環境にいるだけ
・真面目な人ほど限界まで我慢する
・SOSを出せないのも、普通のこと

弱くて辞めたいんじゃなくて、もう十分頑張ったんだよ。

SLIDE_3:
だから、こうしてみて

・まず誰かに話すだけでいい
・退職代行という選択肢があることを知っておく
・「辞めたい」と思うこと自体は正常なサイン

一歩だけ、踏み出してみよう。

SLIDE_4:
退職代行、どれを使えばいい？

民間  → 費用が安め・気軽に使える
労組  → 未払い給与や有休の交渉もできる
弁護士 → トラブルがある場合はここ一択

迷ったら労組がバランスいいよ。

SLIDE_5:
あなたは一人じゃないよ。
辞めたいって思うのは、逃げじゃなくて選択だから。
退職・転職のリアルを毎日発信中。
フォローして一緒に前に進もう。

---

【出力ルール】
・SLIDE_1：「〇〇な人、正直に言っていい？」「〇〇な人いる？」「〇〇でしょ？」など、視聴者に呼びかける1行
・友達に話しかけるような温かい口調を徹底する
・SLIDE_2：共感ヘッダー＋・箇条書き＋コメンタリー
・SLIDE_3：やさしい解決策リスト
・SLIDE_4：退職代行の選び方（友達目線）
・SLIDE_5：励まし1〜2行＋フォローCTA
・✅ ① → ■ などの記号は使わない。箇条書きは・のみ
・SLIDE_1〜SLIDE_5のラベルのみ出力

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_taishoku_oa(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """taishoku_oa（体験告白・日記系）向けプロンプト — SLIDE_1は「私も〇〇だった。」形式"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【参考フォーマット（このスタイルで生成すること）】

SLIDE_1:
私も毎朝泣きながら出勤してた。

SLIDE_2:
正直に言うと、あのころの私はもう限界だった

・シャワー浴びながら泣いてた
・日曜の夜が怖くてたまらなかった
・「辞めたい」を言えなくて、ひとりで抱えてた

弱いんじゃなくて、もう限界だったんだよ。

SLIDE_3:
あのとき私がやったこと

・とにかく「退職代行」を調べてみた
・使う使わないより、選択肢があることを知った
・勇気を出して、一本電話した

それだけで、息ができるようになった気がした。

SLIDE_4:
あの私に教えてあげたいこと

・退職は権利。会社に許可はいらない
・退職代行を使えば自分で言わなくていい
・辞めた後、後悔はゼロだった

SLIDE_5:
今の私から、あのころの私へ。
逃げていいよ。それが正解だったから。
限界OLのリアルを毎日発信してます。
フォローして、一緒に抜け出そう。

---

【出力ルール】
・SLIDE_1：次のどちらかの型で1行
  A) 一人称・過去形の体験告白「私も〇〇だった。」「退職代行を使った日の朝の話。」
  B) 視聴者の不安をそのまま疑問形に「退職代行って次の職場にバレる？」→本文で体験談として回答
・日記調・モノローグで書く。感情をそのまま出す
・SLIDE_2：「あのころ」の感情・状況を・箇条書きで。生活の具体名詞（終電・コンビニ・日曜21時・シャワー・上司からのLINEなど）を必ず1つ入れる
・SLIDE_3：「私がやったこと」を具体的に。可能なら会話再現を1つ入れる（例:「もう出社しなくて大丈夫ですよ」って言われた）
・SLIDE_4：「今だから言える」気づき・事実
・SLIDE_5：「今の私から昔の私へ」的な励まし＋フォローCTA
・✅ ① → ■ などの記号は使わない。箇条書きは・のみ
・SLIDE_1〜SLIDE_5のラベルのみ出力

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_chatlady_yui(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """chatlady_yui（チャットレディ募集・共感体験談系）向けプロンプト"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【動画の構造】1スライド＝約4秒のクリップ1本に対応する。1スライド内で表示するテキストは1行のみ・20〜30文字程度に収めること（長文・箇条書き・複数行は厳禁。画面内で文字が重なって表示が崩れる）。

【最重要: SLIDE_1はインパクト最優先】
曖昧な感想文（「〜だった」「〜な人へ」だけ）では弱い。属性＋変化（ビフォーアフター）を断定的に言い切り、
結果を先に見せて興味を引く。例:「チャットレディで人生変わった20代の話」「収入ゼロだった私がここまで変わった話」
のように、具体的で言い切り型のフックにすること。

【参考フォーマット（このスタイルで生成すること。文字数を厳守）】

SLIDE_1:
チャットレディで人生変わった20代の話

SLIDE_2:
シフト制バイトで収入が全然安定しなかった

SLIDE_3:
未経験だったけど事務所のサポートで始められた

SLIDE_4:
レスポンスの速さと入金の安心感がすごい

SLIDE_5:
気になる人はLINEで話だけ聞いてみて

---

【出力ルール】
・各SLIDEは必ず1行・20〜30文字程度。改行・箇条書き（・）・複数文は禁止
・SLIDE_1：属性＋変化を断定的に言い切る一言（上記の最重要ルール参照）。ターゲット（収入が不安定・将来が不安な20代女性）に直接刺さる言葉を選ぶ
・SLIDE_2：ターゲットが「これ私だ」と思う具体的な痛みを一言で言い切る。通帳・シフト表・LINE通知など生活の具体名詞を入れてよい
・SLIDE_3：「私がやったこと」または心境の変化を一言で
・SLIDE_4：事務所に入って良かったこと（レスポンスの速さ・入金の安心感・サポート体制）を一言で。たまに「憧れの未来・ライフスタイル」（時間の自由・美容・推し活・旅行など）の一言に差し替えてもよい
・SLIDE_5：LINE誘導のCTA一言。「LINEで話だけ聞いてみて」のような低ハードルな言い回しを基本にする
・日記調の弱さより、言い切り型の説得力を優先する。ただし断定・保証表現（絶対稼げる等）は使わない
・「チャットレディ」という職種名は明示してよいが、露骨な収入煽り・性的示唆表現は避ける
・✅ ① → ■ などの記号は使わない
・SLIDE_1〜SLIDE_5のラベルのみ出力、それぞれ1行のみ

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_chatlady_miku(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """chatlady_miku（チャットレディ募集・シングルマザー系）向けプロンプト"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【動画の構造】1スライド＝約4秒のクリップ1本に対応する。1スライド内で表示するテキストは1行のみ・20〜30文字程度に収めること（長文・箇条書き・複数行は厳禁。画面内で文字が重なって表示が崩れる）。

【最重要: SLIDE_1はインパクト最優先】
曖昧な感想文では弱い。属性＋変化（ビフォーアフター）を断定的に言い切り、結果を先に見せて興味を引く。
例:「シングルマザーの私がチャットレディで生活を立て直した話」のように、具体的で言い切り型のフックにすること。

【参考フォーマット（このスタイルで生成すること。文字数を厳守）】

SLIDE_1:
シングルマザーの私がチャットレディで生活を立て直した話

SLIDE_2:
パート収入だけじゃ学校行事のたび出費が怖かった

SLIDE_3:
未経験だったけど事務所のサポートで始められた

SLIDE_4:
レスポンスの速さと入金の安心感がすごい

SLIDE_5:
気になる人はLINEで話だけ聞いてみて

---

【出力ルール】
・各SLIDEは必ず1行・20〜30文字程度。改行・箇条書き（・）・複数文は禁止
・SLIDE_1：属性＋変化を断定的に言い切る一言（上記の最重要ルール参照）。ターゲット（シングルマザーで収入・時間の両立に悩む女性）に直接刺さる言葉を選ぶ
・SLIDE_2：ターゲットが「これ私だ」と思う具体的な痛みを一言で言い切る。学校行事・保育園のお迎え・急な出費など子育て特有の具体名詞を入れてよい
・SLIDE_3：「私がやったこと」または心境の変化を一言で
・SLIDE_4：事務所に入って良かったこと（レスポンスの速さ・入金の安心感・サポート体制）を一言で。たまに「子どもに我慢させなくなった生活」の一言に差し替えてもよい
・SLIDE_5：LINE誘導のCTA一言。「LINEで話だけ聞いてみて」のような低ハードルな言い回しを基本にする
・日記調の弱さより、言い切り型の説得力を優先する。ただし断定・保証表現（絶対稼げる等）は使わない
・「チャットレディ」という職種名は明示してよいが、露骨な収入煽り・性的示唆表現は避ける
・✅ ① → ■ などの記号は使わない
・SLIDE_1〜SLIDE_5のラベルのみ出力、それぞれ1行のみ

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_chatlady_marina(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """chatlady_marina（チャットレディ募集・主婦系）向けプロンプト"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【動画の構造】1スライド＝約4秒のクリップ1本に対応する。1スライド内で表示するテキストは1行のみ・20〜30文字程度に収めること（長文・箇条書き・複数行は厳禁。画面内で文字が重なって表示が崩れる）。

【最重要: SLIDE_1はインパクト最優先】
曖昧な感想文では弱い。属性＋変化（ビフォーアフター）を断定的に言い切り、結果を先に見せて興味を引く。
例:「専業主婦の私がチャットレディで家計を助けた話」のように、具体的で言い切り型のフックにすること。

【参考フォーマット（このスタイルで生成すること。文字数を厳守）】

SLIDE_1:
専業主婦の私がチャットレディで家計を助けた話

SLIDE_2:
家計簿を見るたびにため息が出てた

SLIDE_3:
未経験だったけど事務所のサポートで始められた

SLIDE_4:
レスポンスの速さと入金の安心感がすごい

SLIDE_5:
気になる人はLINEで話だけ聞いてみて

---

【出力ルール】
・各SLIDEは必ず1行・20〜30文字程度。改行・箇条書き（・）・複数文は禁止
・SLIDE_1：属性＋変化を断定的に言い切る一言（上記の最重要ルール参照）。ターゲット（家計不安・パートとの両立に悩む主婦）に直接刺さる言葉を選ぶ
・SLIDE_2：ターゲットが「これ私だ」と思う具体的な痛みを一言で言い切る。家計簿・教育費・夫に言えないお金の不安など主婦特有の具体名詞を入れてよい
・SLIDE_3：「私がやったこと」または心境の変化を一言で
・SLIDE_4：事務所に入って良かったこと（レスポンスの速さ・入金の安心感・サポート体制）を一言で。たまに「家計に我慢がなくなった生活」の一言に差し替えてもよい
・SLIDE_5：LINE誘導のCTA一言。「LINEで話だけ聞いてみて」のような低ハードルな言い回しを基本にする
・日記調の弱さより、言い切り型の説得力を優先する。ただし断定・保証表現（絶対稼げる等）は使わない
・「チャットレディ」という職種名は明示してよいが、露骨な収入煽り・性的示唆表現は避ける
・✅ ① → ■ などの記号は使わない
・SLIDE_1〜SLIDE_5のラベルのみ出力、それぞれ1行のみ

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_taishoku_couple(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """taishoku_couple（夫婦・状況共鳴系）向けプロンプト — SLIDE_1は「〜なの、うちだけ？」形式"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【参考フォーマット（このスタイルで生成すること）】

SLIDE_1:
子どもいて辞めたい、これうちだけ？

SLIDE_2:
うちの場合、夫婦でこう話し合った

・「辞めたい」を言い出せずに3ヶ月我慢してた
・子どもとローンがあって踏み出せなかった
・でも実際は、夫も同じこと考えてた

「言えてよかった」がスタートだった。

SLIDE_3:
夫婦で決めたこと

・生活費の最低ラインを二人で計算した
・退職後3ヶ月の貯金があれば動ける
・退職代行を使えば、もめずに辞められる

二人で決めたら、こんなにシンプルだった。

SLIDE_4:
退職後のリアルな数字

・夫の退職後、生活費は月-3万に抑えた
・妻のパート収入で繋ぎながら転職活動
・6ヶ月で夫の収入は元に戻った

子どもいても、ローンあっても、なんとかなった。

SLIDE_5:
うちだけじゃなかった、あなたもきっと同じ。
子どもいてもローンあっても、辞めた夫婦のリアルを発信中。
フォローして、一緒に前に進もう。

---

【出力ルール】
・SLIDE_1：「〇〇なの、うちだけ？」「〇〇なのって、うちだけじゃないよね？」「〇〇って言いづらいよね」など、夫婦の状況に共鳴する1行
・夫婦掛け合い・本音ベースの口調で書く（「うちの場合」「夫がさ」「二人で〜」）
・SLIDE_2：「うちの場合」の実情を・箇条書きで
・SLIDE_3：「夫婦で決めたこと・やったこと」
・SLIDE_4：退職後のリアルな数字・現実
・SLIDE_5：「うちだけじゃない」系の励まし＋フォローCTA
・✅ ① → ■ などの記号は使わない。箇条書きは・のみ
・SLIDE_1〜SLIDE_5のラベルのみ出力

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""


def _build_prompt_career_young(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """career_young — 体験談Vlog風・会話テロップ（6スライド・25秒構成）"""
    return f"""あなたはTikTok動画のテロップライターです。
25歳の転職体験を語る縦型動画（約25秒・6スライド）のテロップを書いてください。

【キャラクター】{persona['character']}
【今日のテーマ】{pain_word}

【構成の型（6スライド）】
①失敗告白 → ②苦労・状況 → ③数字で苦労感 → ④解決策（口コミ風） → ⑤成果（数字） → ⑥対比オチ＋CTA

【絶対ルール】
・1スライド＝1〜2行（3行厳禁）
・1行＝最大13文字（短くテンポよく）
・1スライドの合計文字数＝24文字以内（4秒で読める量）
・会話口調（正直 / 実は / 〜しちゃった / 〜なんですよ）
・箇条書き（・）は使わない
・広告っぽい言葉は使わない
・年収は必ず「350万→720万」で表現する

【参考テンプレ（この短さ・テイストで）】

SLIDE_1:
手取り18万で転勤辞令来て
正直終わったと思いました

SLIDE_2:
転職サイト20個使ったけど
1年間うまくいかなかった

SLIDE_3:
同期と100万以上差がついて
夜中ずっと求人見てました

SLIDE_4:
先に転職した同期に聞いて
エージェント使ってみたら

SLIDE_5:
年収350万→720万になって
手取り50万になりました

SLIDE_6:
20個のサイトより1個の相談
↓無料相談はプロフリンクから

---

今日のテーマ「{pain_word}」で、たくや（25歳）の体験として上の型で作ること。
SLIDE_1〜SLIDE_6のラベルのみ出力。余計な説明は不要。
"""


def _build_prompt_taishoku(persona: dict, pain_word: str, hook_hint: str = "") -> str:
    """退職代行系アカウント向けプロンプト（フォールバック）"""
    hook_line = f"【SLIDE_1フックの方向性】「{hook_hint}」→ このテイストを参考に、このペルソナの言葉で作ること" if hook_hint else ""
    return f"""あなたはTikTok/Shortsの動画クリエイターです。
以下のペルソナに基づいて5枚スライド構成の動画コンテンツを生成してください。

【アカウント】{persona['name']}
【キャラクター】{persona['character']}
【口調】{persona['tone']}
【ターゲット】{persona['target']}
【今日のテーマ（痛み語）】{pain_word}
{hook_line}
{_unique_angle_line(persona)}

【出力形式】必ず以下の形式のみ出力。余計な説明は不要。

SLIDE_1:
＼（テーマに沿った断定的な一言。「〜な人へ」「〜の話」「〜は危険です」など）／

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
・SLIDE_1は必ず「＼〜／」の形式で1行。インパクト最優先
・✅ ① → ■ などの記号は絶対に使わない。箇条書きは・（中点）のみ
・各グループは空行で区切る
・ペルソナの口調を徹底する
・SLIDE_1〜SLIDE_5 のラベルのみ出力

【最重要】このアカウント（{persona['name']}）として完全になりきること。
他のどのアカウントとも内容・言葉・切り口が被らないように、
このキャラクターの実体験・視点・口調だけで生成すること。
"""

# ─── Claude API 呼び出し ─────────────────────────────────────

def generate_slides_with_claude(account: str, pain_word: str, iteration: int = 0) -> list:
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

        hook_hint = _pick_shared_hook(account, iteration=iteration)
        prompt = _build_prompt(persona, pain_word, account=account, hook_hint=hook_hint)
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        logger.info(f"[content_generator] Claude生成完了: {account} / {pain_word}")

        return _parse_slides(raw)

    except Exception as e:
        logger.error(f"[content_generator] Claude APIエラー: {e}")
        return []


_HASHTAGS = {
    "career_young":    "#転職 #20代転職 #年収アップ #転職エージェント #転職活動 #手取りアップ #キャリアアップ #ホワイト転職 #20代 #転職体験",
    "account_A":       "#転職 #年収アップ #キャリアアップ #転職エージェント #転職活動 #市場価値 #サラリーマン #転職成功",
    "account_B":       "#退職代行 #仕事辞めたい #転職 #退職 #転職活動 #退職代行サービス #仕事 #社会人",
    "taishoku_oa":     "#退職代行 #仕事辞めたい #退職 #限界OL #社会人女子 #パワハラ #転職 #仕事やめたい",
    "taishoku_ob":     "#退職代行 #仕事辞めたい #退職 #ブラック企業 #パワハラ #労働問題 #転職 #社会人男子",
    "taishoku_couple": "#退職代行 #夫婦 #共働き #退職 #転職 #子育て #仕事辞めたい #育児",
    "chatlady_yui":     "#チャットレディ #在宅ワーク #在宅のお仕事 #スマホ1台 #女性の働き方 #在宅バイト #未経験OK",
    "chatlady_miku":    "#チャットレディ #シングルマザー #シンママ #在宅ワーク #在宅のお仕事 #スマホ1台 #未経験OK",
    "chatlady_marina":  "#チャットレディ #主婦 #主婦のお小遣い稼ぎ #在宅ワーク #在宅のお仕事 #スマホ1台 #未経験OK",
}


def generate_caption_text(account: str, topic: str, slides: list) -> str:
    """
    スライド内容からTikTok投稿文（キャプション＋ハッシュタグ）を生成する。
    Claude APIを使って自然な投稿文を作る。失敗時はテンプレートで返す。
    """
    persona = PERSONA_MAP.get(account, {})
    hashtags = _HASHTAGS.get(account, "#転職 #仕事")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    hook = slides[0] if slides else topic
    result = slides[4] if len(slides) >= 5 else ""
    cta = slides[5] if len(slides) >= 6 else ""

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            slides_text = "\n".join(f"SLIDE_{i+1}: {s}" for i, s in enumerate(slides) if s)
            extra_rule = ""
            if account in ("chatlady_yui", "chatlady_miku", "chatlady_marina"):
                extra_rule = (
                    "・「在宅の仕事」「チャットレディ」など何の話か曖昧にせず、"
                    "1行目を読んだだけで何についての投稿か伝わるようにする\n"
                    "・動画のナレーションは上記スライドのテキストをそのまま読み上げている。"
                    "スライドに書かれていない新しいエピソードや具体的なディテール"
                    "（金額・推し活など、スライドに登場しない固有の出来事）を創作しない。"
                    "投稿文はスライド内容の言い換え・要約にとどめ、ナレーションと矛盾させない\n"
                )
            prompt = f"""以下のTikTok動画のスライド内容から、TikTok投稿文を書いてください。

【アカウント】{persona.get('name', account)}
【テーマ】{topic}
【スライド内容】
{slides_text}

【投稿文のルール】
・1行目は最も強いインパクトのある一言にする（結論・数字・断定・意外性のいずれか）。
  「〜だった😞」のような曖昧な感想文で始めない
・1行目だけで「何についての投稿か」が明確にわかること
・2〜3行目でストーリーを補足し、最後は行動を促す一言で締める
{extra_rule}・広告っぽくなく、友達に話すような口調
・最後にハッシュタグを付ける（別行に）
・ハッシュタグは以下を使用: {hashtags}
・本文は40〜80文字程度

本文とハッシュタグのみ出力。余計な説明は不要。"""

            message = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            caption = message.content[0].text.strip()
            logger.info(f"[content_generator] キャプション生成完了: {account}")
            return caption
        except Exception as e:
            logger.warning(f"[content_generator] キャプション生成エラー: {e}")

    # フォールバック: テンプレートで生成
    body = f"{hook}\n\n→ {result}" if result else hook
    return f"{body}\n\n{hashtags}"


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

    max_slide = max(slide_dict.keys()) if slide_dict else 5
    n_slides = max(5, min(6, max_slide))
    slides = [slide_dict.get(n, "") for n in range(1, n_slides + 1)]
    return slides if any(slides) else []
