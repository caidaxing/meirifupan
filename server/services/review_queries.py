"""SQL query wrappers for market review data."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


from utils import row_to_dict, rows_to_list


DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).resolve().parent.parent.parent / "data" / "market_review.db")))


def get_connection() -> sqlite3.Connection:
    """Get a new database connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_data_job(conn: sqlite3.Connection, job_name: str = "daily_update") -> dict[str, Any] | None:
    """Return the latest recorded data job."""
    row = conn.execute(
        """
        select id, job_name, trade_date, status, message, details, started_at, finished_at, created_at
        from data_jobs
        where job_name = ?
        order by id desc
        limit 1
        """,
        (job_name,),
    ).fetchone()
    if not row:
        return None
    result = row_to_dict(row)
    result["details"] = _json_dict(result.get("details"))
    result["details"] = _compact_job_details(result["details"])
    return result


def _json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _round_or_none(value: Any, digits: int = 2) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _pct(part: int | float | None, total: int | float | None, digits: int = 1) -> float | None:
    if not total:
        return None
    return _round_or_none((part or 0) / total * 100, digits)


def make_review_payload(
    date: str,
    *,
    status: str = "ok",
    summary: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
    items: list[Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build the standard response envelope for review submodules."""
    allowed_status = {"ok", "partial", "empty", "error"}
    normalized_status = status if status in allowed_status else "error"
    return {
        "date": date,
        "status": normalized_status,
        "updated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "summary": summary or {},
        "filters": filters or {},
        "items": items or [],
        "warnings": warnings or [],
    }


def _hot_stock_source_filter(conn: sqlite3.Connection, date: str) -> str:
    """Prefer true popularity rankings; use turnover rank only as a fallback."""
    row = conn.execute(
        """
        SELECT COUNT(*) as total
        FROM hot_stocks
        WHERE trade_date = ? AND source LIKE 'eastmoney%'
        """,
        (date,),
    ).fetchone()
    if row and row["total"]:
        return "source LIKE 'eastmoney%'"
    return "(source IS NULL OR source NOT LIKE 'eastmoney%')"


def _compact_job_details(details: dict[str, Any]) -> dict[str, Any]:
    """Return concise job details for the UI."""
    compact = {
        "trade_date": details.get("trade_date"),
        "is_today_trade_day": details.get("is_today_trade_day"),
        "status": details.get("status"),
        "message": details.get("message"),
        "steps": [],
    }
    for step in details.get("steps") or []:
        if not isinstance(step, dict):
            continue
        compact_step = {
            "name": step.get("name"),
            "status": step.get("status"),
            "started_at": step.get("started_at"),
            "finished_at": step.get("finished_at"),
            "message": step.get("message"),
        }
        result = step.get("result")
        if isinstance(result, dict):
            compact_step["result"] = _compact_step_result(result)
        compact["steps"].append(compact_step)
    return compact


def _compact_step_result(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in result.items():
        if key in {"raw", "raw_payload", "traceback"}:
            continue
        if isinstance(value, list):
            compact[key] = {"count": len(value)}
        elif isinstance(value, dict):
            if {"count"} <= set(value.keys()) or {"keys"} <= set(value.keys()):
                compact[key] = value
            elif len(value) <= 8 and not any(isinstance(v, (dict, list)) for v in value.values()):
                compact[key] = value
            else:
                compact[key] = {"keys": len(value)}
        elif isinstance(value, str):
            compact[key] = value if len(value) <= 160 else value[:160].rstrip() + "..."
        else:
            compact[key] = value
    return compact


def get_indices(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get market indices for a given date."""
    rows = conn.execute(
        """
        SELECT index_code, index_name, close_price, change_pct
        FROM market_index_daily
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchall()
    return rows_to_list(rows)


def get_limit_up_stats(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Get limit-up statistics for a date, including comparison with previous day."""
    row = conn.execute(
        """
        SELECT
            COUNT(DISTINCT stock_code) as total,
            SUM(CASE WHEN up_limit_desc LIKE '%首板%' THEN 1 ELSE 0 END) as first_board,
            SUM(CASE WHEN up_limit_desc NOT LIKE '%首板%' OR up_limit_desc IS NULL THEN 1 ELSE 0 END) as multi_board,
            COALESCE(MAX(up_limit_keep_times), 1) as highest_board
        FROM limit_up_events
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchone()
    current = row_to_dict(row) if row else {
        "total": 0, "first_board": 0, "multi_board": 0, "highest_board": 1
    }

    # Get previous trading day's total
    prev_row = conn.execute(
        """
        SELECT COUNT(DISTINCT stock_code) as prev_total
        FROM limit_up_events
        WHERE trade_date = (
            SELECT MAX(trade_date) FROM limit_up_events WHERE trade_date < ?
        )
        """,
        (date,),
    ).fetchone()
    current["prev_total"] = prev_row["prev_total"] if prev_row else 0

    return current


def get_board_tiers(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get board tier breakdown (multi-board stocks grouped by consecutive days)."""
    tiers = conn.execute(
        """
        SELECT
            up_limit_keep_times as level,
            COUNT(*) as count,
            GROUP_CONCAT(stock_name) as stock_names
        FROM limit_up_events
        WHERE trade_date = ? AND up_limit_keep_times >= 2
        GROUP BY up_limit_keep_times
        ORDER BY level DESC
        """,
        (date,),
    ).fetchall()

    result = []
    for tier in tiers:
        level = tier["level"]
        # Get detailed stock info for this tier
        stocks = conn.execute(
            """
            SELECT
                e.stock_code, e.stock_name, e.up_limit_time,
                e.up_limit_type, e.fengdan_money
            FROM limit_up_events e
            WHERE e.trade_date = ? AND e.up_limit_keep_times = ?
            ORDER BY e.fengdan_money DESC
            """,
            (date, level),
        ).fetchall()

        stock_list = []
        for s in stocks:
            stock_dict = row_to_dict(s)
            # Get plate info for this stock
            plates = conn.execute(
                """
                SELECT p.plate_name
                FROM limit_up_plate_map p
                WHERE p.trade_date = ? AND p.stock_code = ?
                ORDER BY p.plate_score DESC
                LIMIT 3
                """,
                (date, s["stock_code"]),
            ).fetchall()
            stock_dict["plates"] = [p["plate_name"] for p in plates]
            stock_list.append(stock_dict)

        result.append({
            "level": level,
            "count": tier["count"],
            "stock_names": tier["stock_names"],
            "stocks": stock_list,
        })

    return result


def get_hot_plates(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get top 10 hot plates with limit-up count and historical presence."""
    plates = conn.execute(
        """
        SELECT
            r.plate_code, r.plate_name, r.score, r.rank_no,
            COUNT(DISTINCT m.stock_code) as limit_up_count
        FROM plate_hot_rank r
        LEFT JOIN limit_up_plate_map m
            ON r.trade_date = m.trade_date AND r.plate_code = m.plate_code
        WHERE r.trade_date = ? AND r.source = 'uplimit_hot'
        GROUP BY r.plate_code
        ORDER BY r.rank_no
        LIMIT 10
        """,
        (date,),
    ).fetchall()

    result = []
    for plate in plates:
        p = row_to_dict(plate)
        plate_code = p["plate_code"]

        # Count how many recent days this plate was in hot rank
        hot_days = conn.execute(
            """
            SELECT COUNT(DISTINCT trade_date) as days
            FROM plate_hot_rank
            WHERE plate_code = ? AND trade_date <= ? AND source = 'uplimit_hot'
            AND trade_date >= date(?, '-30 days')
            """,
            (plate_code, date, date),
        ).fetchone()
        p["days_in_hot"] = hot_days["days"] if hot_days else 0

        # Check if this plate is new (not in hot rank in previous 5 trading days)
        prev_count = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM plate_hot_rank
            WHERE plate_code = ? AND trade_date < ? AND source = 'uplimit_hot'
            AND trade_date >= (
                SELECT trade_date FROM (
                    SELECT DISTINCT trade_date FROM plate_hot_rank
                    WHERE trade_date < ? ORDER BY trade_date DESC LIMIT 5
                ) ORDER BY trade_date ASC LIMIT 1
            )
            """,
            (plate_code, date, date),
        ).fetchone()
        p["is_new"] = (prev_count["cnt"] == 0) if prev_count else True

        result.append(p)

    return result


def get_recent_hot_plates_with_stocks(
    conn: sqlite3.Connection,
    date: str,
    days: int = 5,
    plate_limit: int = 12,
    stock_limit: int = 8,
) -> dict[str, Any]:
    """Return recent hot plates and their front stocks for the review home."""
    recent_dates = get_recent_dates(conn, date, days)
    if not recent_dates:
        return {"dates": [], "plates": []}

    placeholders = ",".join("?" for _ in recent_dates)
    plate_rows = conn.execute(
        f"""
        SELECT
            r.plate_code,
            COALESCE(MAX(r.plate_name), r.plate_code) as plate_name,
            MIN(r.rank_no) as best_rank,
            COUNT(DISTINCT r.trade_date) as active_days,
            SUM(COALESCE(day_counts.limit_up_count, 0)) as limit_up_count,
            SUM(CASE WHEN r.trade_date = ? THEN COALESCE(day_counts.limit_up_count, 0) ELSE 0 END) as today_limit_up_count,
            MAX(COALESCE(r.score, 0)) as max_score
        FROM plate_hot_rank r
        LEFT JOIN (
            SELECT trade_date, plate_code, COUNT(DISTINCT stock_code) as limit_up_count
            FROM limit_up_plate_map
            WHERE trade_date IN ({placeholders})
            GROUP BY trade_date, plate_code
        ) day_counts
          ON day_counts.trade_date = r.trade_date AND day_counts.plate_code = r.plate_code
        WHERE r.trade_date IN ({placeholders})
          AND r.source = 'uplimit_hot'
        GROUP BY r.plate_code
        ORDER BY active_days DESC, today_limit_up_count DESC, limit_up_count DESC, best_rank ASC
        LIMIT ?
        """,
        (date, *recent_dates, *recent_dates, plate_limit),
    ).fetchall()

    plates: list[dict[str, Any]] = []
    for plate_row in plate_rows:
        plate = row_to_dict(plate_row)
        stock_rows = conn.execute(
            f"""
            SELECT
                e.stock_code,
                COALESCE(MAX(e.stock_name), e.stock_code) as stock_name,
                COUNT(DISTINCT e.trade_date) as active_days,
                MAX(COALESCE(e.up_limit_keep_times, 1)) as max_board,
                SUM(CASE WHEN e.trade_date = ? THEN 1 ELSE 0 END) as is_today_limit_up,
                MAX(CASE WHEN e.trade_date = ? THEN e.up_limit_keep_times ELSE NULL END) as today_board,
                MAX(CASE WHEN e.trade_date = ? THEN e.up_limit_time ELSE NULL END) as today_limit_time,
                MAX(CASE WHEN e.trade_date = ? THEN e.reason ELSE NULL END) as today_reason,
                MAX(COALESCE(e.fengdan_money, 0)) as max_fengdan_money,
                SUM(COALESCE(e.amount, 0)) as total_amount
            FROM limit_up_plate_map m
            JOIN limit_up_events e
              ON e.trade_date = m.trade_date AND e.stock_code = m.stock_code
            WHERE m.plate_code = ?
              AND m.trade_date IN ({placeholders})
            GROUP BY e.stock_code
            ORDER BY is_today_limit_up DESC, max_board DESC, active_days DESC,
                     max_fengdan_money DESC, today_limit_time ASC
            LIMIT ?
            """,
            (date, date, date, date, plate["plate_code"], *recent_dates, stock_limit),
        ).fetchall()
        plate["stocks"] = rows_to_list(stock_rows)
        plates.append(plate)

    return {
        "dates": sorted(recent_dates),
        "plates": plates,
    }


def get_high_stocks(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get high stocks: multi-board (>=2) or top fengdan money."""
    stocks = conn.execute(
        """
        SELECT
            e.stock_code, e.stock_name, e.up_limit_keep_times,
            e.up_limit_time, e.up_limit_type, e.fengdan_money,
            e.reason
        FROM limit_up_events e
        WHERE e.trade_date = ?
          AND (e.up_limit_keep_times >= 2 OR e.fengdan_money IS NOT NULL)
        ORDER BY e.up_limit_keep_times DESC, e.fengdan_money DESC
        LIMIT 20
        """,
        (date,),
    ).fetchall()

    result = []
    for s in stocks:
        stock_dict = row_to_dict(s)
        # Get plate info
        plates = conn.execute(
            """
            SELECT p.plate_name
            FROM limit_up_plate_map p
            WHERE p.trade_date = ? AND p.stock_code = ?
            ORDER BY p.plate_score DESC
            LIMIT 3
            """,
            (date, s["stock_code"]),
        ).fetchall()
        stock_dict["plates"] = [p["plate_name"] for p in plates]
        result.append(stock_dict)

    return result


def get_all_stocks(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get all limit-up stocks for a date with their primary plate info."""
    stocks = conn.execute(
        """
        SELECT
            e.stock_code, e.stock_name, e.stock_price,
            e.up_limit_time, e.up_limit_desc, e.up_limit_keep_times,
            e.up_limit_type, e.fengdan_money, e.fengdan_rate,
            e.reason, e.amount
        FROM limit_up_events e
        WHERE e.trade_date = ?
        ORDER BY e.up_limit_time ASC
        """,
        (date,),
    ).fetchall()

    result = []
    for s in stocks:
        stock_dict = row_to_dict(s)
        # Get the highest-ranked plate for this stock as primary plate
        plate_row = conn.execute(
            """
            SELECT p.plate_name, p.plate_code
            FROM limit_up_plate_map p
            LEFT JOIN plate_hot_rank r
                ON p.trade_date = r.trade_date AND p.plate_code = r.plate_code AND r.source = 'uplimit_hot'
            WHERE p.trade_date = ? AND p.stock_code = ?
            ORDER BY COALESCE(r.rank_no, 9999)
            LIMIT 1
            """,
            (date, s["stock_code"]),
        ).fetchone()
        if plate_row:
            stock_dict["primary_plate"] = plate_row["plate_name"]
            stock_dict["primary_plate_code"] = plate_row["plate_code"]
        else:
            stock_dict["primary_plate"] = None
            stock_dict["primary_plate_code"] = None

        # Get all plates
        plates = conn.execute(
            """
            SELECT p.plate_name
            FROM limit_up_plate_map p
            WHERE p.trade_date = ? AND p.stock_code = ?
            ORDER BY p.plate_score DESC
            """,
            (date, s["stock_code"]),
        ).fetchall()
        stock_dict["plates"] = [p["plate_name"] for p in plates]
        result.append(stock_dict)

    return result


def get_review_limit_up_reasons(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Return limit-up reasons grouped by plate for the review submodule."""
    stats_row = conn.execute(
        """
        SELECT
            COUNT(DISTINCT stock_code) as limit_up_count,
            SUM(CASE WHEN COALESCE(up_limit_keep_times, 1) <= 1 THEN 1 ELSE 0 END) as first_board_count,
            SUM(CASE WHEN COALESCE(up_limit_keep_times, 1) >= 2 THEN 1 ELSE 0 END) as multi_board_count,
            COALESCE(MAX(COALESCE(up_limit_keep_times, 1)), 0) as highest_board
        FROM limit_up_events
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchone()
    summary = row_to_dict(stats_row) if stats_row else {}
    summary = {
        "limit_up_count": summary.get("limit_up_count") or 0,
        "first_board_count": summary.get("first_board_count") or 0,
        "multi_board_count": summary.get("multi_board_count") or 0,
        "highest_board": summary.get("highest_board") or 0,
        "plate_count": 0,
    }

    plate_rows = conn.execute(
        """
        SELECT
            m.plate_code,
            COALESCE(MAX(m.plate_name), MAX(r.plate_name), m.plate_code) as plate_name,
            MAX(COALESCE(r.score, m.plate_score, 0)) as plate_score,
            MIN(r.rank_no) as rank_no,
            COUNT(DISTINCT m.stock_code) as limit_up_count
        FROM limit_up_plate_map m
        LEFT JOIN plate_hot_rank r
          ON r.trade_date = m.trade_date
         AND r.plate_code = m.plate_code
         AND r.source = 'uplimit_hot'
        WHERE m.trade_date = ?
        GROUP BY m.plate_code
        ORDER BY COALESCE(MIN(r.rank_no), 9999), plate_score DESC, limit_up_count DESC, plate_name ASC
        """,
        (date,),
    ).fetchall()

    items: list[dict[str, Any]] = []
    for plate in plate_rows:
        stock_rows = conn.execute(
            """
            SELECT
                e.stock_code,
                e.stock_name,
                e.stock_price,
                e.up_limit_time,
                e.up_limit_desc,
                e.up_limit_keep_times,
                e.up_limit_type,
                COALESCE(m.stock_reason, e.reason) as reason,
                e.fengdan_money,
                e.fengdan_rate,
                e.amount,
                e.circulation_value,
                e.turnover_rate,
                e.market_type
            FROM limit_up_plate_map m
            JOIN limit_up_events e
              ON e.trade_date = m.trade_date
             AND e.stock_code = m.stock_code
            WHERE m.trade_date = ? AND m.plate_code = ?
            ORDER BY COALESCE(e.up_limit_keep_times, 1) DESC,
                     e.up_limit_time ASC,
                     COALESCE(e.fengdan_money, 0) DESC,
                     e.stock_code ASC
            """,
            (date, plate["plate_code"]),
        ).fetchall()

        stocks: list[dict[str, Any]] = []
        reason_counts: dict[str, int] = {}
        for stock in stock_rows:
            concept_rows = conn.execute(
                """
                SELECT plate_name
                FROM limit_up_plate_map
                WHERE trade_date = ? AND stock_code = ?
                ORDER BY COALESCE(plate_score, 0) DESC, plate_name ASC
                """,
                (date, stock["stock_code"]),
            ).fetchall()
            reason = stock["reason"]
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            stocks.append({
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "price": stock["stock_price"],
                "limit_up_time": stock["up_limit_time"],
                "board_label": stock["up_limit_desc"],
                "board_count": stock["up_limit_keep_times"] or 1,
                "limit_up_type": stock["up_limit_type"],
                "reason": stock["reason"],
                "seal_amount": stock["fengdan_money"],
                "seal_rate": stock["fengdan_rate"],
                "turnover": stock["amount"],
                "free_float_market_cap": stock["circulation_value"],
                "turnover_rate": stock["turnover_rate"],
                "market_type": stock["market_type"],
                "concepts": [row["plate_name"] for row in concept_rows if row["plate_name"]],
            })

        reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        items.append({
            "plate_code": plate["plate_code"],
            "plate_name": plate["plate_name"],
            "plate_score": plate["plate_score"] or 0,
            "rank_no": plate["rank_no"],
            "limit_up_count": plate["limit_up_count"],
            "reasons": reasons,
            "stocks": stocks,
        })

    summary["plate_count"] = len(items)
    return make_review_payload(
        date,
        status="ok" if items else "empty",
        summary=summary,
        filters={"plates": [item["plate_name"] for item in items]},
        items=items,
    )


def _get_stock_concepts(conn: sqlite3.Connection, date: str, stock_code: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT plate_name
        FROM limit_up_plate_map
        WHERE trade_date = ? AND stock_code = ?
        ORDER BY COALESCE(plate_score, 0) DESC, plate_name ASC
        """,
        (date, stock_code),
    ).fetchall()
    return [row["plate_name"] for row in rows if row["plate_name"]]


def get_review_limit_up_tiers(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Return limit-up stocks grouped by consecutive board level."""
    rows = conn.execute(
        """
        SELECT
            COALESCE(up_limit_keep_times, 1) as level,
            stock_code,
            stock_name,
            stock_price,
            up_limit_time,
            up_limit_desc,
            up_limit_type,
            reason,
            fengdan_money,
            amount,
            circulation_value,
            turnover_rate
        FROM limit_up_events
        WHERE trade_date = ?
        ORDER BY level DESC, up_limit_time ASC, COALESCE(fengdan_money, 0) DESC, stock_code ASC
        """,
        (date,),
    ).fetchall()

    tiers: dict[int, dict[str, Any]] = {}
    for row in rows:
        level = row["level"] or 1
        tier = tiers.setdefault(level, {
            "level": level,
            "label": "first-board" if level == 1 else f"{level}-board",
            "count": 0,
            "stocks": [],
        })
        tier["count"] += 1
        tier["stocks"].append({
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"],
            "price": row["stock_price"],
            "limit_up_time": row["up_limit_time"],
            "board_label": row["up_limit_desc"],
            "limit_up_type": row["up_limit_type"],
            "reason": row["reason"],
            "seal_amount": row["fengdan_money"],
            "turnover": row["amount"],
            "free_float_market_cap": row["circulation_value"],
            "turnover_rate": row["turnover_rate"],
            "concepts": _get_stock_concepts(conn, date, row["stock_code"]),
        })

    broken_rows = conn.execute(
        """
        SELECT stock_code, stock_name, latest_price, change_pct, first_limit_up_time,
               open_count, limit_up_stat, industry, amount, turnover_rate
        FROM broken_limit_up_events
        WHERE trade_date = ?
        ORDER BY COALESCE(open_count, 0) DESC, COALESCE(amount, 0) DESC, stock_code ASC
        """,
        (date,),
    ).fetchall()
    if broken_rows:
        tiers[0] = {
            "level": 0,
            "label": "broken-limit-up",
            "count": len(broken_rows),
            "stocks": [{
                "stock_code": row["stock_code"],
                "stock_name": row["stock_name"],
                "price": row["latest_price"],
                "change_pct": row["change_pct"],
                "limit_up_time": row["first_limit_up_time"],
                "open_count": row["open_count"],
                "limit_up_stat": row["limit_up_stat"],
                "industry": row["industry"],
                "turnover": row["amount"],
                "turnover_rate": row["turnover_rate"],
            } for row in broken_rows],
        }

    items = [tiers[level] for level in sorted(tiers.keys(), reverse=True)]
    summary = {
        "limit_up_count": sum(item["count"] for item in items if item["level"] > 0),
        "broken_count": tiers.get(0, {}).get("count", 0),
        "tier_count": len([item for item in items if item["level"] > 0]),
        "highest_board": max([item["level"] for item in items if item["level"] > 0], default=0),
    }
    return make_review_payload(
        date,
        status="ok" if items else "empty",
        summary=summary,
        filters={"levels": [item["level"] for item in items]},
        items=items,
    )


def get_review_promotions(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Return board promotion results based on previous trading day."""
    prev_date = get_prev_trade_date(conn, date)
    items = get_board_advancement(conn, date)
    total = sum(item["total"] for item in items)
    advanced = sum(item["advanced"] for item in items)
    summary = {
        "base_date": prev_date,
        "total": total,
        "advanced": advanced,
        "advancement_rate": _pct(advanced, total),
        "level_count": len(items),
    }
    return make_review_payload(
        date,
        status="ok" if items else "empty",
        summary=summary,
        filters={"base_date": prev_date},
        items=items,
        warnings=[] if prev_date else ["缺少前一交易日涨停数据，无法计算晋级。"],
    )


def get_review_price_tiers(conn: sqlite3.Connection, date: str, days: int = 10) -> dict[str, Any]:
    """Return cumulative price-change tiers. This needs enough daily K-line data."""
    date_rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM stock_kline_daily
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (date, days),
    ).fetchall()
    dates = sorted([row["trade_date"] for row in date_rows])
    if len(dates) < 2:
        return make_review_payload(
            date,
            status="partial",
            summary={"days": days, "stock_count": 0},
            filters={"days": days},
            items=[],
            warnings=["缺少足够的个股日 K 数据，暂时不能计算涨幅梯队。"],
        )

    start_date = dates[0]
    end_date = dates[-1]
    rows = conn.execute(
        """
        WITH bounds AS (
            SELECT
                stock_code,
                MIN(trade_date) as start_date,
                MAX(trade_date) as end_date,
                COUNT(*) as sample_days
            FROM stock_kline_daily
            WHERE trade_date BETWEEN ? AND ?
              AND close_price IS NOT NULL
            GROUP BY stock_code
            HAVING sample_days >= 2
        )
        SELECT
            b.stock_code,
            COALESCE(s.stock_name, b.stock_code) as stock_name,
            start_k.close_price as start_close,
            end_k.close_price as end_close,
            start_k.trade_date as stock_start_date,
            end_k.trade_date as stock_end_date,
            b.sample_days,
            end_k.amount
        FROM bounds b
        JOIN stock_kline_daily start_k
          ON start_k.stock_code = b.stock_code
         AND start_k.trade_date = b.start_date
        JOIN stock_kline_daily end_k
          ON end_k.stock_code = b.stock_code
         AND end_k.trade_date = b.end_date
        LEFT JOIN stocks s ON s.stock_code = b.stock_code
        WHERE start_k.close_price IS NOT NULL
          AND start_k.close_price > 0
          AND end_k.close_price IS NOT NULL
        """,
        (start_date, end_date),
    ).fetchall()

    buckets = [
        (100, None, ">=100%"),
        (80, 100, "80%-100%"),
        (60, 80, "60%-80%"),
        (40, 60, "40%-60%"),
        (20, 40, "20%-40%"),
        (0, 20, "0%-20%"),
        (None, 0, "<0%"),
    ]
    items = [{"range": label, "min_pct": low, "max_pct": high, "count": 0, "stocks": []} for low, high, label in buckets]
    for row in rows:
        pct = _round_or_none((row["end_close"] - row["start_close"]) / row["start_close"] * 100)
        if pct is None:
            continue
        for bucket in items:
            low = bucket["min_pct"]
            high = bucket["max_pct"]
            if (low is None or pct >= low) and (high is None or pct < high):
                bucket["count"] += 1
                bucket["stocks"].append({
                    "stock_code": row["stock_code"],
                    "stock_name": row["stock_name"],
                    "change_pct": pct,
                    "start_close": row["start_close"],
                    "end_close": row["end_close"],
                    "start_date": row["stock_start_date"],
                    "end_date": row["stock_end_date"],
                    "sample_days": row["sample_days"],
                    "amount": row["amount"],
                })
                break

    return make_review_payload(
        date,
        status="ok" if rows else "empty",
        summary={"days": len(dates), "start_date": start_date, "end_date": end_date, "stock_count": len(rows)},
        filters={"days": days},
        items=[item for item in items if item["count"]],
    )


def get_review_lhb(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Return daily Dragon Tiger List rows."""
    rows = conn.execute(
        """
        SELECT
            l.stock_code, l.stock_name, l.reason,
            l.buy_amount, l.sell_amount, l.net_buy_amount, l.raw_payload,
            u.up_limit_desc, u.up_limit_keep_times, u.up_limit_time, u.fengdan_money
        FROM lhb_daily l
        LEFT JOIN limit_up_events u
            ON u.trade_date = l.trade_date AND u.stock_code = l.stock_code
        WHERE l.trade_date = ?
        ORDER BY ABS(COALESCE(l.net_buy_amount, 0)) DESC, l.stock_code ASC
        """,
        (date,),
    ).fetchall()
    items = []
    for row in rows:
        raw = _json_dict(row["raw_payload"])
        items.append({
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"],
            "reason": row["reason"],
            "buy_amount": row["buy_amount"],
            "sell_amount": row["sell_amount"],
            "net_buy_amount": row["net_buy_amount"],
            "close_price": raw.get("close_price"),
            "change_pct": raw.get("change_pct"),
            "turnover_rate": raw.get("turnover_rate"),
            "interpretation": (raw.get("raw") or {}).get("解读") if isinstance(raw.get("raw"), dict) else None,
            "is_limit_up": row["up_limit_desc"] is not None,
            "board_label": row["up_limit_desc"],
            "board_level": row["up_limit_keep_times"],
            "up_limit_time": row["up_limit_time"],
            "seal_amount": row["fengdan_money"],
            "concepts": _get_stock_concepts(conn, date, row["stock_code"]),
            "raw": raw,
        })
    summary = {
        "count": len(items),
        "distinct_stock_count": len({item["stock_code"] for item in items}),
        "limit_up_stock_count": len({item["stock_code"] for item in items if item["is_limit_up"]}),
        "net_buy_count": sum(1 for item in items if (item["net_buy_amount"] or 0) >= 0),
        "net_sell_count": sum(1 for item in items if (item["net_buy_amount"] or 0) < 0),
        "buy_amount": sum(item["buy_amount"] or 0 for item in items),
        "sell_amount": sum(item["sell_amount"] or 0 for item in items),
        "net_buy_amount": sum(item["net_buy_amount"] or 0 for item in items),
    }
    return make_review_payload(date, status="ok" if items else "empty", summary=summary, items=items)


def get_review_movement_alerts(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Return intraday movement alerts."""
    rows = conn.execute(
        """
        SELECT alert_time, stock_code, stock_name, alert_type, alert_text, price, change_pct, raw_payload
        FROM movement_alerts
        WHERE trade_date = ?
        ORDER BY alert_time DESC, stock_code ASC
        """,
        (date,),
    ).fetchall()
    items = [{
        "alert_time": row["alert_time"],
        "stock_code": row["stock_code"],
        "stock_name": row["stock_name"],
        "alert_type": row["alert_type"],
        "alert_text": row["alert_text"],
        "price": row["price"],
        "change_pct": row["change_pct"],
        "raw": _json_dict(row["raw_payload"]),
    } for row in rows]
    types = sorted({item["alert_type"] for item in items if item["alert_type"]})
    return make_review_payload(
        date,
        status="ok" if items else "empty",
        summary={"alert_count": len(items), "stock_count": len({item["stock_code"] for item in items})},
        filters={"types": types},
        items=items,
    )


def get_review_plate_rotation(
    conn: sqlite3.Connection,
    date: str | None = None,
    days: int = 8,
    top_n: int = 12,
    plate_code: str | None = None,
) -> dict[str, Any]:
    """Wrap plate rotation data with selected plate detail for the review module."""
    snapshot = get_plate_rotation_snapshot(conn, date, days=days, top_n=top_n, plate_code=plate_code)
    items = [{"date": day, "plates": plates} for day, plates in snapshot.get("rank_by_date", {}).items()]
    detail = snapshot.get("selected_plate")
    result_date = snapshot.get("date") or date or ""
    payload = make_review_payload(
        result_date,
        status="ok" if items else "empty",
        summary={
            "days": len(snapshot.get("dates") or []),
            "top_n": top_n,
            "selected_plate_code": (detail or {}).get("plate_code"),
        },
        filters={"days": days, "top_n": top_n, "plate_code": plate_code},
        items=items,
        warnings=[] if items else ["缺少题材轮动数据，请先运行板块轮动采集任务。"],
    )
    payload["detail"] = detail
    return payload


def get_dates(conn: sqlite3.Connection) -> list[str]:
    """Get list of available trade dates."""
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM limit_up_events
        ORDER BY trade_date DESC
        """
    ).fetchall()
    return [r["trade_date"] for r in rows]


def get_prev_trade_date(conn: sqlite3.Connection, date: str) -> str | None:
    """Get the previous trading date before the given date."""
    row = conn.execute(
        """
        SELECT MAX(trade_date) as prev_date
        FROM limit_up_events
        WHERE trade_date < ?
        """,
        (date,),
    ).fetchone()
    return row["prev_date"] if row else None


def get_recent_dates(conn: sqlite3.Connection, date: str, days: int) -> list[str]:
    """Get up to `days` trading dates ending at `date`."""
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM limit_up_events
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (date, days),
    ).fetchall()
    return [r["trade_date"] for r in rows]


def get_market_environment(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Get broad market context for daily review."""
    breadth_row = conn.execute(
        """
        SELECT total_count, up_count, down_count, flat_count,
               limit_up_count, limit_down_count, natural_limit_up_count,
               natural_limit_down_count, avg_change_pct, amount
        FROM market_breadth_daily
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchone()
    breadth = row_to_dict(breadth_row) if breadth_row else {
        "total_count": 0,
        "up_count": 0,
        "down_count": 0,
        "flat_count": 0,
        "limit_up_count": 0,
        "limit_down_count": 0,
        "natural_limit_up_count": 0,
        "natural_limit_down_count": 0,
        "avg_change_pct": None,
        "amount": 0,
    }
    total = breadth.get("total_count") or 0
    breadth["up_rate"] = round((breadth.get("up_count") or 0) / total * 100, 1) if total else 0

    limit_down_total = conn.execute(
        "SELECT COUNT(*) as total FROM limit_down_events WHERE trade_date = ?",
        (date,),
    ).fetchone()["total"]
    broken_limit_up_total = conn.execute(
        "SELECT COUNT(*) as total FROM broken_limit_up_events WHERE trade_date = ?",
        (date,),
    ).fetchone()["total"]

    if not breadth.get("limit_up_count"):
        breadth["limit_up_count"] = conn.execute(
            "SELECT COUNT(*) as total FROM limit_up_events WHERE trade_date = ?",
            (date,),
        ).fetchone()["total"]
    if not breadth.get("limit_down_count") and limit_down_total:
        breadth["limit_down_count"] = limit_down_total

    limit_down_rows = conn.execute(
        """
        SELECT stock_code, stock_name, latest_price, change_pct,
               limit_down_days, open_count, industry
        FROM limit_down_events
        WHERE trade_date = ?
        ORDER BY change_pct ASC, amount DESC
        LIMIT 20
        """,
        (date,),
    ).fetchall()

    broken_rows = conn.execute(
        """
        SELECT stock_code, stock_name, latest_price, change_pct,
               first_limit_up_time, open_count, limit_up_stat, industry
        FROM broken_limit_up_events
        WHERE trade_date = ?
        ORDER BY open_count DESC, amount DESC
        LIMIT 20
        """,
        (date,),
    ).fetchall()

    lhb_rows = conn.execute(
        """
        SELECT stock_code, stock_name, reason, buy_amount, sell_amount, net_buy_amount
        FROM lhb_daily
        WHERE trade_date = ?
        ORDER BY ABS(COALESCE(net_buy_amount, 0)) DESC
        LIMIT 20
        """,
        (date,),
    ).fetchall()

    movement_rows = conn.execute(
        """
        SELECT alert_type, COUNT(*) as count
        FROM movement_alerts
        WHERE trade_date = ?
        GROUP BY alert_type
        ORDER BY count DESC
        LIMIT 12
        """,
        (date,),
    ).fetchall()

    market_hot_rows = conn.execute(
        """
        SELECT item_name, score, rank_no, raw_payload
        FROM market_hot_daily
        WHERE trade_date = ?
        ORDER BY rank_no
        LIMIT 12
        """,
        (date,),
    ).fetchall()

    return {
        "breadth": breadth,
        "limit_down_total": limit_down_total,
        "broken_limit_up_total": broken_limit_up_total,
        "limit_down": rows_to_list(limit_down_rows),
        "broken_limit_up": rows_to_list(broken_rows),
        "lhb": rows_to_list(lhb_rows),
        "movement_summary": rows_to_list(movement_rows),
        "market_hot": rows_to_list(market_hot_rows),
    }


def get_market_overview_trend(conn: sqlite3.Connection, date: str, days: int = 5) -> list[dict[str, Any]]:
    """Return recent market overview metrics for charting."""
    rows = conn.execute(
        """
        SELECT trade_date
        FROM (
            SELECT DISTINCT trade_date FROM limit_up_events WHERE trade_date <= ?
            UNION
            SELECT DISTINCT trade_date FROM market_breadth_daily WHERE trade_date <= ?
        )
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (date, date, days),
    ).fetchall()
    recent_dates = [row["trade_date"] for row in rows]
    result: list[dict[str, Any]] = []
    prev_amount: float | None = None

    for trade_date in sorted(recent_dates):
        breadth_row = conn.execute(
            """
            SELECT total_count, up_count, down_count, flat_count,
                   limit_up_count, limit_down_count, natural_limit_up_count,
                   natural_limit_down_count, avg_change_pct, amount
            FROM market_breadth_daily
            WHERE trade_date = ?
            """,
            (trade_date,),
        ).fetchone()
        breadth = row_to_dict(breadth_row) if breadth_row else {}

        limit_up_stats = get_limit_up_stats(conn, trade_date)
        event_limit_up_count = limit_up_stats.get("total") or 0
        limit_up_count = breadth.get("limit_up_count") or event_limit_up_count
        highest_board = limit_up_stats.get("highest_board") or 0

        limit_down_total = conn.execute(
            "SELECT COUNT(*) as total FROM limit_down_events WHERE trade_date = ?",
            (trade_date,),
        ).fetchone()["total"]
        limit_down_count = breadth.get("limit_down_count") or limit_down_total or 0

        broken_limit_up_count = conn.execute(
            "SELECT COUNT(*) as total FROM broken_limit_up_events WHERE trade_date = ?",
            (trade_date,),
        ).fetchone()["total"]

        amount = breadth.get("amount")

        total_count = breadth.get("total_count") or 0
        up_count = breadth.get("up_count") or 0
        down_count = breadth.get("down_count") or 0
        flat_count = breadth.get("flat_count") or 0
        up_rate = round(up_count / total_count * 100, 1) if total_count else None

        amount_change_pct = None
        if amount is not None and prev_amount:
            amount_change_pct = round((amount - prev_amount) / prev_amount * 100, 2)
        if amount is not None:
            prev_amount = amount

        result.append({
            "date": trade_date,
            "amount": amount,
            "amount_change_pct": amount_change_pct,
            "total_count": total_count,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "up_rate": up_rate,
            "natural_limit_up_count": breadth.get("natural_limit_up_count"),
            "natural_limit_down_count": breadth.get("natural_limit_down_count"),
            "avg_change_pct": breadth.get("avg_change_pct"),
            "limit_up_count": limit_up_count,
            "has_limit_up_events": event_limit_up_count > 0,
            "limit_down_count": limit_down_count,
            "broken_limit_up_count": broken_limit_up_count,
            "highest_board": highest_board,
        })

    return result


def get_emotion_heat_trend(conn: sqlite3.Connection, date: str, days: int = 60) -> list[dict[str, Any]]:
    """Return daily sources needed for sentiment heat, hot-stock emotion and space-board review."""
    rows = conn.execute(
        """
        SELECT trade_date
        FROM (
            SELECT DISTINCT trade_date FROM limit_up_events WHERE trade_date <= ?
            UNION
            SELECT DISTINCT trade_date FROM market_breadth_daily WHERE trade_date <= ?
            UNION
            SELECT DISTINCT trade_date FROM hot_stocks WHERE trade_date <= ?
        )
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (date, date, date, days),
    ).fetchall()
    recent_dates = [row["trade_date"] for row in rows]
    result: list[dict[str, Any]] = []

    for trade_date in sorted(recent_dates):
        breadth_row = conn.execute(
            """
            SELECT total_count, up_count, down_count, flat_count,
                   limit_up_count, limit_down_count, natural_limit_up_count,
                   natural_limit_down_count, avg_change_pct, amount
            FROM market_breadth_daily
            WHERE trade_date = ?
            """,
            (trade_date,),
        ).fetchone()
        breadth = row_to_dict(breadth_row) if breadth_row else {}

        limit_up_stats = get_limit_up_stats(conn, trade_date)
        event_limit_up_count = limit_up_stats.get("total") or 0
        limit_up_count = event_limit_up_count or breadth.get("limit_up_count") or 0
        highest_board = (limit_up_stats.get("highest_board") or 0) if event_limit_up_count else 0

        limit_down_total = conn.execute(
            "SELECT COUNT(*) as total FROM limit_down_events WHERE trade_date = ?",
            (trade_date,),
        ).fetchone()["total"]
        limit_down_count = breadth.get("limit_down_count") or limit_down_total or 0

        broken_limit_up_count = conn.execute(
            "SELECT COUNT(*) as total FROM broken_limit_up_events WHERE trade_date = ?",
            (trade_date,),
        ).fetchone()["total"]

        seal_denominator = limit_up_count + broken_limit_up_count
        seal_success_rate = _pct(limit_up_count, seal_denominator)
        broken_rate = _pct(broken_limit_up_count, seal_denominator)

        seal_row = conn.execute(
            """
            SELECT AVG(fengdan_money) as avg_fengdan_money,
                   AVG(fengdan_rate) as avg_fengdan_rate
            FROM limit_up_events
            WHERE trade_date = ?
            """,
            (trade_date,),
        ).fetchone()

        space_rows = []
        if highest_board:
            space_rows = conn.execute(
                """
                SELECT stock_code, stock_name, up_limit_keep_times, up_limit_desc,
                       up_limit_time, fengdan_money, fengdan_rate
                FROM limit_up_events
                WHERE trade_date = ? AND up_limit_keep_times = ?
                ORDER BY COALESCE(fengdan_money, 0) DESC, up_limit_time ASC
                """,
                (trade_date, highest_board),
            ).fetchall()

        hot_filter = _hot_stock_source_filter(conn, trade_date)
        hot_rows = conn.execute(
            f"""
            SELECT rank_no, stock_code, stock_name, latest_price, change_pct,
                   change_amount, amount, turnover_rate, source
            FROM hot_stocks
            WHERE trade_date = ? AND {hot_filter}
            ORDER BY rank_no, stock_code
            LIMIT 20
            """,
            (trade_date,),
        ).fetchall()
        hot_items = rows_to_list(hot_rows)
        hot_changes = [
            float(item["change_pct"])
            for item in hot_items
            if item.get("change_pct") is not None
        ]
        hot_codes = [item["stock_code"] for item in hot_items if item.get("stock_code")]
        hot_limit_up_overlap_count = 0
        if hot_codes:
            placeholders = ",".join("?" for _ in hot_codes)
            hot_limit_up_overlap_count = conn.execute(
                f"""
                SELECT COUNT(DISTINCT stock_code) as total
                FROM limit_up_events
                WHERE trade_date = ? AND stock_code IN ({placeholders})
                """,
                [trade_date, *hot_codes],
            ).fetchone()["total"]

        total_count = breadth.get("total_count") or 0
        up_count = breadth.get("up_count") or 0
        down_count = breadth.get("down_count") or 0

        result.append({
            "date": trade_date,
            "has_market_breadth": bool(breadth_row),
            "has_hot_stocks": bool(hot_items),
            "has_limit_down_events": limit_down_total > 0,
            "has_broken_limit_up_events": broken_limit_up_count > 0,
            "total_count": total_count,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": breadth.get("flat_count") or 0,
            "up_rate": _pct(up_count, total_count),
            "down_rate": _pct(down_count, total_count),
            "avg_change_pct": breadth.get("avg_change_pct"),
            "amount": breadth.get("amount"),
            "limit_up_count": limit_up_count,
            "limit_up_event_count": event_limit_up_count,
            "natural_limit_up_count": breadth.get("natural_limit_up_count"),
            "limit_down_count": limit_down_count,
            "natural_limit_down_count": breadth.get("natural_limit_down_count"),
            "broken_limit_up_count": broken_limit_up_count,
            "seal_success_rate": seal_success_rate,
            "broken_rate": broken_rate,
            "avg_fengdan_money": _round_or_none(seal_row["avg_fengdan_money"] if seal_row else None, 0),
            "avg_fengdan_rate": _round_or_none(seal_row["avg_fengdan_rate"] if seal_row else None, 2),
            "highest_board": highest_board,
            "space_board_stocks": rows_to_list(space_rows),
            "hot_top20_count": len(hot_items),
            "hot_top20_avg_change_pct": _round_or_none(sum(hot_changes) / len(hot_changes), 2) if hot_changes else None,
            "hot_top20_up_count": sum(1 for value in hot_changes if value > 0),
            "hot_top20_down_count": sum(1 for value in hot_changes if value < 0),
            "hot_top20_heavy_fall_count": sum(1 for value in hot_changes if value <= -5),
            "hot_limit_up_overlap_count": hot_limit_up_overlap_count,
            "hot_limit_up_overlap_rate": _pct(hot_limit_up_overlap_count, len(hot_items)),
            "hot_top20": hot_items,
        })

    return result


def get_quantzz_daily_overview(conn: sqlite3.Connection, date: str, days: int = 60) -> dict[str, Any]:
    """Return a Quantzz-style daily overview without intraday-only data."""
    heat_trend = get_emotion_heat_trend(conn, date, days)
    latest_heat = heat_trend[-1] if heat_trend else {}
    hot_stocks = get_hot_stocks_rank(conn, date, limit=20)
    hot_codes = [item["stock_code"] for item in hot_stocks if item.get("stock_code")]
    overlap_count = 0
    if hot_codes:
        placeholders = ",".join("?" for _ in hot_codes)
        overlap_count = conn.execute(
            f"""
            SELECT COUNT(DISTINCT stock_code) as total
            FROM limit_up_events
            WHERE trade_date = ? AND stock_code IN ({placeholders})
            """,
            [date, *hot_codes],
        ).fetchone()["total"]

    highest_board = latest_heat.get("highest_board") or 0
    space_board_stocks = latest_heat.get("space_board_stocks") or []
    concept_boards = get_hot_boards_rank(conn, date, board_type="concept", limit=10)
    industry_boards = get_hot_boards_rank(conn, date, board_type="industry", limit=10)
    promotion = get_board_advancement(conn, date)

    market = {
        "total_count": latest_heat.get("total_count") or 0,
        "up_count": latest_heat.get("up_count") or 0,
        "down_count": latest_heat.get("down_count") or 0,
        "flat_count": latest_heat.get("flat_count") or 0,
        "up_rate": latest_heat.get("up_rate"),
        "down_rate": latest_heat.get("down_rate"),
        "avg_change_pct": latest_heat.get("avg_change_pct"),
        "amount": latest_heat.get("amount"),
        "limit_up_count": latest_heat.get("limit_up_count") or 0,
        "natural_limit_up_count": latest_heat.get("natural_limit_up_count"),
        "natural_limit_down_count": latest_heat.get("natural_limit_down_count"),
        "seal_success_rate": latest_heat.get("seal_success_rate"),
        "broken_rate": latest_heat.get("broken_rate"),
    }

    limit_down_rows = conn.execute(
        """
        SELECT stock_code, stock_name, latest_price, change_pct, limit_down_days,
               open_count, industry
        FROM limit_down_events
        WHERE trade_date = ?
        ORDER BY change_pct ASC
        LIMIT 8
        """,
        (date,),
    ).fetchall()
    broken_rows = conn.execute(
        """
        SELECT stock_code, stock_name, latest_price, change_pct, first_limit_up_time,
               open_count, limit_up_stat, industry
        FROM broken_limit_up_events
        WHERE trade_date = ?
        ORDER BY open_count DESC
        LIMIT 8
        """,
        (date,),
    ).fetchall()
    loss_feedback = {
        "limit_down_count": conn.execute(
            "SELECT COUNT(*) as total FROM limit_down_events WHERE trade_date = ?",
            (date,),
        ).fetchone()["total"],
        "broken_limit_up_count": conn.execute(
            "SELECT COUNT(*) as total FROM broken_limit_up_events WHERE trade_date = ?",
            (date,),
        ).fetchone()["total"],
        "heavy_fall_hot_count": latest_heat.get("hot_top20_heavy_fall_count") or 0,
        "limit_down": rows_to_list(limit_down_rows),
        "broken_limit_up": rows_to_list(broken_rows),
    }

    missing_sources = [
        {
            "key": "auction",
            "title": "竞价数据",
            "status": "missing",
            "reason": "集合竞价属于盘前/分时口径，当前日线库还没有竞价金额、竞价涨幅和竞价委买额。",
        },
        {
            "key": "intraday_heat",
            "title": "日内情绪热度",
            "status": "skipped",
            "reason": "你已经明确不需要分时数据，这部分不进入当前版本。",
        },
        {
            "key": "topic_library",
            "title": "题材库原文",
            "status": "missing",
            "reason": "当前有板块日线和涨停原因，但还没有资讯原文、题材分层和人工题材库。",
        },
        {
            "key": "strategy_trades",
            "title": "策略交易流水",
            "status": "missing",
            "reason": "当前是复盘系统，还没有模拟交易、持仓和资金曲线。",
        },
    ]

    return {
        "date": date,
        "days": days,
        "market": market,
        "emotion_heat": latest_heat,
        "emotion_trend": heat_trend,
        "space_board": {
            "highest_board": highest_board,
            "stocks": space_board_stocks,
        },
        "popularity": {
            "top20_count": len(hot_stocks),
            "top20": hot_stocks,
            "avg_change_pct": latest_heat.get("hot_top20_avg_change_pct"),
            "up_count": latest_heat.get("hot_top20_up_count") or 0,
            "down_count": latest_heat.get("hot_top20_down_count") or 0,
            "heavy_fall_count": latest_heat.get("hot_top20_heavy_fall_count") or 0,
            "limit_up_overlap_count": overlap_count,
            "limit_up_overlap_rate": _pct(overlap_count, len(hot_stocks)),
        },
        "hot_boards": {
            "concept": concept_boards,
            "industry": industry_boards,
        },
        "promotion": {
            "levels": promotion,
        },
        "loss_feedback": loss_feedback,
        "missing_sources": missing_sources,
    }


def get_emotion_modules(conn: sqlite3.Connection, date: str, days: int = 60) -> dict[str, Any]:
    """Return Quantzz-style emotion module tabs built from local tables."""
    from server.services.emotion_scorer import compute_emotion

    heat_trend = get_emotion_heat_trend(conn, date, days)
    yearly_trend = get_emotion_heat_trend(conn, date, 250)
    quantzz = get_quantzz_daily_overview(conn, date, days)
    emotion = compute_emotion(conn, date)
    latest_heat = quantzz.get("emotion_heat") or (heat_trend[-1] if heat_trend else {})
    prev_heat = heat_trend[-2] if len(heat_trend) >= 2 else {}

    movement_rows = conn.execute(
        """
        select alert_time, stock_code, stock_name, alert_type, alert_text, price, change_pct
        from movement_alerts
        where trade_date = ?
        order by alert_time desc
        limit 80
        """,
        (date,),
    ).fetchall()
    movement_items = rows_to_list(movement_rows)
    movement_summary = conn.execute(
        """
        select alert_type, count(*) as count
        from movement_alerts
        where trade_date = ?
        group by alert_type
        order by count desc
        limit 8
        """,
        (date,),
    ).fetchall()

    current_hot = quantzz.get("popularity", {}).get("top20") or latest_heat.get("hot_top20") or []
    prev_hot = prev_heat.get("hot_top20") or []
    prev_rank = {item.get("stock_code"): item.get("rank_no") for item in prev_hot if item.get("stock_code")}
    hot_compare = []
    for item in current_hot:
        code = item.get("stock_code")
        old_rank = prev_rank.get(code)
        rank = item.get("rank_no")
        rank_change = (old_rank - rank) if old_rank is not None and rank is not None else None
        hot_compare.append({**item, "prev_rank_no": old_rank, "rank_change": rank_change})

    yearly_limit_up = [row.get("limit_up_count") or 0 for row in yearly_trend]
    yearly_high_board = [row.get("highest_board") or 0 for row in yearly_trend]
    yearly_up_rate = [row.get("up_rate") for row in yearly_trend if row.get("up_rate") is not None]

    modules = [
        {
            "key": "cycle",
            "label": "情绪周期",
            "status": "ok",
            "summary": {
                "score": emotion.get("total_score"),
                "level": emotion.get("level"),
                "advice": emotion.get("advice"),
                "limit_up_count": latest_heat.get("limit_up_count"),
                "highest_board": latest_heat.get("highest_board"),
                "broken_rate": latest_heat.get("broken_rate"),
            },
            "items": heat_trend,
            "warnings": [],
        },
        {
            "key": "intraday",
            "label": "情绪日内",
            "status": "ok" if movement_items else "empty",
            "summary": {
                "alert_count": len(movement_items),
                "top_types": rows_to_list(movement_summary),
            },
            "items": movement_items,
            "warnings": [] if movement_items else ["暂无日内异动数据"],
        },
        {
            "key": "cycle_vip",
            "label": "情绪周期VIP",
            "status": "ok",
            "summary": {
                "seal_success_rate": latest_heat.get("seal_success_rate"),
                "broken_rate": latest_heat.get("broken_rate"),
                "hot_top20_avg_change_pct": latest_heat.get("hot_top20_avg_change_pct"),
                "hot_top20_heavy_fall_count": latest_heat.get("hot_top20_heavy_fall_count"),
                "limit_down_count": quantzz.get("loss_feedback", {}).get("limit_down_count"),
                "broken_limit_up_count": quantzz.get("loss_feedback", {}).get("broken_limit_up_count"),
            },
            "items": quantzz.get("promotion", {}).get("levels") or [],
            "warnings": [],
        },
        {
            "key": "cycle_year",
            "label": "情绪周期-年",
            "status": "ok" if yearly_trend else "empty",
            "summary": {
                "days": len(yearly_trend),
                "max_limit_up_count": max(yearly_limit_up) if yearly_limit_up else 0,
                "max_highest_board": max(yearly_high_board) if yearly_high_board else 0,
                "avg_up_rate": _round_or_none(sum(yearly_up_rate) / len(yearly_up_rate), 1) if yearly_up_rate else None,
            },
            "items": yearly_trend,
            "warnings": [],
        },
        {
            "key": "space_board",
            "label": "空间板",
            "status": "ok" if quantzz.get("space_board", {}).get("stocks") else "empty",
            "summary": {
                "highest_board": quantzz.get("space_board", {}).get("highest_board") or 0,
                "stock_count": len(quantzz.get("space_board", {}).get("stocks") or []),
            },
            "items": quantzz.get("space_board", {}).get("stocks") or [],
            "warnings": [],
        },
        {
            "key": "popularity",
            "label": "人气",
            "status": "ok" if current_hot else "empty",
            "summary": quantzz.get("popularity") or {},
            "items": current_hot,
            "warnings": [],
        },
        {
            "key": "popularity_compare",
            "label": "人气对比",
            "status": "ok" if hot_compare else "empty",
            "summary": {
                "current_count": len(current_hot),
                "prev_count": len(prev_hot),
                "new_count": sum(1 for item in hot_compare if item.get("prev_rank_no") is None),
            },
            "items": hot_compare,
            "warnings": [] if prev_hot else ["缺少前一交易日人气榜，暂不能计算完整排名变化"],
        },
        {
            "key": "heat_single",
            "label": "情绪热度单页",
            "status": "ok" if latest_heat else "empty",
            "summary": latest_heat,
            "items": heat_trend,
            "warnings": [],
        },
    ]

    return {"date": date, "days": days, "modules": modules}


def get_premarket_guide(conn: sqlite3.Connection, guide_date: str) -> dict[str, Any] | None:
    """Return a generated pre-market guide."""
    row = conn.execute(
        """
        select guide_date, review_date, headline, market_tone, focus_plates,
               watch_points, risk_points, catalyst_news, announcements,
               us_markets, raw_payload, created_at, updated_at
        from premarket_guides
        where guide_date = ?
        """,
        (guide_date,),
    ).fetchone()
    if not row:
        return None
    result = row_to_dict(row)
    raw = _json_dict(result.get("raw_payload"))
    result["generated_at"] = raw.get("generated_at") or result.get("updated_at") or result.get("created_at")
    result["market_snapshot"] = raw.get("market_snapshot") or {}
    result["market_state"] = raw.get("market_state") or {}
    result["high_position_effect"] = raw.get("high_position_effect") or {}
    result["trend_hot_status"] = raw.get("trend_hot_status") or {}
    result["next_day_strategy"] = raw.get("next_day_strategy") or {}
    result["hot_stocks"] = raw.get("hot_stocks") or []
    result["space_stocks"] = raw.get("space_stocks") or []
    result["focus_plates"] = _json_list(result.get("focus_plates"))
    result["watch_points"] = _json_list(result.get("watch_points"))
    result["risk_points"] = _json_list(result.get("risk_points"))
    result["catalyst_news"] = _json_list(result.get("catalyst_news"))
    result["announcements"] = _json_list(result.get("announcements"))
    result["us_markets"] = _json_list(result.get("us_markets"))
    result.pop("raw_payload", None)
    return result


def get_latest_premarket_guide(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the latest generated pre-market guide."""
    row = conn.execute(
        """
        select guide_date
        from premarket_guides
        order by guide_date desc
        limit 1
        """
    ).fetchone()
    if not row:
        return None
    return get_premarket_guide(conn, row["guide_date"])


def get_saved_review(conn: sqlite3.Connection, date: str) -> dict[str, Any] | None:
    """Get the generated structured review if it has been saved."""
    row = conn.execute(
        """
        SELECT trade_date, limit_up_stock_count, limit_up_plate_count,
               first_board_count, multi_board_count, highest_board,
               strongest_plates, core_stocks, risk_flags, opportunities,
               next_plan, markdown_path, raw_payload, summary, updated_at
        FROM daily_reviews
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchone()
    if not row:
        return None
    review = row_to_dict(row)
    raw_payload = _json_dict(review.pop("raw_payload", None))
    review["strongest_plates"] = _json_list(review.pop("strongest_plates"))
    review["core_stocks"] = _json_list(review.pop("core_stocks"))
    review["risk_flags"] = _json_list(review.pop("risk_flags", None))
    review["opportunities"] = _json_list(review.pop("opportunities", None))
    review["next_plan"] = _json_list(review.pop("next_plan", None))
    review["plate_reviews"] = raw_payload.get("plate_reviews") or []
    review["hot_stock_summary"] = raw_payload.get("hot_stock_summary") or {}
    review["hot_stocks"] = raw_payload.get("hot_stocks") or []
    review["watch_stocks"] = raw_payload.get("watch_stocks") or []
    return review


def get_seal_quality(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Analyze seal quality distribution for limit-up stocks."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN up_limit_type = '一' THEN 1 ELSE 0 END) as one_seal,
            SUM(CASE WHEN up_limit_type NOT LIKE '烂%' AND up_limit_type != '一' THEN 1 ELSE 0 END) as normal_seal,
            SUM(CASE WHEN up_limit_type LIKE '烂%' THEN 1 ELSE 0 END) as broken_seal,
            AVG(CASE WHEN fengdan_rate IS NOT NULL THEN fengdan_rate END) as avg_seal_rate,
            AVG(CASE WHEN fengdan_money IS NOT NULL THEN fengdan_money END) as avg_seal_money,
            SUM(CASE WHEN up_limit_desc LIKE '%首板%' THEN 1 ELSE 0 END) as first_board,
            SUM(CASE WHEN up_limit_desc NOT LIKE '%首板%' OR up_limit_desc IS NULL THEN 1 ELSE 0 END) as multi_board
        FROM limit_up_events
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchone()

    if not row:
        return {"total": 0, "one_seal": 0, "normal_seal": 0, "broken_seal": 0,
                "avg_seal_rate": 0, "avg_seal_money": 0, "first_board": 0, "multi_board": 0}

    result = row_to_dict(row)

    # Compute derived metrics
    total = result["total"]
    result["broken_rate"] = round(result["broken_seal"] / total * 100, 1) if total > 0 else 0
    result["one_seal_rate"] = round(result["one_seal"] / total * 100, 1) if total > 0 else 0
    result["first_board_rate"] = round(result["first_board"] / total * 100, 1) if total > 0 else 0

    # Get previous day for comparison
    prev_date = get_prev_trade_date(conn, date)
    if prev_date:
        prev_row = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN up_limit_type LIKE '烂%' THEN 1 ELSE 0 END) as broken_seal,
                AVG(CASE WHEN fengdan_rate IS NOT NULL THEN fengdan_rate END) as avg_seal_rate
            FROM limit_up_events WHERE trade_date = ?
            """,
            (prev_date,),
        ).fetchone()
        if prev_row:
            prev = row_to_dict(prev_row)
            result["prev_total"] = prev["total"]
            result["prev_broken_rate"] = round(prev["broken_seal"] / prev["total"] * 100, 1) if prev["total"] > 0 else 0
            result["prev_avg_seal_rate"] = prev["avg_seal_rate"] or 0
    else:
        result["prev_total"] = 0
        result["prev_broken_rate"] = 0
        result["prev_avg_seal_rate"] = 0

    return result


def get_board_advancement(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Analyze board advancement: how many N-board stocks from prev day advanced to N+1."""
    prev_date = get_prev_trade_date(conn, date)
    if not prev_date:
        return []

    # Get prev day's stocks by board count
    prev_stocks = conn.execute(
        """
        SELECT stock_code, stock_name, up_limit_keep_times
        FROM limit_up_events
        WHERE trade_date = ?
        """,
        (prev_date,),
    ).fetchall()

    # Get current day's stocks
    cur_stocks = conn.execute(
        """
        SELECT stock_code, up_limit_keep_times
        FROM limit_up_events
        WHERE trade_date = ?
        """,
        (date,),
    ).fetchall()

    cur_map = {s["stock_code"]: s["up_limit_keep_times"] for s in cur_stocks}

    # Group prev stocks by board level
    prev_by_level: dict[int, list] = {}
    for s in prev_stocks:
        level = s["up_limit_keep_times"]
        if level not in prev_by_level:
            prev_by_level[level] = []
        prev_by_level[level].append(s)

    result = []
    for level in sorted(prev_by_level.keys(), reverse=True):
        stocks = prev_by_level[level]
        total = len(stocks)
        advanced = 0
        maintained = 0
        failed = 0
        failed_names = []

        for s in stocks:
            cur_level = cur_map.get(s["stock_code"])
            if cur_level is not None:
                if cur_level > level:
                    advanced += 1
                else:
                    maintained += 1
            else:
                failed += 1
                failed_names.append(s["stock_name"])

        result.append({
            "level": level,
            "total": total,
            "advanced": advanced,
            "maintained": maintained,
            "failed": failed,
            "advancement_rate": round((advanced / total) * 100, 1) if total > 0 else 0,
            "fail_rate": round((failed / total) * 100, 1) if total > 0 else 0,
            "failed_names": failed_names[:5],
        })

    return result


def get_capital_flow(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get top plates by net capital flow from plate_daily."""
    rows = conn.execute(
        """
        SELECT
            plate_code, plate_name, raw_payload
        FROM plate_daily
        WHERE trade_date = ?
        ORDER BY plate_code
        """,
        (date,),
    ).fetchall()

    result = []
    import json
    for row in rows:
        try:
            payload = json.loads(row["raw_payload"])
        except (json.JSONDecodeError, TypeError):
            continue

        money_leader = payload.get("money_leader", 0)
        result.append({
            "plate_code": row["plate_code"],
            "plate_name": row["plate_name"],
            "net_flow": money_leader,
            "buy": payload.get("money_leader_buy", 0),
            "sell": payload.get("money_leader_sell", 0),
            "rate": payload.get("rate", 0),
            "trade_money": payload.get("trade_money", 0),
            "volume_ration": payload.get("volume_ration", 0),
        })

    # Sort by absolute net flow descending
    result.sort(key=lambda x: abs(x["net_flow"]), reverse=True)
    return result[:20]


def get_hot_stocks_derived(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Derive hot stocks from fengdan_money and cross-plate presence."""
    # Top stocks by fengdan_money
    stocks = conn.execute(
        """
        SELECT
            e.stock_code, e.stock_name, e.up_limit_keep_times,
            e.up_limit_time, e.up_limit_type, e.fengdan_money,
            e.fengdan_rate, e.reason, e.amount
        FROM limit_up_events e
        WHERE e.trade_date = ? AND e.fengdan_money IS NOT NULL
        ORDER BY e.fengdan_money DESC
        LIMIT 20
        """,
        (date,),
    ).fetchall()

    result = []
    for s in stocks:
        d = row_to_dict(s)
        # Get plates
        plates = conn.execute(
            """
            SELECT p.plate_name
            FROM limit_up_plate_map p
            WHERE p.trade_date = ? AND p.stock_code = ?
            ORDER BY p.plate_score DESC
            """,
            (date, s["stock_code"]),
        ).fetchall()
        d["plates"] = [p["plate_name"] for p in plates]
        d["plate_count"] = len(plates)
        result.append(d)

    return result


def get_hot_stocks_rank(conn: sqlite3.Connection, date: str, limit: int = 30) -> list[dict[str, Any]]:
    """Get hot stock rankings from hot_stocks table."""
    hot_filter = _hot_stock_source_filter(conn, date)
    rows = conn.execute(
        f"""
        SELECT rank_no, stock_code, stock_name, latest_price, change_pct,
               change_amount, amount, turnover_rate, source
        FROM hot_stocks
        WHERE trade_date = ? AND {hot_filter}
        ORDER BY rank_no
        LIMIT ?
        """,
        (date, limit),
    ).fetchall()
    return rows_to_list(rows)


def get_hot_boards_rank(conn: sqlite3.Connection, date: str, board_type: str = "concept", limit: int = 20) -> list[dict[str, Any]]:
    """Get hot board rankings from hot_boards table."""
    rows = conn.execute(
        """
        SELECT rank_no, board_code, board_name, latest_price, change_pct, change_amount,
               total_market_cap, turnover_rate, up_count, down_count,
               leading_stock, leading_stock_change
        FROM hot_boards
        WHERE trade_date = ? AND board_type = ?
        ORDER BY rank_no
        LIMIT ?
        """,
        (date, board_type, limit),
    ).fetchall()
    return rows_to_list(rows)


def get_plate_rotation_snapshot(
    conn: sqlite3.Connection,
    date: str | None = None,
    days: int = 8,
    top_n: int = 12,
    plate_code: str | None = None,
    source: str = "quant_yjj",
) -> dict[str, Any]:
    """Return plate rotation ranks and selected plate details."""
    if not date:
        latest_row = conn.execute(
            """
            SELECT MAX(trade_date) AS trade_date
            FROM plate_rotation_rank
            WHERE source = ?
            """,
            (source,),
        ).fetchone()
        date = latest_row["trade_date"] if latest_row else None

    if not date:
        return {
            "date": "",
            "dates": [],
            "rank_by_date": {},
            "selected_plate": None,
            "source": source,
        }

    date_rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM plate_rotation_rank
        WHERE trade_date <= ? AND source = ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (date, source, days),
    ).fetchall()
    dates = sorted([row["trade_date"] for row in date_rows])
    if not dates:
        return {
            "date": date,
            "dates": [],
            "rank_by_date": {},
            "selected_plate": None,
            "source": source,
        }

    rank_by_date: dict[str, list[dict[str, Any]]] = {}
    selected_code = plate_code
    latest_date = dates[-1]
    for day in dates:
        rows = conn.execute(
            """
            SELECT trade_date, plate_code, plate_name, rank_no, rate, score, speed,
                   money_leader, money_leader_buy, money_leader_sell,
                   trade_money, volume_ration
            FROM plate_rotation_rank
            WHERE trade_date = ? AND source = ?
            ORDER BY rank_no
            LIMIT ?
            """,
            (day, source, top_n),
        ).fetchall()
        items = rows_to_list(rows)
        rank_by_date[day] = items
        if not selected_code and day == latest_date and items:
            selected_code = items[0]["plate_code"]

    selected_plate = None
    if selected_code:
        selected_plate = _get_plate_rotation_detail(conn, selected_code, dates[0], latest_date, top_n, source)

    return {
        "date": latest_date,
        "dates": dates,
        "rank_by_date": rank_by_date,
        "selected_plate": selected_plate,
        "source": source,
    }


def _get_plate_rotation_detail(
    conn: sqlite3.Connection,
    plate_code: str,
    day_start: str,
    day_end: str,
    stock_limit: int,
    source: str,
) -> dict[str, Any] | None:
    plate_row = conn.execute(
        """
        SELECT plate_code, plate_name
        FROM plate_rotation_rank
        WHERE plate_code = ? AND source = ?
        ORDER BY trade_date DESC
        LIMIT 1
        """,
        (plate_code, source),
    ).fetchone()
    if not plate_row:
        return None

    trend_rows = conn.execute(
        """
        SELECT trade_date, plate_code, plate_name, rate, score, speed,
               money_leader, money_leader_buy, money_leader_sell,
               trade_money, volume_ration
        FROM plate_rotation_trend
        WHERE plate_code = ?
          AND source = ?
          AND trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        (plate_code, source, day_start, day_end),
    ).fetchall()

    reason_rows = conn.execute(
        """
        SELECT reason_date as date, msg_id, plate_name, title, boomreason,
               is_boom, limit_up_count, strength_score, leader_info
        FROM plate_rotation_reasons
        WHERE plate_code = ? AND source = ?
        ORDER BY reason_date DESC
        LIMIT 10
        """,
        (plate_code, source),
    ).fetchall()

    stock_rows = conn.execute(
        """
        SELECT trade_date, plate_code, stock_code, stock_name, rank_no, rank_diff,
               change_pct, high_change_pct, open_change_pct, turnover_ratio,
               volume_ratio, circulation_value
        FROM plate_rotation_stocks
        WHERE plate_code = ?
          AND source = ?
          AND trade_date = (
              SELECT MAX(trade_date)
              FROM plate_rotation_stocks
              WHERE plate_code = ? AND source = ? AND trade_date <= ?
          )
        ORDER BY rank_no
        LIMIT ?
        """,
        (plate_code, source, plate_code, source, day_end, stock_limit),
    ).fetchall()

    result = row_to_dict(plate_row)
    result["trend"] = rows_to_list(trend_rows)
    result["reasons"] = rows_to_list(reason_rows)
    result["stocks"] = rows_to_list(stock_rows)
    return result


def get_stock_hot_ranks(
    conn: sqlite3.Connection,
    date: str,
    source: str = "ths_hot",
    period: str = "day",
    list_type: str = "normal",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Get multi-source stock hot ranks."""
    rows = conn.execute(
        """
        SELECT rank_no, stock_code, stock_name, latest_price, change_pct,
               hot_value, rank_change, concept_tags, popularity_tag,
               source, period, list_type
        FROM stock_hot_ranks
        WHERE trade_date = ?
          AND source = ?
          AND period = ?
          AND list_type = ?
        ORDER BY rank_no
        LIMIT ?
        """,
        (date, source, period, list_type, limit),
    ).fetchall()
    result = []
    for row in rows:
        item = row_to_dict(row)
        item["concept_tags"] = _json_list(item.get("concept_tags"))
        result.append(item)
    return result


def get_hot_available_dates(conn: sqlite3.Connection) -> list[str]:
    """Get dates that have hot stock/board data."""
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date FROM hot_stocks
        UNION
        SELECT DISTINCT trade_date FROM stock_hot_ranks
        UNION
        SELECT DISTINCT trade_date FROM hot_boards
        ORDER BY trade_date DESC
        """
    ).fetchall()
    return [r["trade_date"] for r in rows]
