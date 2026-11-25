"""API keys of the signed-in user: list, create (the key is shown once), revoke.

A key only identifies its owner to the rate limiter (see qanoun_api.ratelimit): read endpoints
stay open without one, and a key never opens the owner's account or conversations.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from qanoun_api import accounts
from qanoun_api.db import db
from qanoun_api.routers.auth import User, same_origin_json

router = APIRouter(prefix="/api/keys", tags=["api keys"], dependencies=[Depends(same_origin_json)])


class NewKey(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.get("")
def list_keys(user: User):
    with db() as conn:
        return accounts.list_api_keys(conn, user["id"])


@router.post("", status_code=201)
def create_key(body: NewKey, user: User):
    with db() as conn:
        key = accounts.create_api_key(conn, user["id"], body.name.strip() or "key")
    if key is None:
        raise HTTPException(409, f"at most {accounts.MAX_KEYS} active keys: revoke one first")
    return key


@router.delete("/{key_id}", status_code=204)
def revoke_key(key_id: int, user: User):
    with db() as conn:
        if not accounts.revoke_api_key(conn, user["id"], key_id):
            raise HTTPException(404, "no such key")
