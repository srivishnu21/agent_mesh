from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Channel
from app.models.entities import Conversation as ConversationModel
from app.models.entities import Message as MessageModel
from app.schemas.contract import Conversation, ConversationDetail, Message

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[Conversation])
async def list_conversations(
    channel: Channel | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationModel]:
    stmt = select(ConversationModel).offset(offset).limit(limit).order_by(ConversationModel.created_at)
    if channel:
        stmt = stmt.where(ConversationModel.channel == channel)
    result = await db.execute(stmt)
    return list(result.scalars())


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
