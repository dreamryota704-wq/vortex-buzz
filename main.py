#!/usr/bin/env python3
"""
main.py — Buzz Video Pipeline System CLI

Commands:
  start              Start scheduler daemon
  stop               Stop daemon
  run-now            Process queue now
  install-cron       Install launchd plist (macOS)
  record             Record video performance
  record-conversion  Record conversion data
  record-csv         Batch record from CSV
  analyze            Generate analysis report
  optimize           Run optimizer
  dashboard          Show rich terminal dashboard
  learn              Add manual note to knowledge base
  learn-from-data    Auto-update knowledge from PDCA data
  add-account        Create new account scaffold
"""
import json
import os
import shutil
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import yaml

# Ensure buzz_system root is on sys.path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# Rich imports
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.columns import Columns
from rich.text import Text

console = Console()

PID_FILE = BASE_DIR / ".scheduler.pid"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# CLI group
# ============================================================

@click.group()
def cli():
    """Buzz Video Pipeline System — TikTok/Shorts/Reels 自動化ツール"""
    pass


# ============================================================
# Scheduler commands
# ============================================================

@cli.command()
def start():
    """Start the video scheduler daemon (runs at 5am daily)."""
    import schedule as schedule_lib
    import time

    schedule_cfg = _load_yaml(BASE_DIR / "config" / "schedule.yaml")
    run_time = schedule_cfg.get("schedule", {}).get("time", "05:00")

    def run_batch_job():
        console.print(f"[bold green]⏰ {datetime.now().strftime('%H:%M')} — バッチ処理開始[/]")
        from modules.scheduler import VideoScheduler
        scheduler = VideoScheduler()
        results = scheduler.run_batch()
        console.print(f"[green]✅ バッチ完了: {len(results)}件処理[/]")

    schedule_lib.every().day.at(run_time).do(run_batch_job)

    # Save PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    console.print(Panel(
        f"[bold green]スケジューラー起動[/]\n"
        f"実行時刻: 毎日 {run_time}\n"
        f"PID: {os.getpid()}\n"
        f"Ctrl+C で停止",
        title="Buzz Video Scheduler",
        border_style="green",
    ))

    try:
        while True:
            schedule_lib.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        console.print("\n[yellow]スケジューラー停止[/]")
        if PID_FILE.exists():
            PID_FILE.unlink()


@cli.command()
def stop():
    """Stop the running scheduler daemon."""
    if not PID_FILE.exists():
        console.print("[yellow]スケジューラーは起動していません[/]")
        return
    with open(PID_FILE) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        console.print(f"[green]スケジューラー停止 (PID={pid})[/]")
    except ProcessLookupError:
        console.print(f"[yellow]プロセス {pid} が見つかりません (既に終了済み)[/]")
        PID_FILE.unlink()


