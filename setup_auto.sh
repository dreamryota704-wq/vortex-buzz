#!/bin/bash
# setup_auto.sh — VORTEX 自動化ワンクリックセットアップ
# 実行: bash setup_auto.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_LABEL="com.vortex.auto_daily"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
LOG_DIR="$SCRIPT_DIR/logs"

echo ""
echo "================================================"
echo "  VORTEX 自動化セットアップ"
echo "================================================"

# ── 1. venv の Python パスを取得 ──────────────────────────
if [ ! -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    echo "❌ .venv が見つかりません。先に setup.sh を実行してください"
    exit 1
fi
PYTHON="$SCRIPT_DIR/.venv/bin/python"
echo "✅ Python: $PYTHON"

# ── 2. ログフォルダ作成 ───────────────────────────────────
mkdir -p "$LOG_DIR"
echo "✅ ログフォルダ: $LOG_DIR"

# ── 3. launchd plist を作成 ───────────────────────────────
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/auto_daily.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>5</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/auto_daily.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/auto_daily_error.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF
echo "✅ launchd 設定ファイル作成: $PLIST_PATH"

# ── 4. launchd に登録 ─────────────────────────────────────
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "✅ launchd に登録しました（毎朝5:00に自動実行）"

# ── 5. Mac スリープから自動起動を設定 ─────────────────────
echo ""
echo "⚙️  Macのスリープ自動起動を設定しています..."
echo "   ※ 管理者パスワードが必要です"
sudo pmset repeat wakeorpoweron MTWRFSU 04:55:00 && \
    echo "✅ 毎朝4:55にMacが自動起動するよう設定しました" || \
    echo "⚠️  pmset の設定に失敗しました（手動でスリープ解除が必要です）"

# ── 完了メッセージ ────────────────────────────────────────
echo ""
echo "================================================"
echo "  セットアップ完了！"
echo "================================================"
echo ""
echo "  毎朝 5:00 に自動で動画が生成されます"
echo "  生成された動画は output/ フォルダに入ります"
echo "  完成したら Mac に通知が届きます"
echo ""
echo "  【注意】Macは「シャットダウン」ではなく"
echo "  「スリープ」にしておいてください"
echo ""
echo "  ログ確認: $LOG_DIR/auto_daily.log"
echo "  今すぐテスト: python auto_daily.py --test"
echo ""
