"""Daily data update entry point for A-share review data."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import QuantAPI
from db import MarketDB
from derive_review_data import derive_review_data
from derive_shortline_hot import derive_shortline_hot
from fetch_daily_review import get_recent_local_trade_days, get_recent_public_trade_days, get_recent_trade_days
from fetch_hot import fetch_hot_boards, fetch_hot_stocks
from fetch_market_overview import fetch_market_overview
from fetch_missing_data import DEFAULT_DB_PATH, run_collectors
from fetch_plate_index_daily import fetch_plate_index_daily
from fetch_plate_rotation import fetch_plate_rotation
from fetch_premarket import collect_premarket_data
from fetch_ths_hot import fetch_ths_hot_bundle
from fetch_uplimit import fetch_sentiment_data, fetch_uplimit_data, load_token
from fuyao_collect import collect_fuyao_daily
from generate_review import generate_daily_review


DEFAULT_REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def compact_result(value: Any, depth: int = 0) -> Any:
    """Keep job details readable instead of storing full report payloads."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 240 else value[:240].rstrip() + "..."
    if isinstance(value, list):
        return {"count": len(value)}
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"raw_payload", "raw", "traceback"}:
                continue
            if isinstance(item, list):
                compact[key] = {"count": len(item)}
            elif isinstance(item, dict):
                compact[key] = compact_result(item, depth + 1) if depth < 1 else {"keys": len(item)}
            else:
                compact[key] = compact_result(item, depth + 1)
        return compact
    return str(value)


def resolve_target_trade_day(
    api: QuantAPI | None,
    db_path: str,
    trade_date: str | None = None,
    allow_public_calendar: bool = True,
) -> tuple[str, bool, list[str]]:
    """Return target trade day, whether today is a trade day, and recent days."""
    today = datetime.now().strftime("%Y-%m-%d")
    if trade_date:
        return trade_date, trade_date == today, [trade_date]

    recent_days: list[str] = []
    if api is not None:
        try:
            recent_days = get_recent_trade_days(api, 8)
        except Exception as exc:
            print(f"交易日历接口失败，继续尝试公开交易日历: {exc}")
    if not recent_days and allow_public_calendar:
        try:
            recent_days = get_recent_public_trade_days(8)
        except Exception as exc:
            print(f"公开交易日历失败，改用本地已有日期: {exc}")
    if not recent_days:
        recent_days = get_recent_local_trade_days(db_path, 8)
    if not recent_days:
        raise RuntimeError("没有可用交易日")

    target = recent_days[-1]
    return target, target == today, recent_days


def run_step(name: str, fn, summary: dict[str, Any]) -> None:
    started = now_text()
    try:
        result = fn()
        summary["steps"].append({
            "name": name,
            "status": "success",
            "started_at": started,
            "finished_at": now_text(),
            "result": compact_result(result),
        })
    except Exception as exc:
        summary["steps"].append({
            "name": name,
            "status": "failed",
            "started_at": started,
            "finished_at": now_text(),
            "message": str(exc),
            "traceback": traceback.format_exc(limit=8),
        })
        if summary.get("strict"):
            raise


