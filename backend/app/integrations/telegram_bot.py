import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.config import settings
from app.db import async_session_factory
from app.models.entities import Agent, Channel, Conversation, Message, MessageRole, Run, RunEvent, RunEventType, RunStatus, Workflow
from app.runtime.workflow_runner import execute_run

log = logging.getLogger(__name__)
_bot: Any | None = None
_polling_app: Any | None = None


def get_bot() -> Any:
    global _bot
    if _bot is None:
        if not settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
        from telegram import Bot

        _bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    return _bot


async def handle_incoming_message(chat_id: str, user_text: str, telegram_user: dict[str, Any]) -> None:
    """Core entry point called by both polling and webhook paths."""
    if not settings.TELEGRAM_DEFAULT_WORKFLOW_ID:
        log.error("TELEGRAM_DEFAULT_WORKFLOW_ID not configured")
        await get_bot().send_message(
            chat_id=chat_id,
            text="This bot is not configured yet. Ask the admin to set a default workflow.",
        )
        return

    workflow_id = UUID(settings.TELEGRAM_DEFAULT_WORKFLOW_ID)

    async with async_session_factory() as session:
        workflow = await session.get(Workflow, workflow_id)
        if not workflow:
            await get_bot().send_message(chat_id=chat_id, text="The configured Telegram workflow was not found.")
            return

        agent_id = UUID(workflow.graph["nodes"][0]["agent_id"]) if workflow.graph.get("nodes") else None
        if agent_id is None:
            result = await session.execute(select(Agent.id).limit(1))
            agent_id = result.scalar_one_or_none()
        if agent_id is None:
            await get_bot().send_message(chat_id=chat_id, text="No agents are configured yet.")
            return

        result = await session.execute(
            select(Conversation).where(
                Conversation.channel == Channel.telegram,
                Conversation.external_id == str(chat_id),
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            conversation = Conversation(channel=Channel.telegram, external_id=str(chat_id), agent_id=agent_id)
            session.add(conversation)
            await session.flush()

        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.user,
            content=user_text,
            metadata_={"telegram_chat_id": str(chat_id), "telegram_user": telegram_user},
        )
        session.add(user_message)

        run = Run(
            id=uuid4(),
            workflow_id=workflow_id,
            status=RunStatus.pending,
            trigger={
                "source": "telegram",
                "payload": {
                    "chat_id": str(chat_id),
                    "input": user_text,
                    "conversation_id": str(conversation.id),
                    "telegram_user": telegram_user,
                },
            },
        )
        session.add(run)
        await session.commit()
        run_id = run.id
        conversation_id = conversation.id

    try:
        await get_bot().send_chat_action(chat_id=chat_id, action="typing")
    except Exception as exc:
        log.warning("Failed to send Telegram typing indicator: %s", exc)

    await execute_run(run_id, workflow_id, user_text)

    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        result = await session.execute(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.event_type == RunEventType.agent_message)
            .order_by(RunEvent.created_at.desc())
        )
        final_text = None
        events = result.scalars().all()
        if events:
            final_text = events[0].payload.get("content", "")

        if not final_text:
            result = await session.execute(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.event_type == RunEventType.run_completed)
                .order_by(RunEvent.created_at.desc())
            )
            event = result.scalar_one_or_none()
            if event:
                final_text = event.payload.get("final_message", "")

        if not final_text and run and run.status == RunStatus.failed:
            final_text = f"Sorry, something went wrong: {run.error or 'workflow failed'}"
        if not final_text:
            final_text = "I processed your request but did not produce a response. Try again."

        session.add(
            Message(
                conversation_id=conversation_id,
                role=MessageRole.agent,
                content=final_text,
                metadata_={"run_id": str(run_id)},
            )
        )
        await session.commit()

    chunks = [final_text[index : index + 4000] for index in range(0, len(final_text), 4000)] or [""]
    for chunk in chunks:
        await get_bot().send_message(chat_id=chat_id, text=chunk)


async def _on_message(update: Any, context: Any) -> None:
    if not update.message or not update.message.text:
        return
    user = update.message.from_user
    await handle_incoming_message(
        chat_id=str(update.message.chat_id),
        user_text=update.message.text,
        telegram_user={
            "id": user.id if user else None,
            "username": user.username if user else None,
            "first_name": user.first_name if user else None,
        },
    )


async def start_polling() -> None:
    global _polling_app
    if not settings.TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set; Telegram integration disabled")
        return
    if settings.TELEGRAM_MODE != "polling":
        return

    from telegram.ext import Application, MessageHandler, filters

    _polling_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    _polling_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

    await _polling_app.initialize()
    await _polling_app.start()
    await _polling_app.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram polling started")


async def stop_polling() -> None:
    global _polling_app
    if _polling_app is None:
        return
    await _polling_app.updater.stop()
    await _polling_app.stop()
    await _polling_app.shutdown()
    _polling_app = None
