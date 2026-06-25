"""Fetch plate rotation data from Quantzz-style endpoints."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH


API_BASE = os.environ.get("QUANTZZ_API_BASE", "https://api.zizizaizai.com")
SOURCE = "quant_yjj"


class PlateRotationClient:
    def __init__(self, token: str | None = None):
        self.token = token
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def _request(self, path: str, params: dict[str, Any] | None = None, method: str = "GET", payload: dict[str, Any] | None = None) -> dict:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}{query}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(req, context=self.ctx, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def login(self, email: str, password: str) -> str:
        data = self._request("v2/login/email/login", method="POST", payload={"email": email, "password": password})
        token = ((data.get("data") or {}).get("access_token") or "").strip()
        if not token:
            raise RuntimeError(f"quantzz login failed: {data.get('message') or data.get('msg') or 'no token'}")
        self.token = token
        return token

    def get_trade_days(self, end_date: str, days: int) -> list[str]:
        data = self._request("market/trade/days", {"day_end": end_date, "days": days})
        return data.get("data") or []

    def get_rank_days(self, date: str, n_days: int = 1, data_src: int = 1, n_type: int = 9) -> list[dict[str, Any]]:
        data = self._request(
            "market/plates/17/rank/days",
            {"date2": date, "n_days": n_days, "data_src": data_src, "n_type": n_type},
        )
        rows = data.get("data") or []
        normalized = []
        for rank_no, item in enumerate(rows, start=1):
            last = item.get("last_day") or {}
            normalized.append({
                "trade_date": date,
                "plate_code": item.get("plate_code") or last.get("plate_code"),
                "plate_name": item.get("plate_name") or last.get("plate_name"),
                "rank_no": rank_no,
                "rate": item.get("sum_rate") if item.get("sum_rate") is not None else last.get("rate"),
                "score": _to_float(item.get("sum_score")) if item.get("sum_score") is not None else last.get("score"),
                "money_leader": item.get("sum_leader_money") if item.get("sum_leader_money") is not None else last.get("money_leader"),
                "days": item.get("days") or n_days,
                "raw": item,
            })
        return normalized

    def get_rank(self, date: str, limit: int = 12) -> list[dict[str, Any]]:
        data = self._request("market/plates/17/rank", {"date1": date, "limit": limit})
        rows = data.get("data") or []
        normalized = []
        for rank_no, item in enumerate(rows, start=1):
            item = dict(item)
            item["rank_no"] = item.get("rank_no") or rank_no
            normalized.append(item)
        return normalized

    def get_trend(self, plate_code: str, day_start: str, day_end: str) -> list[dict[str, Any]]:
        data = self._request("market/plates/17/trend", {
            "plate_code": plate_code,
            "day_start": day_start,
            "day_end": day_end,
        })
        return data.get("data") or []

    def get_reasons(self, plate_code: str) -> list[dict[str, Any]]:
        data = self._request("market/plate/popular/reason", {"plate_code": plate_code})
        return data.get("data") or []

    def get_stocks(self, plate_code: str, date: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request(
            f"market/plates/17/{plate_code}/stocks/rank",
            {"is_real": 1, "limit": limit, "date1": date},
        )
        rows = data.get("data") or []
        normalized = []
        for rank_no, item in enumerate(rows, start=1):
            item = dict(item)
            item["trade_date"] = date
            item["rank_no"] = item.get("rank_no") or item.get("rank") or rank_no
            normalized.append(item)
        return normalized


def load_quantzz_token() -> str | None:
    token = (os.environ.get("QUANTZZ_TOKEN") or "").strip()
    if token:
        return token.removeprefix("Bearer ").strip()
    token_file = Path(os.environ.get("QUANTZZ_TOKEN_FILE", Path(__file__).resolve().parents[1] / "config" / "quantzz_token.json"))
    if token_file.exists():
        try:
            payload = json.loads(token_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        token = str(payload.get("access_token") or payload.get("token") or "").strip()
        return token.removeprefix("Bearer ").strip() or None
    return None


def get_quantzz_client() -> PlateRotationClient:
    client = PlateRotationClient(load_quantzz_token())
    if client.token:
        return client
    email = (os.environ.get("QUANTZZ_EMAIL") or "").strip()
    password = (os.environ.get("QUANTZZ_PASSWORD") or "").strip()
    if email and password:
        client.login(email, password)
    return client


def fetch_plate_rotation(
    db_path: str = DEFAULT_DB_PATH,
    end_date: str | None = None,
    days: int = 8,
    top_n: int = 12,
    stock_limit: int = 20,
) -> dict[str, int | str | list[str]]:
    """Fetch and store plate rotation data."""
    client = get_quantzz_client()
    target_end = _day_after(end_date) if end_date else (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    trade_days = client.get_trade_days(target_end, max(days + 5, 13))
    if not trade_days:
        raise RuntimeError("没有拿到题材轮动交易日")
    selected_days = trade_days[-days:]
    latest_date = selected_days[-1]

    ranks: dict[str, list[dict[str, Any]]] = {}
    for day in selected_days:
        try:
            rows = client.get_rank_days(day, n_days=1, data_src=1, n_type=9)
        except Exception as exc:
            print(f"  轮动强度榜跳过登录接口 {day}: {exc}")
            rows = []
        if not rows:
            rows = client.get_rank(day, limit=top_n)
        ranks[day] = rows[:top_n]

    latest_rows = ranks.get(latest_date) or []
    plate_codes = [row.get("plate_code") for row in latest_rows[: min(3, len(latest_rows))] if row.get("plate_code")]
    if not plate_codes and latest_rows:
        plate_codes = [latest_rows[0]["plate_code"]]

    trends: dict[str, list[dict[str, Any]]] = {}
    reasons: dict[str, list[dict[str, Any]]] = {}
    stocks: dict[str, list[dict[str, Any]]] = {}
    for code in plate_codes:
        trends[code] = client.get_trend(code, selected_days[0], latest_date)
        try:
            reasons[code] = client.get_reasons(code)
        except Exception as exc:
            print(f"  板块原因跳过 {code}: {exc}")
            reasons[code] = []
        stocks[code] = client.get_stocks(code, latest_date, stock_limit)

    db = MarketDB(db_path)
    db.init_schema()
    try:
        counts = db.import_plate_rotation_data({
            "date": latest_date,
            "dates": selected_days,
            "ranks": ranks,
            "trends": trends,
            "reasons": reasons,
            "stocks": stocks,
        }, raw_source=SOURCE)
    finally:
        db.close()

    return {
        **counts,
        "date": latest_date,
        "dates": selected_days,
        "plates": plate_codes,
    }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _day_after(value: str) -> str:
    return (datetime.strptime(value, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def main() -> None:
    parser = argparse.ArgumentParser(description="采集题材轮动数据")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--date", help="结束日期，默认取今天后一天以覆盖盘中最近交易日")
    parser.add_argument("--days", type=int, default=8)
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--stock-limit", type=int, default=20)
    args = parser.parse_args()
    result = fetch_plate_rotation(args.db, args.date, args.days, args.top_n, args.stock_limit)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
