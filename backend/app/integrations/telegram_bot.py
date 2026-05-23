import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.config import settings
from app.db import async_session_factory
from app.models.entities import (
    Agent,
    Channel,
    Conversation,
    Message,
    MessageRole,
    Run,
    RunEvent,
    RunEventType,
    RunStatus,
    Workflow,
)
from app.runtime.workflow_runner import execute_run

log = logging.getLogger(__name__)
_bot: Any | None = None
_polling_app: Any | None = None

CALLBACK_WORKFLOW_PREFIX = "wf:"
HELP_TEXT = (
    "Hi! I'm Agent Mesh. Send any message and I'll route it through the workflow you pick.\n\n"
    "Commands:\n"
    "  /workflows — list workflows and pick one for this chat\n"
    "  /current — show the workflow currently in use\n"
    "  /help — show this message"
)


def get_bot() -> Any:
    global _bot
    if _bot is None:
        if not settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
        from telegram import Bot

        _bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    return _bot


def _default_workflow_id() -> UUID | None:
    if not settings.TELEGRAM_DEFAULT_WORKFLOW_ID:
        return None
    try:
        return UUID(settings.TELEGRAM_DEFAULT_WORKFLOW_ID)
    except (TypeError, ValueError):
        return None


async def _get_or_create_conversation(session, chat_id: str, agent_id: UUID) -> Conversation:
    result = await session.execute(
        select(Conversation).where(
            Conversation.channel == Channel.telegram,
            Conversation.external_id == str(chat_id),
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(channel=Channel.telegram, external_id=str(chat_id), agent_id=agent_id)
        session.add(conversation)
        await session.flush()
    return conversation


async def _resolve_workflow_for_chat(session, chat_id: str) -> Workflow | None:
    """Per-chat selection wins; falls back to TELEGRAM_DEFAULT_WORKFLOW_ID."""
    result = await session.execute(
        select(Conversation).where(
            Conversation.channel == Channel.telegram,
            Conversation.external_id == str(chat_id),
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation and conversation.workflow_id:
        workflow = await session.get(Workflow, conversation.workflow_id)
        if workflow:
            return workflow

    default_id = _default_workflow_id()
    if not default_id:
        return None
    return await session.get(Workflow, default_id)


async def list_available_workflows() -> list[Workflow]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Workflow).order_by(Workflow.is_template.desc(), Workflow.name)
        )
        return [w for w in result.scalars() if (w.graph or {}).get("nodes")]


async def set_workflow_for_chat(chat_id: str, workflow_id: UUID) -> Workflow | None:
    async with async_session_factory() as session:
        workflow = await session.get(Workflow, workflow_id)
        if workflow is None:
            return None
        first_agent_id = None
        nodes = (workflow.graph or {}).get("nodes") or []
        if nodes:
            try:
                first_agent_id = UUID(nodes[0]["agent_id"])
            except (KeyError, TypeError, ValueError):
                first_agent_id = None
        if first_agent_id is None:
            scalar = await session.execute(select(Agent.id).limit(1))
            first_agent_id = scalar.scalar_one_or_none()
        if first_agent_id is None:
            return None

        conversation = await _get_or_create_conversation(session, chat_id, first_agent_id)
        conversation.workflow_id = workflow.id
        conversation.agent_id = first_agent_id
        await session.commit()
        return workflow


async def get_current_workflow(chat_id: str) -> tuple[Workflow | None, str]:
    """Returns (workflow, source) where source is 'chat' or 'default'."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.channel == Channel.telegram,
                Conversation.external_id == str(chat_id),
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation and conversation.workflow_id:
            workflow = await session.get(Workflow, conversation.workflow_id)
            if workflow:
                return workflow, "chat"
        default_id = _default_workflow_id()
        if default_id:
            workflow = await session.get(Workflow, default_id)
            if workflow:
                return workflow, "default"
        return None, "none"


def _build_workflow_keyboard(workflows: list[Workflow]):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    rows = []
    for workflow in workflows:
        label = f"{workflow.name}{' (template)' if workflow.is_template else ''}"
        rows.append(
            [InlineKeyboardButton(label[:60], callback_data=f"{CALLBACK_WORKFLOW_PREFIX}{workflow.id}")]
        )
    return InlineKeyboardMarkup(rows)


async def send_workflow_picker(chat_id: str) -> None:
    workflows = await list_available_workflows()
    if not workflows:
        await get_bot().send_message(
            chat_id=chat_id, text="No workflows available yet. Ask the admin to seed templates."
        )
        return
    current, _ = await get_current_workflow(chat_id)
    header = "Pick a workflow for this chat:"
    if current:
        header += f"\n(Currently: *{current.name}*)"
    await get_bot().send_message(
        chat_id=chat_id,
        text=header,
        reply_markup=_build_workflow_keyboard(workflows),
        parse_mode="Markdown",
    )


async def handle_workflow_selection(chat_id: str, workflow_id_str: str) -> str:
    try:
        workflow_id = UUID(workflow_id_str)
    except ValueError:
        return "That workflow id is not valid."
    workflow = await set_workflow_for_chat(chat_id, workflow_id)
    if workflow is None:
        return "Workflow not found or has no agents."
    return (
        f"Got it. New messages in this chat will run *{workflow.name}*.\n"
        "Send a message to try it. Use /workflows to switch again."
    )


async def handle_incoming_message(chat_id: str, user_text: str, telegram_user: dict[str, Any]) -> None:
    """Core entry point called by both polling and webhook paths for regular text."""
    async with async_session_factory() as session:
        workflow = await _resolve_workflow_for_chat(session, str(chat_id))
        if workflow is None:
            await get_bot().send_message(
                chat_id=chat_id,
                text=(
                    "This bot has no workflow selected. Use /workflows to pick one, "
                    "or ask the admin to set TELEGRAM_DEFAULT_WORKFLOW_ID."
                ),
            )
            return

        nodes = (workflow.graph or {}).get("nodes") or []
        if not nodes:
            await get_bot().send_message(chat_id=chat_id, text=f"Workflow *{workflow.name}* has no nodes.")
            return

        try:
            first_agent_id = UUID(nodes[0]["agent_id"])
        except (KeyError, TypeError, ValueError):
            first_agent_id = None
        if first_agent_id is None:
            result = await session.execute(select(Agent.id).limit(1))
            first_agent_id = result.scalar_one_or_none()
        if first_agent_id is None:
            await get_bot().send_message(chat_id=chat_id, text="No agents are configured yet.")
            return

        conversation = await _get_or_create_conversation(session, str(chat_id), first_agent_id)
        if conversation.workflow_id is None:
            conversation.workflow_id = workflow.id

        workflow_id = workflow.id

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
                    "workflow_name": workflow.name,
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

    await execute_run(run_id, workflow_id, user_text, conversation_id=conversation_id)

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


async def _on_start(update: Any, context: Any) -> None:
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT)
    await send_workflow_picker(str(update.message.chat_id))


async def _on_help(update: Any, context: Any) -> None:
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT)


async def _on_workflows(update: Any, context: Any) -> None:
    if not update.message:
        return
    await send_workflow_picker(str(update.message.chat_id))


async def _on_current(update: Any, context: Any) -> None:
    if not update.message:
        return
    workflow, source = await get_current_workflow(str(update.message.chat_id))
    if workflow is None:
        await update.message.reply_text("No workflow selected. Use /workflows to pick one.")
        return
    suffix = "(set by you)" if source == "chat" else "(server default)"
    await update.message.reply_text(f"Current workflow: {workflow.name} {suffix}")


async def _on_callback_query(update: Any, context: Any) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    if not query.data.startswith(CALLBACK_WORKFLOW_PREFIX):
        return
    workflow_id_str = query.data[len(CALLBACK_WORKFLOW_PREFIX):]
    reply = await handle_workflow_selection(str(query.message.chat_id), workflow_id_str)
    await query.edit_message_text(reply, parse_mode="Markdown")


async def start_polling() -> None:
    global _polling_app
    if not settings.TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set; Telegram integration disabled")
        return
    if settings.TELEGRAM_MODE != "polling":
        return

    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    _polling_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    _polling_app.add_handler(CommandHandler("start", _on_start))
    _polling_app.add_handler(CommandHandler("help", _on_help))
    _polling_app.add_handler(CommandHandler("workflows", _on_workflows))
    _polling_app.add_handler(CommandHandler("current", _on_current))
    _polling_app.add_handler(CallbackQueryHandler(_on_callback_query))
    _polling_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

    await _polling_app.initialize()
    await _polling_app.start()
    await _polling_app.updater.start_polling(drop_pending_updates=True)
    log.warning("Telegram polling started for bot @%s", (await get_bot().get_me()).username)


async def stop_polling() -> None:
    global _polling_app
    if _polling_app is None:
        return
    await _polling_app.updater.stop()
    await _polling_app.stop()
    await _polling_app.shutdown()
    _polling_app = None
