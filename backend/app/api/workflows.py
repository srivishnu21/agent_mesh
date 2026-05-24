import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Conversation as ConversationModel
from app.models.entities import Run as RunModel
from app.models.entities import Workflow as WorkflowModel
from app.runtime.workflow_runner import execute_run
from app.scheduler import reload as reload_scheduler
from app.schemas.contract import RunCreate, RunTriggerResponse, Workflow, WorkflowCreate, WorkflowUpdate

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=Workflow, status_code=status.HTTP_201_CREATED)
async def create_workflow(payload: WorkflowCreate, db: AsyncSession = Depends(get_db)) -> WorkflowModel:
    workflow = WorkflowModel(**payload.model_dump())
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    await reload_scheduler()
    return workflow


@router.get("", response_model=list[Workflow])
async def list_workflows(
    is_template: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowModel]:
    stmt = select(WorkflowModel).offset(offset).limit(limit).order_by(WorkflowModel.created_at)
    if is_template is not None:
        stmt = stmt.where(WorkflowModel.is_template == is_template)
    result = await db.execute(stmt)
    return list(result.scalars())


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: UUID, db: AsyncSession = Depends(get_db)) -> WorkflowModel:
    workflow = await db.get(WorkflowModel, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.patch("/{workflow_id}", response_model=Workflow)
async def update_workflow(workflow_id: UUID, payload: WorkflowUpdate, db: AsyncSession = Depends(get_db)) -> WorkflowModel:
    workflow = await db.get(WorkflowModel, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(workflow, key, value)
    await db.commit()
    await db.refresh(workflow)
    await reload_scheduler()
    return workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    force: bool = Query(False, description="Cascade-delete linked runs and detach conversations."),
    db: AsyncSession = Depends(get_db),
) -> None:
    workflow = await db.get(WorkflowModel, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    run_count = (
        await db.execute(select(func.count(RunModel.id)).where(RunModel.workflow_id == workflow_id))
    ).scalar_one()

    if run_count and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow has {run_count} run(s). Re-issue DELETE with ?force=true to cascade-delete runs and events.",
        )

    if run_count:
        # Cascade: delete runs (run_events auto-cascade via relationship), detach conversations.
        runs = (
            await db.execute(select(RunModel).where(RunModel.workflow_id == workflow_id))
        ).scalars().all()
        for run in runs:
            await db.delete(run)
        await db.execute(
            ConversationModel.__table__.update()
            .where(ConversationModel.workflow_id == workflow_id)
            .values(workflow_id=None)
        )

    await db.delete(workflow)
    await db.commit()
    await reload_scheduler()


@router.post("/{workflow_id}/run", response_model=RunTriggerResponse, status_code=status.HTTP_201_CREATED)
async def trigger_workflow(workflow_id: UUID, payload: RunCreate, db: AsyncSession = Depends(get_db)) -> RunTriggerResponse:
    workflow = await db.get(WorkflowModel, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    user_input = payload.input or str(payload.trigger.get("payload", {}).get("input") or payload.trigger.get("input") or "")
    if not user_input.strip():
        raise HTTPException(status_code=422, detail="Run input is required")
    run = RunModel(
        workflow_id=workflow_id,
        trigger={"source": "manual", "payload": {"input": user_input}},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    asyncio.create_task(execute_run(run.id, workflow_id, user_input))
    return RunTriggerResponse(run_id=run.id)