@cli.command("run-now")
def run_now():
    """Process the queue immediately without waiting for scheduled time."""
    from modules.scheduler import VideoScheduler
    scheduler = VideoScheduler()
    stats = scheduler.get_queue_stats()

    if stats["pending"] == 0:
        console.print("[yellow]キューにジョブがありません[/]")
        return

    console.print(f"[bold]キュー処理開始: {stats['pending']}件のジョブ[/]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("処理中...", total=None)
        results = scheduler.run_batch()
        progress.update(task, description=f"完了: {len(results)}件")

    success = [r for r in results if r.get("result") == "success"]
    failed = [r for r in results if r.get("result") != "success"]
    console.print(f"[green]✅ 成功: {len(success)}件[/]  [red]❌ 失敗: {len(failed)}件[/]")


@cli.command("install-cron")
def install_cron():
    """Install a macOS launchd plist to run the scheduler at 5am daily."""
    schedule_cfg = _load_yaml(BASE_DIR / "config" / "schedule.yaml")
    hour, minute = map(int, schedule_cfg.get("schedule", {}).get("time", "05:00").split(":"))
    python_path = sys.executable
    script_path = BASE_DIR / "main.py"
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.buzzsystem.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
        <string>run-now</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{log_dir}/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/scheduler_error.log</string>
    <key>WorkingDirectory</key>
    <string>{BASE_DIR}</string>
</dict>
</plist>
"""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.buzzsystem.scheduler.plist"

    with open(plist_path, "w") as f:
        f.write(plist_content)

    console.print(f"[green]✅ launchd plist を作成しました:[/]")
    console.print(f"   {plist_path}")
    console.print(f"\n有効化するには:")
    console.print(f"   launchctl load {plist_path}")
    console.print(f"\n無効化するには:")
    console.print(f"   launchctl unload {plist_path}")


# ============================================================
# Data recording commands
# ============================================================

@cli.command()
@click.option("--video-id", required=True, help="Video ID (YYYYMMDD_HHMMSS)")
@click.option("--views", required=True, type=int)
@click.option("--likes", required=True, type=int)
@click.option("--comments", default=0, type=int)
@click.option("--shares", default=0, type=int)
@click.option("--saves", default=0, type=int)
@click.option("--account", default=None)
@click.option("--topic", default=None)
@click.option("--template", default=None)
@click.option("--hook-type", default=None)
def record(video_id, views, likes, comments, shares, saves, account, topic, template, hook_type):
    """Record video performance metrics."""
    from modules.pdca.recorder import record_performance
    path = record_performance(
        video_id=video_id,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        saves=saves,
        account=account,
        topic=topic,
        template=template,
        hook_type=hook_type,
    )
    console.print(f"[green]✅ パフォーマンス記録: {path}[/]")


@cli.command("record-conversion")
@click.option("--video-id", required=True, help="Video ID")
@click.option("--lp-clicks", required=True, type=int, help="LP click count")
@click.option("--lp-cvr", required=True, type=float, help="LP conversion rate (0.0-1.0)")
@click.option("--sales", required=True, type=int, help="Number of sales")
@click.option("--revenue", required=True, type=float, help="Revenue in JPY")
def record_conversion(video_id, lp_clicks, lp_cvr, sales, revenue):
    """Record conversion data for a video."""
    from modules.pdca.recorder import record_conversion as _record_conv
    path = _record_conv(
        video_id=video_id,
        lp_clicks=lp_clicks,
        lp_cvr=lp_cvr,
        sales=sales,
        revenue=revenue,
    )
    console.print(f"[green]✅ コンバージョン記録: {path}[/]")


@cli.command("record-csv")
@click.argument("csv_path", type=click.Path(exists=True))
def record_csv(csv_path):
    """Batch record performance and conversion data from a CSV file."""
    from modules.pdca.recorder import record_from_csv
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("CSV処理中...", total=None)
        count = record_from_csv(csv_path)
        progress.update(task, description=f"完了: {count}件")
    console.print(f"[green]✅ {count}件の記録を完了しました[/]")


# ============================================================
# Analysis commands
# ============================================================

@cli.command()
@click.option("--period", default="weekly", type=click.Choice(["weekly", "monthly", "all"]))
@click.option("--account", default=None, help="Filter by account")
def analyze(period, account):
    """Generate analysis report and save to pdca/reports/."""
    from modules.pdca.analyzer import generate_report, analyze_period

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("分析中...", total=None)
        report_path = generate_report(period=period, account=account)
        analysis = analyze_period(period=period, account=account)
        progress.update(task, description="完了")

    console.print(f"\n[bold green]レポート生成完了[/]: {report_path}")
    console.print(f"\n[bold]サマリー ({period})[/]")

    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("指標")
    table.add_column("値", justify="right")
    table.add_row("動画本数", f"{analysis['video_count']}本")
    table.add_row("総売上", f"¥{analysis['total_revenue']:,.0f}")
    table.add_row("1本あたり収益", f"¥{analysis['avg_revenue_per_video']:,.0f}")
    table.add_row("平均LP CTR", f"{analysis['avg_lp_ctr']:.2f}%")
    table.add_row("最高RPV", f"¥{analysis['best_rpv']:.4f}")
    console.print(table)


@cli.command()
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without applying")
def optimize(dry_run):
    """Run the PDCA optimizer to improve template weights and queue priorities."""
    from modules.pdca.optimizer import optimize as _optimize

    mode = "DRY RUN" if dry_run else "実行"
    console.print(f"[bold]最適化 {mode} 開始...[/]")

    result = _optimize(dry_run=dry_run)

    if not result.get("changes"):
        console.print("[green]最適化は不要です (現状維持)[/]")
        return

    change_id = result.get("change_id")
    changes = result.get("changes", [])

    console.print(f"\n[bold]{'提案された' if dry_run else '適用された'}変更 ({len(changes)}件)[/]")
    if change_id:
        console.print(f"change_id: [cyan]{change_id}[/] (ロールバック用)")

    for change in changes:
        ctype = change.get("type", "")
        target = change.get("target", "")
        reason = change.get("reason", "")
        if "weight" in change:
            old_v = change.get("old_value")
            new_v = change.get("new_value")
            console.print(f"  [yellow]{ctype}[/] {target}: {old_v} → {new_v}  ({reason})")
        elif ctype == "cta_review":
            console.print(f"  [yellow]{ctype}[/]: {len(change.get('items', []))}件のCTAを確認してください")
        else:
            console.print(f"  [yellow]{ctype}[/] {target}: {reason}")

    if dry_run:
        console.print("\n[dim]--dry-run なので変更は適用されていません[/]")


# ============================================================
# Dashboard
# ============================================================

@cli.command()
def dashboard():
    """Show rich terminal dashboard with revenue metrics."""
    from modules.scheduler import VideoScheduler
    from modules.pdca.analyzer import analyze_period
    from modules.pdca.recorder import load_all_conversions

    console.clear()
    console.print(Panel(
        "[bold cyan]Buzz Video Pipeline System[/]\n"
        "TikTok / Shorts / Reels 自動化ダッシュボード",
        border_style="cyan",
    ))

    scheduler = VideoScheduler()
    queue_stats = scheduler.get_queue_stats()

    # Schedule info
    schedule_cfg = _load_yaml(BASE_DIR / "config" / "schedule.yaml")
    next_time = schedule_cfg.get("schedule", {}).get("time", "05:00")

    console.print(Panel(
        f"[bold]次回生成時刻[/]: 毎日 [green]{next_time}[/]\n"
        f"[bold]キュー[/]: [yellow]{queue_stats['pending']}件[/] 待機中 "
        f"/ 完了 {queue_stats['done']}件 / 失敗 {queue_stats['failed']}件",
        title="スケジュール",
        border_style="blue",
    ))

    # Monthly revenue
    analysis_monthly = analyze_period(period="monthly")
    analysis_weekly = analyze_period(period="weekly")

    target_revenue = 1_000_000
    monthly_rev = analysis_monthly["total_revenue"]
    progress_pct = min(100, monthly_rev / target_revenue * 100)
    progress_bar = "█" * int(progress_pct / 5) + "░" * (20 - int(progress_pct / 5))

    console.print(Panel(
        f"[bold]今月の収益[/]\n\n"
        f"  総売上       : [green]¥{monthly_rev:>12,.0f}[/]\n"
        f"  目標進捗     : [{progress_bar}] {progress_pct:.1f}% / ¥1,000,000\n"
        f"  動画1本あたり: ¥{analysis_monthly['avg_revenue_per_video']:,.0f}\n"
        f"  総再生数     : {analysis_monthly['total_views']:,}回\n"
        f"  動画本数     : {analysis_monthly['video_count']}本",
        title="収益サマリー (今月)",
        border_style="green",
    ))

    # Weekly summary
    console.print(Panel(
        f"今週: 売上 [green]¥{analysis_weekly['total_revenue']:,.0f}[/] / "
        f"{analysis_weekly['video_count']}本 / "
        f"LP CTR: {analysis_weekly['avg_lp_ctr']:.2f}% / "
        f"RPV: ¥{analysis_weekly['best_rpv']:.4f}",
        title="今週サマリー",
        border_style="blue",
    ))

    # Funnel health
    funnels_cfg = _load_yaml(BASE_DIR / "config" / "funnels.yaml")
    funnel_table = Table(title="ファネル健全性", box=box.SIMPLE, show_header=True, header_style="bold")
    funnel_table.add_column("ファネル")
    funnel_table.add_column("種類")
    funnel_table.add_column("LP CTR")
    funnel_table.add_column("CVR")
    funnel_table.add_column("状態")

    # Get per-funnel stats from conversion data
    all_convs = load_all_conversions()
    funnel_stats: dict = {}
    for c in all_convs:
        # We need to match by video_id → account → funnel
        # Load corresponding performance metadata
        perf_path = BASE_DIR / "pdca" / "data" / "performance" / f"{c['video_id']}.json"
        if perf_path.exists():
            perf_data = _load_json(perf_path)
        else:
            perf_data = {}
        f_name = perf_data.get("funnel", "unknown")
        if f_name not in funnel_stats:
            funnel_stats[f_name] = {"lp_clicks": 0, "views": 0, "sales": 0, "revenue": 0}
        funnel_stats[f_name]["lp_clicks"] += c.get("lp_clicks", 0)
        funnel_stats[f_name]["views"] += perf_data.get("views", 0)
        funnel_stats[f_name]["sales"] += c.get("sales", 0)

    for f_key, f_data in funnels_cfg.get("funnels", {}).items():
        stats = funnel_stats.get(f_key, {})
        views = stats.get("views", 0)
        lp_clicks = stats.get("lp_clicks", 0)
        sales = stats.get("sales", 0)
        lp_ctr = f"{lp_clicks / views * 100:.1f}%" if views > 0 else "N/A"
        cvr = f"{sales / lp_clicks * 100:.1f}%" if lp_clicks > 0 else "N/A"

        # Health check
        if views == 0:
            status = "⚪ データなし"
        elif lp_clicks / max(views, 1) >= 0.02:
            status = "✅ 良好"
        else:
            status = "⚠️  要改善"

        funnel_table.add_row(
            f_data.get("name", f_key)[:20],
            f_data.get("type", "N/A"),
            lp_ctr,
            cvr,
            status,
        )

    console.print(funnel_table)

    # Account-level revenue table
    accounts_cfg = _load_yaml(BASE_DIR / "config" / "accounts.yaml")
    account_table = Table(title="アカウント別売上 (今月)", box=box.SIMPLE, show_header=True, header_style="bold")
    account_table.add_column("アカウント")
    account_table.add_column("名前")
    account_table.add_column("動画数", justify="right")
    account_table.add_column("売上", justify="right")
    account_table.add_column("RPV", justify="right")

    for acct_key, acct_data in accounts_cfg.get("accounts", {}).items():
        acct_analysis = analyze_period(period="monthly", account=acct_key)
        account_table.add_row(
            acct_key,
            acct_data.get("name", "")[:15],
            str(acct_analysis["video_count"]),
            f"¥{acct_analysis['total_revenue']:,.0f}",
            f"¥{acct_analysis['best_rpv']:.4f}",
        )

    console.print(account_table)

    # Optimization suggestions
    from modules.pdca.analyzer import analyze_period as _ap
    suggestions = []
    templates_cfg = _load_yaml(BASE_DIR / "config" / "templates.yaml")
    by_template = analysis_monthly.get("by_template", {})
    if by_template:
        avg_rpv = sum(v["rpv"] for v in by_template.values()) / len(by_template)
        for tpl, v in by_template.items():
            if v["rpv"] > avg_rpv * 1.3:
                suggestions.append(f"📈 テンプレート「{tpl}」のRPVが平均より30%以上高い → 使用頻度を増やすことを推奨")
            elif v["rpv"] < avg_rpv * 0.5 and v["count"] >= 3:
                suggestions.append(f"📉 テンプレート「{tpl}」のRPVが低い → 見直しまたは廃止を検討")

    if analysis_monthly["avg_lp_ctr"] < 1.0 and analysis_monthly["video_count"] > 0:
        suggestions.append("⚠️  LP CTRが1%未満 → CTAテキストの改善またはファネルLPの見直しが必要")

    if not suggestions:
        suggestions.append("✅ 現状維持 — 大きな問題は検出されませんでした")

    console.print(Panel(
        "\n".join(suggestions),
        title="最適化提案",
        border_style="yellow",
    ))


# ============================================================
# Knowledge base commands
# ============================================================

@cli.command()
@click.option("--account", required=True, help="Account identifier")
@click.option("--note", required=True, help="Learning note to add")
@click.option("--category", default="general", help="Category (hook/cta/template/topic/general)")
def learn(account, note, category):
    """Add a manual learning note to the account's knowledge base."""
    kb_dir = BASE_DIR / "knowledge" / account
    if not kb_dir.exists():
        console.print(f"[red]エラー: アカウント '{account}' のナレッジベースが見つかりません[/]")
        console.print(f"  作成するには: python main.py add-account --account {account}")
        sys.exit(1)

    log_path = kb_dir / "learning_log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## [{timestamp}] [{category}]\n\n{note}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

    console.print(f"[green]✅ 学習ログに追記しました[/]")
    console.print(f"   ファイル: {log_path}")
    console.print(f"   カテゴリ: {category}")
    console.print(f"   内容: {note[:60]}{'...' if len(note) > 60 else ''}")


@cli.command("learn-from-data")
@click.option("--account", required=True, help="Account identifier")
def learn_from_data(account):
    """Auto-update knowledge base from PDCA performance data."""
    from modules.pdca.analyzer import update_knowledge_base

    console.print(f"[bold]ナレッジベース自動更新: {account}[/]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("分析・更新中...", total=None)
        updated = update_knowledge_base(account)
        progress.update(task, description="完了")

    console.print(f"[green]✅ 更新完了 ({len(updated)}ファイル)[/]")
    for key, path in updated.items():
        console.print(f"   {key}: {path}")


# ============================================================
# Account management
# ============================================================

@cli.command("add-account")
@click.option("--account", required=True, help="New account identifier (e.g. new_account)")
@click.option("--name", required=True, help="Display name (Japanese OK)")
@click.option("--hook-tone", default="friendly", help="Hook tone (aggressive/friendly/empathy/factual/warm)")
@click.option("--funnel", default="affiliate_01", help="Default funnel identifier")
def add_account(account, name, hook_tone, funnel):
    """Create a new account scaffold (knowledge base, templates, persona)."""
    kb_dir = BASE_DIR / "knowledge" / account
    if kb_dir.exists():
        console.print(f"[yellow]警告: アカウント '{account}' は既に存在します[/]")
        if not click.confirm("上書きしますか？"):
            return

    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "templates").mkdir(exist_ok=True)

    # Copy shared templates as starting point
    shared_templates = BASE_DIR / "knowledge" / "shared" / "templates"
    for tmpl_file in shared_templates.glob("*.txt"):
        dest = kb_dir / "templates" / tmpl_file.name
        if not dest.exists():
            shutil.copy2(tmpl_file, dest)

    # Create persona.yaml
    persona = {
        "account": account,
        "name": name,
        "hook_tone": hook_tone,
        "hook_style": hook_tone,
        "default_funnel": funnel,
        "target_audience": "ターゲット読者を記入",
        "value_proposition": "提供価値を記入",
        "avoid_words": ["詐欺", "絶対", "保証", "必ず儲かる"],
        "key_topics": ["topic1", "topic2"],
        "content_pillars": ["教育", "共感", "行動喚起"],
        "created_at": datetime.now().isoformat(),
    }
    persona_path = kb_dir / "persona.yaml"
    with open(persona_path, "w", encoding="utf-8") as f:
        yaml.dump(persona, f, allow_unicode=True, default_flow_style=False)

    # Create empty knowledge files
    timestamp = datetime.now().strftime("%Y-%m-%d")

    kb_path = kb_dir / "knowledge_base.md"
    with open(kb_path, "w", encoding="utf-8") as f:
        f.write(f"# {name} ナレッジベース\n\n作成日: {timestamp}\n\n## 基本情報\n\n(ここにアカウントの基本情報を記入)\n")

    winning_path = kb_dir / "winning_hooks.md"
    with open(winning_path, "w", encoding="utf-8") as f:
        f.write(f"# {name} 勝ちフックパターン\n\n## 手動追加\n\n(パフォーマンスの高いフックをここに記録)\n\n## 自動更新\n\n(learn-from-data コマンドで自動追記されます)\n")

    losing_path = kb_dir / "losing_hooks.md"
    with open(losing_path, "w", encoding="utf-8") as f:
        f.write(f"# {name} 負けフックパターン\n\n## 手動追加\n\n(パフォーマンスの低いフックをここに記録)\n\n## 自動更新\n\n(learn-from-data コマンドで自動追記されます)\n")

    log_path = kb_dir / "learning_log.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# {name} 学習ログ\n\n## [{timestamp}] [general]\n\nアカウント作成\n")

    # Create template files
    hook_tmpl_path = kb_dir / "templates" / "hook_templates.txt"
    if not hook_tmpl_path.exists():
        with open(hook_tmpl_path, "w", encoding="utf-8") as f:
            f.write(f"# {name} フックテンプレート\n# 1行1テンプレート、{'{'}topic{'}'} {'{'}amount{'}'} {'{'}days{'}'} をプレースホルダーとして使用\n\n")

    cta_tmpl_path = kb_dir / "templates" / "cta_templates.txt"
    if not cta_tmpl_path.exists():
        with open(cta_tmpl_path, "w", encoding="utf-8") as f:
            f.write(f"# {name} CTAテンプレート\nプロフィールリンクから詳しく確認できます👆\n詳細は無料で見られます\n")

    struct_tmpl_path = kb_dir / "templates" / "structure_templates.txt"
    if not struct_tmpl_path.exists():
        with open(struct_tmpl_path, "w", encoding="utf-8") as f:
            f.write(f"# {name} 動画構成テンプレート\n\n## 基本構成\n1. フック (0-3秒)\n2. ポイント提示 (3-12秒)\n3. CTA (12-15秒)\n")

    # Add to accounts.yaml
    accounts_cfg = _load_yaml(BASE_DIR / "config" / "accounts.yaml")
    if "accounts" not in accounts_cfg:
        accounts_cfg["accounts"] = {}
    if account not in accounts_cfg["accounts"]:
        accounts_cfg["accounts"][account] = {
            "name": name,
            "style": hook_tone,
            "hook_tone": hook_tone,
            "cta": "詳しくはプロフィールのリンクから👆",
            "color_filter": "clean",
            "sfx_volume": -15,
            "default_funnel": funnel,
            "funnels": [funnel],
        }
        with open(BASE_DIR / "config" / "accounts.yaml", "w", encoding="utf-8") as f:
            yaml.dump(accounts_cfg, f, allow_unicode=True, default_flow_style=False)
        console.print(f"[green]accounts.yaml に {account} を追加しました[/]")

    # Create output directory
    (BASE_DIR / "output" / account).mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold green]アカウント作成完了: {account}[/]\n\n"
        f"名前    : {name}\n"
        f"トーン  : {hook_tone}\n"
        f"ファネル: {funnel}\n\n"
        f"次のステップ:\n"
        f"  1. {persona_path} を編集して詳細を設定\n"
        f"  2. {kb_dir}/templates/ のテンプレートを編集\n"
        f"  3. python make_video.py --account {account} ... で動画生成",
        title="新規アカウント",
        border_style="green",
    ))


