"""
PDCA performance recorder.
Saves video performance and conversion data as JSON files.
"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
PERF_DIR = BASE_DIR / "pdca" / "data" / "performance"
CONV_DIR = BASE_DIR / "pdca" / "data" / "conversions"


def _ensure_dirs():
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    CONV_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_performance(
    video_id: str,
    views: int,
    likes: int,
    comments: int,
    shares: int,
    saves: int,
    account: Optional[str] = None,
    topic: Optional[str] = None,
    template: Optional[str] = None,
    hook_type: Optional[str] = None,
    recorded_at: Optional[str] = None,
) -> Path:
    """
    Save or update video performance metrics.

    Args:
        video_id: Unique video identifier (YYYYMMDD_HHMMSS format)
        views: Total view count
        likes: Total like count
        comments: Total comment count
        shares: Total share count
        saves: Total save count
        account: Account identifier (optional metadata)
        topic: Video topic (optional metadata)
        template: Template used (optional metadata)
        hook_type: Hook tone used (optional metadata)
        recorded_at: ISO timestamp (defaults to now)

    Returns:
        Path to the saved JSON file
    """
    _ensure_dirs()
    perf_path = PERF_DIR / f"{video_id}.json"

    existing = _load_json(perf_path)
    timestamp = recorded_at or datetime.now().isoformat()

    updated = {
        **existing,
        "video_id": video_id,
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "updated_at": timestamp,
    }

    # Add optional metadata fields only if provided
    if account:
        updated["account"] = account
    if topic:
        updated["topic"] = topic
    if template:
        updated["template"] = template
    if hook_type:
        updated["hook_type"] = hook_type
    if "created_at" not in updated:
        updated["created_at"] = timestamp

    # Calculate derived metrics
    if views > 0:
        updated["engagement_rate"] = round((likes + comments + shares + saves) / views * 100, 2)
        updated["save_rate"] = round(saves / views * 100, 2)
        updated["like_rate"] = round(likes / views * 100, 2)
    else:
        updated["engagement_rate"] = 0.0
        updated["save_rate"] = 0.0
        updated["like_rate"] = 0.0

    _save_json(perf_path, updated)
    logger.info(f"Recorded performance for {video_id}: views={views}, likes={likes}")
    return perf_path


def record_conversion(
    video_id: str,
    lp_clicks: int,
    lp_cvr: float,
    sales: int,
    revenue: float,
    recorded_at: Optional[str] = None,
) -> Path:
    """
    Save or update conversion metrics for a video.

    Args:
        video_id: Unique video identifier
        lp_clicks: Landing page clicks from UTM tracking
        lp_cvr: Landing page conversion rate (0.0–1.0)
        sales: Number of sales/conversions
        revenue: Total revenue in JPY
        recorded_at: ISO timestamp (defaults to now)

    Returns:
        Path to the saved JSON file
    """
    _ensure_dirs()
    conv_path = CONV_DIR / f"{video_id}.json"
    existing = _load_json(conv_path)
    timestamp = recorded_at or datetime.now().isoformat()

    # Load corresponding performance for RPV calculation
    perf_path = PERF_DIR / f"{video_id}.json"
    perf = _load_json(perf_path)
    views = perf.get("views", 0)

    rpv = round(revenue / views, 4) if views > 0 else 0.0
    lp_ctr = round(lp_clicks / views * 100, 2) if views > 0 else 0.0

    updated = {
        **existing,
        "video_id": video_id,
        "lp_clicks": lp_clicks,
        "lp_cvr": lp_cvr,
        "sales": sales,
        "revenue": revenue,
        "rpv": rpv,
        "lp_ctr": lp_ctr,
        "updated_at": timestamp,
    }
    if "created_at" not in updated:
        updated["created_at"] = timestamp

    _save_json(conv_path, updated)
    logger.info(f"Recorded conversion for {video_id}: revenue=¥{revenue}, RPV=¥{rpv}")
    return conv_path


def record_from_csv(csv_path: str) -> int:
    """
    Batch record performance and conversions from a CSV file.

    Expected CSV columns:
        video_id, views, likes, comments, shares, saves,
        lp_clicks, sales, revenue
    Optional columns: account, topic, template, hook_type, lp_cvr

    Args:
        csv_path: Path to the CSV file

    Returns:
        Number of records processed
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    count = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_id = row.get("video_id", "").strip()
            if not video_id:
                continue

            try:
                record_performance(
                    video_id=video_id,
                    views=int(row.get("views", 0)),
                    likes=int(row.get("likes", 0)),
                    comments=int(row.get("comments", 0)),
                    shares=int(row.get("shares", 0)),
                    saves=int(row.get("saves", 0)),
                    account=row.get("account", "").strip() or None,
                    topic=row.get("topic", "").strip() or None,
                    template=row.get("template", "").strip() or None,
                    hook_type=row.get("hook_type", "").strip() or None,
                )
                lp_clicks = int(row.get("lp_clicks", 0))
                sales = int(row.get("sales", 0))
                revenue = float(row.get("revenue", 0))
                lp_cvr_raw = row.get("lp_cvr", "0")
                lp_cvr = float(lp_cvr_raw) if lp_cvr_raw else 0.0

                record_conversion(
                    video_id=video_id,
                    lp_clicks=lp_clicks,
                    lp_cvr=lp_cvr,
                    sales=sales,
                    revenue=revenue,
                )
                count += 1
            except Exception as e:
                logger.warning(f"Error processing row for video_id={video_id}: {e}")

    logger.info(f"Processed {count} records from CSV: {csv_path}")
    return count


def load_all_performance() -> List[Dict[str, Any]]:
    """
    Load all performance JSON files.

    Returns:
        List of performance data dicts
    """
    _ensure_dirs()
    results = []
    for path in sorted(PERF_DIR.glob("*.json")):
        data = _load_json(path)
        if data:
            results.append(data)
    return results


def load_all_conversions() -> List[Dict[str, Any]]:
    """
    Load all conversion JSON files.

    Returns:
        List of conversion data dicts
    """
    _ensure_dirs()
    results = []
    for path in sorted(CONV_DIR.glob("*.json")):
        data = _load_json(path)
        if data:
            results.append(data)
    return results
