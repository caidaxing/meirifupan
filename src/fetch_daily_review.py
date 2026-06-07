"""One-command daily review backfill runner."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import QuantAPI
from db import MarketDB
from derive_review_data import derive_review_data
from fetch_missing_data import DEFAULT_DB_PATH, run_collectors
from fetch_uplimit import fetch_sentiment_data, fetch_uplimit_data, load_token
from generate_review import generate_daily_review


def _date_text(day: object) -> str:
    if isinstance(day, str):
        return day
    if isinstance(day, dict):
        return str(day.get("date") or day.get("trade_date") or "")
    return str(day)


def get_recent_trade_days(api: QuantAPI, days: int) -> list[str]:
    """Fetch recent trade days from the authenticated market API."""
    end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    raw_days = api.get_trade_days(end_date, days=max(days + 10, 30))
    trade_days = [_date_text(day) for day in raw_days]
    trade_days = [day for day in trade_days if day]
    return trade_days[-days:]


def get_recent_public_trade_days(days: int) -> list[str]:
    """Fetch recent A-share trade days from a public AkShare calendar."""
    import akshare as ak

    today = datetime.now().strftime("%Y-%m-%d")
    df = ak.tool_trade_date_hist_sina()
    trade_days = [str(day) for day in df["trade_date"]]
    trade_days = [day for day in trade_days if day <= today]
    return trade_days[-days:]


def get_recent_local_trade_days(db_path: str, days: int) -> list[str]:
    db = MarketDB(db_path)
    db.init_schema()
    try:
        rows = db.conn.execute(
            """
            select distinct trade_date from (
                select trade_date from trade_calendar
                union
                select trade_date from limit_up_events
                union
                select trade_date from limit_down_events
                union
                select trade_date from lhb_daily
            )
            order by trade_date desc
            limit ?
            """,
            (days,),
        ).fetchall()
        return [row["trade_date"] for row in reversed(rows)]
    finally:
        db.close()


def backfill_daily_review(days: int = 20, db_path: str = DEFAULT_DB_PATH, kline_limit: int = 10) -> None:
    """Backfill review data for recent trading days.

    Historical-capable collectors run for every date. Realtime-only collectors
    run for the latest trade date, so old dates are not filled with fake snapshots.
    """
    token = load_token()
    if not token:
        raise RuntimeError("未找到 token，请先配置 config/token.json")

    api = QuantAPI(token)
    try:
        trade_days = get_recent_trade_days(api, days)
    except Exception as exc:
        print(f"交易日历接口失败，改用公开交易日历: {exc}")
        try:
            trade_days = get_recent_public_trade_days(days)
        except Exception as public_exc:
            print(f"公开交易日历失败，改用本地已有日期: {public_exc}")
            trade_days = get_recent_local_trade_days(db_path, days)
    if not trade_days:
        raise RuntimeError("获取交易日历失败")

    print(f"准备回补最近 {len(trade_days)} 个交易日: {trade_days[0]} ~ {trade_days[-1]}")
    latest_day = trade_days[-1]

    db = MarketDB(db_path)
    db.init_schema()
    try:
        for trade_date in trade_days:
            try:
                fetch_uplimit_data(api, trade_date, db)
            except Exception as exc:
                print(f"  涨停主数据失败 {trade_date}: {exc}")
    finally:
        db.close()

    # Sentiment API returns a batch and can safely be called once.
    db = MarketDB(db_path)
    db.init_schema()
    try:
        try:
            fetch_sentiment_data(api, db, days=days)
        except Exception as exc:
            print(f"  情绪数据失败: {exc}")
    finally:
        db.close()

    for trade_date in trade_days:
        run_collectors(
            trade_date=trade_date,
            db_path=db_path,
            kline_limit=kline_limit,
            include_realtime=False,
            include_historical=True,
        )

    run_collectors(
        trade_date=latest_day,
        db_path=db_path,
        kline_limit=kline_limit,
        include_realtime=True,
        include_historical=False,
    )

    try:
        counts = derive_review_data(db_path, trade_days)
        print(
            "  派生数据: "
            f"板块趋势 {counts['plate_trends']}，"
            f"板块原因 {counts['plate_reasons']}，"
            f"核心股快照 {counts['stock_info_snapshots']}"
        )
    except Exception as exc:
        print(f"  派生数据失败: {exc}")

    for trade_date in trade_days:
        try:
            review = generate_daily_review(trade_date, db_path=db_path)
            print(f"  review: {trade_date} -> {review['markdown_path']}")
        except Exception as exc:
            print(f"  复盘生成失败 {trade_date}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="回补 A 股每日复盘数据")
    parser.add_argument("--days", type=int, default=20, help="回补最近多少个交易日")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--kline-limit", type=int, default=10, help="每个交易日补多少只核心股日 K")
    args = parser.parse_args()

    backfill_daily_review(args.days, args.db, args.kline_limit)


if __name__ == "__main__":
    main()
