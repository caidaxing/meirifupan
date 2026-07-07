"""Fetch pre-market news, announcements and US stock movers."""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH
from generate_premarket import resolve_review_date
from utils import is_blank, to_float, to_text


US_FAMOUS_SECTORS = ["科技类", "汽车能源类", "媒体类", "金融类", "医药食品类", "制造零售类"]
CLS_ROLL_URL = "https://www.cls.cn/v1/roll/get_roll_list"
CLS_WEB_VERSION = "8.7.9"
CHINA_TZ = timezone(timedelta(hours=8))
TENCENT_US_QUOTES_URL = "https://qt.gtimg.cn/q="
TENCENT_US_SYMBOLS: dict[str, tuple[str, str]] = {
    "NVDA": ("英伟达", "科技类"),
    "AAPL": ("苹果", "科技类"),
    "MSFT": ("微软", "科技类"),
    "GOOGL": ("谷歌A", "科技类"),
    "META": ("Meta", "媒体类"),
    "AMZN": ("亚马逊", "制造零售类"),
    "TSLA": ("特斯拉", "汽车能源类"),
    "AMD": ("AMD", "科技类"),
    "AVGO": ("博通", "科技类"),
    "MU": ("美光科技", "科技类"),
    "NFLX": ("奈飞", "媒体类"),
    "JPM": ("摩根大通", "金融类"),
    "LLY": ("礼来", "医药食品类"),
    "WMT": ("沃尔玛", "制造零售类"),
}


class TimeoutError(RuntimeError):
    pass


def _timeout_handler(signum, frame) -> None:
    raise TimeoutError("数据源响应超时")