# ============================================================
# Queue management
# ============================================================

@cli.command("add-job")
@click.option("--account", required=True)
@click.option("--video", required=True, type=click.Path())
@click.option("--bgm", default="", help="Path to BGM file")
@click.option("--info", required=True, help="Body info text")
@click.option("--topic", required=True)
@click.option("--funnel", default=None)
@click.option("--priority", default=5, type=int, help="Priority 1-10")
def add_job(account, video, bgm, info, topic, funnel, priority):
    """Add a video job to the processing queue."""
    accounts_cfg = _load_yaml(BASE_DIR / "config" / "accounts.yaml")
    if account not in accounts_cfg.get("accounts", {}):
        console.print(f"[red]エラー: アカウント '{account}' が見つかりません[/]")
        sys.exit(1)
    if funnel is None:
        funnel = accounts_cfg["accounts"][account].get("default_funnel", "affiliate_01")

    from modules.scheduler import VideoScheduler
    scheduler = VideoScheduler()
    job_id = scheduler.add_job(
        account=account,
        video_path=video,
        bgm_path=bgm,
        info=info,
        topic=topic,
        funnel=funnel,
        priority=priority,
    )
    console.print(f"[green]✅ ジョブ追加: ID={job_id}, account={account}, topic={topic}[/]")


