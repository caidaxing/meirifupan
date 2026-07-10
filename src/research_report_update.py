"""Backfill and incrementally update individual stock research reports."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH
from research_reports import download_research_report_pdf, fetch_research_report_detail, fetch_research_report_list


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _date_range(days: int) -> tuple[str, str]:
    end = datetime.now().date()
    begin = end - timedelta(days=max(1, days) - 1)
    return begin.isoformat(), end.isoformat()


def _process_one(
    item: dict[str, Any],
    *,
    db_path: str | Path,
    data_root: Path,
) -> dict[str, Any]:
    info_code = str(item["info_code"])
    db = MarketDB(db_path)
    db.init_schema()
    result = {"info_code": info_code, "detail": False, "pdf": False, "bytes": 0, "error": None}
    try:
        detail = fetch_research_report_detail(info_code, url=item.get("source_url"))
        db.save_research_report_content(info_code, detail)
        result["detail"] = True
        pdf_url = detail.get("pdf_url")
        if not pdf_url:
            raise ValueError("research report has no PDF URL")

        report_date = str(item.get("publish_date") or "")[:10]
        target = data_root / report_date.replace("-", "/") / f"{info_code}.pdf"
        file_result = download_research_report_pdf(
            str(pdf_url),
            target,
            declared_size_kb=detail.get("declared_pdf_size_kb"),
        )
        relative_path = target.relative_to(data_root).as_posix()
        db.mark_research_report_pdf(
            info_code,
            pdf_status="downloaded",
            local_pdf_path=relative_path,
            pdf_size=file_result["pdf_size"],
            pdf_sha256=file_result["pdf_sha256"],
            pdf_error=None,
        )
        result["pdf"] = True
        result["bytes"] = file_result["pdf_size"]
    except Exception as exc:
        result["error"] = str(exc)
        if result["detail"]:
            db.mark_research_report_pdf(info_code, pdf_status="failed", pdf_error=str(exc))
        else:
            db.conn.execute(
                "update stock_research_reports set detail_status = 'failed', updated_at = current_timestamp where info_code = ?",
                (info_code,),
            )
            db.conn.commit()
    finally:
        db.close()
    return result


def run_research_report_update(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    begin_date: str | None = None,
    end_date: str | None = None,
    backfill_days: int = 30,
    data_root: str | Path | None = None,
    workers: int = 3,
    strict: bool = False,
) -> dict[str, Any]:
    """Fetch list metadata, detail pages, and PDFs for a date range."""
    if not begin_date or not end_date:
        begin_date, end_date = _date_range(backfill_days)
    data_root_path = Path(data_root) if data_root else Path(db_path).resolve().parent / "research_reports"
    data_root_path.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    summary: dict[str, Any] = {
        "begin_date": begin_date,
        "end_date": end_date,
        "steps": [],
        "failed_ids": [],
    }
    logger_db = MarketDB(db_path)
    logger_db.init_schema()
    logger_db.log_data_job("research_reports_update", end_date, "running", "开始研报更新", summary, started_at, None)
    logger_db.close()

    try:
        records, current_year = fetch_research_report_list(begin_date, end_date)
        db = MarketDB(db_path)
        db.init_schema()
        try:
            imported = db.import_research_reports(records, current_year=current_year or int(end_date[:4]))
            pending = db.get_pending_research_reports(begin_date, end_date)
        finally:
            db.close()

        summary.update({"list_count": len(records), "imported": imported, "pending": len(pending)})
        summary["steps"].append({"name": "采集研报列表", "status": "success", "result": {"fetched": len(records), "imported": imported}})
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 8))) as executor:
            futures = [
                executor.submit(_process_one, item, db_path=db_path, data_root=data_root_path)
                for item in pending
            ]
            for future in as_completed(futures):
                results.append(future.result())

        failed = [item for item in results if item.get("error")]
        summary.update({
            "detail_success": sum(1 for item in results if item["detail"]),
            "detail_failed": sum(1 for item in results if not item["detail"]),
            "pdf_success": sum(1 for item in results if item["pdf"]),
            "pdf_failed": sum(1 for item in results if not item["pdf"]),
            "pdf_bytes": sum(int(item.get("bytes") or 0) for item in results),
            "failed_ids": [item["info_code"] for item in failed],
        })
        summary["steps"].append({
            "name": "抓取研报详情和PDF",
            "status": "failed" if failed else "success",
            "result": {key: summary[key] for key in ("pending", "detail_success", "detail_failed", "pdf_success", "pdf_failed", "pdf_bytes")},
            "failed_ids": summary["failed_ids"],
        })
        status = "failed" if failed else "success"
        message = f"研报更新完成，列表 {len(records)} 条，PDF 成功 {summary['pdf_success']} 条"
    except Exception as exc:
        status = "failed"
        message = str(exc)
        summary["error"] = message
        summary["traceback"] = traceback.format_exc(limit=8)

    finished_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    db = MarketDB(db_path)
    db.init_schema()
    db.log_data_job("research_reports_update", end_date, status, message, summary, started_at, finished_at)
    db.close()
    summary.update({"status": status, "message": message})
    if strict and status != "success":
        raise RuntimeError(message)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="采集东方财富个股研报并下载PDF")
    parser.add_argument("--days", type=int, default=30, help="回补最近多少个自然日")
    parser.add_argument("--begin-date")
    parser.add_argument("--end-date")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--data-root", default=str(PROJECT_ROOT / "data" / "research_reports"))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = run_research_report_update(
        db_path=args.db,
        begin_date=args.begin_date,
        end_date=args.end_date,
        backfill_days=args.days,
        data_root=args.data_root,
        workers=args.workers,
        strict=args.strict,
    )
    print(result)


if __name__ == "__main__":
    main()
