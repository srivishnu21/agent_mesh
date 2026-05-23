from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Channel
from app.models.entities import Conversation as ConversationModel
from app.models.entities import Message as MessageModel
from app.schemas.contract import Conversation, ConversationDetail, ConversationSummary, Message

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    channel: Channel | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    stmt = select(ConversationModel).offset(offset).limit(limit).order_by(ConversationModel.created_at)
    if channel:
        stmt = stmt.where(ConversationModel.channel == channel)
    result = await db.execute(stmt)
    conversations = list(result.scalars())
    summaries: list[ConversationSummary] = []
    for conversation in conversations:
        count = await db.scalar(select(func.count(MessageModel.id)).where(MessageModel.conversation_id == conversation.id))
        last_message = (
            await db.execute(
                select(MessageModel)
                .where(MessageModel.conversation_id == conversation.id)
                .order_by(MessageModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        telegram_user = None
        if last_message and isinstance(last_message.metadata_, dict):
            telegram_user = last_message.metadata_.get("telegram_user")
        data = Conversation.model_validate(conversation).model_dump()
        data.update(
            {
                "last_message_preview": last_message.content[:160] if last_message else None,
                "last_message_at": last_message.created_at if last_message else None,
                "message_count": count or 0,
                "telegram_user": telegram_user,
            }
        )
        summaries.append(ConversationSummary.model_validate(data))
    return summaries


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    message_limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conversation = await db.get(ConversationModel, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at.desc())
        .limit(message_limit)
    )
    data = Conversation.model_validate(conversation).model_dump()
    data["messages"] = list(result.scalars())
    return ConversationDetail.model_validate(data)


@router.get("/{conversation_id}/messages", response_model=list[Message])
async def list_messages(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MessageModel]:
    if not await db.get(ConversationModel, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .offset(offset)
        .limit(limit)
        .order_by(MessageModel.created_at)
    )
    return list(result.scalars())
