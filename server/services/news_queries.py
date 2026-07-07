"""News query helpers for the news module."""

from __future__ import annotations

import sqlite3
from typing import Any


def list_news_dates(conn: sqlite3.Connection) -> list[str]:
    """Return available dates for the news center, newest first."""
    rows = conn.execute(
        """
        select guide_date as data_date from premarket_news
        union
        select notice_date as data_date from stock_announcements
        order by data_date desc
        """
    ).fetchall()
    return [row["data_date"] for row in rows if row["data_date"]]


def list_news(
    conn: sqlite3.Connection,
    date: str,
    *,
    source: str | None = None,
    query: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Return premarket news rows for one guide date."""
    data_date, date_mode = _resolve_news_date(conn, date, source)
    params: list[Any] = [data_date]
    where = ["guide_date = ?"]
    if source:
        where.append("source = ?")
        params.append(source)
    if query:
        where.append("(title like ? or content like ?)")
        keyword = f"%{query}%"
        params.extend([keyword, keyword])

    where_sql = " and ".join(where)
    total = conn.execute(
        f"select count(*) from premarket_news where {where_sql}",
        params,
    ).fetchone()[0]
    source_rows = conn.execute(
        f"""
        select source, count(*) as count
        from premarket_news
        where {where_sql}
        group by source
        order by source
        """,
        params,
    ).fetchall()
    rows = conn.execute(
        f"""
        select guide_date, source, published_at, title, content, url
        from premarket_news
        where {where_sql}
        order by coalesce(published_at, '') desc, updated_at desc, title asc
        limit ?
        """,
        [*params, limit],
    ).fetchall()

    items = [
        {
            "guide_date": row["guide_date"],
            "source": row["source"] or "",
            "published_at": row["published_at"],
            "title": row["title"] or "",
            "content": row["content"],
            "url": row["url"],
        }
        for row in rows
    ]
    return {
        "requested_date": date,
        "date": data_date,
        "status": "ok",
        "summary": {
            "data_date": data_date,
            "date_mode": date_mode,
            "total": total,
            "returned": len(items),
            "sources": [{"source": row["source"] or "", "count": row["count"]} for row in source_rows],
        },
        "items": items,
    }


def _resolve_news_date(conn: sqlite3.Connection, requested_date: str, source: str | None = None) -> tuple[str, str]:
    params: list[Any] = [requested_date]
    where = ["guide_date = ?"]
    if source:
        where.append("source = ?")
        params.append(source)
    exact_count = conn.execute(
        f"select count(*) from premarket_news where {' and '.join(where)}",
        params,
    ).fetchone()[0]
    if exact_count:
        return requested_date, "exact"

    next_params: list[Any] = [requested_date]
    next_where = ["guide_date > ?"]
    if source:
        next_where.append("source = ?")
        next_params.append(source)
    row = conn.execute(
        f"""
        select guide_date
        from premarket_news
        where {' and '.join(next_where)}
        group by guide_date
        order by guide_date asc
        limit 1
        """,
        next_params,
    ).fetchone()
    if row:
        return row["guide_date"], "next_available"
    return requested_date, "exact"
