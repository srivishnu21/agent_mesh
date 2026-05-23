from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Agent, Run, Workflow
from app.schemas.contract import DashboardRecentRun, DashboardStats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)

    agents = await db.scalar(select(func.count(Agent.id)))
    workflows = await db.scalar(select(func.count(Workflow.id)))
    runs_today = await db.scalar(select(func.count(Run.id)).where(Run.started_at >= today_start))
    tokens_today = await db.scalar(select(func.coalesce(func.sum(Run.total_tokens), 0)).where(Run.started_at >= today_start))

    result = await db.execute(
        select(Run, Workflow.name)
        .join(Workflow, Workflow.id == Run.workflow_id)
        .order_by(Run.started_at.desc().nullslast(), Run.id.desc())
        .limit(10)
    )
    recent_runs = [
        DashboardRecentRun(
            id=run.id,
            workflow_id=run.workflow_id,
            workflow_name=workflow_name,
            status=run.status,
            started_at=run.started_at,
            total_tokens=run.total_tokens,
            total_cost_usd=run.total_cost_usd,
        )
        for run, workflow_name in result.all()
    ]

    return DashboardStats(
        agents=agents or 0,
        workflows=workflows or 0,
        runs_today=runs_today or 0,
        tokens_today=tokens_today or 0,
        recent_runs=recent_runs,
    )
