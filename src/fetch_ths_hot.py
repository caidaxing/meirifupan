"""Fetch free THS hot stock rankings from the 10jqka web endpoint."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH
from utils import to_float, to_int


THS_HOT_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"


def _concept_tags(item: dict[str, Any]) -> list[str]:
    tags = item.get("tag") or {}
    concepts = tags.get("concept_tag") or []
    if isinstance(concepts, list):
        return [str(tag) for tag in concepts if str(tag).strip()]
    if isinstance(concepts, str):
        return [tag.strip() for tag in concepts.split(",") if tag.strip()]
    return []


def _popularity_tag(item: dict[str, Any]) -> str | None:
    tags = item.get("tag") or {}
    value = tags.get("popularity_tag")
    return str(value).strip() if value else None


def parse_ths_hot_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert THS hot-list payload items into local records."""
    records: list[dict[str, Any]] = []
    for item in items:
        code = str(item.get("code") or "").strip()
        rank_no = to_int(item.get("order"))
        if not code or rank_no is None:
            continue
        records.append({
            "rank_no": rank_no,
            "stock_code": code,
            "stock_name": item.get("name"),
            "latest_price": None,
            "change_pct": to_float(item.get("rise_and_fall")),
            "hot_value": to_float(item.get("rate")),
            "rank_change": to_int(item.get("hot_rank_chg")),
            "concept_tags": _concept_tags(item),
            "popularity_tag": _popularity_tag(item),
            "raw_payload": item,
        })
    return records


def fetch_ths_hot_records(
    stock_type: str = "a",
    period: str = "day",
    list_type: str = "normal",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch THS hot stock records.

    period: hour/day. list_type: normal/skyrocket.
    """
    import requests

    response = requests.get(
        THS_HOT_URL,
        params={
            "stock_type": stock_type,
            "type": period,
            "list_type": list_type,
        },
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Referer": "https://eq.10jqka.com.cn/",
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status_code") not in (0, "0"):
        raise RuntimeError(payload.get("status_msg") or "同花顺热榜接口返回异常")
    items = (payload.get("data") or {}).get("stock_list") or []
    return parse_ths_hot_items(items[:limit])


def fetch_and_store_ths_hot(
    db: MarketDB,
    trade_date: str,
    period: str = "day",
    list_type: str = "normal",
    limit: int = 100,
) -> int:
    records = fetch_ths_hot_records(period=period, list_type=list_type, limit=limit)
    return db.import_stock_hot_ranks(
        trade_date=trade_date,
        records=records,
        source="ths_hot",
        period=period,
        list_type=list_type,
    )


def fetch_ths_hot_bundle(db: MarketDB, trade_date: str, limit: int = 100) -> dict[str, int]:
    """Fetch the THS hot list and the fast-rising list."""
    return {
        "ths_hot_day": fetch_and_store_ths_hot(db, trade_date, period="day", list_type="normal", limit=limit),
        "ths_hot_hour": fetch_and_store_ths_hot(db, trade_date, period="hour", list_type="normal", limit=limit),
        "ths_skyrocket_day": fetch_and_store_ths_hot(db, trade_date, period="day", list_type="skyrocket", limit=limit),
        "ths_skyrocket_hour": fetch_and_store_ths_hot(db, trade_date, period="hour", list_type="skyrocket", limit=limit),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="采集同花顺热榜")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="归属交易日")
    parser.add_argument("--limit", type=int, default=100, help="每个榜单采集数量")
    args = parser.parse_args()

    db = MarketDB(args.db)
    db.init_schema()
    try:
        result = fetch_ths_hot_bundle(db, args.date, args.limit)
    finally:
        db.close()
    print(result)


if __name__ == "__main__":
    main()
