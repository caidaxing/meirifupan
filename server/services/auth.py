"""Local username/password authentication helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


HASH_ITERATIONS = 200_000
SESSION_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        HASH_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        method, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def user_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


def ensure_default_admin(conn: sqlite3.Connection, password: str = "123456") -> dict[str, Any]:
    row = conn.execute("select * from users where username = ?", ("admin",)).fetchone()
    if row:
        return user_payload(row)
    conn.execute(
        """
        insert into users(username, password_hash)
        values(?, ?)
        """,
        ("admin", hash_password(password)),
    )
    conn.commit()
    row = conn.execute("select * from users where username = ?", ("admin",)).fetchone()
    return user_payload(row)


def authenticate_user(conn: sqlite3.Connection, username: str, password: str) -> dict[str, Any]:
    row = conn.execute("select * from users where username = ?", (username.strip(),)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise PermissionError("用户名或密码错误")

    token = secrets.token_urlsafe(32)
    expires_at = _iso(_now() + timedelta(days=SESSION_DAYS))
    conn.execute(
        """
        insert into auth_sessions(token, user_id, expires_at)
        values(?, ?, ?)
        """,
        (token, row["id"], expires_at),
    )
    conn.execute(
        "update users set last_login_at = current_timestamp, updated_at = current_timestamp where id = ?",
        (row["id"],),
    )
    conn.commit()
    fresh = conn.execute("select * from users where id = ?", (row["id"],)).fetchone()
    return {
        "token": token,
        "expires_at": expires_at,
        "user": user_payload(fresh),
        "username": fresh["username"],
    }


def get_user_by_token(conn: sqlite3.Connection, token: str) -> dict[str, Any]:
    row = conn.execute(
        """
        select u.*
        from auth_sessions s
        join users u on u.id = s.user_id
        where s.token = ? and s.revoked_at is null
        """,
        (token,),
    ).fetchone()
    session = conn.execute(
        "select expires_at, revoked_at from auth_sessions where token = ?",
        (token,),
    ).fetchone()
    if not row or not session:
        raise PermissionError("登录已失效")
    if session["revoked_at"] is not None or _parse_iso(session["expires_at"]) <= _now():
        raise PermissionError("登录已失效")
    return user_payload(row)


def logout_token(conn: sqlite3.Connection, token: str) -> None:
    conn.execute(
        "update auth_sessions set revoked_at = current_timestamp where token = ? and revoked_at is null",
        (token,),
    )
    conn.commit()
