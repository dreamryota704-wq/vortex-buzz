"""
Video job scheduler.
Manages the jobs queue (queue/jobs.json) and CTA rotation.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
JOBS_FILE = BASE_DIR / "queue" / "jobs.json"
SCHEDULE_CONFIG = BASE_DIR / "config" / "schedule.yaml"
FUNNELS_CONFIG = BASE_DIR / "config" / "funnels.yaml"


def _load_jobs() -> Dict[str, Any]:
    """Load the jobs.json file."""
    if not JOBS_FILE.exists():
        return {"jobs": [], "last_updated": None, "cta_counter": 0}
    with open(JOBS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_jobs(data: Dict[str, Any]):
    """Save data to jobs.json."""
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now().isoformat()
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_schedule_config() -> Dict[str, Any]:
    if not SCHEDULE_CONFIG.exists():
        return {"schedule": {"time": "05:00", "batch_count": 3}}
    with open(SCHEDULE_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_funnels_config() -> Dict[str, Any]:
    if not FUNNELS_CONFIG.exists():
        return {}
    with open(FUNNELS_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class VideoScheduler:
    """Manages the video generation job queue and CTA rotation."""

    def __init__(self):
        self.schedule_cfg = _load_schedule_config()
        self.funnels_cfg = _load_funnels_config()
        self.batch_count = self.schedule_cfg.get("schedule", {}).get("batch_count", 3)
        cta_rotation = self.funnels_cfg.get("cta_rotation", {})
        self.organic_ratio = cta_rotation.get("organic_ratio", 2)
        self.conversion_ratio = cta_rotation.get("conversion_ratio", 1)
        self.cycle_length = self.organic_ratio + self.conversion_ratio

    def determine_cta_type(self, account: str = None) -> str:
        """
        Determine whether the next video should use organic or conversion CTA.
        Based on the cta_counter in jobs.json and the 2:1 organic:conversion ratio.

        Args:
            account: Account identifier (currently global counter, can be per-account in future)

        Returns:
            "organic" or "conversion"
        """
        data = _load_jobs()
        counter = data.get("cta_counter", 0)

        # Cycle pattern: organic, organic, conversion (for 2:1 ratio)
        position_in_cycle = counter % self.cycle_length
        if position_in_cycle < self.organic_ratio:
            cta_type = "organic"
        else:
            cta_type = "conversion"

        # Increment counter and save
        data["cta_counter"] = counter + 1
        _save_jobs(data)

        logger.debug(f"CTA type: {cta_type} (counter={counter}, position={position_in_cycle})")
        return cta_type

    def get_next_jobs(self, batch_count: int = None) -> List[Dict[str, Any]]:
        """
        Return the next N pending jobs from the queue.

        Args:
            batch_count: Number of jobs to return (defaults to schedule config)

        Returns:
            List of job dicts with status="pending"
        """
        if batch_count is None:
            batch_count = self.batch_count

        data = _load_jobs()
        pending = [j for j in data["jobs"] if j.get("status") == "pending"]
        return pending[:batch_count]

    def mark_job_done(self, job_id: str, success: bool = True, error_msg: str = None):
        """
        Mark a job as completed (or failed) in jobs.json.

        Args:
            job_id: The job's unique ID
            success: True if job completed successfully
            error_msg: Optional error message if success=False
        """
        data = _load_jobs()
        for job in data["jobs"]:
            if job.get("id") == job_id:
                job["status"] = "done" if success else "failed"
                job["completed_at"] = datetime.now().isoformat()
                if error_msg:
                    job["error"] = error_msg
                break
        _save_jobs(data)

    def add_job(
        self,
        account: str,
        video_path: str,
        bgm_path: str,
        info: str,
        topic: str,
        funnel: str,
        priority: int = 5,
    ) -> str:
        """
        Add a new job to the queue.

        Args:
            account: Account identifier
            video_path: Path to input video file
            bgm_path: Path to BGM file
            info: Info text for body points
            topic: Video topic keyword
            funnel: Funnel identifier
            priority: Job priority 1-10 (higher = processed first)

        Returns:
            The new job's ID string
        """
        data = _load_jobs()
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "account": account,
            "video_path": video_path,
            "bgm_path": bgm_path,
            "info": info,
            "topic": topic,
            "funnel": funnel,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        data["jobs"].append(job)
        # Sort by priority descending, then by creation time ascending
        data["jobs"].sort(key=lambda j: (-j.get("priority", 5), j.get("created_at", "")))
        _save_jobs(data)
        logger.info(f"Added job {job_id} for account={account}, topic={topic}")
        return job_id

    def run_batch(self, processor_fn=None) -> List[Dict[str, Any]]:
        """
        Process the next batch of pending jobs.

        Args:
            processor_fn: Callable(job) -> bool. If None, jobs are marked done without processing.

        Returns:
            List of processed job dicts
        """
        jobs = self.get_next_jobs()
        if not jobs:
            logger.info("No pending jobs in queue")
            return []

        results = []
        for job in jobs:
            job_id = job["id"]
            logger.info(f"Processing job {job_id}: account={job['account']}, topic={job['topic']}")
            try:
                if processor_fn is not None:
                    success = processor_fn(job)
                else:
                    success = True
                self.mark_job_done(job_id, success=success)
                job["result"] = "success" if success else "failed"
            except Exception as e:
                logger.error(f"Job {job_id} failed with exception: {e}")
                self.mark_job_done(job_id, success=False, error_msg=str(e))
                job["result"] = "error"
                job["error"] = str(e)
            results.append(job)

        return results

    def get_queue_stats(self) -> Dict[str, Any]:
        """Return queue statistics."""
        data = _load_jobs()
        jobs = data.get("jobs", [])
        return {
            "total": len(jobs),
            "pending": len([j for j in jobs if j.get("status") == "pending"]),
            "done": len([j for j in jobs if j.get("status") == "done"]),
            "failed": len([j for j in jobs if j.get("status") == "failed"]),
            "cta_counter": data.get("cta_counter", 0),
            "last_updated": data.get("last_updated"),
        }

    def clear_completed(self):
        """Remove all done/failed jobs from the queue."""
        data = _load_jobs()
        data["jobs"] = [j for j in data["jobs"] if j.get("status") == "pending"]
        _save_jobs(data)
        logger.info("Cleared completed jobs from queue")
