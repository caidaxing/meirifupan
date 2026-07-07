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
from news_update import run_announcements_update, run_news_update


DailySchedule = dict[str, str | list[str]]
IntervalSchedule = dict[str, int]


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


def next_interval_run_time(interval_minutes: int, now: datetime | None = None) -> datetime:
    """Return the next wall-clock interval boundary."""
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be greater than 0")
    now = now or datetime.now()
    minute = (now.minute // interval_minutes + 1) * interval_minutes
    target = now.replace(second=0, microsecond=0)
    if minute >= 60:
        target = target.replace(minute=0) + timedelta(hours=1)
    else:
        target = target.replace(minute=minute)
    if target <= now:
        target += timedelta(minutes=interval_minutes)
    return target


def _daily_candidates(schedule: DailySchedule, now: datetime) -> list[tuple[str, datetime]]:
    candidates: list[tuple[str, datetime]] = []
    for name, run_at_values in schedule.items():
        values = run_at_values if isinstance(run_at_values, list) else [run_at_values]
        for run_at in values:
            candidates.append((name, next_run_time(run_at, now)))
    return candidates


def next_named_run_time(
    schedule: DailySchedule,
    now: datetime | None = None,
    interval_schedule: IntervalSchedule | None = None,
) -> tuple[str, datetime]:
    """Return the next task name and run time from daily and interval schedules."""
    now = now or datetime.now()
    candidates = _daily_candidates(schedule, now)
    for name, interval_minutes in (interval_schedule or {}).items():
        candidates.append((name, next_interval_run_time(interval_minutes, now)))
    if not candidates:
        raise ValueError("schedule is empty")
    return min(candidates, key=lambda item: item[1])


def due_task_names(schedule: DailySchedule, target: datetime) -> list[str]:
    """Return all daily tasks configured for the target HH:MM."""
    hhmm = target.strftime("%H:%M")
    names: list[str] = []
    for name, run_at_values in schedule.items():
        values = run_at_values if isinstance(run_at_values, list) else [run_at_values]
        if hhmm in values:
            names.append(name)
    return sorted(set(names))


def due_interval_task_names(schedule: IntervalSchedule, target: datetime, now: datetime | None = None) -> list[str]:
    """Return interval tasks whose next boundary is the target time."""
    now = now or datetime.now()
    names: list[str] = []
    for name, interval_minutes in schedule.items():
        if next_interval_run_time(interval_minutes, now) == target:
            names.append(name)
    return sorted(names)


def _parse_time_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def run_scheduler(
    run_at: str,
    db_path: str = DEFAULT_DB_PATH,
    kline_limit: int = 30,
    force: bool = False,
    news_interval_minutes: int = 10,
    announcement_ats: list[str] | None = None,
) -> None:
    announcement_ats = announcement_ats or ["17:30", "22:00"]
    daily_schedule: DailySchedule = {
        "announcements_update": announcement_ats,
        "daily_update": [run_at],
    }
    interval_schedule: IntervalSchedule = {
        "news_update": news_interval_minutes,
    }
    print(
        f"自动调度已启动: 新闻每 {news_interval_minutes} 分钟，公告 {','.join(announcement_ats)}，复盘 {run_at}，数据库 {db_path}",
        flush=True,
    )
    while True:
        planning_now = datetime.now()
        _, target = next_named_run_time(daily_schedule, planning_now, interval_schedule=interval_schedule)
        wait_seconds = max(1, int((target - datetime.now()).total_seconds()))
        due_tasks = due_task_names(daily_schedule, target)
        due_tasks.extend(due_interval_task_names(interval_schedule, target, planning_now))
        due_tasks = sorted(set(due_tasks))
        print(f"下次执行: {','.join(due_tasks)} {target.isoformat(timespec='seconds')}", flush=True)
        time.sleep(wait_seconds)
        for due_task in due_tasks:
            try:
                if due_task == "news_update":
                    summary = run_news_update(db_path=db_path)
                    print(f"新闻结束: {summary.get('guide_date')} {summary.get('status')} {summary.get('message')}", flush=True)
                elif due_task == "announcements_update":
                    summary = run_announcements_update(db_path=db_path)
                    print(f"公告结束: {summary.get('notice_date')} {summary.get('status')} {summary.get('message')}", flush=True)
                elif due_task == "daily_update":
                    summary = run_daily_update(db_path=db_path, kline_limit=kline_limit, force=force)
                    print(f"复盘结束: {summary.get('trade_date')} {summary.get('status')} {summary.get('message')}", flush=True)
            except Exception as exc:
                print(f"{due_task} 更新失败: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="每日 A 股复盘数据自动更新调度器")
    parser.add_argument("--run-at", default=os.environ.get("DAILY_UPDATE_AT", "17:30"), help="每天执行时间，格式 HH:MM")
    parser.add_argument("--db", default=os.environ.get("DB_PATH", DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--kline-limit", type=int, default=int(os.environ.get("DAILY_KLINE_LIMIT", "30")))
    parser.add_argument("--force", action="store_true", default=os.environ.get("DAILY_UPDATE_FORCE") == "1")
    parser.add_argument(
        "--news-interval-minutes",
        type=int,
        default=int(os.environ.get("NEWS_UPDATE_INTERVAL_MINUTES", "10")),
        help="新闻高频更新间隔，单位分钟",
    )
    parser.add_argument(
        "--announcement-at",
        action="append",
        default=None,
        help="公告更新时间，格式 HH:MM；可重复传入。默认读取 ANNOUNCEMENT_UPDATE_ATS=17:30,22:00",
    )
    args = parser.parse_args()
    announcement_ats = args.announcement_at or _parse_time_list(os.environ.get("ANNOUNCEMENT_UPDATE_ATS", "17:30,22:00"))

    run_scheduler(
        args.run_at,
        args.db,
        args.kline_limit,
        args.force,
        args.news_interval_minutes,
        announcement_ats,
    )


if __name__ == "__main__":
    main()
