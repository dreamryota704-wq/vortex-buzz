"""
PDCA analyzer module.
Analyzes video performance and conversion data to generate reports and insights.
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
REPORTS_DIR = BASE_DIR / "pdca" / "reports"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"


def calculate_rpv(revenue: float, views: int) -> float:
    """
    Calculate Revenue Per View (RPV).

    Args:
        revenue: Total revenue in JPY
        views: Total view count

    Returns:
        RPV value (0.0 if views == 0)
    """
    if views == 0:
        return 0.0
    return round(revenue / views, 6)


def _load_all_data(account: Optional[str] = None) -> Tuple[List[Dict], List[Dict]]:
    """Load performance and conversion data, optionally filtered by account."""
    from modules.pdca.recorder import load_all_performance, load_all_conversions

    perfs = load_all_performance()
    convs = load_all_conversions()

    # Build a lookup for conversions by video_id
    conv_map = {c["video_id"]: c for c in convs}

    # Filter by account if specified
    if account:
        perfs = [p for p in perfs if p.get("account") == account]

    # Merge performance + conversion data
    merged = []
    for p in perfs:
        vid = p["video_id"]
        c = conv_map.get(vid, {})
        merged.append({**p, **c})

    return merged


def _filter_by_period(records: List[Dict], period: str) -> List[Dict]:
    """Filter records by time period (weekly, monthly, all)."""
    now = datetime.now()
    if period == "weekly":
        cutoff = now - timedelta(days=7)
    elif period == "monthly":
        cutoff = now - timedelta(days=30)
    else:
        return records

    filtered = []
    for r in records:
        created = r.get("created_at") or r.get("updated_at")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if dt >= cutoff:
                    filtered.append(r)
            except ValueError:
                filtered.append(r)  # Include if date can't be parsed
        else:
            filtered.append(r)

    return filtered


def analyze_period(period: str = "weekly", account: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze video performance and conversions for a given period.

    Args:
        period: "weekly", "monthly", or "all"
        account: Optional account filter

    Returns:
        Analysis dict with totals, averages, and grouped breakdowns
    """
    all_data = _load_all_data(account)
    data = _filter_by_period(all_data, period)

    if not data:
        return {
            "period": period,
            "account": account,
            "video_count": 0,
            "total_revenue": 0,
            "avg_revenue_per_video": 0,
            "avg_lp_ctr": 0,
            "avg_cvr": 0,
            "best_rpv": 0,
            "total_views": 0,
            "total_sales": 0,
            "by_template": {},
            "by_topic": {},
            "by_hook_type": {},
            "top_videos": [],
            "bottom_videos": [],
        }

    # Aggregate totals
    total_revenue = sum(r.get("revenue", 0) for r in data)
    total_views = sum(r.get("views", 0) for r in data)
    total_sales = sum(r.get("sales", 0) for r in data)
    total_lp_clicks = sum(r.get("lp_clicks", 0) for r in data)
    total_lp_ctr = round(total_lp_clicks / total_views * 100, 2) if total_views > 0 else 0
    avg_revenue = round(total_revenue / len(data), 0) if data else 0
    avg_cvr = round(sum(r.get("lp_cvr", 0) for r in data) / len(data) * 100, 2) if data else 0

    # Compute RPV per video and find best
    for r in data:
        r["_rpv"] = calculate_rpv(r.get("revenue", 0), r.get("views", 0))

    best_rpv = max((r["_rpv"] for r in data), default=0)

    # Group by template
    by_template: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "revenue": 0, "views": 0, "sales": 0})
    for r in data:
        t = r.get("template", "unknown")
        by_template[t]["count"] += 1
        by_template[t]["revenue"] += r.get("revenue", 0)
        by_template[t]["views"] += r.get("views", 0)
        by_template[t]["sales"] += r.get("sales", 0)
    for t, v in by_template.items():
        v["rpv"] = calculate_rpv(v["revenue"], v["views"])
        v["avg_revenue"] = round(v["revenue"] / v["count"], 0) if v["count"] else 0

    # Group by topic
    by_topic: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "revenue": 0, "views": 0})
    for r in data:
        topic = r.get("topic", "unknown")
        by_topic[topic]["count"] += 1
        by_topic[topic]["revenue"] += r.get("revenue", 0)
        by_topic[topic]["views"] += r.get("views", 0)
    for topic, v in by_topic.items():
        v["rpv"] = calculate_rpv(v["revenue"], v["views"])

    # Group by hook_type
    by_hook: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "revenue": 0, "views": 0})
    for r in data:
        hook = r.get("hook_type", "unknown")
        by_hook[hook]["count"] += 1
        by_hook[hook]["revenue"] += r.get("revenue", 0)
        by_hook[hook]["views"] += r.get("views", 0)
    for hook, v in by_hook.items():
        v["rpv"] = calculate_rpv(v["revenue"], v["views"])

    # Top/bottom 20% by RPV
    sorted_data = sorted(data, key=lambda r: r["_rpv"], reverse=True)
    top_n = max(1, len(sorted_data) // 5)
    top_videos = [{"video_id": r["video_id"], "rpv": r["_rpv"], "revenue": r.get("revenue", 0), "views": r.get("views", 0), "topic": r.get("topic"), "template": r.get("template"), "hook_type": r.get("hook_type")} for r in sorted_data[:top_n]]
    bottom_videos = [{"video_id": r["video_id"], "rpv": r["_rpv"], "revenue": r.get("revenue", 0), "views": r.get("views", 0), "topic": r.get("topic"), "template": r.get("template"), "hook_type": r.get("hook_type")} for r in sorted_data[-top_n:]]

    return {
        "period": period,
        "account": account,
        "video_count": len(data),
        "total_revenue": total_revenue,
        "avg_revenue_per_video": avg_revenue,
        "avg_lp_ctr": total_lp_ctr,
        "avg_cvr": avg_cvr,
        "best_rpv": best_rpv,
        "total_views": total_views,
        "total_sales": total_sales,
        "by_template": dict(by_template),
        "by_topic": dict(by_topic),
        "by_hook_type": dict(by_hook),
        "top_videos": top_videos,
        "bottom_videos": bottom_videos,
    }


def generate_report(period: str = "weekly", account: Optional[str] = None) -> Path:
    """
    Generate a markdown analysis report and save to pdca/reports/{period}/.

    Args:
        period: "weekly" or "monthly"
        account: Optional account filter

    Returns:
        Path to the generated report file
    """
    analysis = analyze_period(period, account)
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    account_suffix = f"_{account}" if account else "_all"
    filename = f"{date_str}{account_suffix}.md"

    report_dir = REPORTS_DIR / period
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / filename

    lines = [
        f"# PDCA レポート — {period.capitalize()} ({now.strftime('%Y年%m月%d日')})",
        "",
        f"**対象アカウント**: {account or '全アカウント'}",
        f"**集計期間**: {period}",
        f"**生成日時**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## 収益サマリー",
        "",
        f"| 指標 | 値 |",
        f"|------|-----|",
        f"| 動画本数 | {analysis['video_count']}本 |",
        f"| 総売上 | ¥{analysis['total_revenue']:,.0f} |",
        f"| 動画1本あたり収益 | ¥{analysis['avg_revenue_per_video']:,.0f} |",
        f"| 総再生数 | {analysis['total_views']:,}回 |",
        f"| 最高RPV | ¥{analysis['best_rpv']:.4f} |",
        f"| 平均LP CTR | {analysis['avg_lp_ctr']:.2f}% |",
        f"| 平均CVR | {analysis['avg_cvr']:.2f}% |",
        f"| 総成約数 | {analysis['total_sales']}件 |",
        "",
        "---",
        "",
        "## テンプレート別分析",
        "",
        "| テンプレート | 本数 | 総売上 | 平均売上 | RPV |",
        "|------------|------|--------|---------|-----|",
    ]

    for tpl, v in sorted(analysis["by_template"].items(), key=lambda x: -x[1]["revenue"]):
        lines.append(f"| {tpl} | {v['count']}本 | ¥{v['revenue']:,.0f} | ¥{v['avg_revenue']:,.0f} | ¥{v['rpv']:.4f} |")

    lines += [
        "",
        "## トピック別分析",
        "",
        "| トピック | 本数 | 総売上 | RPV |",
        "|--------|------|--------|-----|",
    ]
    for topic, v in sorted(analysis["by_topic"].items(), key=lambda x: -x[1]["revenue"]):
        lines.append(f"| {topic} | {v['count']}本 | ¥{v['revenue']:,.0f} | ¥{v['rpv']:.4f} |")

    lines += [
        "",
        "## フック種別分析",
        "",
        "| フック種 | 本数 | 総売上 | RPV |",
        "|--------|------|--------|-----|",
    ]
    for hook, v in sorted(analysis["by_hook_type"].items(), key=lambda x: -x[1]["revenue"]):
        lines.append(f"| {hook} | {v['count']}本 | ¥{v['revenue']:,.0f} | ¥{v['rpv']:.4f} |")

    lines += [
        "",
        "---",
        "",
        "## 勝ちパターン (上位20%)",
        "",
    ]
    for v in analysis["top_videos"]:
        lines.append(f"- **{v['video_id']}** | RPV: ¥{v['rpv']:.4f} | 売上: ¥{v['revenue']:,.0f} | トピック: {v.get('topic', 'N/A')} | テンプレート: {v.get('template', 'N/A')}")

    lines += [
        "",
        "## 負けパターン (下位20%)",
        "",
    ]
    for v in analysis["bottom_videos"]:
        lines.append(f"- **{v['video_id']}** | RPV: ¥{v['rpv']:.4f} | 売上: ¥{v['revenue']:,.0f} | トピック: {v.get('topic', 'N/A')} | テンプレート: {v.get('template', 'N/A')}")

    lines += ["", "---", "", "*このレポートは自動生成されました*", ""]

    report_content = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info(f"Report saved to {report_path}")
    return report_path


def update_knowledge_base(account: str) -> Dict[str, Path]:
    """
    Update the knowledge base for an account based on PDCA data.
    Identifies winning and losing patterns and updates knowledge files.

    Args:
        account: Account identifier

    Returns:
        Dict of updated file paths
    """
    analysis = analyze_period(period="all", account=account)
    account_kb_dir = KNOWLEDGE_DIR / account
    account_kb_dir.mkdir(parents=True, exist_ok=True)

    updated_files = {}
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    # ── Update winning_hooks.md ──────────────────────────────────────────────
    winning_path = account_kb_dir / "winning_hooks.md"
    winning_lines = [
        f"\n## 自動更新: {timestamp}\n",
        f"**集計動画数**: {analysis['video_count']}本\n",
        "",
        "### 勝ちパターン (上位20% by RPV)\n",
    ]
    for v in analysis["top_videos"]:
        winning_lines.append(
            f"- video_id: {v['video_id']} | RPV: ¥{v['rpv']:.4f} | "
            f"トピック: {v.get('topic', 'N/A')} | テンプレート: {v.get('template', 'N/A')} | "
            f"フック: {v.get('hook_type', 'N/A')}"
        )

    # Top template
    by_tpl = analysis["by_template"]
    if by_tpl:
        best_tpl = max(by_tpl.items(), key=lambda x: x[1]["rpv"])
        winning_lines.append(f"\n**最高パフォーマンス テンプレート**: {best_tpl[0]} (RPV: ¥{best_tpl[1]['rpv']:.4f})")

    # Top topic
    by_topic = analysis["by_topic"]
    if by_topic:
        best_topic = max(by_topic.items(), key=lambda x: x[1]["rpv"])
        winning_lines.append(f"**最高パフォーマンス トピック**: {best_topic[0]} (RPV: ¥{best_topic[1]['rpv']:.4f})")

    with open(winning_path, "a", encoding="utf-8") as f:
        f.write("\n".join(winning_lines) + "\n")
    updated_files["winning_hooks"] = winning_path

    # ── Update losing_hooks.md ───────────────────────────────────────────────
    losing_path = account_kb_dir / "losing_hooks.md"
    losing_lines = [
        f"\n## 自動更新: {timestamp}\n",
        "",
        "### 負けパターン (下位20% by RPV)\n",
    ]
    for v in analysis["bottom_videos"]:
        losing_lines.append(
            f"- video_id: {v['video_id']} | RPV: ¥{v['rpv']:.4f} | "
            f"トピック: {v.get('topic', 'N/A')} | テンプレート: {v.get('template', 'N/A')} | "
            f"フック: {v.get('hook_type', 'N/A')}"
        )

    if by_tpl:
        worst_tpl = min(by_tpl.items(), key=lambda x: x[1]["rpv"])
        losing_lines.append(f"\n**最低パフォーマンス テンプレート**: {worst_tpl[0]} (RPV: ¥{worst_tpl[1]['rpv']:.4f})")

    with open(losing_path, "a", encoding="utf-8") as f:
        f.write("\n".join(losing_lines) + "\n")
    updated_files["losing_hooks"] = losing_path

    # ── Update knowledge_base.md ─────────────────────────────────────────────
    kb_path = account_kb_dir / "knowledge_base.md"

    kb_update = f"""
## PDCA 自動更新: {timestamp}

### パフォーマンスサマリー
- 分析動画数: {analysis['video_count']}本
- 総売上: ¥{analysis['total_revenue']:,.0f}
- 平均RPV: ¥{analysis['best_rpv']:.4f}
- 平均LP CTR: {analysis['avg_lp_ctr']:.2f}%

### 推奨アクション
"""
    if by_tpl:
        best_tpl_name = max(by_tpl.items(), key=lambda x: x[1]["rpv"])[0]
        kb_update += f"- テンプレート「{best_tpl_name}」を優先して使用する\n"
    if by_topic:
        best_topic_name = max(by_topic.items(), key=lambda x: x[1]["rpv"])[0]
        kb_update += f"- トピック「{best_topic_name}」の動画を増やす\n"
    by_hook = analysis["by_hook_type"]
    if by_hook:
        best_hook = max(by_hook.items(), key=lambda x: x[1]["rpv"])
        kb_update += f"- フックトーン「{best_hook[0]}」が最高RPV\n"

    with open(kb_path, "a", encoding="utf-8") as f:
        f.write(kb_update + "\n")
    updated_files["knowledge_base"] = kb_path

    logger.info(f"Knowledge base updated for account: {account}")
    return updated_files
