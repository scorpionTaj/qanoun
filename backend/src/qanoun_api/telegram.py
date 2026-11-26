"""Telegram bot: ask Qanoun in a private chat, get a cited answer with links to the articles.

Off unless QANOUN_TELEGRAM_TOKEN is set (from @BotFather). Telegram calls the webhook
(routers/telegram.py) for each message; register it once the API is deployed:

    QANOUN_TELEGRAM_TOKEN=… uv run --project backend python -m qanoun_api.telegram \\
        set-webhook https://<api-host>/api/telegram/webhook

Telegram sends the secret derived here in a header on every call, so only Telegram can post
to the webhook; it is derived from the token, so there is no second secret to manage.
"""

import argparse
import hashlib
import hmac
import html
import logging
import re
import sys

import httpx

from qanoun_api.config import SETTINGS

API = "https://api.telegram.org/bot{token}/{method}"
_TOKEN_IN_URL = re.compile(r"/bot\d+:[A-Za-z0-9_-]+/")


class _RedactToken(logging.Filter):
    """Telegram puts the bot token in the URL, and httpx logs every request URL at INFO:
    mask it, or the token ends up in the host's logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "/bot" in message:
            record.msg, record.args = _TOKEN_IN_URL.sub("/bot<redacted>/", message), ()
        return True


logging.getLogger("httpx").addFilter(_RedactToken())
MAX_MESSAGE = 4096  # Telegram's limit, in characters


def webhook_secret(token: str) -> str:
    """The `secret_token` Telegram must send back: [A-Za-z0-9_-], up to 256 characters."""
    return hmac.new(token.encode(), b"qanoun-telegram-webhook", hashlib.sha256).hexdigest()


def call(method: str, payload: dict, token: str | None = None) -> dict:
    response = httpx.post(API.format(token=token or SETTINGS.telegram_token, method=method), json=payload, timeout=20)
    return response.json()


def send_message(chat_id: int, text: str) -> None:
    call("sendMessage", {"chat_id": chat_id, "text": text[:MAX_MESSAGE], "parse_mode": "HTML",
                         "link_preview_options": {"is_disabled": True}})


def send_typing(chat_id: int) -> None:
    call("sendChatAction", {"chat_id": chat_id, "action": "typing"})


def _source_line(n: int, source: dict) -> str:
    french = source["language"] == "fr"
    title = (french and source.get("law_title_fr")) or source["law_title"]
    label = html.escape(f"{title} — {'Article' if french else 'المادة'} {source['article_number']}")
    if not SETTINGS.web_url:
        return f"[{n}] {label}"
    locale = "fr" if source["language"] == "fr" else "ar"
    url = f"{SETTINGS.web_url}/{locale}/laws/{source['law_slug']}#article-{source['article_number']}"
    return f'[{n}] <a href="{html.escape(url, quote=True)}">{label}</a>'


def format_answer(text: str, sources: list[dict], cited: list[int]) -> str:
    """The answer (HTML-escaped) and the sources it cites, as links into the reader.

    `cited` holds 0-based source indexes (answer.parse_citations): «[2]» in the text is 1.

    The sources go first in the budget: an answer cut short keeps its citations."""
    lines = [_source_line(i + 1, sources[i]) for i in cited if 0 <= i < len(sources)]
    footer = ("\n\n📚 " + "\n".join(lines)) if lines else ""
    body = html.escape(text)
    room = MAX_MESSAGE - len(footer) - 1
    if len(body) > room:
        body = body[: room - 1].rsplit(" ", 1)[0] + "…"
    return body + footer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Telegram bot setup")
    sub = parser.add_subparsers(dest="command", required=True)
    hook = sub.add_parser("set-webhook", help="point the bot at the API's webhook")
    hook.add_argument("url")
    sub.add_parser("info", help="show the webhook Telegram has")
    args = parser.parse_args(argv)
    token = SETTINGS.telegram_token
    if not token:
        print("QANOUN_TELEGRAM_TOKEN is not set", file=sys.stderr)
        return 1
    if args.command == "set-webhook":
        result = call("setWebhook", {"url": args.url, "secret_token": webhook_secret(token),
                                     "allowed_updates": ["message"], "drop_pending_updates": True})
        call("setMyCommands", {"commands": [{"command": "start", "description": "Qanoun: how to ask"}]})
    else:
        result = call("getWebhookInfo", {})
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
