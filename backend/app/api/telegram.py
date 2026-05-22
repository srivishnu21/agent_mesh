from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Agent, Channel, Conversation, Message, MessageRole
from app.schemas.contract import TelegramWebhookResponse

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def telegram_webhook(update: dict[str, Any], db: AsyncSession = Depends(get_db)) -> TelegramWebhookResponse:
    message_payload = update.get("message", {})
    chat = message_payload.get("chat", {})
    external_id = str(chat.get("id", "unknown"))
    content = message_payload.get("text", "")

    agent = (await db.execute(select(Agent).limit(1))).scalar_one_or_none()
    if not agent:
        return TelegramWebhookResponse(ok=False)

    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.channel == Channel.telegram,
                Conversation.external_id == external_id,
                Conversation.agent_id == agent.id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        conversation = Conversation(channel=Channel.telegram, external_id=external_id, agent_id=agent.id)
        db.add(conversation)
        await db.flush()

    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=content,
        metadata_={"telegram_update_id": update.get("update_id")},
    )
    db.add(message)
    await db.commit()
    await db.refresh(conversation)
    await db.refresh(message)
    return TelegramWebhookResponse(ok=True, conversation_id=conversation.id, message_id=message.id)
