"""Collect and persist Fuyao datasets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

from db import MarketDB
from fuyao_client import FuyaoClient


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "market_review.db"


def _chunks(values: Iterable[str], size: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for value in values:
        if not value:
            continue
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def collect_fuyao_daily(
    trade_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    client: FuyaoClient | None = None,
    include_indexes: bool = True,
    index_tags: tuple[str, ...] = ("cn_concept", "industry"),
    constituent_limit: int = 0,
) -> dict[str, int]:
    """Collect Fuyao daily datasets into SQLite."""
    client = client or FuyaoClient()
    counts = {
        "limit_up_pool": 0,
        "limit_up_ladder": 0,
        "anomaly_reasons": 0,
        "stock_snapshots": 0,
        "index_catalog": 0,
        "index_constituents": 0,
    }

    db = MarketDB(db_path)
    db.init_schema()
    try:
        limit_up_items = client.limit_up_pool(trade_date)
        counts["limit_up_pool"] = db.import_fuyao_limit_up_pool(trade_date, limit_up_items)

        ladder_payload = client.limit_up_ladder()
        counts["limit_up_ladder"] = db.import_fuyao_limit_up_ladder(ladder_payload)

        thscodes = sorted({
            str(item.get("thscode") or "").strip().upper()
            for item in limit_up_items
            if item.get("thscode")
        })
        anomaly_items: list[dict[str, Any]] = []
        for batch in _chunks(thscodes, 50):
            anomaly_items.extend(client.anomaly_analysis_stock(batch))
        counts["anomaly_reasons"] = db.import_fuyao_anomaly_reasons(trade_date, anomaly_items)

        if hasattr(client, "stock_snapshot") and thscodes:
            snapshot_items: list[dict[str, Any]] = []
            for batch in _chunks(thscodes, 50):
                snapshot_items.extend(client.stock_snapshot(batch))
            counts["stock_snapshots"] = db.import_fuyao_stock_snapshots(trade_date, snapshot_items)

        if include_indexes:
            indexed: list[str] = []
            for tag in index_tags:
                rows = client.ths_index_list(tag)
                counts["index_catalog"] += db.import_fuyao_ths_index_catalog(tag, rows)
                indexed.extend(str(row.get("thscode") or "") for row in rows if row.get("thscode"))
            for index_thscode in indexed[:constituent_limit]:
                rows = client.ths_stock_list(index_thscode)
                counts["index_constituents"] += db.import_fuyao_ths_index_constituents(index_thscode, rows)
        return counts
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="采集 Fuyao 数据并写入 SQLite")
    parser.add_argument("--date", required=True, help="交易日，格式 YYYY-MM-DD")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--skip-indexes", action="store_true", help="跳过同花顺指数目录")
    parser.add_argument("--constituent-limit", type=int, default=0, help="额外采集前 N 个指数的成分股")
    args = parser.parse_args()

    counts = collect_fuyao_daily(
        args.date,
        args.db,
        include_indexes=not args.skip_indexes,
        constituent_limit=args.constituent_limit,
    )
    print(counts)


if __name__ == "__main__":
    main()
