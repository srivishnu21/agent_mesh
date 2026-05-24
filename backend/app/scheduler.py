"""Workflow scheduler driven by per-workflow cron entries.

Each workflow row stores its schedule under ``graph.config.schedule``:

    {
        "enabled": true,
        "cron":    "0 9 * * *",
        "input":   "Run the daily summary.",
        "timezone": "UTC"          # optional
    }

On startup the scheduler scans every workflow and registers a job for every
enabled schedule. ``reload()`` re-scans (used after any PATCH on a workflow).
Jobs fire ``execute_run`` directly so the scheduled execution path is the
same one used by the API and Telegram triggers.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID, uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import async_session_factory
from app.models.entities import Run as RunModel
from app.models.entities import Workflow as WorkflowModel
from app.runtime.workflow_runner import execute_run

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _extract_schedule(workflow: WorkflowModel) -> dict | None:
    graph = workflow.graph or {}
    config = graph.get("config") or {}
    schedule = config.get("schedule") or {}
    if not schedule.get("enabled"):
        return None
    cron = (schedule.get("cron") or "").strip()
    if not cron:
        return None
    return schedule


async def _trigger_scheduled_run(workflow_id_str: str, default_input: str) -> None:
    """Body of the cron job. Inserts a Run row, then runs it."""
    workflow_id = UUID(workflow_id_str)
    async with async_session_factory() as session:
        workflow = await session.get(WorkflowModel, workflow_id)
        if workflow is None:
            logger.warning("Scheduled workflow %s no longer exists, skipping.", workflow_id)
            return
        text = default_input or "Scheduled run."
        run = RunModel(
            workflow_id=workflow_id,
            trigger={"source": "schedule", "payload": {"input": text}},
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id
    # execute_run opens its own session; do not pass the closed one.
    asyncio.create_task(execute_run(run_id, workflow_id, default_input or "Scheduled run."))


async def _register_jobs(scheduler: AsyncIOScheduler) -> int:
    """Wipe and rebuild every scheduled job from the current workflow table."""
    scheduler.remove_all_jobs()
    registered = 0
    async with async_session_factory() as session:
        result = await session.execute(select(WorkflowModel))
        workflows = result.scalars().all()
    for workflow in workflows:
        schedule = _extract_schedule(workflow)
        if not schedule:
            continue
        try:
            trigger = CronTrigger.from_crontab(schedule["cron"], timezone=schedule.get("timezone") or "UTC")
        except Exception as exc:
            logger.warning("Workflow %s has invalid cron %r: %s", workflow.id, schedule["cron"], exc)
            continue
        scheduler.add_job(
            _trigger_scheduled_run,
            trigger=trigger,
            args=[str(workflow.id), schedule.get("input") or ""],
            id=f"workflow:{workflow.id}",
            name=f"workflow:{workflow.name}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        registered += 1
    return registered


async def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = AsyncIOScheduler(timezone="UTC")
    registered = await _register_jobs(scheduler)
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started with %d job(s).", registered)


async def reload() -> int:
    """Re-scan workflow rows and rebuild the job table. Returns number of jobs registered."""
    if _scheduler is None:
        return 0
    return await _register_jobs(_scheduler)


async def stop() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
