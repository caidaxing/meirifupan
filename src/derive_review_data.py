"""Derive local summary tables used by the A-share review system."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH
from utils import row_to_dict


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _unique(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def build_plate_trends(conn: sqlite3.Connection, dates: list[str] | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    date_filter = ""
    if dates:
        placeholders = ",".join(["?"] * len(dates))
        date_filter = f"where m.trade_date in ({placeholders})"
        params = tuple(dates)

    rows = conn.execute(
        f"""
        select
            m.trade_date,
            m.plate_code,
            coalesce(max(m.plate_name), max(p.plate_name)) as plate_name,
            count(distinct m.stock_code) as limit_up_count,
            coalesce(max(h.score), max(m.plate_score), 0) as score,
            coalesce(sum(e.fengdan_money), 0) as seal_amount,
            group_concat(distinct e.stock_name) as stock_names,
            group_concat(distinct coalesce(nullif(m.stock_reason, ''), nullif(e.reason, ''))) as reasons
        from limit_up_plate_map m
        left join limit_up_events e
            on m.trade_date = e.trade_date and m.stock_code = e.stock_code
        left join plates p
            on m.plate_code = p.plate_code
        left join plate_hot_rank h
            on m.trade_date = h.trade_date
           and m.plate_code = h.plate_code
           and h.source = 'uplimit_hot'
        {date_filter}
        group by m.trade_date, m.plate_code
        order by m.plate_code, m.trade_date
        """,
        params,
    ).fetchall()

    previous_count: dict[str, float] = {}
    records: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        plate_code = item["plate_code"]
        limit_up_count = float(item["limit_up_count"] or 0)
        prev = previous_count.get(plate_code)
        change_pct = None
        if prev is not None:
            change_pct = 100.0 if prev == 0 and limit_up_count else round((limit_up_count - prev) / prev * 100, 2)
        previous_count[plate_code] = limit_up_count

        stocks = _unique((item.get("stock_names") or "").split(","), 12)
        reasons = _unique((item.get("reasons") or "").split(","), 8)
        records.append({
            "plate_code": plate_code,
            "trade_date": item["trade_date"],
            "plate_name": item.get("plate_name"),
            "open_price": limit_up_count,
            "high_price": limit_up_count,
            "low_price": limit_up_count,
            "close_price": limit_up_count,
            "change_pct": change_pct,
            "amount": item.get("seal_amount"),
            "raw_payload": {
                "source": "derived_from_limit_up",
                "metric": "limit_up_count",
                "limit_up_count": int(limit_up_count),
                "score": item.get("score"),
                "seal_amount": item.get("seal_amount"),
                "represent_stocks": stocks,
                "reasons": reasons,
            },
        })
    return records


def build_plate_reasons(conn: sqlite3.Connection, dates: list[str] | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    date_filter = ""
    if dates:
        placeholders = ",".join(["?"] * len(dates))
        date_filter = f"where m.trade_date in ({placeholders})"
        params = tuple(dates)

    rows = conn.execute(
        f"""
        select
            m.plate_code,
            coalesce(max(m.plate_name), max(p.plate_name)) as plate_name,
            count(distinct m.trade_date) as active_days,
            count(distinct m.trade_date || ':' || m.stock_code) as total_limit_up_count,
            max(m.trade_date) as latest_trade_date,
            group_concat(distinct e.stock_name) as stock_names,
            group_concat(distinct coalesce(nullif(m.stock_reason, ''), nullif(e.reason, ''))) as reasons
        from limit_up_plate_map m
        left join limit_up_events e
            on m.trade_date = e.trade_date and m.stock_code = e.stock_code
        left join plates p
            on m.plate_code = p.plate_code
        {date_filter}
        group by m.plate_code
        order by active_days desc, total_limit_up_count desc
        """,
        params,
    ).fetchall()

    records: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        stocks = _unique((item.get("stock_names") or "").split(","), 10)
        reasons = _unique((item.get("reasons") or "").split(","), 10)
        reason_counter = Counter(reasons)
        reason_text = "；".join(reasons[:4]) if reasons else "由涨停股聚合而来，暂无更细原因。"
        stock_text = "、".join(stocks[:6]) if stocks else "-"
        summary = (
            f"{item.get('plate_name') or item['plate_code']}：近样本期活跃 {item['active_days']} 天，"
            f"累计 {item['total_limit_up_count']} 次涨停映射。代表股：{stock_text}。主要原因：{reason_text}"
        )
        records.append({
            "plate_code": item["plate_code"],
            "plate_name": item.get("plate_name"),
            "reason": summary,
            "raw_payload": {
                "source": "derived_from_limit_up",
                "latest_trade_date": item.get("latest_trade_date"),
                "active_days": item.get("active_days"),
                "total_limit_up_count": item.get("total_limit_up_count"),
                "represent_stocks": stocks,
                "reasons": reasons,
                "reason_frequency": dict(reason_counter),
            },
        })
    return records


def _core_stocks_from_review(conn: sqlite3.Connection, trade_date: str) -> list[dict[str, Any]]:
    row = conn.execute(
        "select core_stocks from daily_reviews where trade_date = ?",
        (trade_date,),
    ).fetchone()
    stocks = _json_list(row["core_stocks"] if row else None)
    return [item for item in stocks if isinstance(item, dict)]


def _core_stocks_from_limit_up(conn: sqlite3.Connection, trade_date: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select stock_code, stock_name, up_limit_keep_times, up_limit_time, fengdan_money, reason
        from limit_up_events
        where trade_date = ?
        order by coalesce(up_limit_keep_times, 1) desc,
                 coalesce(fengdan_money, 0) desc,
                 up_limit_time asc
        limit ?
        """,
        (trade_date, limit),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def _available_dates(conn: sqlite3.Connection, dates: list[str] | None) -> list[str]:
    if dates:
        return dates
    rows = conn.execute(
        """
        select distinct trade_date from (
            select trade_date from daily_reviews
            union
            select trade_date from limit_up_events
        )
        order by trade_date
        """
    ).fetchall()
    return [row["trade_date"] for row in rows]


