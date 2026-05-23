from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Agent, Run, RunEvent, Workflow
from app.schemas.contract import (
    DashboardAgentCost,
    DashboardCostPoint,
    DashboardRecentRun,
    DashboardStats,
)

router = APIRouter(prefix="/stats", tags=["stats"])

_TREND_DAYS = 7


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    today_utc = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today_utc, time.min, tzinfo=timezone.utc)
    trend_start = datetime.combine(today_utc - timedelta(days=_TREND_DAYS - 1), time.min, tzinfo=timezone.utc)

    agents = await db.scalar(select(func.count(Agent.id)))
    workflows = await db.scalar(select(func.count(Workflow.id)))
    runs_today = await db.scalar(select(func.count(Run.id)).where(Run.started_at >= today_start))
    tokens_today = await db.scalar(
        select(func.coalesce(func.sum(Run.total_tokens), 0)).where(Run.started_at >= today_start)
    )
    cost_today = await db.scalar(
        select(func.coalesce(func.sum(Run.total_cost_usd), 0)).where(Run.started_at >= today_start)
    )

    recent_result = await db.execute(
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
        for run, workflow_name in recent_result.all()
    ]

    cost_trend = await _cost_trend(db, today_utc, trend_start)
    agent_cost = await _agent_cost(db, trend_start)

    return DashboardStats(
        agents=agents or 0,
        workflows=workflows or 0,
        runs_today=runs_today or 0,
        tokens_today=tokens_today or 0,
        cost_today_usd=Decimal(cost_today or 0),
        recent_runs=recent_runs,
        cost_trend=cost_trend,
        agent_cost=agent_cost,
    )


async def _cost_trend(db: AsyncSession, today: date, trend_start: datetime) -> list[DashboardCostPoint]:
    result = await db.execute(
        select(Run.started_at, Run.total_tokens, Run.total_cost_usd).where(Run.started_at >= trend_start)
    )
    aggregates: dict[str, list] = defaultdict(lambda: [0, Decimal("0"), 0])
    for started_at, tokens, cost in result.all():
        if not started_at:
            continue
        key = started_at.date().isoformat()
        bucket = aggregates[key]
        bucket[0] += int(tokens or 0)
        bucket[1] += Decimal(cost or 0)
        bucket[2] += 1
    points: list[DashboardCostPoint] = []
    for offset in range(_TREND_DAYS):
        day = today - timedelta(days=_TREND_DAYS - 1 - offset)
        tokens, cost, runs = aggregates.get(day.isoformat(), [0, Decimal("0"), 0])
        points.append(DashboardCostPoint(date=day.isoformat(), tokens=tokens, cost_usd=cost, runs=runs))
    return points


async def _agent_cost(db: AsyncSession, trend_start: datetime) -> list[DashboardAgentCost]:
    result = await db.execute(
        select(
            RunEvent.agent_id,
            Agent.name,
            func.coalesce(func.sum(RunEvent.tokens), 0),
            func.coalesce(func.sum(RunEvent.cost_usd), 0),
            func.count(func.distinct(RunEvent.run_id)),
        )
        .join(Agent, Agent.id == RunEvent.agent_id, isouter=True)
        .where(RunEvent.created_at >= trend_start)
        .group_by(RunEvent.agent_id, Agent.name)
        .order_by(func.coalesce(func.sum(RunEvent.cost_usd), 0).desc())
        .limit(10)
    )
    rows = []
    for agent_id, name, tokens, cost, runs in result.all():
        if agent_id is None and not name:
            continue
        rows.append(
            DashboardAgentCost(
                agent_id=agent_id,
                agent_name=name or "(orchestrator)",
                runs=int(runs or 0),
                tokens=int(tokens or 0),
                cost_usd=Decimal(cost or 0),
            )
        )
    return rows
