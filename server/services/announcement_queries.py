"""Announcement query and content-cache helpers."""

from __future__ import annotations

import json
import re
import ssl
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


FetchAnnouncementContent = Callable[[str], dict[str, Any]]


ART_CODE_RE = re.compile(r"(AN\d{18})")
IPO_KEYWORDS = (
    "IPO",
    "首发",
    "招股说明书",
    "上市保荐书",
    "发行保荐书",
    "发行上市",
    "上市审核",
    "上市委",
    "北交所上市",
    "科创板发行",
    "创业板IPO",
    "沪主板发行上市",
    "深主板发行上市",
)
SYSTEM_CA_FILES = (
    Path("/etc/ssl/cert.pem"),
    Path("/private/etc/ssl/cert.pem"),
)

try:
    import certifi
except Exception:  # pragma: no cover - depends on local Python install
    class _MissingCertifi:
        @staticmethod
        def where() -> str | None:
            return None

    certifi = _MissingCertifi()


def parse_art_code(*values: str | None) -> str | None:
    """Extract Eastmoney announcement art_code from URL or raw text."""
    for value in values:
        if not value:
            continue
        match = ART_CODE_RE.search(str(value))
        if match:
            return match.group(1)
    return None


def list_announcements(
    conn: sqlite3.Connection,
    date: str,
    *,
    notice_type: str | None = None,
    query: str | None = None,
    limit: int = 500,
    include_ipo: bool = False,
) -> dict[str, Any]:
    """Return announcements for one notice date from the current table."""
    rows = conn.execute(
        """
        select notice_date, stock_code, stock_name, notice_type, title, url, raw_payload, updated_at
        from stock_announcements
        where notice_date = ?
        order by stock_code desc, title asc
        """,
        (date,),
    ).fetchall()

    filtered_items = []
    type_counter: dict[str, int] = {}
    keyword = (query or "").strip().lower()
    type_filter = (notice_type or "").strip()

    for row in rows:
        raw_payload = _json_dict(row["raw_payload"])
        source_url = row["url"] or raw_payload.get("网址") or raw_payload.get("url") or ""
        art_code = parse_art_code(source_url, row["raw_payload"])
        item_type = row["notice_type"] or "未分类"
        item = {
            "art_code": art_code,
            "notice_date": row["notice_date"],
            "stock_code": row["stock_code"] or "",
            "stock_name": row["stock_name"] or "",
            "notice_type": item_type,
            "title": row["title"],
            "source_url": source_url,
            "updated_at": row["updated_at"],
        }

        if type_filter and item_type != type_filter:
            continue
        if not include_ipo and _is_ipo_related(item):
            continue
        if keyword and keyword not in _search_text(item):
            continue

        type_counter[item_type] = type_counter.get(item_type, 0) + 1
        filtered_items.append(item)

    items = filtered_items[:limit]

    return {
        "date": date,
        "status": "ok" if filtered_items else "empty",
        "updated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "summary": {
            "total": len(filtered_items),
            "returned": len(items),
            "limit": limit,
            "types": [
                {"notice_type": name, "count": count}
                for name, count in sorted(type_counter.items(), key=lambda pair: (-pair[1], pair[0]))
            ],
        },
        "filters": {"notice_type": notice_type, "query": query, "limit": limit, "include_ipo": include_ipo},
        "items": items,
        "warnings": [],
    }


def get_announcement_detail(
    conn: sqlite3.Connection,
    art_code: str,
    *,
    cache_root: Path,
    fetcher: FetchAnnouncementContent | None = None,
) -> dict[str, Any]:
    """Return announcement detail and cache original API JSON plus text."""
    row = _find_announcement_row(conn, art_code)
    if not row:
        raise KeyError(f"Announcement not found: {art_code}")

    base = _row_base(row, art_code)
    paths = _cache_paths(cache_root, base["stock_code"], base["notice_date"], art_code)
    if paths["text"].exists() and paths["json"].exists():
        return _detail_from_cache(base, paths)

    payload = (fetcher or fetch_eastmoney_announcement_content)(art_code)
    content_text = str(payload.get("notice_content") or payload.get("content_text") or "").strip()
    notice_title = str(payload.get("notice_title") or base["title"]).strip()
    pdf_url = payload.get("attach_url_web") or payload.get("pdf_url") or ""
    published_at = payload.get("eitime") or payload.get("published_at") or base["notice_date"]

    paths["dir"].mkdir(parents=True, exist_ok=True)
    raw_payload = payload.get("raw") if isinstance(payload.get("raw"), dict) else payload
    paths["json"].write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["text"].write_text(content_text, encoding="utf-8")

    return {
        **base,
        "notice_title": notice_title,
        "published_at": published_at,
        "content_text": content_text,
        "content_chars": len(content_text),
        "pdf_url": pdf_url,
        "json_path": str(paths["json"]),
        "text_path": str(paths["text"]),
        "cache_status": "fetched",
    }


