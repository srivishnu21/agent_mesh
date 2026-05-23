from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.integrations.telegram_bot import (
    CALLBACK_WORKFLOW_PREFIX,
    get_bot,
    handle_incoming_message,
    handle_workflow_selection,
    send_workflow_picker,
    HELP_TEXT,
)
from app.schemas.contract import TelegramWebhookResponse

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def telegram_webhook(request: Request) -> TelegramWebhookResponse:
    if settings.TELEGRAM_MODE != "webhook":
        raise HTTPException(status_code=503, detail="Webhook mode not enabled; server is in polling mode")

    update = await request.json()

    callback = update.get("callback_query")
    if callback:
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        data = callback.get("data") or ""
        if chat_id and data.startswith(CALLBACK_WORKFLOW_PREFIX):
            workflow_id_str = data[len(CALLBACK_WORKFLOW_PREFIX):]
            reply = await handle_workflow_selection(str(chat_id), workflow_id_str)
            try:
                await get_bot().answer_callback_query(callback["id"])
            except Exception:
                pass
            await get_bot().send_message(chat_id=str(chat_id), text=reply, parse_mode="Markdown")
        return TelegramWebhookResponse(ok=True)

    message = update.get("message") or update.get("edited_message")
    if not message or not message.get("text"):
        return TelegramWebhookResponse(ok=True)

    chat_id = str(message["chat"]["id"])
    text = message["text"].strip()
    user = message.get("from", {})

    if text.startswith("/"):
        command = text.split()[0].lstrip("/").split("@")[0].lower()
        if command in {"start", "help"}:
            await get_bot().send_message(chat_id=chat_id, text=HELP_TEXT)
            if command == "start":
                await send_workflow_picker(chat_id)
            return TelegramWebhookResponse(ok=True)
        if command == "workflows":
            await send_workflow_picker(chat_id)
            return TelegramWebhookResponse(ok=True)
        if command == "current":
            from app.integrations.telegram_bot import get_current_workflow

            workflow, source = await get_current_workflow(chat_id)
            if workflow is None:
                await get_bot().send_message(chat_id=chat_id, text="No workflow selected. Use /workflows to pick one.")
            else:
                suffix = "(set by you)" if source == "chat" else "(server default)"
                await get_bot().send_message(chat_id=chat_id, text=f"Current workflow: {workflow.name} {suffix}")
            return TelegramWebhookResponse(ok=True)
        await get_bot().send_message(chat_id=chat_id, text=f"Unknown command {text}. Try /help.")
        return TelegramWebhookResponse(ok=True)

    await handle_incoming_message(
        chat_id=chat_id,
        user_text=text,
        telegram_user={
            "id": user.get("id"),
            "username": user.get("username"),
            "first_name": user.get("first_name"),
        },
    )
    return TelegramWebhookResponse(ok=True)
