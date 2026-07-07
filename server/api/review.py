"""Review data API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from server.services.announcement_queries import get_announcement_detail, list_announcements
from server.services.emotion_scorer import compute_emotion
from server.services.news_queries import list_news, list_news_dates
from server.services.realtime_emotion import collect_realtime_emotion
from server.services.review_queries import (
    get_all_stocks,
    get_board_advancement,
    get_board_tiers,
    get_capital_flow,
    get_dates,
    get_emotion_heat_trend,
    get_emotion_modules,
    get_high_stocks,
    get_hot_boards_rank,
    get_hot_plates,
    get_hot_stocks_derived,
    get_hot_stocks_rank,
    get_hot_available_dates,
    get_indices,
    get_latest_data_job,
    get_limit_up_stats,
    get_market_environment,
    get_market_overview_trend,
    get_latest_premarket_guide,
    get_plate_rotation_snapshot,
    get_premarket_guide,
    get_quantzz_daily_overview,
    get_recent_hot_plates_with_stocks,
    get_connection,
    get_recent_dates,
    get_review_lhb,
    get_review_limit_up_reasons,
    get_review_limit_up_tiers,
    get_review_movement_alerts,
    get_review_plate_rotation,
    get_review_price_tiers,
    get_review_promotions,
    get_saved_review,
    get_seal_quality,
    get_stock_hot_ranks,
    DB_PATH,
)

router = APIRouter()


@router.get("/api/announcements")
def get_announcements(
    date: str = Query(..., description="Notice date, e.g. 2026-06-30"),
    notice_type: str | None = Query(None, description="Announcement type"),
    q: str | None = Query(None, description="Search keyword"),
    limit: int = Query(500, ge=1, le=500, description="Maximum rows"),
    include_ipo: bool = Query(False, description="Include IPO/listing-review announcements"),
):
    """Return stock announcements for a given date."""
    conn = get_connection()
    try:
        return list_announcements(conn, date, notice_type=notice_type, query=q, limit=limit, include_ipo=include_ipo)
    finally:
        conn.close()


@router.get("/api/announcements/{art_code}")
def get_announcement(art_code: str):
    """Return announcement original text and local cache paths."""
    conn = get_connection()
    try:
        return get_announcement_detail(
            conn,
            art_code,
            cache_root=DB_PATH.parent / "announcements",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/api/news")
def get_news(
    date: str = Query(..., description="Guide date, e.g. 2026-07-03"),
    source: str | None = Query(None, description="News source"),
    q: str | None = Query(None, description="Search keyword"),
    limit: int = Query(200, ge=1, le=500, description="Maximum rows"),
):
    """Return daily news items from premarket_news."""
    conn = get_connection()
    try:
        return list_news(conn, date, source=source, query=q, limit=limit)
    finally:
        conn.close()


@router.get("/api/news/dates")
def get_news_dates():
    """Return available dates for news and announcements."""
    conn = get_connection()
    try:
        return {"dates": list_news_dates(conn)}
    finally:
        conn.close()


@router.get("/api/review")
def get_review(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return full review data for a given date."""
    conn = get_connection()
    try:
        available = get_dates(conn)
        if date not in available:
            raise HTTPException(
                status_code=404,
                detail=f"No data for date {date}. Available: {available[:5]}...",
            )

        indices = get_indices(conn, date)
        stats = get_limit_up_stats(conn, date)
        board_tiers = get_board_tiers(conn, date)
        hot_plates = get_hot_plates(conn, date)
        high_stocks = get_high_stocks(conn, date)
        all_stocks = get_all_stocks(conn, date)
        market_environment = get_market_environment(conn, date)
        recent_hot_plates = get_recent_hot_plates_with_stocks(conn, date, days=5)
        saved_review = get_saved_review(conn, date)
        emotion = compute_emotion(conn, date, stats=stats, indices=indices)

        return {
            "date": date,
            "indices": indices,
            "limit_up_stats": stats,
            "market_environment": market_environment,
            "saved_review": saved_review,
            "board_tiers": board_tiers,
            "hot_plates": hot_plates,
            "recent_hot_plates": recent_hot_plates,
            "high_stocks": high_stocks,
            "all_stocks": all_stocks,
            "emotion": emotion,
        }
    finally:
        conn.close()


