from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.integrations.telegram_bot import handle_incoming_message
from app.schemas.contract import TelegramWebhookResponse

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def telegram_webhook(request: Request) -> TelegramWebhookResponse:
    if settings.TELEGRAM_MODE != "webhook":
        raise HTTPException(status_code=503, detail="Webhook mode not enabled; server is in polling mode")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message or not message.get("text"):
        return TelegramWebhookResponse(ok=True)

    chat_id = message["chat"]["id"]
    user = message.get("from", {})
    await handle_incoming_message(
        chat_id=str(chat_id),
        user_text=message["text"],
        telegram_user={
            "id": user.get("id"),
            "username": user.get("username"),
            "first_name": user.get("first_name"),
        },
    )
    return TelegramWebhookResponse(ok=True)
