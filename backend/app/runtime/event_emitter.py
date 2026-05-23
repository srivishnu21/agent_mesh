from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import RunEvent, RunEventType
from app.websocket import serialize_run_event, ws_manager


async def emit(
    session: AsyncSession,
    run_id: UUID,
    event_type: str,
    payload: dict,
    agent_id: UUID | None = None,
    tokens: int = 0,
    cost_usd: Decimal | float = 0,
) -> None:
    event = RunEvent(
        run_id=run_id,
        agent_id=agent_id,
        event_type=RunEventType(event_type),
        payload=payload,
        tokens=tokens,
        cost_usd=Decimal(str(cost_usd)),
    )
    session.add(event)
    await session.flush()
    await session.commit()
    await session.refresh(event)
    await ws_manager.broadcast(str(run_id), serialize_run_event(event))