@router.get("/api/review/report")
def get_review_report(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return the generated review report for a given date."""
    conn = get_connection()
    try:
        review = get_saved_review(conn, date)
        if not review:
            raise HTTPException(status_code=404, detail=f"No generated review for date {date}.")
        return review
    finally:
        conn.close()


@router.get("/api/review/limit-up-reasons")
def get_limit_up_reasons(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return limit-up reason groups for the review module."""
    conn = get_connection()
    try:
        return get_review_limit_up_reasons(conn, date)
    finally:
        conn.close()


@router.get("/api/review/limit-up-tiers")
def get_limit_up_tiers(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return limit-up board tiers for the review module."""
    conn = get_connection()
    try:
        return get_review_limit_up_tiers(conn, date)
    finally:
        conn.close()


@router.get("/api/review/price-tiers")
def get_price_tiers(
    date: str = Query(..., description="Trade date, e.g. 2026-06-03"),
    days: int = Query(10, description="Number of trading days to include"),
):
    """Return price-change tiers for the review module."""
    conn = get_connection()
    try:
        return get_review_price_tiers(conn, date, days=days)
    finally:
        conn.close()


@router.get("/api/review/promotions")
def get_promotions(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return board promotion data for the review module."""
    conn = get_connection()
    try:
        return get_review_promotions(conn, date)
    finally:
        conn.close()


@router.get("/api/review/plate-rotation")
def get_review_rotation(
    date: str | None = Query(None, description="End date, e.g. 2026-06-16. Empty means latest date."),
    days: int = Query(8, description="Number of trading days to include"),
    top_n: int = Query(12, description="Top plates per day"),
    plate_code: str | None = Query(None, description="Selected plate code"),
):
    """Return plate rotation data for the review module."""
    conn = get_connection()
    try:
        return get_review_plate_rotation(conn, date, days=days, top_n=top_n, plate_code=plate_code)
    finally:
        conn.close()


@router.get("/api/review/lhb")
def get_lhb(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return Dragon Tiger List rows for the review module."""
    conn = get_connection()
    try:
        return get_review_lhb(conn, date)
    finally:
        conn.close()


@router.get("/api/review/movement-alerts")
def get_movement_alerts(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return movement alerts for the review module."""
    conn = get_connection()
    try:
        return get_review_movement_alerts(conn, date)
    finally:
        conn.close()


@router.get("/api/emotion/trend")
def get_emotion_trend(
    date: str = Query(..., description="End date, e.g. 2026-06-03"),
    days: int = Query(5, description="Number of trading days to include"),
):
    """Return emotion scores for recent N trading days."""
    conn = get_connection()
    try:
        available = get_dates(conn)
        if date not in available:
            raise HTTPException(
                status_code=404,
                detail=f"No data for date {date}.",
            )

        recent_dates = get_recent_dates(conn, date, days)
        trend = []
        for d in recent_dates:
            stats = get_limit_up_stats(conn, d)
            indices = get_indices(conn, d)
            emotion = compute_emotion(conn, d, stats=stats, indices=indices)
            trend.append(emotion)

        # Sort by date ascending for chart display
        trend.sort(key=lambda x: x["date"])

        return {
            "date": date,
            "days": days,
            "trend": trend,
        }
    finally:
        conn.close()


@router.get("/api/emotion/heat-trend")
def get_emotion_heat(
    date: str = Query(..., description="End date, e.g. 2026-06-03"),
    days: int = Query(60, description="Number of trading days to include"),
):
    """Return daily heat metrics for sentiment, hot stocks and space-board review."""
    conn = get_connection()
    try:
        return {
            "date": date,
            "days": days,
            "trend": get_emotion_heat_trend(conn, date, days),
        }
    finally:
        conn.close()


@router.get("/api/emotion/modules")
def get_emotion_module_tabs(
    date: str = Query(..., description="End date, e.g. 2026-06-03"),
    days: int = Query(60, description="Number of trading days to include"),
):
    """Return Quantzz-style emotion modules."""
    conn = get_connection()
    try:
        available = get_dates(conn)
        if date not in available:
            raise HTTPException(status_code=404, detail=f"No data for date {date}.")
        return get_emotion_modules(conn, date, days)
    finally:
        conn.close()


@router.get("/api/emotion/realtime")
def get_emotion_realtime(
    date: str | None = Query(None, description="Trade date, empty means today in Asia/Shanghai."),
):
    """Return realtime intraday emotion modules from live sources."""
    return collect_realtime_emotion(date=date, db_path=DB_PATH)


@router.get("/api/quantzz/daily")
def get_quantzz_daily(
    date: str = Query(..., description="Trade date, e.g. 2026-06-03"),
    days: int = Query(60, description="Number of trading days to include"),
):
    """Return a Quantzz-style daily overview built from daily-level data."""
    conn = get_connection()
    try:
        available = get_dates(conn)
        if date not in available:
            raise HTTPException(status_code=404, detail=f"No data for date {date}.")
        return get_quantzz_daily_overview(conn, date, days)
    finally:
        conn.close()


@router.get("/api/plate-rotation")
def get_plate_rotation(
    date: str | None = Query(None, description="End date, e.g. 2026-06-16. Empty means latest plate rotation date."),
    days: int = Query(8, description="Number of trading days to include"),
    top_n: int = Query(12, description="Top plates per day"),
    plate_code: str | None = Query(None, description="Selected plate code"),
):
    """Return topic/plate rotation data."""
    conn = get_connection()
    try:
        return get_plate_rotation_snapshot(conn, date, days=days, top_n=top_n, plate_code=plate_code)
    finally:
        conn.close()


@router.get("/api/premarket")
def get_premarket(date: str | None = Query(None, description="Guide date, e.g. 2026-06-10")):
    """Return pre-market guidance. If no date is given, return the latest guide."""
    conn = get_connection()
    try:
        guide = get_premarket_guide(conn, date) if date else get_latest_premarket_guide(conn)
        if not guide:
            raise HTTPException(status_code=404, detail=f"No premarket guide for {date or 'latest'}.")
        return guide
    finally:
        conn.close()


@router.get("/api/market/overview-trend")
def get_market_trend(
    date: str = Query(..., description="End date, e.g. 2026-06-03"),
    days: int = Query(5, description="Number of trading days to include"),
):
    """Return recent market overview metrics."""
    conn = get_connection()
    try:
        available = get_dates(conn)
        if date not in available:
            raise HTTPException(status_code=404, detail=f"No data for date {date}.")
        return {
            "date": date,
            "days": days,
            "trend": get_market_overview_trend(conn, date, days),
        }
    finally:
        conn.close()


@router.get("/api/insights")
def get_insights(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return market insights: seal quality, board advancement, capital flow, hot stocks."""
    conn = get_connection()
    try:
        available = get_dates(conn)
        if date not in available:
            raise HTTPException(
                status_code=404,
                detail=f"No data for date {date}.",
            )

        seal_quality = get_seal_quality(conn, date)
        board_advancement = get_board_advancement(conn, date)
        capital_flow = get_capital_flow(conn, date)
        hot_stocks = get_hot_stocks_derived(conn, date)

        return {
            "date": date,
            "seal_quality": seal_quality,
            "board_advancement": board_advancement,
            "capital_flow": capital_flow,
            "hot_stocks": hot_stocks,
        }
    finally:
        conn.close()


@router.get("/api/hot")
def get_hot(date: str = Query(..., description="Trade date, e.g. 2026-06-03")):
    """Return hot stocks and hot boards for a given date."""
    conn = get_connection()
    try:
        hot_stocks = get_hot_stocks_rank(conn, date, limit=30)
        shortline_hot = get_stock_hot_ranks(conn, date, source="shortline_hot", period="day", list_type="kpl_style", limit=30)
        ths_hot = get_stock_hot_ranks(conn, date, source="ths_hot", period="day", list_type="normal", limit=30)
        ths_skyrocket = get_stock_hot_ranks(conn, date, source="ths_hot", period="hour", list_type="skyrocket", limit=30)
        concept_boards = get_hot_boards_rank(conn, date, board_type="concept", limit=20)
        industry_boards = get_hot_boards_rank(conn, date, board_type="industry", limit=20)

        return {
            "date": date,
            "hot_stocks": hot_stocks,
            "shortline_hot": shortline_hot,
            "ths_hot": ths_hot,
            "ths_skyrocket": ths_skyrocket,
            "concept_boards": concept_boards,
            "industry_boards": industry_boards,
        }
    finally:
        conn.close()


@router.get("/api/hot/dates")
def get_hot_dates():
    """Return available dates for hot data."""
    conn = get_connection()
    try:
        dates = get_hot_available_dates(conn)
        return {"dates": dates}
    finally:
        conn.close()


@router.get("/api/jobs/latest")
def get_latest_job(job_name: str = Query("daily_update", description="Job name")):
    """Return latest data update job status."""
    conn = get_connection()
    try:
        job = get_latest_data_job(conn, job_name)
        if not job:
            raise HTTPException(status_code=404, detail=f"No job records for {job_name}.")
        return job
    finally:
        conn.close()
