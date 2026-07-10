"""API routes for individual stock research reports."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from server.services.research_report_queries import (
    get_research_report_detail,
    list_research_report_dates,
    list_research_reports,
    resolve_research_report_pdf,
)
from server.services.review_queries import DB_PATH, get_connection


router = APIRouter()


@router.get("/api/research-reports/dates")
def get_research_report_dates():
    conn = get_connection()
    try:
        return {"dates": list_research_report_dates(conn)}
    finally:
        conn.close()


@router.get("/api/research-reports")
def get_research_reports(
    date: str = Query(..., description="Report date, e.g. 2026-07-10"),
    q: str | None = Query(None, description="Stock code, name, title, or industry"),
    rating: str | None = Query(None, description="Current rating"),
    org: str | None = Query(None, description="Research institution"),
    limit: int = Query(200, ge=1, le=500),
):
    conn = get_connection()
    try:
        return list_research_reports(conn, date, query=q, rating=rating, org=org, limit=limit)
    finally:
        conn.close()


@router.get("/api/research-reports/{info_code}")
def get_research_report(info_code: str):
    conn = get_connection()
    try:
        try:
            return get_research_report_detail(conn, info_code)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/api/research-reports/{info_code}/pdf")
def get_research_report_pdf(info_code: str):
    conn = get_connection()
    try:
        try:
            path = resolve_research_report_pdf(conn, info_code, DB_PATH.parent / "research_reports")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )
