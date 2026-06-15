#!/usr/bin/env python3
"""
upload_to_drive.py — 生成した動画を Google Drive にアップロード

必要な環境変数:
  GOOGLE_SERVICE_ACCOUNT  : サービスアカウントのJSON文字列
  GOOGLE_DRIVE_FOLDER_ID  : アップロード先フォルダのID
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def main():
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    if not service_account_json or not folder_id:
        print("❌ 環境変数 GOOGLE_SERVICE_ACCOUNT / GOOGLE_DRIVE_FOLDER_ID が未設定です")
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json),
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    # 今日の日付フォルダを Drive 上に作成
    today = date.today().strftime("%Y-%m-%d")
    folder_meta = {
        "name": today,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [folder_id],
    }
    date_folder = service.files().create(body=folder_meta, fields="id").execute()
    date_folder_id = date_folder["id"]
    print(f"📁 Drive フォルダ作成: {today}")

    # output/ 以下の全 .mp4 をアップロード
    output_dir = Path("output")
    mp4_files = list(output_dir.rglob("*.mp4"))

    if not mp4_files:
        print("⚠️  アップロードする動画がありません")
        return

    for mp4 in mp4_files:
        account = mp4.parent.name
        file_name = f"{account}_{mp4.name}"
        print(f"⬆️  アップロード中: {file_name}")
        media = MediaFileUpload(str(mp4), mimetype="video/mp4", resumable=True)
        file_meta = {"name": file_name, "parents": [date_folder_id]}
        service.files().create(body=file_meta, media_body=media, fields="id").execute()
        print(f"   ✅ 完了: {file_name}")

    print(f"\n✅ {len(mp4_files)}本の動画を Google Drive にアップロードしました")
    print(f"   フォルダ: {today}")


if __name__ == "__main__":
    main()
