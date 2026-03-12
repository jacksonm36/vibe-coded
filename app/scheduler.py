"""Time-based scheduler: runs job templates on a cron-like schedule."""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter

from app.database import SessionLocal
from app import crud
from app.api.jobs import launch_job_template_by_id

logger = logging.getLogger(__name__)

_scheduler_thread = None
_stop = False


def _tick():
    """Check all scheduled templates and launch if due."""
    db = SessionLocal()
    try:
        templates = crud.get_scheduled_job_templates(db)
    finally:
        db.close()
    for jt in templates:
        try:
            tz_name = (jt.schedule_tz or "UTC").strip()
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz = ZoneInfo("UTC")
            now_utc = datetime.utcnow()
            now_in_tz = now_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            now_naive = now_in_tz.replace(tzinfo=None)
            # Start from 2 min ago so get_next gives us "this" occurrence if we're in the run window
            start = now_naive - timedelta(minutes=2)
            c = croniter(jt.schedule_cron.strip(), start)
            next_run = c.get_next(datetime)
            # Launch if the scheduled time is in the last 90s (tick runs every 60s)
            if now_naive - timedelta(seconds=90) <= next_run <= now_naive:
                logger.info("Scheduled run: template id=%s", jt.id)
                launch_job_template_by_id(jt.id)
        except Exception as e:
            logger.warning("Schedule check failed for template %s: %s", jt.id, e)


def _loop():
    import time
    while not _stop:
        try:
            _tick()
        except Exception as e:
            logger.exception("Scheduler tick error: %s", e)
        time.sleep(60)


def start_scheduler():
    """Start the background scheduler thread."""
    global _scheduler_thread, _stop
    _stop = False
    import threading
    _scheduler_thread = threading.Thread(target=_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Job schedule checker started (every 60s)")


def stop_scheduler():
    global _stop
    _stop = True
