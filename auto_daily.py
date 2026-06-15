#!/usr/bin/env python3
"""
auto_daily.py — 全アカウント一括動画生成（毎日自動実行）

使い方:
  python auto_daily.py          # 今日分を全アカウント生成
  python auto_daily.py --test   # テスト実行（dry-run）
"""
import argparse
import json
import logging
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "auto_daily.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 毎日のトピックローテーション（曜日ベース: 0=月, 6=日）
# ──────────────────────────────────────────────────────────────────────────────
DAILY_TOPICS = {
    "account_A": [
        {"topic": "副業",           "info": "・月10万円を3ヶ月で達成した方法\n・初期費用0円でできる副業3選"},
        {"topic": "アフィリエイト", "info": "・アフィリエイトの基本の仕組み\n・初心者が最初にやるべきこと"},
        {"topic": "在宅ワーク",     "info": "・在宅で稼ぐ具体的な手順\n・会社にバレない副業のやり方"},
        {"topic": "スキルマーケット","info": "・スキルゼロでも売れるもの\n・ランサーズ・クラウドワークスの使い方"},
        {"topic": "月10万",         "info": "・月10万円の壁を超えた実録\n・挫折した人がやりがちなミス"},
        {"topic": "副業",           "info": "・サラリーマンが副業で稼いだリアル\n・時間がなくてもできる副業"},
        {"topic": "アフィリエイト", "info": "・アフィリエイトで失敗する人の共通点\n・稼げるジャンルの選び方"},
    ],
    "account_B": [
        {"topic": "副業",           "info": "・副業を始めて変わった3つのこと\n・失敗しない副業の選び方"},
        {"topic": "在宅ワーク",     "info": "・在宅ワークで月5万稼ぐ方法\n・在宅でできる仕事の種類一覧"},
        {"topic": "アフィリエイト", "info": "・アフィリエイトを3ヶ月続けた結果\n・継続するためのコツ"},
        {"topic": "スキルマーケット","info": "・スキルマーケットで稼ぐコツ\n・プロフィールの書き方"},
        {"topic": "副業",           "info": "・副業初心者におすすめの3つの方法\n・それぞれのメリット・デメリット"},
        {"topic": "月10万",         "info": "・月10万を達成した人に聞いた共通点\n・今日からできる行動リスト"},
        {"topic": "在宅ワーク",     "info": "・在宅ワークのよくある失敗と対策\n・継続できる仕組みの作り方"},
    ],
    "taishoku_oa": [
        {"topic": "仕事辞めたい",   "info": "・仕事辞めたいと思ったら最初にすること\n・退職前に確認すべき3つのこと"},
        {"topic": "退職代行",       "info": "・退職代行を実際に使った体験談\n・費用・流れ・注意点まとめ"},
        {"topic": "パワハラ",       "info": "・パワハラされたときの対処法\n・証拠の集め方と相談先"},
        {"topic": "職場の人間関係", "info": "・職場の人間関係で消耗していた私が変わったこと\n・正しい距離の取り方"},
        {"topic": "限界OL",         "info": "・毎朝泣きながら出勤していた私が退職した話\n・あの頃の自分に言いたいこと"},
        {"topic": "仕事辞めたい",   "info": "・「辞めたいけど言えない」人へ\n・退職を伝えるのが怖い理由と解決策"},
        {"topic": "退職代行",       "info": "・退職代行のよくある疑問Q&A\n・本当に会社に行かなくていいの？"},
    ],
    "taishoku_ob": [
        {"topic": "退職代行",       "info": "・退職代行の仕組みを徹底解説\n・使うべき人・使わなくていい人"},
        {"topic": "仕事辞めたい",   "info": "・ブラック企業を辞めた男性の実体験\n・退職後の生活はどう変わったか"},
        {"topic": "パワハラ",       "info": "・パワハラ上司から身を守る方法\n・会社を辞める前にやること"},
        {"topic": "退職代行",       "info": "・退職代行サービス比較3選\n・選び方のポイントと料金相場"},
        {"topic": "仕事辞めたい",   "info": "・30代男性が転職を決意したきっかけ\n・後悔しない退職のタイミング"},
        {"topic": "退職代行",       "info": "・退職代行は本当に即日辞められるのか\n・注意すべき落とし穴"},
        {"topic": "パワハラ",       "info": "・精神的に追い詰められる前にすること\n・逃げることは正しい選択"},
    ],
    "taishoku_couple": [
        {"topic": "退職代行",       "info": "・夫婦で話し合って退職代行を使った理由\n・2人で決断したこと"},
        {"topic": "仕事辞めたい",   "info": "・二人ともブラック企業にいた私たちの話\n・同じ境遇の方へ"},
        {"topic": "退職代行",       "info": "・退職代行を使うまで迷っていたこと\n・使って良かった3つの理由"},
        {"topic": "職場の人間関係", "info": "・夫婦で職場の悩みを話し合うメリット\n・パートナーに相談するコツ"},
        {"topic": "仕事辞めたい",   "info": "・2人で新しい生活を始めて変わったこと\n・退職後の不安と現実"},
        {"topic": "退職代行",       "info": "・退職代行を使った後のリアルな声\n・夫婦それぞれの感想"},
        {"topic": "退職代行",       "info": "・「もう限界」と思ったら読んでほしい\n・二人で乗り越えた経験談"},
    ],
}


