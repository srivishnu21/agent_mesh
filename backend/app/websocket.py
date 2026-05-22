import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/runs/{run_id}")
async def run_events_socket(websocket: WebSocket, run_id: UUID) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(
                {
                    "id": str(uuid4()),
                    "run_id": str(run_id),
                    "agent_id": None,
                    "event_type": "agent_message",
                    "payload": {"message": "Stub heartbeat event for UI development"},
                    "tokens": 0,
                    "cost_usd": "0.0000",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
