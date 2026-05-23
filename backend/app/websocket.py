import asyncio
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db import SessionLocal
from app.models.entities import RunEvent

router = APIRouter(tags=["websocket"])


def serialize_run_event(event: RunEvent) -> dict:
    return {
        "id": str(event.id),
        "run_id": str(event.run_id),
        "agent_id": str(event.agent_id) if event.agent_id else None,
        "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
        "payload": event.payload,
        "tokens": event.tokens,
        "cost_usd": float(event.cost_usd if isinstance(event.cost_usd, Decimal) else event.cost_usd),
        "created_at": event.created_at.isoformat(),
    }


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[run_id].add(websocket)

    async def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[run_id].discard(websocket)
            if not self._connections[run_id]:
                del self._connections[run_id]

    async def broadcast(self, run_id: str, message: dict) -> None:
        async with self._lock:
            targets = list(self._connections.get(run_id, set()))
        dead = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            await self.disconnect(run_id, websocket)


ws_manager = WebSocketManager()


async def replay_history(run_id: UUID, websocket: WebSocket) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.created_at)
        )
        for event in result.scalars():
            await websocket.send_json(serialize_run_event(event))


@router.websocket("/ws/runs/{run_id}")
async def run_events_socket(websocket: WebSocket, run_id: UUID) -> None:
    run_key = str(run_id)
    await ws_manager.connect(run_key, websocket)
    await replay_history(run_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(run_key, websocket)