def call_with_timeout(fn: Callable[[], Any], seconds: int = 18) -> Any:
    """Run a blocking AkShare call with a hard timeout on Unix-like systems."""
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _first(row: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in row and not is_blank(row.get(name)):
            return row.get(name)
    lowered = {str(k).lower(): k for k in row.keys()}
    for name in names:
        key = lowered.get(name.lower())
        if key is not None and not is_blank(row.get(key)):
            return row.get(key)
    return None


def _records(df: Any) -> list[dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    return [dict(row) for row in df.to_dict(orient="records")]


def _ak_date(value: str) -> str:
    return value.replace("-", "")


def _code(value: Any) -> str | None:
    text = to_text(value)
    if not text:
        return None
    text = text.upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
    return text


def _normalize_us_symbol(value: Any) -> str | None:
    text = to_text(value)
    if not text:
        return None
    text = text.upper().strip()
    if text.startswith("US") and len(text) > 2:
        text = text[2:]
    if "." in text:
        left, right = text.split(".", 1)
        if left.isdigit() and right:
            text = right
        else:
            text = left
    return text.replace("-", ".") or None


def _fallback_title(row: dict[str, Any]) -> str | None:
    for value in row.values():
        text = to_text(value)
        if text and len(text) >= 6:
            return text[:120]
    return None


def _cls_param_string(params: dict[str, Any]) -> str:
    return "&".join(f"{key}={params[key]}" for key in sorted(params) if params.get(key) is not None)


def _cls_sign(params: dict[str, Any]) -> str:
    digest = hashlib.sha1(_cls_param_string(params).encode("utf-8")).hexdigest()
    return hashlib.md5(digest.encode("utf-8")).hexdigest()


def _datetime_from_epoch(value: Any) -> str | None:
    timestamp = to_float(value)
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return None


def _title_from_content(content: str | None) -> str | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("【") and "】" in text[:80]:
        title = text[1:text.index("】")].strip()
        if title:
            return title[:80]
    for separator in ["。", "；", ";", "\n"]:
        if separator in text:
            text = text.split(separator, 1)[0]
            break
    return text[:80].strip() or None


def _parse_cls_roll_item(item: dict[str, Any]) -> dict[str, Any] | None:
    content = to_text(item.get("content"))
    title = to_text(item.get("title")) or _title_from_content(content)
    if not title:
        return None
    url = to_text(item.get("shareurl"))
    if not url and item.get("id"):
        url = f"https://www.cls.cn/detail/{item.get('id')}"
    return {
        "source": "cls",
        "published_at": _datetime_from_epoch(item.get("ctime")),
        "title": title,
        "content": content,
        "url": url,
        "raw_payload": item,
    }


def fetch_cls_news_records(limit: int = 40) -> list[dict[str, Any]]:
    """Fetch Cailian Press telegraph news from the current web endpoint."""
    import requests

    params = {
        "app": "CailianpressWeb",
        "last_time": int(time.time()),
        "os": "web",
        "refresh_type": 1,
        "rn": limit,
        "sv": CLS_WEB_VERSION,
    }
    signed_params = {**params, "sign": _cls_sign(params)}
    response = requests.get(
        CLS_ROLL_URL,
        params=signed_params,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Referer": "https://www.cls.cn/telegraph",
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errno") not in (0, "0"):
        raise RuntimeError(payload.get("msg") or f"财联社接口返回异常: {payload.get('errno')}")
    records: list[dict[str, Any]] = []
    for item in payload.get("data", {}).get("roll_data", []):
        if not isinstance(item, dict):
            continue
        record = _parse_cls_roll_item(item)
        if record:
            records.append(record)
        if len(records) >= limit:
            break
    return records


def fetch_news_records(guide_date: str, limit: int = 40) -> list[dict[str, Any]]:
    """Fetch market news from all configured public sources.

    ``limit`` is the maximum rows per source, not the total row cap.
    """
    import akshare as ak

    sources: list[tuple[str, Callable[[], Any]]] = [
        ("eastmoney", ak.stock_info_global_em),
        ("sina", ak.stock_info_global_sina),
        ("cctv", lambda: ak.news_cctv(date=_ak_date(guide_date))),
    ]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        for record in fetch_cls_news_records(limit=limit):
            title = to_text(record.get("title"))
            if not title:
                continue
            key = title[:80]
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
            if sum(1 for item in records if item.get("source") == "cls") >= limit:
                break
    except Exception as exc:
        print(f"  ⚠️  新闻源 cls 失败: {exc}")

    for source, fn in sources:
        source_count = 0
        try:
            rows = _records(call_with_timeout(fn))
        except Exception as exc:
            print(f"  ⚠️  新闻源 {source} 失败: {exc}")
            continue
        for row in rows:
            title = to_text(_first(row, ["标题", "title", "新闻标题", "内容", "摘要"])) or _fallback_title(row)
            if not title:
                continue
            key = title[:80]
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "source": source,
                "published_at": to_text(_first(row, ["发布时间", "时间", "日期", "date", "datetime"])),
                "title": title,
                "content": to_text(_first(row, ["内容", "摘要", "简介", "summary"])),
                "url": to_text(_first(row, ["链接", "url", "新闻链接"])),
                "raw_payload": row,
            })
            source_count += 1
            if source_count >= limit:
                break
    return records


def fetch_announcement_records(notice_date: str, limit: int = 500) -> list[dict[str, Any]]:
    """Fetch A-share announcements for the review date."""
    import akshare as ak

    try:
        rows = _records(call_with_timeout(lambda: ak.stock_notice_report(symbol="全部", date=_ak_date(notice_date)), 22))
    except Exception as exc:
        print(f"  ⚠️  公告源失败: {exc}")
        return []
    records: list[dict[str, Any]] = []
    for row in rows[:limit]:
        title = to_text(_first(row, ["公告标题", "标题", "notice_title", "title"])) or _fallback_title(row)
        if not title:
            continue
        records.append({
            "stock_code": _code(_first(row, ["代码", "股票代码", "证券代码", "stock_code"])),
            "stock_name": to_text(_first(row, ["名称", "股票简称", "证券简称", "stock_name"])),
            "notice_date": notice_date,
            "notice_type": to_text(_first(row, ["公告类型", "类型", "notice_type"])),
            "title": title,
            "url": to_text(_first(row, ["公告链接", "链接", "url"])),
            "raw_payload": row,
        })
    return records


def fetch_us_stock_records(quote_date: str, limit: int = 60) -> list[dict[str, Any]]:
    """Fetch famous US stock movers for overnight reference."""
    try:
        import akshare as ak
    except Exception as exc:
        print(f"  ⚠️  美股源 eastmoney 不可用: {exc}")
        try:
            return fetch_tencent_us_stock_records(limit=limit)
        except Exception as fallback_exc:
            print(f"  ⚠️  美股备用源 tencent 失败: {fallback_exc}")
            return []

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sector in US_FAMOUS_SECTORS:
        try:
            rows = _records(call_with_timeout(lambda sector=sector: ak.stock_us_famous_spot_em(symbol=sector), 18))
        except Exception as exc:
            print(f"  ⚠️  美股源 {sector} 失败: {exc}")
            continue
        for row in rows:
            symbol = _normalize_us_symbol(_first(row, ["代码", "symbol", "编码"]))
            if not symbol:
                continue
            if symbol in seen:
                continue
            seen.add(symbol)
            records.append({
                "symbol": symbol,
                "stock_name": to_text(_first(row, ["名称", "股票名称", "中文名称", "name"])) or symbol,
                "sector": sector,
                "latest_price": to_float(_first(row, ["最新价", "价格", "price", "最新"])),
                "change_pct": to_float(_first(row, ["涨跌幅", "涨幅", "change_pct", "percent"])),
                "change_amount": to_float(_first(row, ["涨跌额", "change_amount", "涨跌"])),
                "raw_payload": row,
            })
    records.sort(key=lambda item: abs(item.get("change_pct") or 0), reverse=True)
    if records:
        return records[:limit]
    try:
        return fetch_tencent_us_stock_records(limit=limit)
    except Exception as exc:
        print(f"  ⚠️  美股备用源 tencent 失败: {exc}")
        return []


def _parse_tencent_us_quote_line(
    line: str,
    symbol_meta: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    symbol_meta = symbol_meta or TENCENT_US_SYMBOLS
    if '="' not in line:
        return None
    raw_symbol = line.split("=", 1)[0].replace("v_us", "").strip().upper()
    if not raw_symbol:
        return None
    payload = line.split("=", 1)[1].strip().strip(";").strip('"')
    parts = payload.split("~")
    if len(parts) < 33:
        return None
    symbol = (parts[2] or raw_symbol).split(".", 1)[0].upper()
    default_name, default_sector = symbol_meta.get(symbol, (symbol, "美股核心"))
    return {
        "symbol": symbol,
        "stock_name": to_text(parts[1]) or default_name,
        "sector": default_sector,
        "latest_price": to_float(parts[3]),
        "change_pct": to_float(parts[32]),
        "change_amount": to_float(parts[31]),
        "raw_payload": {
            "source": "tencent_us_quote",
            "line": line,
            "parts": parts,
        },
    }


def fetch_tencent_us_stock_records(limit: int = 60) -> list[dict[str, Any]]:
    """Fetch core US stock quotes from Tencent as a fallback for Eastmoney."""
    import requests

    query = ",".join(f"us{symbol}" for symbol in TENCENT_US_SYMBOLS.keys())
    response = requests.get(
        f"{TENCENT_US_QUOTES_URL}{query}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Referer": "https://gu.qq.com/",
        },
        timeout=10,
    )
    response.raise_for_status()
    text = response.content.decode(response.apparent_encoding or "gbk", errors="replace")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        record = _parse_tencent_us_quote_line(line)
        if not record:
            continue
        symbol = record["symbol"]
        if symbol in seen:
            continue
        seen.add(symbol)
        records.append(record)
    records.sort(key=lambda item: abs(item.get("change_pct") or 0), reverse=True)
    return records[:limit]


def collect_premarket_data(
    guide_date: str | None = None,
    review_date: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> dict[str, int | str]:
    """Fetch and store pre-market external data."""
    guide_date = guide_date or datetime.now().strftime("%Y-%m-%d")
    db = MarketDB(db_path)
    db.init_schema()
    try:
        resolved_review_date = resolve_review_date(db.conn, guide_date, review_date)
        news = fetch_news_records(guide_date)
        announcements = fetch_announcement_records(resolved_review_date)
        us_quotes = fetch_us_stock_records(guide_date)
        return {
            "guide_date": guide_date,
            "review_date": resolved_review_date,
            "news": db.import_premarket_news(guide_date, news),
            "announcements": db.import_stock_announcements(resolved_review_date, announcements),
            "us_quotes": db.import_us_stock_quotes(guide_date, us_quotes),
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="采集盘前新闻、公告和隔夜美股")
    parser.add_argument("--date", help="盘前指引日期，默认今天")
    parser.add_argument("--review-date", help="公告对应的上一交易日")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    args = parser.parse_args()
    result = collect_premarket_data(args.date, args.review_date, args.db)
    print(result)


if __name__ == "__main__":
    main()
