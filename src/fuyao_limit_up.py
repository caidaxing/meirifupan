"""Fuyao limit-up pool integration."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    import certifi
except Exception:  # pragma: no cover - depends on local Python install
    class _MissingCertifi:
        @staticmethod
        def where() -> str | None:
            return None

    certifi = _MissingCertifi()


BASE_URL = "https://fuyao.aicubes.cn"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "market_review.db"
SHANGHAI_TZ = timezone(timedelta(hours=8))


def shanghai_midnight_ms(date: str) -> int:
    dt = datetime.fromisoformat(date).replace(tzinfo=SHANGHAI_TZ)
    return int(dt.timestamp() * 1000)


def make_ssl_context() -> ssl.SSLContext:
    cafile = certifi.where()
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def fetch_limit_up_pool(api_key: str, date: str, *, base_url: str = BASE_URL) -> list[dict[str, Any]]:
    if not api_key:
        raise ValueError("FUYAO_API_KEY is required")

    query = urllib.parse.urlencode({
        "date_ms": shanghai_midnight_ms(date),
        "page": 1,
        "size": 200,
        "sort_field": "limit_up_time",
        "sort_dir": "asc",
    })
    url = f"{base_url}/api/a-share/special-data/limit-up-pool?{query}"
    req = urllib.request.Request(url, headers={"X-api-key": api_key})
    ctx = make_ssl_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if payload.get("code") != 0:
        raise RuntimeError(f"Fuyao limit-up pool returned code={payload.get('code')}: {payload.get('message')}")
    data = payload.get("data") or {}
    items = data.get("item") or []
    return [item for item in items if item.get("ticker")]


def update_limit_up_reasons(db_path: str | Path, date: str, items: list[dict[str, Any]]) -> int:
    conn = sqlite3.connect(db_path)
    try:
        count = 0
        for item in items:
            stock_code = str(item.get("ticker") or "").strip()
            reason = item.get("limit_up_reason")
            if not stock_code or not reason:
                continue
            continue_day_cnt = item.get("continue_day_cnt")
            continue_day_text = item.get("continue_day_text")
            limit_up_time = item.get("limit_up_time")
            if limit_up_time and len(str(limit_up_time)) == 5:
                limit_up_time = f"{limit_up_time}:00"

            conn.execute(
                """
                UPDATE limit_up_events
                SET
                    reason = ?,
                    stock_name = COALESCE(?, stock_name),
                    stock_price = COALESCE(?, stock_price),
                    up_limit_desc = COALESCE(?, up_limit_desc),
                    up_limit_keep_times = COALESCE(?, up_limit_keep_times),
                    up_limit_time = COALESCE(?, up_limit_time),
                    fengdan_money = COALESCE(?, fengdan_money),
                    updated_at = current_timestamp
                WHERE trade_date = ? AND stock_code = ?
                """,
                (
                    reason,
                    item.get("name"),
                    item.get("last_price"),
                    continue_day_text,
                    continue_day_cnt,
                    limit_up_time,
                    item.get("seal_money"),
                    date,
                    stock_code,
                ),
            )
            changed = conn.total_changes
            conn.execute(
                """
                UPDATE limit_up_plate_map
                SET stock_reason = ?, updated_at = current_timestamp
                WHERE trade_date = ? AND stock_code = ?
                """,
                (reason, date, stock_code),
            )
            if conn.total_changes > changed:
                count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def enrich_day_data_with_fuyao(day_data: dict[str, Any], items: list[dict[str, Any]]) -> int:
    reason_by_code = {
        str(item.get("ticker") or "").strip(): item
        for item in items
        if item.get("ticker") and item.get("limit_up_reason")
    }
    count = 0
    for plate in day_data.get("uplimit_reason") or []:
        for stock in plate.get("stocks") or []:
            stock_code = str(stock.get("stock_code") or "").strip()
            item = reason_by_code.get(stock_code)
            if not item:
                continue
            stock["reason"] = item.get("limit_up_reason")
            stock["stock_name"] = item.get("name") or stock.get("stock_name")
            stock["stock_price"] = item.get("last_price") or stock.get("stock_price")
            stock["up_limit_desc"] = item.get("continue_day_text") or stock.get("up_limit_desc")
            stock["up_limit_keep_times"] = item.get("continue_day_cnt") or stock.get("up_limit_keep_times")
            stock["fengdan_money"] = item.get("seal_money") or stock.get("fengdan_money")
            if item.get("limit_up_time"):
                stock["up_limit_time"] = f"{item['limit_up_time']}:00" if len(str(item["limit_up_time"])) == 5 else item["limit_up_time"]
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Fuyao limit-up reasons into SQLite.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()

    api_key = os.environ.get("FUYAO_API_KEY", "")
    items = fetch_limit_up_pool(api_key, args.date)
    count = update_limit_up_reasons(args.db, args.date, items)
    print(f"updated={count}, fetched={len(items)}, date={args.date}")


if __name__ == "__main__":
    main()