def build_stock_info_snapshots(conn: sqlite3.Connection, dates: list[str] | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for trade_date in _available_dates(conn, dates):
        candidates = _core_stocks_from_review(conn, trade_date) or _core_stocks_from_limit_up(conn, trade_date)
        seen: set[str] = set()
        for stock in candidates:
            stock_code = str(stock.get("stock_code") or "")
            if not stock_code or stock_code in seen:
                continue
            seen.add(stock_code)

            stock_row = conn.execute(
                "select stock_name from stocks where stock_code = ?",
                (stock_code,),
            ).fetchone()
            event = conn.execute(
                """
                select *
                from limit_up_events
                where trade_date = ? and stock_code = ?
                """,
                (trade_date, stock_code),
            ).fetchone()
            plates = conn.execute(
                """
                select plate_code, plate_name, plate_score, stock_reason
                from limit_up_plate_map
                where trade_date = ? and stock_code = ?
                order by coalesce(plate_score, 0) desc
                """,
                (trade_date, stock_code),
            ).fetchall()
            kline = conn.execute(
                """
                select trade_date, open_price, high_price, low_price, close_price, volume, amount
                from stock_kline_daily
                where stock_code = ? and trade_date <= ?
                order by trade_date desc
                limit 1
                """,
                (stock_code, trade_date),
            ).fetchone()
            lhb = conn.execute(
                """
                select reason, net_buy_amount
                from lhb_daily
                where trade_date = ? and stock_code = ?
                order by coalesce(net_buy_amount, 0) desc
                limit 3
                """,
                (trade_date, stock_code),
            ).fetchall()

            stock_name = (
                stock.get("stock_name")
                or (stock_row["stock_name"] if stock_row else None)
                or (event["stock_name"] if event else None)
            )
            records.append({
                "stock_code": stock_code,
                "snapshot_date": trade_date,
                "stock_name": stock_name,
                "raw_payload": {
                    "source": "derived_from_local_review",
                    "review_core": stock,
                    "limit_up_event": row_to_dict(event) if event else None,
                    "plates": [row_to_dict(row) for row in plates],
                    "latest_kline": row_to_dict(kline) if kline else None,
                    "lhb": [row_to_dict(row) for row in lhb],
                },
            })
    return records


def derive_review_data(
    db_path: str | Path = DEFAULT_DB_PATH,
    dates: list[str] | None = None,
) -> dict[str, int]:
    """Build local derived tables from already-collected review data."""
    conn = _connect(db_path)
    try:
        plate_trends = build_plate_trends(conn, dates)
        plate_reasons = build_plate_reasons(conn, dates)
        stock_snapshots = build_stock_info_snapshots(conn, dates)
    finally:
        conn.close()

    db = MarketDB(db_path)
    db.init_schema()
    try:
        counts = {
            "plate_trends": db.import_plate_trends(plate_trends),
            "plate_reasons": db.import_plate_reasons(plate_reasons),
            "stock_info_snapshots": db.import_stock_info_snapshots(stock_snapshots),
        }
        date_label = ",".join(dates) if dates else None
        db.log_data_job(
            "derive_review_data",
            date_label,
            "success",
            (
                f"plate_trends={counts['plate_trends']}, "
                f"plate_reasons={counts['plate_reasons']}, "
                f"stock_info_snapshots={counts['stock_info_snapshots']}"
            ),
        )
        return counts
    except Exception as exc:
        db.log_data_job("derive_review_data", ",".join(dates) if dates else None, "failed", str(exc))
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="从本地复盘数据派生板块趋势、板块原因和核心股快照")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--date", action="append", help="只处理指定交易日；可重复传入")
    args = parser.parse_args()

    counts = derive_review_data(args.db, args.date)
    print(
        "派生完成: "
        f"板块趋势 {counts['plate_trends']} 条，"
        f"板块原因 {counts['plate_reasons']} 条，"
        f"核心股快照 {counts['stock_info_snapshots']} 条"
    )
    print(f"数据库: {args.db}")


if __name__ == "__main__":
    main()
