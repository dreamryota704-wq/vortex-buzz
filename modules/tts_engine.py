"""
tts_engine.py
edge-tts を使ってペルソナ別の音声を生成する（完全無料）。
"""
import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# アカウント別音声設定（edge-tts の日本語ニューラル音声）
VOICE_MAP = {
    "account_A":       "ja-JP-KeitaNeural",    # 男性・クール
    "account_B":       "ja-JP-NanamiNeural",   # 女性・フレンドリー
    "taishoku_oa":     "ja-JP-NanamiNeural",   # あかり: 女性・やさしい
    "taishoku_ob":     "ja-JP-KeitaNeural",    # りょう: 男性・落ち着いた
    "taishoku_couple": "ja-JP-NanamiNeural",   # 夫婦: 女性メイン
}

# 話速設定（ペルソナの口調に合わせて）
RATE_MAP = {
    "account_A":       "+25%",   # 速め・テンポ良く
    "account_B":       "+10%",   # やや速め・親しみやすく
    "taishoku_oa":     "+10%",   # 少し速め（以前は遅すぎた）
    "taishoku_ob":     "+20%",   # 速め・ロジカル
    "taishoku_couple": "+10%",   # やや速め・温かみ
}


async def _generate_tts_async(text: str, voice: str, rate: str, output_path: Path):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(output_path))


def generate_narration(account: str, slides: list, output_dir: Path) -> Path | None:
    """
    5枚のスライドテキストを結合して音声ファイルを生成する。
    Returns: 生成されたmp3ファイルのPath、失敗時はNone
    """
    if not slides:
        return None

    try:
        import edge_tts
    except ImportError:
        logger.warning("[tts_engine] edge-tts がインストールされていません: pip install edge-tts")
        return None

    voice = VOICE_MAP.get(account, "ja-JP-NanamiNeural")
    rate  = RATE_MAP.get(account, "+0%")

    # スライドテキストをナレーション用に整形
    # SLIDE_1: 少し間を置く、SLIDE_2〜4: 読み上げ、SLIDE_5: CTA
    narration_parts = []
    for i, slide in enumerate(slides):
        if not slide:
            continue
        # 記号を除去してナレーション向けに整形
        clean = _clean_for_tts(slide)
        if clean:
            narration_parts.append(clean)

    full_text = "　".join(narration_parts)  # 全角スペースで間を挿入

    if not full_text.strip():
        return None

    output_path = output_dir / "narration.mp3"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(_generate_tts_async(full_text, voice, rate, output_path))
        logger.info(f"[tts_engine] 音声生成完了: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"[tts_engine] 音声生成エラー: {e}")
        return None


def _clean_for_tts(text: str) -> str:
    """TTS向けにテキストを整形する（記号除去・読みやすく）"""
    import re
    # ・ を読点に変換
    text = text.replace("・", "、")
    # 記号除去
    text = re.sub(r'[✅✓①②③④⑤→▶■□]', '', text)
    # 複数空行を1行に
    text = re.sub(r'\n{2,}', '　', text)
    text = text.replace('\n', '、')
    # 余分な記号
    text = re.sub(r'[【】「」『』（）()〜〜]', '', text)
    return text.strip()
