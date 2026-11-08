"""Synced conversations for signed-in users (last write wins, by the client's timestamp)."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from qanoun_api.db import db
from qanoun_api.routers.auth import User, same_origin_json

router = APIRouter(prefix="/api/conversations", tags=["conversations"], dependencies=[Depends(same_origin_json)])

MAX_CONVERSATIONS = 200
MAX_BYTES = 1_000_000  # one conversation's messages


class ConversationIn(BaseModel):
    title: str = Field(default="", max_length=300)
    updated_at: int = Field(ge=0)
    messages: list[dict] = Field(max_length=400)


@router.get("")
def list_conversations(user: User):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at, messages FROM conversations WHERE user_id = %s "
            "ORDER BY updated_at DESC LIMIT %s",
            (user["id"], MAX_CONVERSATIONS),
        ).fetchall()
    return [{"id": r[0], "title": r[1], "updatedAt": r[2], "messages": r[3]} for r in rows]


@router.put("/{conversation_id}")
def put_conversation(conversation_id: str, body: ConversationIn, user: User):
    if not 1 <= len(conversation_id) <= 64:
        raise HTTPException(422, "bad id")
    payload = json.dumps(body.messages, ensure_ascii=False)
    if len(payload.encode()) > MAX_BYTES:
        raise HTTPException(413, "conversation too large")
    with db() as conn:
        count = conn.execute(
            "SELECT count(*) FROM conversations WHERE user_id = %s AND id <> %s",
            (user["id"], conversation_id),
        ).fetchone()[0]
        if count >= MAX_CONVERSATIONS:
            raise HTTPException(409, f"limit of {MAX_CONVERSATIONS} conversations reached")
        # last write wins: an older copy never overwrites a newer one
        conn.execute(
            """
            INSERT INTO conversations (user_id, id, title, updated_at, messages)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (user_id, id) DO UPDATE
               SET title = EXCLUDED.title, updated_at = EXCLUDED.updated_at,
                   messages = EXCLUDED.messages
             WHERE conversations.updated_at <= EXCLUDED.updated_at
            """,
            (user["id"], conversation_id, body.title, body.updated_at, payload),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, user: User):
    with db() as conn:
        conn.execute("DELETE FROM conversations WHERE user_id = %s AND id = %s", (user["id"], conversation_id))
        conn.commit()
    return {"ok": True}


@router.delete("")
def delete_all(user: User):
    with db() as conn:
        conn.execute("DELETE FROM conversations WHERE user_id = %s", (user["id"],))
        conn.commit()
    return {"ok": True}
