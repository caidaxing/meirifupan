"""Simple daily scheduler for market review updates."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_update import run_daily_update
from fetch_missing_data import DEFAULT_DB_PATH


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def next_run_time(run_at: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    hour, minute = _parse_hhmm(run_at)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def run_scheduler(
    run_at: str,
    db_path: str = DEFAULT_DB_PATH,
    kline_limit: int = 30,
    force: bool = False,
) -> None:
    print(f"每日更新调度已启动: {run_at} 执行，数据库 {db_path}", flush=True)
    while True:
        target = next_run_time(run_at)
        wait_seconds = max(1, int((target - datetime.now()).total_seconds()))
        print(f"下次执行时间: {target.isoformat(timespec='seconds')}", flush=True)
        time.sleep(wait_seconds)
        try:
            summary = run_daily_update(db_path=db_path, kline_limit=kline_limit, force=force)
            print(f"更新结束: {summary.get('trade_date')} {summary.get('status')} {summary.get('message')}", flush=True)
        except Exception as exc:
            print(f"更新失败: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="每日 A 股复盘数据自动更新调度器")
    parser.add_argument("--run-at", default=os.environ.get("DAILY_UPDATE_AT", "17:30"), help="每天执行时间，格式 HH:MM")
    parser.add_argument("--db", default=os.environ.get("DB_PATH", DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--kline-limit", type=int, default=int(os.environ.get("DAILY_KLINE_LIMIT", "30")))
    parser.add_argument("--force", action="store_true", default=os.environ.get("DAILY_UPDATE_FORCE") == "1")
    args = parser.parse_args()

    run_scheduler(args.run_at, args.db, args.kline_limit, args.force)


if __name__ == "__main__":
    main()