def _pick_video(account: str) -> Path:
    """input/videos/ からアカウント専用 or 共通の素材を選ぶ"""
    videos_dir = BASE_DIR / "input" / "videos"

    # アカウント専用フォルダがあれば優先
    account_dir = videos_dir / account
    if account_dir.exists():
        mp4s = sorted(account_dir.glob("*.mp4"))
        if mp4s:
            # 曜日でローテーション
            idx = date.today().weekday() % len(mp4s)
            return mp4s[idx]

    # 共通フォルダから選ぶ（dummy.mp4 を除外、なければ使う）
    all_mp4s = [p for p in sorted(videos_dir.glob("*.mp4")) if p.name != "dummy.mp4"]
    if not all_mp4s:
        all_mp4s = list(videos_dir.glob("*.mp4"))

    if not all_mp4s:
        raise FileNotFoundError(f"input/videos/ に .mp4 ファイルがありません")

    idx = date.today().weekday() % len(all_mp4s)
    return all_mp4s[idx]


def _pick_bgm() -> Path | None:
    """input/bgm/ からBGMを選ぶ"""
    bgm_dir = BASE_DIR / "input" / "bgm"
    mp3s = [p for p in sorted(bgm_dir.glob("*.mp3")) if p.name != "dummy.mp3"]
    if not mp3s:
        mp3s = list(bgm_dir.glob("*.mp3"))
    if not mp3s:
        return None
    idx = date.today().weekday() % len(mp3s)
    return mp3s[idx]


def _notify(title: str, message: str):
    """macOS デスクトップ通知を送る"""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}"'],
            check=False, capture_output=True,
        )
    except Exception:
        pass


def _open_finder(folder: Path):
    """Finder でフォルダを開く"""
    try:
        subprocess.run(["open", str(folder)], check=False)
    except Exception:
        pass


def _move_to_date_folder(account: str, stdout: str, today_str: str) -> Path | None:
    """生成された動画を output/YYYY-MM-DD/account/ に移動して新パスを返す"""
    # make_video.py の出力から「出力先 : /path/to/file.mp4」を探す
    for line in stdout.splitlines():
        if "出力先" in line and ".mp4" in line:
            src = Path(line.split(":")[-1].strip())
            if src.exists():
                dest_dir = BASE_DIR / "output" / today_str / account
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                src.rename(dest)
                return dest
    return None


def generate_for_account(account: str, dry_run: bool = False) -> dict:
    """1アカウント分の動画を生成して結果を返す"""
    today_weekday = date.today().weekday()
    today_str = date.today().strftime("%Y-%m-%d")
    topics = DAILY_TOPICS.get(account, [])
    if not topics:
        return {"account": account, "status": "skip", "reason": "トピック未設定"}

    config = topics[today_weekday % len(topics)]
    topic = config["topic"]
    info = config["info"]

    try:
        video_path = _pick_video(account)
    except FileNotFoundError as e:
        return {"account": account, "status": "error", "reason": str(e)}

    bgm_path = _pick_bgm()

    cmd = [
        sys.executable, str(BASE_DIR / "make_video.py"),
        "--account", account,
        "--video", str(video_path),
        "--info", info,
        "--topic", topic,
    ]
    if bgm_path:
        cmd += ["--bgm", str(bgm_path)]
    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"[{account}] 生成開始: topic={topic}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))

    if result.returncode == 0:
        dest = _move_to_date_folder(account, result.stdout, today_str)
        dest_str = str(dest) if dest else "不明"
        logger.info(f"[{account}] 生成完了 → {dest_str}")
        return {"account": account, "status": "ok", "topic": topic, "output": dest_str}
    else:
        logger.error(f"[{account}] 失敗\n{result.stderr}")
        return {"account": account, "status": "error", "reason": result.stderr[-300:]}


def main():
    parser = argparse.ArgumentParser(description="全アカウント動画一括生成")
    parser.add_argument("--test", action="store_true", help="dry-run（動画処理なし）")
    parser.add_argument("--accounts", nargs="+", help="対象アカウントを限定 (例: account_A taishoku_oa)")
    args = parser.parse_args()

    today_str = date.today().strftime("%Y-%m-%d")
    logger.info(f"=== auto_daily 開始: {today_str} {'[TEST]' if args.test else ''} ===")

    accounts = args.accounts or list(DAILY_TOPICS.keys())
    results = []

    for account in accounts:
        result = generate_for_account(account, dry_run=args.test)
        results.append(result)

    # 結果サマリー
    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]

    logger.info(f"=== 完了: 成功 {len(ok)}/{len(results)} ===")
    for r in errors:
        logger.error(f"  [{r['account']}] {r.get('reason', '')}")

    # 結果をJSONで保存
    result_path = LOG_DIR / f"result_{today_str}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"date": today_str, "results": results}, f, ensure_ascii=False, indent=2)

    # 出力フォルダを特定してFinderで開く
    output_base = BASE_DIR / "output"

    if ok:
        _notify(
            "VORTEX 動画生成完了",
            f"{len(ok)}本の動画が完成しました → output/ フォルダを確認してください",
        )
        _open_finder(output_base)
    else:
        _notify("VORTEX エラー", f"動画生成に失敗しました。logs/auto_daily.log を確認してください")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
