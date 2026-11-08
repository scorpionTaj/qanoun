"""Optional accounts: sign up, sign in, sign out, who am I.

Cookie session (httpOnly, SameSite=Lax). State-changing requests must be JSON from an
allowed origin: with SameSite=Lax that blocks cross-site request forgery.
"""

import re
from typing import Annotated

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
    if origin and origin.rstrip("/") not in SETTINGS.cors_origins:
        raise HTTPException(403, "origin not allowed")


def current_user(request: Request) -> dict | None:
    with db() as conn:
        return accounts.session_user(conn, request.cookies.get(COOKIE))


OptionalUser = Annotated[dict | None, Depends(current_user)]


def require_user(user: OptionalUser) -> dict:
    if user is None:
        raise HTTPException(401, "sign in required")
    return user


User = Annotated[dict, Depends(require_user)]


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=accounts.MIN_PASSWORD, max_length=200)


def _start_session(response: Response, user_id: int) -> None:
    with db() as conn:
        token = accounts.create_session(conn, user_id)
    response.set_cookie(
        COOKIE, token, max_age=accounts.SESSION_DAYS * 86400, httponly=True,
        samesite="lax", secure=SETTINGS.cookie_secure, path="/",
    )


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
    _start_session(response, user_id)
    return {"ok": True}


@router.post("/login", dependencies=[Depends(same_origin_json), Depends(auth_limit)])
def login(body: Credentials, response: Response):
    with db() as conn:
        user_id = accounts.authenticate(conn, body.email, body.password)
    if user_id is None:
        raise HTTPException(401, "wrong email or password")
    _start_session(response, user_id)
    return {"ok": True}


@router.post("/logout", dependencies=[Depends(same_origin_json)])
def logout(request: Request, response: Response):
    with db() as conn:
        accounts.delete_session(conn, request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
