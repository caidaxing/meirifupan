"""Shared utility functions for data cleaning and type conversion."""

from __future__ import annotations

import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Value cleaning
# ---------------------------------------------------------------------------

def is_blank(value: Any) -> bool:
    """Return True if value is None or NaN."""
    if value is None:
        return True
    try:
        return value != value  # NaN check
    except Exception:
        return False


def clean(value: Any) -> Any:
    """Normalize pandas/numpy scalars to plain Python values; NaN → None."""
    if is_blank(value):
        return None
    if hasattr(value, "item"):
        try:
            return clean(value.item())
        except Exception:
            pass
    return value


# ---------------------------------------------------------------------------
# Type conversion
# ---------------------------------------------------------------------------

def to_float(value: Any) -> float | None:
    """Convert value to float; return None for blanks and non-numeric strings."""
    value = clean(value)
    if value in ("", "-", "--", None):
        return None
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    """Convert value to int via to_float; return None for blanks."""
    value = to_float(value)
    return int(value) if value is not None else None


def to_text(value: Any) -> str | None:
    """Convert value to stripped string; return None for blanks."""
    value = clean(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# Stock helpers
# ---------------------------------------------------------------------------

def stock_code(value: Any) -> str:
    """Normalize stock code: strip exchange prefix, uppercase, handle .SS/.SZ suffix."""
    code = str(value or "").strip()
    if code.lower().startswith(("sh", "sz", "bj")):
        code = code[2:]
    if "." in code:
        code = code.split(".", 1)[0]
    return code.upper()


def compact_time(value: Any) -> str | None:
    """Convert '143025' → '14:30:25'; pass through already-formatted times."""
    text = to_text(value)
    if not text:
        return None
    if len(text) == 6 and text.isdigit():
        return f"{text[:2]}:{text[2:4]}:{text[4:]}"
    return text


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert a list of sqlite3.Row to a list of dicts."""
    return [row_to_dict(r) for r in rows]
