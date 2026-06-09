"""Fetch historical market overview metrics for trend charts."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH, _num


def _trade_amount_from_flow(row: dict[str, Any]) -> float | None:
    """Estimate full-market turnover from net flow amount and net-flow ratio."""
    net_amount = _num(row.get("主力净流入-净额"))
    net_ratio = _num(row.get("主力净流入-净占比"))
    if net_amount is None or not net_ratio:
        return None
    return abs(net_amount) / abs(net_ratio / 100)


def fetch_market_turnover_records(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Fetch recent full-market turnover from Eastmoney fund-flow history."""
    df = _fetch_stock_market_fund_flow()
    if df is None or df.empty:
        return []

    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        trade_date = str(row.get("日期") or "")
        if not trade_date or trade_date < start_date or trade_date > end_date:
            continue
        amount = _trade_amount_from_flow(row)
        if amount is None:
            continue
        records.append({
            "trade_date": trade_date,
            "amount": amount,
            "source": "akshare.stock_market_fund_flow",
            "raw": row,
        })
    return records


def _fetch_stock_market_fund_flow() -> Any:
    import akshare as ak

    last_error: Exception | None = None
    for _ in range(3):
        try:
            return ak.stock_market_fund_flow()
        except Exception as exc:
            last_error = exc
            time.sleep(1)

    try:
        return _fetch_stock_market_fund_flow_direct()
    except Exception as exc:
        if last_error is not None:
            raise last_error
        raise exc


def _fetch_stock_market_fund_flow_direct() -> Any:
    import pandas as pd
    import requests

    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": "1.000001",
        "secid2": "0.399001",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": int(time.time() * 1000),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/zjlx/dpzjlx.html",
    }
    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    rows = ((data.get("data") or {}).get("klines") or [])
    parsed = [item.split(",") for item in rows]
    df = pd.DataFrame(parsed)
    if df.empty:
        return df
    df.columns = [
        "日期",
        "主力净流入-净额",
        "小单净流入-净额",
        "中单净流入-净额",
        "大单净流入-净额",
        "超大单净流入-净额",
        "主力净流入-净占比",
        "小单净流入-净占比",
        "中单净流入-净占比",
        "大单净流入-净占比",
        "超大单净流入-净占比",
        "上证-收盘价",
        "上证-涨跌幅",
        "深证-收盘价",
        "深证-涨跌幅",
    ]
    return df


def fetch_market_overview(
    start_date: str | None = None,
    end_date: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
    strict: bool = False,
) -> dict[str, Any]:
    """Update historical market turnover without overwriting breadth counts."""
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=14)).strftime("%Y-%m-%d")

    try:
        records = fetch_market_turnover_records(start_date, end_date)
    except Exception as exc:
        if strict:
            raise
        return {"market_turnover": 0, "warning": str(exc)}
    db = MarketDB(db_path)
    db.init_schema()
    try:
        count = 0
        for record in records:
            db.import_market_breadth(record["trade_date"], {
                "amount": record["amount"],
                "source": record["source"],
                "raw": record["raw"],
            })
            count += 1
        return {"market_turnover": count}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="补齐大盘成交额等总览趋势数据")
    parser.add_argument("--start-date", help="开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end-date", help="结束日期，格式 YYYY-MM-DD")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--strict", action="store_true", help="数据源失败时直接退出")
    args = parser.parse_args()

    result = fetch_market_overview(args.start_date, args.end_date, args.db, strict=args.strict)
    print(f"大盘总览补齐完成: {result}")


if __name__ == "__main__":
    main()
