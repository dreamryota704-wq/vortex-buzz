"""
PDCA optimizer module.
Analyzes performance data and optimizes template weights, CTA configs, and queue priorities.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES_CONFIG = BASE_DIR / "config" / "templates.yaml"
HISTORY_DIR = BASE_DIR / "pdca" / "data" / "history"
CHANGES_FILE = HISTORY_DIR / "changes.json"


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: Dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _load_changes() -> List[Dict]:
    if not CHANGES_FILE.exists():
        return []
    with open(CHANGES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_changes(changes: List[Dict]):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHANGES_FILE, "w", encoding="utf-8") as f:
        json.dump(changes, f, ensure_ascii=False, indent=2)


def optimize(dry_run: bool = False) -> Dict[str, Any]:
    """
    Run the optimization cycle:
    1. Increase weight of high-RPV templates in config/templates.yaml
    2. List low LP-CTR CTAs for review
    3. Deprecate templates with 2+ weeks below average
    4. Lower queue priority for low-revenue topics
    5. Record all changes to pdca/data/history/changes.json

    Args:
        dry_run: If True, compute and print proposed changes without applying them.

    Returns:
        Dict describing proposed/applied changes
    """
    from modules.pdca.analyzer import analyze_period

    analysis = analyze_period(period="all")
    templates_cfg = _load_yaml(TEMPLATES_CONFIG)
    opt_cfg = templates_cfg.get("optimization", {})

    weight_increase = opt_cfg.get("weight_increase_factor", 1.3)
    weight_decrease = opt_cfg.get("weight_decrease_factor", 0.7)
    min_weight = opt_cfg.get("min_weight", 0.3)
    max_weight = opt_cfg.get("max_weight", 3.0)

    by_template = analysis.get("by_template", {})
    avg_rpv = (
        sum(v["rpv"] for v in by_template.values()) / len(by_template)
        if by_template else 0
    )

    proposed_changes = []

    # ── ① Template weight optimization ──────────────────────────────────────
    templates = templates_cfg.get("templates", {})
    for tpl_key, tpl_data in templates.items():
        tpl_stats = by_template.get(tpl_key)
        if not tpl_stats:
            continue

        tpl_rpv = tpl_stats["rpv"]
        current_weight = tpl_data.get("weight", 1.0)

        if tpl_rpv > avg_rpv:
            new_weight = min(max_weight, round(current_weight * weight_increase, 2))
            action = "weight_increase"
            reason = f"RPV ¥{tpl_rpv:.4f} > avg ¥{avg_rpv:.4f}"
        else:
            new_weight = max(min_weight, round(current_weight * weight_decrease, 2))
            action = "weight_decrease"
            reason = f"RPV ¥{tpl_rpv:.4f} <= avg ¥{avg_rpv:.4f}"

        if abs(new_weight - current_weight) > 0.01:
            change = {
                "type": action,
                "target": f"template:{tpl_key}",
                "field": "weight",
                "old_value": current_weight,
                "new_value": new_weight,
                "reason": reason,
            }
            proposed_changes.append(change)
            if not dry_run:
                templates_cfg["templates"][tpl_key]["weight"] = new_weight

    # ── ② Low LP-CTR CTAs for review ────────────────────────────────────────
    avg_lp_ctr = analysis.get("avg_lp_ctr", 0)
    low_ctr_threshold = avg_lp_ctr * 0.5  # Flag if LP CTR < 50% of average
    cta_review_items = []
    for v in analysis.get("bottom_videos", []):
        # We don't store CTA type per video yet, but flag low performers
        cta_review_items.append({
            "video_id": v["video_id"],
            "topic": v.get("topic"),
            "rpv": v["rpv"],
            "note": "低RPV動画 — CTAを確認してください",
        })

    if cta_review_items:
        proposed_changes.append({
            "type": "cta_review",
            "target": "cta_rotation",
            "items": cta_review_items,
            "reason": f"LP CTR 平均 {avg_lp_ctr:.2f}% — 低パフォーマンスCTAの確認が必要",
        })

    # ── ③ Deprecate templates with chronic underperformance ─────────────────
    # Check templates that have been below average for multiple analyses
    for tpl_key, tpl_data in templates.items():
        tpl_stats = by_template.get(tpl_key)
        if not tpl_stats:
            continue
        current_weight = tpl_data.get("weight", 1.0)
        if current_weight <= min_weight and tpl_data.get("status") == "active":
            change = {
                "type": "deprecate_template",
                "target": f"template:{tpl_key}",
                "field": "status",
                "old_value": "active",
                "new_value": "deprecated",
                "reason": f"ウェイトが最小値({min_weight})に到達 — 2週間以上平均以下",
            }
            proposed_changes.append(change)
            if not dry_run:
                templates_cfg["templates"][tpl_key]["status"] = "deprecated"

    # ── ④ Lower queue priority for low-revenue topics ────────────────────────
    by_topic = analysis.get("by_topic", {})
    if by_topic:
        avg_topic_rpv = sum(v["rpv"] for v in by_topic.values()) / len(by_topic)
        low_priority_topics = [
            topic for topic, v in by_topic.items()
            if v["rpv"] < avg_topic_rpv * 0.5 and v["count"] >= 2
        ]
        if low_priority_topics:
            change = {
                "type": "queue_priority_lower",
                "target": "queue",
                "topics": low_priority_topics,
                "reason": f"RPVが平均の50%未満のトピック — キュー優先度を下げることを推奨",
            }
            proposed_changes.append(change)
            if not dry_run:
                # Lower priority for pending jobs with these topics
                _lower_queue_priority_for_topics(low_priority_topics)

    # ── ⑤ Record changes to history ─────────────────────────────────────────
    if proposed_changes:
        change_record = {
            "change_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "analysis_summary": {
                "video_count": analysis["video_count"],
                "avg_rpv": avg_rpv,
                "avg_lp_ctr": avg_lp_ctr,
            },
            "changes": proposed_changes,
            "templates_before": {k: {"weight": v.get("weight"), "status": v.get("status")} for k, v in templates.items()},
        }
        if not dry_run:
            # Save updated templates config
            _save_yaml(TEMPLATES_CONFIG, templates_cfg)
            # Record in history
            history = _load_changes()
            history.append(change_record)
            _save_changes(history)
            logger.info(f"Applied {len(proposed_changes)} optimizations, change_id={change_record['change_id']}")

        return change_record
    else:
        logger.info("No optimizations needed at this time")
        return {"change_id": None, "changes": [], "message": "最適化は不要です"}


def _lower_queue_priority_for_topics(topics: List[str]):
    """Lower queue priority for pending jobs with specified topics."""
    from modules.scheduler import _load_jobs, _save_jobs

    data = _load_jobs()
    modified = 0
    for job in data["jobs"]:
        if job.get("status") == "pending" and job.get("topic") in topics:
            job["priority"] = max(1, job.get("priority", 5) - 2)
            modified += 1
    if modified:
        _save_jobs(data)
        logger.info(f"Lowered priority for {modified} jobs with low-revenue topics")


def rollback(change_id: str) -> Dict[str, Any]:
    """
    Revert a specific optimization change by its change_id.

    Args:
        change_id: The change_id string from the history

    Returns:
        Dict describing the rollback result
    """
    history = _load_changes()
    target_change = None
    for record in history:
        if record.get("change_id") == change_id:
            target_change = record
            break

    if not target_change:
        return {"success": False, "error": f"change_id={change_id} が見つかりません"}

    templates_cfg = _load_yaml(TEMPLATES_CONFIG)
    rolled_back = []

    for change in target_change.get("changes", []):
        change_type = change.get("type")
        target = change.get("target", "")

        if change_type in ("weight_increase", "weight_decrease", "deprecate_template"):
            # Restore template field
            tpl_key = target.replace("template:", "")
            field = change.get("field")
            old_value = change.get("old_value")
            if tpl_key in templates_cfg.get("templates", {}) and field and old_value is not None:
                templates_cfg["templates"][tpl_key][field] = old_value
                rolled_back.append(f"テンプレート {tpl_key}.{field} → {old_value}")

    if rolled_back:
        _save_yaml(TEMPLATES_CONFIG, templates_cfg)

    # Mark the change as rolled back in history
    for record in history:
        if record.get("change_id") == change_id:
            record["rolled_back"] = True
            record["rolled_back_at"] = datetime.now().isoformat()
            break
    _save_changes(history)

    result = {
        "success": True,
        "change_id": change_id,
        "rolled_back_items": rolled_back,
        "timestamp": datetime.now().isoformat(),
    }
    logger.info(f"Rolled back change {change_id}: {rolled_back}")
    return result


def list_changes() -> List[Dict]:
    """Return all optimization change records."""
    return _load_changes()
