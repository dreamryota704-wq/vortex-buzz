"""
image_selector.py
スライドテキストの感情・内容を分析して、最適な画像を自動選択する。
career_young アカウント専用。
"""
from pathlib import Path

# キーワード → 感情タグ（上から順に優先）
_KEYWORD_EMOTION = [
    (["地方転勤辞令", "転勤辞令", "地方転勤"], "transfer_order"),
    (["頭を抱え", "もう無理", "崩壊", "限界が来た", "追い詰め"], "breakdown"),
    (["深夜", "残業月", "長時間労働", "終電", "月60", "月80", "月100"], "overwork"),
    (["手取り18", "給与明細", "18万", "給料明細", "低賃金", "薄給"], "salary_shock"),
    (["上司に詰め", "パワハラ", "怒鳴", "上司が怖", "引き止め"], "boss_meeting"),
    (["怒り", "ストレス爆発", "むかつく", "理不尽"], "angry"),
    (["落ち込", "絶望", "どうしよう", "辛い", "泣きそう", "暗い"], "depressed"),
    (["疲れ", "ぐったり", "しんどい", "体がきつ", "朝が怖"], "tired"),
    (["転職エージェントに登録", "エージェントを使", "決意した", "動くことにし", "申し込ん"], "determined"),
    (["転職エージェント", "エージェント", "非公開求人", "調べ", "登録し"], "thinking"),
    (["内定", "転職成功", "年収アップ", "年収が上がった", "転職後の"], "success"),
    (["笑顔", "楽しい", "充実", "フレックス", "リモートあり", "余裕が生まれ"], "happy"),
    (["後悔ゼロ", "正解だった", "変われた", "思い込みだった", "🔥"], "victory"),
    (["リラックス", "解放", "自由", "余裕", "やっと"], "relaxed"),
    (["悩", "迷", "わからなかった", "不安", "どうすれば"], "thinking"),
    (["驚", "衝撃", "知らなかった", "まさか", "えっ"], "shocked"),
]

# 感情 → ファイル名のキー文字列
_EMOTION_TO_FILE_HINT = {
    "tired":          "9.15.14",
    "overwork":       "9.15.18",
    "salary_shock":   "9.15.22",
    "boss_meeting":   "9.15.26",
    "thinking":       "9.15.31",
    "transfer_order": "9.15.35",
    "intimidated":    "9.15.40",
    "success":        "9.15.45",
    "happy":          "9.15.49",
    "victory":        "9.16.04",
    "angry":          "9.16.09",
    "depressed":      "9.16.12",
    "breakdown":      "9.16.17",
    "shocked":        "9.16.21",
    "relaxed":        "9.16.26",
    "exhausted":      "9.16.32",
    "determined":     "9.16.38",
    "content":        "9.16.43",
}

# スライド番号（0始まり）ごとのデフォルト感情
_DEFAULT_BY_POSITION = [
    "tired",       # SLIDE_1: フック → 疲れ顔で共感
    "overwork",    # SLIDE_2: 当時のリアル → 深夜残業
    "thinking",    # SLIDE_3: やったこと → 転職エージェント登録
    "success",     # SLIDE_4: 結果 → 内定・ガッツポーズ
    "victory",     # SLIDE_5: CTA → 勝利・解放
]


def _detect_emotion(text: str) -> str | None:
    for keywords, emotion in _KEYWORD_EMOTION:
        if any(kw in text for kw in keywords):
            return emotion
    return None


def _find_image(emotion: str, image_dir: Path) -> Path | None:
    hint = _EMOTION_TO_FILE_HINT.get(emotion, "")
    if not hint:
        return None
    matches = list(image_dir.glob(f"*{hint}*"))
    return matches[0] if matches else None