@cli.command("queue-status")
def queue_status():
    """Show current queue status."""
    from modules.scheduler import VideoScheduler
    scheduler = VideoScheduler()
    stats = scheduler.get_queue_stats()

    table = Table(title="キュー状態", box=box.SIMPLE)
    table.add_column("項目")
    table.add_column("値", justify="right")
    table.add_row("合計", str(stats["total"]))
    table.add_row("待機中", f"[yellow]{stats['pending']}[/]")
    table.add_row("完了", f"[green]{stats['done']}[/]")
    table.add_row("失敗", f"[red]{stats['failed']}[/]")
    table.add_row("CTA カウンター", str(stats["cta_counter"]))
    table.add_row("最終更新", stats.get("last_updated") or "N/A")
    console.print(table)


@cli.command("clear-queue")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def clear_queue(confirm):
    """Remove all completed jobs from the queue."""
    if not confirm:
        if not click.confirm("完了済みジョブをキューから削除しますか？"):
            return
    from modules.scheduler import VideoScheduler
    VideoScheduler().clear_completed()
    console.print("[green]✅ 完了済みジョブを削除しました[/]")


# ============================================================
# Rollback command
# ============================================================

@cli.command()
@click.argument("change_id")
def rollback(change_id):
    """Rollback a specific optimization change by its change_id."""
    from modules.pdca.optimizer import rollback as _rollback
    result = _rollback(change_id)
    if result["success"]:
        console.print(f"[green]✅ ロールバック成功: {change_id}[/]")
        for item in result.get("rolled_back_items", []):
            console.print(f"   {item}")
    else:
        console.print(f"[red]❌ ロールバック失敗: {result.get('error')}[/]")


if __name__ == "__main__":
    cli()
