"""Telegram webhook: each private message is a question, answered like /api/chat.

It answers 200 to Telegram whatever happens (failures go to the user as a message): any other
status makes Telegram redeliver the update, and the user would get the answer twice.
"""

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from qanoun_api import querylog, telegram
from qanoun_api.config import SETTINGS
from qanoun_api.ratelimit import chat_limit
from qanoun_api.routers.chat import ChatRequest, _chat_events

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
log = logging.getLogger(__name__)

WELCOME = (
    "مرحبا بك في <b>قانون</b> 🇲🇦\n"
    "اطرح سؤالك عن القانون المغربي بالعربية أو الدارجة أو الفرنسية، وسأجيبك من النصوص الرسمية مع ذكر المواد.\n\n"
    "Posez votre question sur le droit marocain : la réponse cite les articles des textes officiels.\n\n"
    "Ask about Moroccan law in English too.\n\n"
    "<i>معلومات قانونية وليست استشارة قانونية · Information juridique, pas un conseil juridique.</i>"
)


def welcome() -> str:
    """WELCOME, with a link to the privacy notice when the web app's address is known (law 09-08)."""
    if not SETTINGS.web_url:
        return WELCOME
    return WELCOME + f'\n\n🔒 <a href="{SETTINGS.web_url}/fr/privacy">Confidentialité · الخصوصية · Privacy</a>'


TOO_MANY = "⏳ أسئلة كثيرة في وقت قصير. حاول بعد دقيقة.\nTrop de questions : réessayez dans une minute."
FAILED = "⚠️ تعذر الحصول على جواب الآن. حاول مرة أخرى.\nImpossible de répondre pour le moment, réessayez."
ONLY_TEXT = "✍️ أرسل سؤالك نصا. · Envoyez votre question sous forme de texte."


@router.post("/webhook", include_in_schema=False)
def webhook(update: dict, request: Request):
    token = SETTINGS.telegram_token
    if not token:
        raise HTTPException(404)
    sent = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not hmac.compare_digest(sent, telegram.webhook_secret(token)):
        raise HTTPException(403)

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    if chat.get("type") != "private":  # groups and channels: stay quiet
        return {"ok": True}
    chat_id, text = chat["id"], (message.get("text") or "").strip()
    try:
        _handle(chat_id, text)
    except Exception:
        log.exception("telegram update failed")
        try:
            telegram.send_message(chat_id, FAILED)
        except Exception:
            log.exception("telegram reply failed")
    return {"ok": True}


def _handle(chat_id: int, text: str) -> None:
    if not text:
        telegram.send_message(chat_id, ONLY_TEXT)
        return
    if text.startswith("/"):  # /start, /help, anything else: how to use the bot
        telegram.send_message(chat_id, welcome())
        return
    if chat_limit.check(f"telegram:{chat_id}") is not None:
        telegram.send_message(chat_id, TOO_MANY)
        return
    telegram.send_typing(chat_id)

    question = text[:1000]
    record = querylog.QueryRecord(question=question)
    sources: list[dict] = []
    reply = FAILED
    try:
        for event, data in _chat_events(ChatRequest(question=question)):
            record.observe(event, data)
            if event == "sources":
                sources = data["sources"]
            elif event == "done":
                reply = telegram.format_answer(data["text"], sources, data["cited"])
            elif event == "error":
                log.warning("telegram answer failed: %s", data)
    finally:
        querylog.write(record)
    telegram.send_message(chat_id, reply)