def select_clips_for_slides(slides: list, clips_dir: Path) -> list:
    """
    Seedance 2.0 生成済みクリップを5本選んで返す（4秒×5本=20秒構成）。
    - clips 1-4: 本編スライド1-4 に対応（各4秒 × 4本 = 16秒）
    - clip 5:    CTA用（4秒）
    全5本揃わない場合は [] を返し、呼び元が静止画にフォールバックする。
    """
    clips_dir = Path(clips_dir)
    if not clips_dir.exists():
        return []

    # 6フェーズ: [対象スライドindices, フォールバック感情順]
    phase_defs = [
        ([0],    ["tired",      "salary_shock", "transfer_order", "overwork",   "depressed"]),   # ①失敗告白
        ([1],    ["overwork",   "exhausted",    "depressed",      "angry",      "breakdown"]),   # ②苦労・状況
        ([2],    ["breakdown",  "boss_meeting", "intimidated",    "shocked",    "angry"]),       # ③数字で苦労感
        ([3],    ["thinking",   "determined",   "shocked",        "relaxed",    "content"]),     # ④解決策
        ([4],    ["success",    "happy",        "determined",     "relaxed",    "content"]),     # ⑤成果
        ([5],    ["victory",    "relaxed",      "content",        "happy",      "success"]),     # ⑥オチ・CTA
    ]

    result = []
    used_clips = set()

    for slide_indices, fallback_emotions in phase_defs:
        chosen = None

        # スライドテキストから感情検出 → クリップを探す
        for idx in slide_indices:
            if idx < len(slides):
                emotion = _detect_emotion(slides[idx])
                if emotion:
                    clip = clips_dir / f"clip_{emotion}.mp4"
                    if clip.exists() and str(clip) not in used_clips:
                        chosen = clip
                        break

        # 検出できなければフォールバック順で探す（使用済みは避ける）
        if chosen is None:
            for fb in fallback_emotions:
                clip = clips_dir / f"clip_{fb}.mp4"
                if clip.exists() and str(clip) not in used_clips:
                    chosen = clip
                    break

        # それでも見つからなければ使用済みでも許可
        if chosen is None:
            for fb in fallback_emotions:
                clip = clips_dir / f"clip_{fb}.mp4"
                if clip.exists():
                    chosen = clip
                    break

        # 最後の手段: clips_dir にある何でも
        if chosen is None:
            any_clips = sorted(clips_dir.glob("clip_*.mp4"))
            chosen = any_clips[0] if any_clips else None

        if chosen:
            result.append(chosen)
            used_clips.add(str(chosen))

    expected = len(phase_defs)
    return result if len(result) == expected else []


def select_images_for_slides(slides: list, image_dir: Path) -> list:
    """
    5枚のスライドテキストを受け取り、各スライドに対応する画像パスのリストを返す。
    - スライドの文章からキーワードで感情を判定
    - 同じ画像が連続しないよう調整
    - マッチしない場合はデフォルト感情を使用
    """
    image_dir = Path(image_dir)
    all_imgs = sorted(
        [p for p in image_dir.glob("*.png")] +
        [p for p in image_dir.glob("*.jpg")] +
        [p for p in image_dir.glob("*.jpeg")]
    )
    if not all_imgs:
        return []

    result = []
    used_paths = []

    for i, text in enumerate(slides):
        emotion = _detect_emotion(text)
        default_emotion = _DEFAULT_BY_POSITION[min(i, len(_DEFAULT_BY_POSITION) - 1)]

        # 感情マッチの画像を取得
        img = _find_image(emotion, image_dir) if emotion else None

        # 直前と同じ画像なら代替を探す
        if img and result and img == result[-1]:
            alt = _find_image(default_emotion, image_dir)
            if alt and alt != result[-1]:
                img = alt
            else:
                # 未使用の画像から選ぶ
                unused = [p for p in all_imgs if p not in used_paths[-2:]]
                img = unused[0] if unused else img

        # マッチなし → デフォルト感情
        if not img:
            img = _find_image(default_emotion, image_dir)

        # それでもなければ残りから選ぶ
        if not img or not img.exists():
            img = all_imgs[i % len(all_imgs)]

        result.append(img)
        used_paths.append(img)

    return result
