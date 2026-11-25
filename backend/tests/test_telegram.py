"""Telegram webhook: secret check, commands, cited answers, limits; Telegram itself faked."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from qanoun_api import telegram
from qanoun_api.main import app
from qanoun_api.routers import telegram as webhook

client = TestClient(app)
TOKEN = "123:test-token"
SECRET = {"X-Telegram-Bot-Api-Secret-Token": telegram.webhook_secret(TOKEN)}
SOURCE = {"law_slug": "family-code-ar", "law_title": "مدونة الأسرة", "language": "ar", "article_number": "19"}


def update(text: str = "ما هو سن الزواج؟", chat_type: str = "private") -> dict:
    return {"update_id": 1, "message": {"message_id": 5, "chat": {"id": 42, "type": chat_type}, "text": text}}


@pytest.fixture
def bot(monkeypatch):
    """Token set, web reader address set, Telegram calls and the query log recorded."""
    settings = replace(telegram.SETTINGS, telegram_token=TOKEN, web_url="https://qanoun.example")
    monkeypatch.setattr(telegram, "SETTINGS", settings)
    monkeypatch.setattr(webhook, "SETTINGS", settings)
    sent: list[tuple[int, str]] = []
    monkeypatch.setattr(telegram, "send_message", lambda chat_id, text: sent.append((chat_id, text)))
    monkeypatch.setattr(telegram, "send_typing", lambda chat_id: None)
    logged = []
    monkeypatch.setattr(webhook.querylog, "write", logged.append)
    monkeypatch.setattr(webhook.chat_limit, "check", lambda key, limit=None: None)
    return sent, logged


def answer_with(monkeypatch, events):
    monkeypatch.setattr(webhook, "_chat_events", lambda req: iter(events))


def test_off_without_a_token():
    assert client.post("/api/telegram/webhook", json=update()).status_code == 404


def test_refuses_calls_without_telegrams_secret(bot):
    assert client.post("/api/telegram/webhook", json=update()).status_code == 403
    wrong = {"X-Telegram-Bot-Api-Secret-Token": "guess"}
    assert client.post("/api/telegram/webhook", json=update(), headers=wrong).status_code == 403
    assert bot[0] == []


def test_start_explains_the_bot(bot):
    assert client.post("/api/telegram/webhook", json=update("/start"), headers=SECRET).json() == {"ok": True}
    assert "قانون" in bot[0][0][1] and "pas un conseil juridique" in bot[0][0][1]


def test_a_question_gets_a_cited_answer_with_links(bot, monkeypatch):
    seen = {}

    def events(req):
        seen["question"] = req.question
        yield ("sources", {"sources": [{**SOURCE, "article_number": "20"}, SOURCE]})
        # «[2]» in the text; `cited` is 0-based (answer.parse_citations), as /api/chat sends it
        yield ("done", {"abstained": False, "cited": [1], "text": "سن الزواج 18 سنة <b> [2]"})

    monkeypatch.setattr(webhook, "_chat_events", events)
    client.post("/api/telegram/webhook", json=update("شحال خاص يكون العمر باش تزوج؟"), headers=SECRET)
    chat_id, text = bot[0][0]
    assert chat_id == 42 and seen["question"] == "شحال خاص يكون العمر باش تزوج؟"
    assert text.startswith("سن الزواج 18 سنة &lt;b&gt; [2]")  # model text is escaped for HTML mode
    assert '[2] <a href="https://qanoun.example/ar/laws/family-code-ar#article-19">مدونة الأسرة — المادة 19</a>' in text
    assert "article-20" not in text  # only what the answer cites
    assert len(bot[1]) == 1  # logged like a web question


def test_no_answer_and_errors_still_reply(bot, monkeypatch):
    answer_with(monkeypatch, [("sources", {"sources": []}), ("done", {"abstained": True, "cited": [], "text": "لا أجد"})])
    client.post("/api/telegram/webhook", json=update(), headers=SECRET)
    assert bot[0][-1][1] == "لا أجد"

    answer_with(monkeypatch, [("error", {"code": "quota", "message": "429"})])
    client.post("/api/telegram/webhook", json=update(), headers=SECRET)
    assert bot[0][-1][1] == webhook.FAILED

    def crash(req):
        raise RuntimeError("database down")

    monkeypatch.setattr(webhook, "_chat_events", crash)
    response = client.post("/api/telegram/webhook", json=update(), headers=SECRET)
    assert response.status_code == 200  # Telegram must not redeliver (the user would get it twice)
    assert bot[0][-1][1] == webhook.FAILED


def test_rate_limited_per_chat(bot, monkeypatch):
    keys = []
    monkeypatch.setattr(webhook.chat_limit, "check", lambda key, limit=None: keys.append(key) or 30.0)
    client.post("/api/telegram/webhook", json=update(), headers=SECRET)
    assert keys == ["telegram:42"] and bot[0][0][1] == webhook.TOO_MANY


def test_groups_and_non_text_messages(bot):
    client.post("/api/telegram/webhook", json=update(chat_type="group"), headers=SECRET)
    assert bot[0] == []  # quiet in groups
    client.post("/api/telegram/webhook", json=update(""), headers=SECRET)
    assert bot[0][0][1] == webhook.ONLY_TEXT


def test_long_answers_keep_their_sources():
    text = telegram.format_answer("كلمة " * 2000, [SOURCE], [0])
    assert len(text) <= telegram.MAX_MESSAGE and text.endswith("المادة 19")


def test_the_token_never_reaches_the_logs(caplog):
    import logging

    url = "https://api.telegram.org/bot123456:AAH-secret_token/sendMessage"
    with caplog.at_level(logging.INFO, logger="httpx"):
        logging.getLogger("httpx").info('HTTP Request: %s %s "%s"', "POST", url, "HTTP/1.1 200 OK")
    assert "secret_token" not in caplog.text and "123456" not in caplog.text
    assert "/bot<redacted>/sendMessage" in caplog.text
