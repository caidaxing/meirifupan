"""Authentication API endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from server.services.auth import authenticate_user, ensure_default_admin, get_user_by_token, logout_token
from server.services.review_queries import get_connection


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


@router.post("/api/auth/login")
def login(payload: LoginRequest):
    """Login with the local admin account."""
    conn = get_connection()
    try:
        ensure_default_admin(conn, password=os.environ.get("FAJIAZHIFU_ADMIN_PASSWORD", "123456"))
        return authenticate_user(conn, payload.username, payload.password)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/api/auth/logout")
def logout(authorization: str | None = Header(None)):
    """Revoke the current session token."""
    token = _bearer_token(authorization)
    conn = get_connection()
    try:
        logout_token(conn, token)
        return {"status": "ok"}
    finally:
        conn.close()


@router.get("/api/auth/me")
def me(authorization: str | None = Header(None)):
    """Return current user from bearer token."""
    token = _bearer_token(authorization)
    conn = get_connection()
    try:
        return {"user": get_user_by_token(conn, token)}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    finally:
        conn.close()