def fetch_eastmoney_announcement_content(art_code: str) -> dict[str, Any]:
    """Fetch announcement original text from Eastmoney content endpoint."""
    url = (
        "https://np-cnotice-stock.eastmoney.com/api/content/ann"
        f"?art_code={urllib.parse.quote(art_code)}&client_source=web&page_index=1"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.eastmoney.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, context=make_ssl_context(), timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to fetch announcement content: {art_code}") from exc

    payload = data.get("data") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        raise RuntimeError(f"Announcement content response has no data: {art_code}")
    return {**payload, "raw": data}


def make_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that works in local venvs with missing CA config."""
    cafile = certifi.where()
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    for path in SYSTEM_CA_FILES:
        if path.exists():
            return ssl.create_default_context(cafile=str(path))
    return ssl.create_default_context()


def _find_announcement_row(conn: sqlite3.Connection, art_code: str) -> sqlite3.Row | None:
    rows = conn.execute(
        """
        select notice_date, stock_code, stock_name, notice_type, title, url, raw_payload, updated_at
        from stock_announcements
        order by notice_date desc
        """
    ).fetchall()
    for row in rows:
        raw_payload = _json_dict(row["raw_payload"])
        source_url = row["url"] or raw_payload.get("网址") or raw_payload.get("url") or ""
        if parse_art_code(source_url, row["raw_payload"]) == art_code:
            return row
    return None


def _row_base(row: sqlite3.Row, art_code: str) -> dict[str, Any]:
    raw_payload = _json_dict(row["raw_payload"])
    source_url = row["url"] or raw_payload.get("网址") or raw_payload.get("url") or ""
    return {
        "art_code": art_code,
        "notice_date": row["notice_date"],
        "stock_code": row["stock_code"] or "unknown",
        "stock_name": row["stock_name"] or "",
        "notice_type": row["notice_type"] or "未分类",
        "title": row["title"],
        "source_url": source_url,
        "updated_at": row["updated_at"],
    }


def _detail_from_cache(base: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    content_text = paths["text"].read_text(encoding="utf-8")
    raw_payload = _json_dict(paths["json"].read_text(encoding="utf-8"))
    data = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else raw_payload
    return {
        **base,
        "notice_title": data.get("notice_title") or base["title"],
        "published_at": data.get("eitime") or data.get("published_at") or base["notice_date"],
        "content_text": content_text,
        "content_chars": len(content_text),
        "pdf_url": data.get("attach_url_web") or data.get("pdf_url") or "",
        "json_path": str(paths["json"]),
        "text_path": str(paths["text"]),
        "cache_status": "cached",
    }


def _cache_paths(cache_root: Path, stock_code: str, notice_date: str, art_code: str) -> dict[str, Path]:
    safe_stock_code = stock_code or "unknown"
    dir_path = cache_root / safe_stock_code / notice_date
    return {
        "dir": dir_path,
        "json": dir_path / f"{art_code}.json",
        "text": dir_path / f"{art_code}.txt",
    }


def _json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _search_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("stock_code", "stock_name", "notice_type", "title")
    ).lower()


def _is_ipo_related(item: dict[str, Any]) -> bool:
    stock_code = str(item.get("stock_code") or "").upper()
    if stock_code.startswith("A") and stock_code[1:].isdigit():
        return True
    text = " ".join(str(item.get(key) or "") for key in ("notice_type", "title")).upper()
    return any(keyword.upper() in text for keyword in IPO_KEYWORDS)
