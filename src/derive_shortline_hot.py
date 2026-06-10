"""Build a short-line hot stock rank from local review data.

The public free path for KaiPanLa-style hot stocks is unstable, so this module
derives a practical short-line rank from data we already collect: limit-up
events, plate tags, Eastmoney popularity, and THS hot/skyrocket ranks.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from collections.abc import Iterable
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH


SOURCE = "shortline_hot"
PERIOD = "day"
LIST_TYPE = "kpl_style"


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _json_list(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return loaded if isinstance(loaded, list) else []


def _split_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item and item.strip()]


def _add_unique(items: list[str], values: Iterable[Any], limit: int | None = None) -> None:
    for value in values:
        text = str(value or "").strip()
        if not text or text in items:
            continue
        items.append(text)
        if limit and len(items) >= limit:
            return


def _candidate(candidates: dict[str, dict[str, Any]], stock_code: str, stock_name: str | None = None) -> dict[str, Any]:
    item = candidates.setdefault(
        stock_code,
        {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "latest_price": None,
            "change_pct": None,
            "score": 0.0,
            "tags": [],
            "signals": [],
            "raw": {},
            "primary_tag": None,
        },
    )
    if stock_name and not item.get("stock_name"):
        item["stock_name"] = stock_name
    return item


def _first_seal_bonus(time_text: str | None) -> float:
    if not time_text:
        return 0.0
    text = str(time_text)
    if text <= "09:35:00":
        return 18.0
    if text <= "10:00:00":
        return 12.0
    if text <= "11:30:00":
        return 6.0
    return 2.0


def _seal_amount_bonus(value: Any) -> float:
    amount = _as_float(value)
    if not amount or amount <= 0:
        return 0.0
    return min(24.0, math.log10(amount / 1_000_000 + 1) * 7)


def _rank_bonus(rank_no: Any, base: int, weight: float, floor_bonus: float = 0.0) -> float:
    rank = _as_int(rank_no)
    if rank <= 0:
        return 0.0
    return max(0.0, (base - rank) * weight) + floor_bonus


def derive_shortline_hot_ranks(conn: sqlite3.Connection, trade_date: str, limit: int = 30) -> int:
    """Derive and save short-line hot ranks for one trade date."""
    candidates: dict[str, dict[str, Any]] = {}

    limit_up_rows = _rows(
        conn,
        """
        SELECT e.stock_code, e.stock_name, e.stock_price, e.up_limit_keep_times,
               e.up_limit_type, e.up_limit_time, e.reason, e.fengdan_money,
               e.fengdan_rate, e.turnover_rate, e.amount,
               group_concat(distinct m.plate_name) AS plate_names,
               group_concat(distinct m.stock_reason) AS stock_reasons
        FROM limit_up_events e
        LEFT JOIN limit_up_plate_map m
          ON m.trade_date = e.trade_date AND m.stock_code = e.stock_code
        WHERE e.trade_date = ?
        GROUP BY e.stock_code
        """,
        (trade_date,),
    )
    for row in limit_up_rows:
        stock_code = str(row.get("stock_code") or "").strip()
        if not stock_code:
            continue
        item = _candidate(candidates, stock_code, row.get("stock_name"))
        item["latest_price"] = row.get("stock_price") or item.get("latest_price")

        board_count = max(1, _as_int(row.get("up_limit_keep_times"), 1))
        score = 52 + board_count * 26
        score += _first_seal_bonus(row.get("up_limit_time"))
        score += _seal_amount_bonus(row.get("fengdan_money"))
        item["score"] += score

        board_tag = f"{board_count}连板" if board_count > 1 else "首板涨停"
        item["primary_tag"] = board_tag
        _add_unique(item["tags"], _split_names(row.get("plate_names")), limit=5)
        _add_unique(item["signals"], [board_tag])
        if row.get("up_limit_time"):
            _add_unique(item["signals"], [f"封板{row['up_limit_time']}"])
        item["raw"]["limit_up"] = {
            "up_limit_keep_times": board_count,
            "up_limit_type": row.get("up_limit_type"),
            "up_limit_time": row.get("up_limit_time"),
            "reason": row.get("reason"),
            "stock_reasons": _split_names(row.get("stock_reasons")),
            "fengdan_money": row.get("fengdan_money"),
            "fengdan_rate": row.get("fengdan_rate"),
            "turnover_rate": row.get("turnover_rate"),
            "amount": row.get("amount"),
        }

    ths_rows = _rows(
        conn,
        """
        SELECT rank_no, stock_code, stock_name, latest_price, change_pct,
               hot_value, rank_change, concept_tags, popularity_tag, period, list_type
        FROM stock_hot_ranks
        WHERE trade_date = ? AND source = 'ths_hot'
          AND (
            (period = 'day' AND list_type = 'normal')
            OR (period = 'hour' AND list_type = 'skyrocket')
          )
        ORDER BY period, list_type, rank_no
        """,
        (trade_date,),
    )
    for row in ths_rows:
        stock_code = str(row.get("stock_code") or "").strip()
        if not stock_code:
            continue
        item = _candidate(candidates, stock_code, row.get("stock_name"))
        item["latest_price"] = row.get("latest_price") or item.get("latest_price")
        if row.get("change_pct") is not None:
            item["change_pct"] = row.get("change_pct")
        _add_unique(item["tags"], _json_list(row.get("concept_tags")), limit=5)
        if row.get("popularity_tag") and not item.get("primary_tag"):
            item["primary_tag"] = row.get("popularity_tag")

        hot_value_bonus = min(12.0, math.log10((_as_float(row.get("hot_value")) or 0) + 1) * 1.5)
        if row.get("list_type") == "skyrocket":
            item["score"] += _rank_bonus(row.get("rank_no"), base=45, weight=1.0, floor_bonus=22) + hot_value_bonus
            _add_unique(item["signals"], [f"飙升#{row['rank_no']}"])
        else:
            item["score"] += _rank_bonus(row.get("rank_no"), base=46, weight=0.9, floor_bonus=8) + hot_value_bonus
            _add_unique(item["signals"], [f"同花顺#{row['rank_no']}"])
        item["raw"].setdefault("ths", []).append(row)

    hot_stock_rows = _rows(
        conn,
        """
        SELECT rank_no, stock_code, stock_name, latest_price, change_pct,
               change_amount, amount, turnover_rate, source
        FROM hot_stocks
        WHERE trade_date = ?
        ORDER BY rank_no
        LIMIT 80
        """,
        (trade_date,),
    )
    for row in hot_stock_rows:
        stock_code = str(row.get("stock_code") or "").strip()
        if not stock_code:
            continue
        item = _candidate(candidates, stock_code, row.get("stock_name"))
        item["latest_price"] = row.get("latest_price") or item.get("latest_price")
        if row.get("change_pct") is not None:
            item["change_pct"] = row.get("change_pct")
        item["score"] += _rank_bonus(row.get("rank_no"), base=55, weight=0.55, floor_bonus=6)
        _add_unique(item["signals"], [f"人气#{row['rank_no']}"])
        item["raw"]["eastmoney_hot"] = row

    broken_rows = _rows(
        conn,
        "SELECT stock_code, open_count, limit_up_stat FROM broken_limit_up_events WHERE trade_date = ?",
        (trade_date,),
    )
    for row in broken_rows:
        item = candidates.get(str(row.get("stock_code") or "").strip())
        if item:
            item["score"] -= 35
            _add_unique(item["signals"], ["炸板"])
            item["raw"]["broken_limit_up"] = row

    limit_down_rows = _rows(
        conn,
        "SELECT stock_code, limit_down_days FROM limit_down_events WHERE trade_date = ?",
        (trade_date,),
    )
    for row in limit_down_rows:
        item = candidates.get(str(row.get("stock_code") or "").strip())
        if item:
            item["score"] -= 80
            _add_unique(item["signals"], ["跌停"])
            item["raw"]["limit_down"] = row

    ranked = [
        item
        for item in candidates.values()
        if item.get("stock_code") and item.get("score", 0) > 0
    ]
    ranked.sort(key=lambda item: (-item["score"], item["stock_code"]))
    records = []
    for rank_no, item in enumerate(ranked[:limit], start=1):
        signals = item["signals"][:6]
        records.append({
            "rank_no": rank_no,
            "stock_code": item["stock_code"],
            "stock_name": item.get("stock_name"),
            "latest_price": item.get("latest_price"),
            "change_pct": item.get("change_pct"),
            "hot_value": round(item.get("score", 0), 2),
            "rank_change": None,
            "concept_tags": item["tags"][:5],
            "popularity_tag": item.get("primary_tag") or (signals[0] if signals else None),
            "raw_payload": {
                "score": round(item.get("score", 0), 2),
                "signals": signals,
                "sources": item.get("raw") or {},
            },
        })

    conn.execute(
        """
        INSERT INTO trade_calendar(trade_date, is_trade_day)
        VALUES(?, 1)
        ON CONFLICT(trade_date) DO UPDATE SET
            is_trade_day = excluded.is_trade_day,
            updated_at = current_timestamp
        """,
        (trade_date,),
    )
    conn.execute(
        """
        DELETE FROM stock_hot_ranks
        WHERE trade_date = ? AND source = ? AND period = ? AND list_type = ?
        """,
        (trade_date, SOURCE, PERIOD, LIST_TYPE),
    )
    for record in records:
        conn.execute(
            """
            INSERT INTO stocks(stock_code, stock_name)
            VALUES(?, ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                stock_name = coalesce(excluded.stock_name, stocks.stock_name),
                updated_at = current_timestamp
            """,
            (record["stock_code"], record.get("stock_name")),
        )
        conn.execute(
            """
            INSERT INTO stock_hot_ranks(
                trade_date, source, period, list_type, rank_no, stock_code, stock_name,
                latest_price, change_pct, hot_value, rank_change,
                concept_tags, popularity_tag, raw_payload
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_date,
                SOURCE,
                PERIOD,
                LIST_TYPE,
                record["rank_no"],
                record["stock_code"],
                record.get("stock_name"),
                record.get("latest_price"),
                record.get("change_pct"),
                record.get("hot_value"),
                record.get("rank_change"),
                json.dumps(record.get("concept_tags") or [], ensure_ascii=False),
                record.get("popularity_tag"),
                json.dumps(record.get("raw_payload") or record, ensure_ascii=False),
            ),
        )
    conn.commit()
    return len(records)


def derive_shortline_hot(db_path: str, trade_date: str, limit: int = 30) -> int:
    db = MarketDB(db_path)
    db.init_schema()
    try:
        return derive_shortline_hot_ranks(db.conn, trade_date, limit=limit)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成短线热榜")
    parser.add_argument("--date", required=True, help="交易日，格式 YYYY-MM-DD")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--limit", type=int, default=30, help="榜单数量")
    args = parser.parse_args()

    count = derive_shortline_hot(args.db, args.date, limit=args.limit)
    print(json.dumps({"date": args.date, "shortline_hot": count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
