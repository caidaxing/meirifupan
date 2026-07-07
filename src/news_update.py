"""Standalone news and announcement update entry points."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB
from daily_update import compact_result, now_text
from fetch_missing_data import DEFAULT_DB_PATH
from fetch_premarket import fetch_announcement_records, fetch_news_records


def _log_start(db_path: str, job_name: str, task_date: str, message: str, summary: dict[str, Any], started_at: str) -> None:
    db = MarketDB(db_path)
    db.init_schema()
    try:
        db.log_data_job(job_name, task_date, "running", message, summary, started_at, None)
    finally:
        db.close()


def _log_finish(
    db_path: str,
    job_name: str,
    task_date: str,
    status: str,
    message: str,
    summary: dict[str, Any],
    started_at: str,
) -> None:
    db = MarketDB(db_path)
    db.init_schema()
    try:
        db.log_data_job(job_name, task_date, status, message, summary, started_at, now_text())
    finally:
        db.close()


def run_news_update(
    guide_date: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = 40,
    strict: bool = False,
) -> dict[str, Any]:
    """Fetch current market news and store it for the selected date."""
    guide_date = guide_date or datetime.now().strftime("%Y-%m-%d")
    started_at = now_text()
    summary: dict[str, Any] = {
        "guide_date": guide_date,
        "limit_per_source": limit,
        "steps": [],
    }
    _log_start(db_path, "news_update", guide_date, "开始新闻高频更新", summary, started_at)

    try:
        step_started = now_text()
        records = fetch_news_records(guide_date, limit=limit)
        db = MarketDB(db_path)
        db.init_schema()
        try:
            imported = db.import_premarket_news(guide_date, records)
        finally:
            db.close()
        summary["steps"].append({
            "name": "采集新闻",
            "status": "success",
            "started_at": step_started,
            "finished_at": now_text(),
            "result": compact_result({"fetched": len(records), "imported": imported}),
        })
        summary["news"] = imported
        status = "success"
        message = f"新闻更新完成，写入 {imported} 条"
    except Exception as exc:
        status = "failed"
        message = str(exc)
        summary["steps"].append({
            "name": "新闻更新",
            "status": "failed",
            "started_at": started_at,
            "finished_at": now_text(),
            "message": message,
            "traceback": traceback.format_exc(limit=8),
        })
        if strict:
            summary["status"] = status
            summary["message"] = message
            _log_finish(db_path, "news_update", guide_date, status, message, summary, started_at)
            raise

    summary["status"] = status
    summary["message"] = message
    _log_finish(db_path, "news_update", guide_date, status, message, summary, started_at)
    return summary


def run_announcements_update(
    notice_date: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = 500,
    strict: bool = False,
) -> dict[str, Any]:
    """Fetch A-share announcements and store them for the selected date."""
    notice_date = notice_date or datetime.now().strftime("%Y-%m-%d")
    started_at = now_text()
    summary: dict[str, Any] = {
        "notice_date": notice_date,
        "limit": limit,
        "steps": [],
    }
    _log_start(db_path, "announcements_update", notice_date, "开始公告定时更新", summary, started_at)

    try:
        step_started = now_text()
        records = fetch_announcement_records(notice_date, limit=limit)
        db = MarketDB(db_path)
        db.init_schema()
        try:
            imported = db.import_stock_announcements(notice_date, records)
        finally:
            db.close()
        summary["steps"].append({
            "name": "采集公告",
            "status": "success",
            "started_at": step_started,
            "finished_at": now_text(),
            "result": compact_result({"fetched": len(records), "imported": imported}),
        })
        summary["announcements"] = imported
        status = "success"
        message = f"公告更新完成，写入 {imported} 条"
    except Exception as exc:
        status = "failed"
        message = str(exc)
        summary["steps"].append({
            "name": "公告更新",
            "status": "failed",
            "started_at": started_at,
            "finished_at": now_text(),
            "message": message,
            "traceback": traceback.format_exc(limit=8),
        })
        if strict:
            summary["status"] = status
            summary["message"] = message
            _log_finish(db_path, "announcements_update", notice_date, status, message, summary, started_at)
            raise

    summary["status"] = status
    summary["message"] = message
    _log_finish(db_path, "announcements_update", notice_date, status, message, summary, started_at)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="新闻和公告独立更新")
    parser.add_argument("kind", nargs="?", choices=["news", "announcements", "all"], default="all")
    parser.add_argument("--date", help="更新日期，默认今天")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--news-limit", type=int, default=40, help="每个新闻源最多抓取条数")
    parser.add_argument("--announcement-limit", type=int, default=500, help="公告最多抓取条数")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.kind in ("news", "all"):
        print(run_news_update(args.date, args.db, args.news_limit, args.strict))
    if args.kind in ("announcements", "all"):
        print(run_announcements_update(args.date, args.db, args.announcement_limit, args.strict))


if __name__ == "__main__":
    main()
