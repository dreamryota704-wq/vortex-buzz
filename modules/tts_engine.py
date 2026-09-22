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
    "career_young":    "ja-JP-KeitaNeural",    # たくや: 25歳男性
}

# 話速設定（ペルソナの口調に合わせて）
RATE_MAP = {
    "account_A":       "+25%",   # 速め・テンポ良く
    "account_B":       "+10%",   # やや速め・親しみやすく
    "taishoku_oa":     "+10%",   # 少し速め（以前は遅すぎた）
    "taishoku_ob":     "+20%",   # 速め・ロジカル
    "taishoku_couple": "+10%",   # やや速め・温かみ
    "career_young":    "+45%",   # 速め・元気よく（4s/スライドに合わせて調整）
}

# ピッチ設定（高めにすると明るく元気な声に）
PITCH_MAP = {
    "career_young": "+15Hz",   # 高め・明るい・元気系（ヒカキン寄り）
}


async def _generate_tts_async(text: str, voice: str, rate: str, output_path: Path, pitch: str = "+0Hz"):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
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
    pitch = PITCH_MAP.get(account, "+0Hz")

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
        asyncio.run(_generate_tts_async(full_text, voice, rate, output_path, pitch))
        logger.info(f"[tts_engine] 音声生成完了: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"[tts_engine] 音声生成エラー: {e}")
        return None


def generate_narration_per_slide(account: str, slides: list, output_dir: Path):
    """
    スライドごとに個別TTS生成 → 結合。テロップと音声の同期用。
    Returns: (combined_mp3_path, [slide_durations_seconds]) or (None, [])
    """
    if not slides:
        return None, []
    try:
        import edge_tts
    except ImportError:
        return None, []

    voice = VOICE_MAP.get(account, "ja-JP-KeitaNeural")
    rate  = RATE_MAP.get(account, "+0%")
    pitch = PITCH_MAP.get(account, "+0Hz")
    output_dir.mkdir(parents=True, exist_ok=True)

    per_paths = []
    durations = []
    CLIP_DUR = 4.0   # Seedance クリップ長（固定）
    MIN_DUR  = 3.5   # スライド最短表示秒数
    PADDING  = 0.3   # 音声終了後の余白

    for i, slide in enumerate(slides):
        clean = _clean_for_tts(slide)
        if not clean:
            durations.append(MIN_DUR)
            per_paths.append(None)
            continue
        slide_mp3 = output_dir / f"_slide_{i+1}.mp3"
        try:
            asyncio.run(_generate_tts_async(clean, voice, rate, slide_mp3, pitch))
            from moviepy.editor import AudioFileClip as _AFC
            with _AFC(str(slide_mp3)) as a:
                dur = min(CLIP_DUR, max(MIN_DUR, a.duration + PADDING))
            durations.append(round(dur, 2))
            per_paths.append(slide_mp3)
        except Exception as e:
            logger.warning(f"[tts_engine] slide {i+1} TTS error: {e}")
            durations.append(MIN_DUR)
            per_paths.append(None)

    # 全スライドを結合して narration.mp3 を作る
    combined_path = output_dir / "narration.mp3"
    try:
        from moviepy.editor import AudioFileClip as _AFC, concatenate_audioclips
        clips = [_AFC(str(p)) for p in per_paths if p and p.exists()]
        if clips:
            combined = concatenate_audioclips(clips)
            combined.write_audiofile(str(combined_path), verbose=False, logger=None)
            for c in clips:
                c.close()
            logger.info(f"[tts_engine] per-slide TTS完了: {len(durations)}枚, 合計{sum(durations):.1f}s → {combined_path}")
            return combined_path, durations
    except Exception as e:
        logger.error(f"[tts_engine] TTS結合エラー: {e}")

    return None, durations


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
