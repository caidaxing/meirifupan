"""Query services for locally stored individual stock research reports."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def list_research_report_dates(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select distinct date(publish_date) as report_date from stock_research_reports order by report_date desc"
    ).fetchall()
    return [row["report_date"] for row in rows if row["report_date"]]


def list_research_reports(
    conn: sqlite3.Connection,
    date: str,
    *,
    query: str | None = None,
    rating: str | None = None,
    org: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    where = ["date(r.publish_date) = ?"]
    params: list[Any] = [date]
    if query:
        where.append("(r.stock_code like ? or r.stock_name like ? or r.title like ? or r.industry_name like ?)")
        keyword = f"%{query.strip()}%"
        params.extend([keyword] * 4)
    if rating:
        where.append("r.rating_name = ?")
        params.append(rating)
    if org:
        where.append("(r.org_name = ? or r.org_short_name = ?)")
        params.extend([org, org])
    where_sql = " and ".join(where)
    total = conn.execute(f"select count(*) from stock_research_reports r where {where_sql}", params).fetchone()[0]
    pdf_downloaded = conn.execute(
        f"""
        select count(*) from stock_research_reports r
        left join stock_research_report_contents c on c.info_code = r.info_code
        where {where_sql} and c.pdf_status = 'downloaded'
        """,
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        select r.info_code, date(r.publish_date) as publish_date, r.publish_date, r.stock_code, r.stock_name,
               r.market, r.title, r.org_code, r.org_name, r.org_short_name,
               r.industry_code, r.industry_name, r.rating_name, r.previous_rating_name,
               r.rating_change_code, r.rating_change_name, r.target_price_low, r.target_price_high,
               r.source_url, r.detail_status, coalesce(c.pdf_status, 'pending') as pdf_status,
               c.attach_pages, c.declared_pdf_size_kb
        from stock_research_reports r
        left join stock_research_report_contents c on c.info_code = r.info_code
        where {where_sql}
        order by r.publish_date desc, r.info_code desc
        limit ?
        """,
        [*params, max(1, min(int(limit), 500))],
    ).fetchall()
    items = [dict(row) for row in rows]
    ratings = conn.execute(
        f"select coalesce(r.rating_name, '未评级') as rating_name, count(*) as count from stock_research_reports r where {where_sql} group by rating_name order by count desc, rating_name",
        params,
    ).fetchall()
    orgs = conn.execute(
        f"select coalesce(r.org_short_name, r.org_name, '未知机构') as org_name, count(*) as count from stock_research_reports r where {where_sql} group by org_name order by count desc, org_name limit 50",
        params,
    ).fetchall()
    return {
        "date": date,
        "status": "ok" if items else "empty",
        "summary": {
            "total": total,
            "returned": len(items),
            "pdf_downloaded": pdf_downloaded,
            "ratings": [{"rating_name": row["rating_name"], "count": row["count"]} for row in ratings],
            "organizations": [{"org_name": row["org_name"], "count": row["count"]} for row in orgs],
        },
        "filters": {"query": query, "rating": rating, "org": org, "limit": limit},
        "items": items,
    }


def get_research_report_detail(conn: sqlite3.Connection, info_code: str) -> dict[str, Any]:
    row = conn.execute(
        """
        select r.*, c.summary_text, c.pdf_url, c.local_pdf_path, coalesce(c.pdf_status, 'pending') as pdf_status,
               c.attach_pages, c.declared_pdf_size_kb, c.pdf_size, c.pdf_sha256, c.pdf_error, c.downloaded_at
        from stock_research_reports r
        left join stock_research_report_contents c on c.info_code = r.info_code
        where r.info_code = ?
        """,
        (info_code,),
    ).fetchone()
    if not row:
        raise KeyError(f"Research report not found: {info_code}")
    item = dict(row)
    item["authors"] = [
        dict(author)
        for author in conn.execute(
            "select author_id, author_name, sort_order from stock_research_report_authors where info_code = ? order by sort_order, author_id",
            (info_code,),
        ).fetchall()
    ]
    item["forecasts"] = [
        dict(forecast)
        for forecast in conn.execute(
            "select forecast_year, eps, pe from stock_research_report_forecasts where info_code = ? order by forecast_year",
            (info_code,),
        ).fetchall()
    ]
    item["local_pdf_url"] = f"/api/research-reports/{info_code}/pdf" if item.get("pdf_status") == "downloaded" else None
    return item


def resolve_research_report_pdf(conn: sqlite3.Connection, info_code: str, data_root: str | Path) -> Path:
    row = conn.execute(
        "select local_pdf_path, pdf_status from stock_research_report_contents where info_code = ?",
        (info_code,),
    ).fetchone()
    if not row:
        raise FileNotFoundError(f"Research report PDF not found: {info_code}")
    if row["pdf_status"] != "downloaded" or not row["local_pdf_path"]:
        raise ValueError(f"Research report PDF is not downloaded: {info_code}")
    root = Path(data_root).resolve()
    candidate = (root / row["local_pdf_path"]).resolve()
    if candidate != root and root not in candidate.parents:
        raise FileNotFoundError(f"Research report PDF path is outside data root: {info_code}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Research report PDF file is missing: {info_code}")
    with candidate.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise FileNotFoundError(f"Research report PDF is corrupt: {info_code}")
    return candidate
