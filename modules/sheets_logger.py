"""
sheets_logger.py
動画生成ログをGoogle Sheetsに自動記録する。
Apps Script Web App に POST するだけなので認証不要。
"""
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import date

logger = logging.getLogger(__name__)

WEBHOOK_ENV_KEY = "SHEETS_WEBHOOK_URL"


def log_to_sheets(
    account: str,
    topic: str,
    slides: list,
    narration_text: str = "",
) -> bool:
    """
    動画生成結果をGoogle Sheetsに1行追記する。
    Returns: 成功=True、失敗=False
    """
    url = os.environ.get(WEBHOOK_ENV_KEY, "")
    if not url:
        logger.warning("[sheets_logger] SHEETS_WEBHOOK_URL が設定されていません")
        return False

    # slides = [s1, s2, s3, s4, s5]
    def _s(i):
        return slides[i] if i < len(slides) else ""

    payload = {
        "date":      date.today().strftime("%Y-%m-%d"),
        "account":   account,
        "topic":     topic,
        "slide_1":   _s(0),
        "slide_2":   _s(1),
        "slide_3":   _s(2),
        "slide_4":   _s(3),
        "slide_5":   _s(4),
        "narration": narration_text,
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = resp.read().decode("utf-8")
            logger.info(f"[sheets_logger] 記録完了: {account} / {topic} → {result}")
            return True
    except urllib.error.URLError as e:
        logger.error(f"[sheets_logger] 送信エラー: {e}")
        return False
    except Exception as e:
        logger.error(f"[sheets_logger] 予期せぬエラー: {e}")
        return False
