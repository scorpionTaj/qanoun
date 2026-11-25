"""Optional accounts: sign up, sign in, sign out, who am I, and settings that follow the account.

The web app holds the session in a cookie (httpOnly, SameSite=Lax); state-changing requests
must be JSON from an allowed origin, which with SameSite=Lax blocks cross-site request forgery.
The mobile app signs in with `"client": "app"`: it gets the session token in the response
body and sends it back in the X-Qanoun-Session header (a header no other site can make a
browser send). Same sessions, same expiry, same sign-out.
"""

import re
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from qanoun_api import accounts
from qanoun_api.config import SETTINGS
from qanoun_api.db import db
from qanoun_api.ratelimit import auth_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE = "qanoun_session"
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


def same_origin_json(request: Request) -> None:
    """CSRF guard for cookie-authenticated writes."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "JSON required")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in SETTINGS.cors_origins and not _same_origin(origin, request):
        raise HTTPException(403, "origin not allowed")


def _same_origin(origin: str, request: Request) -> bool:
    """The API's own pages (the Swagger UI at /) are not a cross-site request."""
    return origin.rstrip("/").split("://", 1)[-1] == request.headers.get("host", "")


SESSION_HEADER = "x-qanoun-session"


def session_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE) or request.headers.get(SESSION_HEADER) or None


def current_user(request: Request) -> dict | None:
    token = session_token(request)
    if not token:
        return None
    with db() as conn:
        return accounts.session_user(conn, token)


OptionalUser = Annotated[dict | None, Depends(current_user)]


def require_user(user: OptionalUser) -> dict:
    if user is None:
        raise HTTPException(401, "sign in required")
    return user


User = Annotated[dict, Depends(require_user)]


def require_admin(user: User) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "admin only")
    return user


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=accounts.MIN_PASSWORD, max_length=200)
    client: Literal["web", "app"] = "web"  # app: the token in the body, not in a cookie


class AccountSettings(BaseModel):
    """What follows the account across devices; unset fields keep the client's defaults."""

    provider: str | None = Field(default=None, pattern=r"^[a-z]{0,20}$")
    model: str | None = Field(default=None, max_length=200)
    style: Literal["concise", "detailed"] | None = None
    answer_language: Literal["auto", "ar", "fr", "en"] | None = None
    ui_language: Literal["ar", "fr", "en"] | None = None
    theme: Literal["system", "light", "dark"] | None = None


def _start_session(response: Response, user_id: int, client: str) -> dict:
    with db() as conn:
        token = accounts.create_session(conn, user_id)
    if client == "app":
        return {"ok": True, "token": token}
    response.set_cookie(
        COOKIE, token, max_age=accounts.SESSION_DAYS * 86400, httponly=True,
        samesite="lax", secure=SETTINGS.cookie_secure, path="/",
    )
    return {"ok": True}


@router.get("/me")
def me(user: OptionalUser):
    return {"user": user, "signup_allowed": SETTINGS.allow_signup}


@router.post("/signup", dependencies=[Depends(same_origin_json), Depends(auth_limit)])
def signup(body: Credentials, response: Response):
    if not SETTINGS.allow_signup:
        raise HTTPException(403, "sign-up is disabled on this server")
    if not _EMAIL.match(body.email.strip()):
        raise HTTPException(422, "invalid email")
    try:
        with db() as conn:
            user_id = accounts.create_user(conn, body.email, body.password)
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(409, "an account with this email already exists") from exc
    return _start_session(response, user_id, body.client)


@router.post("/login", dependencies=[Depends(same_origin_json), Depends(auth_limit)])
def login(body: Credentials, response: Response):
    with db() as conn:
        user_id = accounts.authenticate(conn, body.email, body.password)
    if user_id is None:
        raise HTTPException(401, "wrong email or password")
    return _start_session(response, user_id, body.client)


@router.post("/logout", dependencies=[Depends(same_origin_json)])
def logout(request: Request, response: Response):
    with db() as conn:
        accounts.delete_session(conn, session_token(request))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/settings")
def get_settings(user: User):
    with db() as conn:
        return accounts.get_settings(conn, user["id"])


@router.put("/settings", dependencies=[Depends(same_origin_json)])
def put_settings(body: AccountSettings, user: User):
    settings = body.model_dump(exclude_none=True)
    with db() as conn:
        accounts.put_settings(conn, user["id"], settings)
    return settings