def run_daily_update(
    trade_date: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
    kline_limit: int = 30,
    plate_review_days: int = 20,
    plate_per_day_limit: int = 8,
    force: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    """Fetch today's data, derive review datasets, and generate the daily report."""
    strict_error: Exception | None = None
    token = load_token()
    api = QuantAPI(token) if token else None
    target_day, is_today_trade_day, recent_days = resolve_target_trade_day(api, db_path, trade_date)
    summary: dict[str, Any] = {
        "trade_date": target_day,
        "is_today_trade_day": is_today_trade_day,
        "recent_trade_days": recent_days,
        "strict": strict,
        "steps": [],
    }

    started_at = now_text()
    db = MarketDB(db_path)
    db.init_schema()
    try:
        if not force and trade_date is None and not is_today_trade_day:
            message = f"今天不是交易日，最近交易日是 {target_day}，跳过自动更新"
            db.log_data_job("daily_update", target_day, "skipped", message, summary, started_at, now_text())
            print(message)
            return {**summary, "status": "skipped", "message": message}

        db.log_data_job("daily_update", target_day, "running", "开始每日自动更新", summary, started_at, None)
    finally:
        db.close()

    try:
        if api is None:
            raise RuntimeError("未找到 token，请先配置 config/token.json")

        db = MarketDB(db_path)
        db.init_schema()

        run_step("涨停主数据", lambda: _fetch_uplimit(api, db, target_day), summary)
        run_step("Fuyao补充数据", lambda: _fetch_fuyao(db_path, target_day), summary)
        run_step("情绪数据", lambda: _fetch_sentiment(api, db), summary)
        run_step("大盘指数", lambda: _fetch_index_daily(api, db, target_day), summary)
        run_step(
            "历史口径数据",
            lambda: run_collectors(target_day, db_path, kline_limit, include_realtime=False, include_historical=True),
            summary,
        )
        run_step(
            "实时口径数据",
            lambda: run_collectors(target_day, db_path, kline_limit=0, include_realtime=True, include_historical=False),
            summary,
        )
        run_step(
            "大盘总览趋势",
            lambda: fetch_market_overview(end_date=target_day, db_path=db_path, lookback_days=90),
            summary,
        )
        run_step("热门股票", lambda: _fetch_hot_stocks(db, target_day), summary)
        run_step("热门板块", lambda: _fetch_hot_boards(db, target_day), summary)
        run_step("盘前外部数据", lambda: _fetch_premarket_external(db_path, target_day), summary)
        run_step("题材轮动", lambda: fetch_plate_rotation(db_path=db_path, end_date=target_day, days=8, top_n=12), summary)
        run_step("短线热榜", lambda: {"shortline_hot": derive_shortline_hot(db_path, target_day)}, summary)
        run_step(
            "真实板块日线",
            lambda: fetch_plate_index_daily(
                db_path=db_path,
                end_date=target_day,
                review_days=plate_review_days,
                per_day_limit=plate_per_day_limit,
            ),
            summary,
        )
        # Gate downstream steps: skip derive/generate if critical upstream failed
        critical_steps = {"涨停主数据", "情绪数据", "历史口径数据", "题材轮动"}
        critical_failed = any(
            s["name"] in critical_steps and s["status"] != "success"
            for s in summary["steps"]
        )
        if critical_failed:
            summary["steps"].append({
                "name": "派生数据",
                "status": "skipped",
                "started_at": now_text(),
                "finished_at": now_text(),
                "message": "上游关键步骤失败，跳过",
            })
            summary["steps"].append({
                "name": "生成复盘",
                "status": "skipped",
                "started_at": now_text(),
                "finished_at": now_text(),
                "message": "上游关键步骤失败，跳过",
            })
        else:
            run_step("派生数据", lambda: derive_review_data(db_path, [target_day]), summary)
            run_step("生成复盘", lambda: generate_daily_review(target_day, db_path=db_path, output_dir=DEFAULT_REPORT_DIR), summary)

        failed_steps = [step for step in summary["steps"] if step["status"] != "success"]
        status = "success" if not failed_steps else "partial"
        message = "每日自动更新完成" if status == "success" else f"{len(failed_steps)} 个步骤失败"
    except Exception as exc:
        status = "failed"
        message = str(exc)
        strict_error = exc
        summary["steps"].append({
            "name": "每日自动更新",
            "status": "failed",
            "started_at": started_at,
            "finished_at": now_text(),
            "message": message,
            "traceback": traceback.format_exc(limit=8),
        })
    finally:
        try:
            db.close()  # type: ignore[possibly-undefined]
        except Exception:
            pass
    summary["status"] = status
    summary["message"] = message

    db = MarketDB(db_path)
    db.init_schema()
    try:
        db.log_data_job("daily_update", target_day, status, message, summary, started_at, now_text())
    finally:
        db.close()

    if strict_error is not None and strict:
        raise strict_error

    return summary


def _fetch_sentiment(api: QuantAPI, db: MarketDB) -> dict[str, int]:
    return {"sentiment_daily": fetch_sentiment_data(api, db, days=15)}


def _fetch_index_daily(api: QuantAPI, db: MarketDB, trade_date: str) -> dict[str, int]:
    """采集大盘指数（上证/深证/创业板/北证50）。"""
    try:
        index_result = api.get_index_trends()
    except Exception as e:
        print(f"  ⚠️ Quantzz 指数接口异常: {e}，回退 AkShare")
        index_result = None

    indices: list[dict] = []
    if index_result and index_result.get("code") == 200 and index_result.get("data"):
        for item in index_result["data"]:
            indices.append({
                "code": item.get("code") or "",
                "name": item.get("name") or "",
                "last_px": item.get("last_px"),
                "px_change_rate": item.get("px_change_rate"),
                "amount": item.get("amount"),
            })

    if not indices:
        # AkShare fallback
        try:
            import akshare as ak
            symbols = {"sh000001": ("000001.SS", "上证指数"), "sz399001": ("399001.SZ", "深证成指"),
                        "sz399006": ("399006.SZ", "创业板指"), "bj899050": ("899050.BJ", "北证50")}
            for sym, (code, name) in symbols.items():
                df = ak.stock_zh_index_daily(symbol=sym)
                if df is None or df.empty:
                    continue
                row = df[df["date"].astype(str) == trade_date]
                if row.empty:
                    continue
                r = row.iloc[-1]
                close_price = float(r["close"]) if r.get("close") is not None else None
                prev_df = df[df["date"].astype(str) < trade_date].tail(1)
                change_pct = None
                if close_price and not prev_df.empty:
                    prev_close = float(prev_df.iloc[-1]["close"])
                    if prev_close:
                        change_pct = round((close_price - prev_close) / prev_close * 100, 2)
                indices.append({"code": code, "name": name, "last_px": close_price,
                                "px_change_rate": change_pct, "amount": float(r.get("volume") or 0)})
        except Exception as e:
            print(f"  ⚠️ AkShare 指数回退也失败: {e}")

    if not indices:
        return {"market_index_daily": 0}
    count = db.import_index_daily(trade_date, indices, raw_source="daily_update")
    return {"market_index_daily": count}


def _fetch_uplimit(api: QuantAPI, db: MarketDB, trade_date: str) -> dict[str, Any]:
    data = fetch_uplimit_data(api, trade_date, db)
    return {
        "limit_up_plates": len(data.get("uplimit_reason") or []),
        "hot_plates": len(data.get("uplimit_hot") or []),
        "plate_rank": len(data.get("plate_rank") or []),
    }


def _fetch_fuyao(db_path: str, trade_date: str) -> dict[str, Any]:
    if not os.environ.get("FUYAO_API_KEY"):
        return {"skipped": "未配置 FUYAO_API_KEY"}
    return collect_fuyao_daily(trade_date, db_path, include_indexes=True, constituent_limit=0)


def _fetch_hot_stocks(db: MarketDB, trade_date: str) -> dict[str, int]:
    result = {"hot_stocks": fetch_hot_stocks(db, trade_date)}
    result.update(fetch_ths_hot_bundle(db, trade_date))
    return result


def _fetch_hot_boards(db: MarketDB, trade_date: str) -> dict[str, int]:
    concept = fetch_hot_boards(db, "concept", trade_date)
    industry = fetch_hot_boards(db, "industry", trade_date)
    return {"concept_boards": concept, "industry_boards": industry}


def _fetch_premarket_external(db_path: str, trade_date: str) -> dict[str, int | str]:
    """采集新闻、公告和隔夜美股，写入盘前相关表。"""
    return collect_premarket_data(
        guide_date=datetime.now().strftime("%Y-%m-%d"),
        review_date=trade_date,
        db_path=db_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="每日自动更新 A 股复盘数据")
    parser.add_argument("--date", help="指定交易日，格式 YYYY-MM-DD；不传则自动取最近交易日")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--kline-limit", type=int, default=30, help="补多少只核心股票日 K")
    parser.add_argument("--plate-review-days", type=int, default=20, help="板块指数从最近多少个交易日筛核心板块")
    parser.add_argument("--plate-per-day-limit", type=int, default=8, help="每天候选核心板块数量")
    parser.add_argument("--force", action="store_true", help="非交易日也强制更新最近交易日")
    parser.add_argument("--strict", action="store_true", help="任一步失败就退出")
    args = parser.parse_args()

    summary = run_daily_update(
        trade_date=args.date,
        db_path=args.db,
        kline_limit=args.kline_limit,
        plate_review_days=args.plate_review_days,
        plate_per_day_limit=args.plate_per_day_limit,
        force=args.force,
        strict=args.strict,
    )
    print(f"{summary['trade_date']} {summary.get('status')}: {summary.get('message')}")


if __name__ == "__main__":
    main()
