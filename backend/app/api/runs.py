from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Run as RunModel
from app.models.entities import RunEvent as RunEventModel
from app.models.entities import RunStatus
from app.schemas.contract import Run, RunDetail, RunEvent

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[Run])
async def list_runs(
    workflow_id: UUID | None = None,
    status: RunStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[RunModel]:
    stmt = select(RunModel).offset(offset).limit(limit).order_by(RunModel.started_at.desc().nullslast())
    if workflow_id:
        stmt = stmt.where(RunModel.workflow_id == workflow_id)
    if status:
        stmt = stmt.where(RunModel.status == status)
    result = await db.execute(stmt)
    return list(result.scalars())


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: UUID, event_limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)) -> RunDetail:
    run = await db.get(RunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await db.execute(
        select(RunEventModel).where(RunEventModel.run_id == run_id).order_by(RunEventModel.created_at.desc()).limit(event_limit)
    )
    data = Run.model_validate(run).model_dump()
    data["events"] = list(result.scalars())
    return RunDetail.model_validate(data)


@router.get("/{run_id}/events", response_model=list[RunEvent])
async def list_run_events(
    run_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[RunEventModel]:
    if not await db.get(RunModel, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    result = await db.execute(
        select(RunEventModel).where(RunEventModel.run_id == run_id).offset(offset).limit(limit).order_by(RunEventModel.created_at)
    )
    return list(result.scalars())
