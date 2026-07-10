"""SQLite storage for market review data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _json_ready(value: Any) -> Any:
    """Convert pandas/numpy-ish values into JSON-safe Python values."""
    if value is None:
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def _json_text(value: Any) -> str:
    return json.dumps(_json_ready(value), ensure_ascii=False, default=str)


def _hhmm_to_hhmmss(value: Any) -> str | None:
    if value in ("", None):
        return None
    text = str(value)
    if len(text) == 5 and text[2] == ":":
        return f"{text}:00"
    return text


def _number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _research_rating_change_name(value: Any) -> str:
    return {
        0: "调高",
        1: "调低",
        2: "首次",
        3: "维持",
        4: "无",
    }.get(_int_or_none(value), "-")


class MarketDB:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        from db.schema import SCHEMA_SQL, run_migrations
        self.conn.executescript(SCHEMA_SQL)
        run_migrations(self.conn)


    def _ensure_table_columns(self, table_name: str, columns: dict[str, str]) -> None:
        existing = {
            row["name"]
            for row in self.conn.execute(f"pragma table_info({table_name})").fetchall()
        }
        for name, column_type in columns.items():
            if name not in existing:
                self.conn.execute(f"alter table {table_name} add column {name} {column_type}")

    def _ensure_daily_review_columns(self) -> None:
        """Add new report columns when upgrading an existing database."""
        self._ensure_table_columns("daily_reviews", {
            "risk_flags": "text",
            "opportunities": "text",
            "next_plan": "text",
            "markdown_path": "text",
            "raw_payload": "text",
        })

    def _ensure_data_job_columns(self) -> None:
        """Add job tracking columns when upgrading an existing database."""
        self._ensure_table_columns("data_jobs", {
            "details": "text",
            "started_at": "text",
            "finished_at": "text",
        })

    def _ensure_market_breadth_columns(self) -> None:
        """Add breadth metrics needed by review-home trend charts."""
        self._ensure_table_columns("market_breadth_daily", {
            "natural_limit_up_count": "integer",
            "natural_limit_down_count": "integer",
            "avg_change_pct": "real",
        })

    def _ensure_hot_stock_columns(self) -> None:
        """Add richer hot-rank fields for popularity emotion analysis."""
        self._ensure_table_columns("hot_stocks", {
            "amount": "real",
            "turnover_rate": "real",
            "source": "text",
            "raw_payload": "text",
        })

    def _ensure_stock_hot_rank_table(self) -> None:
        """Create multi-source hot-rank table for THS and future providers."""
        self.conn.executescript(
            """
            create table if not exists stock_hot_ranks (
                trade_date text not null,
                source text not null,
                period text not null,
                list_type text not null,
                rank_no integer not null,
                stock_code text not null,
                stock_name text,
                latest_price real,
                change_pct real,
                hot_value real,
                rank_change integer,
                concept_tags text,
                popularity_tag text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, source, period, list_type, stock_code)
            );
            create index if not exists idx_stock_hot_ranks_date_source_rank
                on stock_hot_ranks(trade_date, source, period, list_type, rank_no);
            """
        )

    def _ensure_premarket_columns(self) -> None:
        """Add columns for pre-market guide data when upgrading old databases."""
        self._ensure_table_columns("premarket_guides", {
            "review_date": "text",
            "headline": "text",
            "market_tone": "text",
            "focus_plates": "text",
            "watch_points": "text",
            "risk_points": "text",
            "catalyst_news": "text",
            "announcements": "text",
            "us_markets": "text",
            "raw_payload": "text",
        })

    def _ensure_plate_rotation_tables(self) -> None:
        """Create plate rotation tables when upgrading deployed databases."""
        self.conn.executescript(
            """
            create table if not exists plate_rotation_rank (
                trade_date text not null,
                plate_code text not null,
                plate_name text,
                rank_no integer not null,
                rate real,
                score real,
                speed real,
                money_leader real,
                money_leader_buy real,
                money_leader_sell real,
                trade_money real,
                volume_ration real,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, plate_code, source)
            );
            create table if not exists plate_rotation_trend (
                plate_code text not null,
                trade_date text not null,
                plate_name text,
                rate real,
                score real,
                speed real,
                money_leader real,
                money_leader_buy real,
                money_leader_sell real,
                trade_money real,
                volume_ration real,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(plate_code, trade_date, source)
            );
            create table if not exists plate_rotation_reasons (
                plate_code text not null,
                reason_date text not null,
                msg_id text not null,
                plate_name text,
                title text,
                boomreason text,
                is_boom integer,
                limit_up_count integer,
                strength_score real,
                leader_info text,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(plate_code, reason_date, msg_id, source)
            );
            create table if not exists plate_rotation_stocks (
                trade_date text not null,
                plate_code text not null,
                stock_code text not null,
                stock_name text,
                rank_no integer,
                rank_diff integer,
                change_pct real,
                high_change_pct real,
                open_change_pct real,
                turnover_ratio real,
                volume_ratio real,
                circulation_value real,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, plate_code, stock_code, source)
            );
            create index if not exists idx_plate_rotation_rank_date_rank
                on plate_rotation_rank(trade_date, source, rank_no);
            create index if not exists idx_plate_rotation_trend_plate_date
                on plate_rotation_trend(plate_code, source, trade_date);
            create index if not exists idx_plate_rotation_stocks_plate_date_rank
                on plate_rotation_stocks(trade_date, plate_code, source, rank_no);
            """
        )


    def import_uplimit_day(self, day_data: dict[str, Any], raw_source: str = "json") -> None:
        trade_date = day_data["date"]
        self._upsert_trade_day(trade_date)
        self._store_raw_response(
            trade_date=trade_date,
            source=raw_source,
            endpoint="uplimit_day",
            params={"date": trade_date},
            payload=day_data,
        )

        for plate in day_data.get("uplimit_reason") or []:
            plate_code = str(plate.get("plate_code") or "")
            plate_name = plate.get("plate_name")
            plate_score = plate.get("plate_score")
            if plate_code:
                self._upsert_plate(plate_code, plate_name)

            for stock in plate.get("stocks") or []:
                stock_code = str(stock.get("stock_code") or "")
                if not stock_code:
                    continue

                stock_name = stock.get("stock_name")
                self._upsert_stock(stock_code, stock_name)
                self._upsert_limit_up_event(trade_date, stock)
                if plate_code:
                    self._upsert_limit_up_plate_map(
                        trade_date=trade_date,
                        stock_code=stock_code,
                        plate_code=plate_code,
                        plate_name=plate_name,
                        plate_score=plate_score,
                        stock_reason=stock.get("reason"),
                    )

        for rank_no, item in enumerate(day_data.get("uplimit_hot") or [], start=1):
            parsed = self._parse_hot_plate(item)
            if parsed is None:
                continue
            plate_name, plate_code, score = parsed
            self._upsert_plate(plate_code, plate_name)
            self.conn.execute(
                """
                insert into plate_hot_rank(trade_date, plate_code, plate_name, score, rank_no, source)
                values(?, ?, ?, ?, ?, 'uplimit_hot')
                on conflict(trade_date, plate_code, source) do update set
                    plate_name = excluded.plate_name,
                    score = excluded.score,
                    rank_no = excluded.rank_no,
                    updated_at = current_timestamp
                """,
                (trade_date, plate_code, plate_name, score, rank_no),
            )

        for rank_no, item in enumerate(day_data.get("plate_rank") or [], start=1):
            plate_code = str(item.get("plate_code") or item.get("code") or "")
            plate_name = item.get("plate_name") or item.get("name")
            if not plate_code:
                continue
            self._upsert_plate(plate_code, plate_name)
            score = item.get("plate_score") or item.get("score") or item.get("amount")
            self.conn.execute(
                """
                insert into plate_daily(trade_date, plate_code, plate_name, rank_no, score, raw_payload)
                values(?, ?, ?, ?, ?, ?)
                on conflict(trade_date, plate_code) do update set
                    plate_name = excluded.plate_name,
                    rank_no = excluded.rank_no,
                    score = excluded.score,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (trade_date, plate_code, plate_name, rank_no, score, json.dumps(item, ensure_ascii=False)),
            )

        self.conn.commit()

    def import_plate_rotation_data(self, data: dict[str, Any], raw_source: str = "quant_yjj") -> dict[str, int]:
        """Import normalized plate rotation data."""
        counts = {
            "rank": 0,
            "trend": 0,
            "reasons": 0,
            "stocks": 0,
        }

        for trade_date in data.get("dates") or []:
            self._upsert_trade_day(str(trade_date))

        rank_by_date = data.get("ranks") or {}
        for trade_date, rows in rank_by_date.items():
            self._upsert_trade_day(str(trade_date))
            self._store_raw_response(
                trade_date=str(trade_date),
                source=raw_source,
                endpoint="plate_rotation_rank",
                params={"date": trade_date},
                payload=rows,
            )
            for fallback_rank, item in enumerate(rows or [], start=1):
                plate_code = str(item.get("plate_code") or "")
                if not plate_code:
                    continue
                plate_name = item.get("plate_name")
                self._upsert_plate(plate_code, plate_name)
                self.conn.execute(
                    """
                    insert into plate_rotation_rank(
                        trade_date, plate_code, plate_name, rank_no, rate, score, speed,
                        money_leader, money_leader_buy, money_leader_sell,
                        trade_money, volume_ration, source, raw_payload
                    )
                    values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(trade_date, plate_code, source) do update set
                        plate_name = excluded.plate_name,
                        rank_no = excluded.rank_no,
                        rate = excluded.rate,
                        score = excluded.score,
                        speed = excluded.speed,
                        money_leader = excluded.money_leader,
                        money_leader_buy = excluded.money_leader_buy,
                        money_leader_sell = excluded.money_leader_sell,
                        trade_money = excluded.trade_money,
                        volume_ration = excluded.volume_ration,
                        raw_payload = excluded.raw_payload,
                        updated_at = current_timestamp
                    """,
                    (
                        str(trade_date),
                        plate_code,
                        plate_name,
                        item.get("rank_no") or item.get("rank") or fallback_rank,
                        item.get("rate"),
                        item.get("score") or item.get("sum_score"),
                        item.get("speed"),
                        item.get("money_leader") or item.get("sum_leader_money"),
                        item.get("money_leader_buy"),
                        item.get("money_leader_sell"),
                        item.get("trade_money"),
                        item.get("volume_ration") or item.get("volume_ratio"),
                        raw_source,
                        _json_text(item),
                    ),
                )
                counts["rank"] += 1

        for plate_code, rows in (data.get("trends") or {}).items():
            for item in rows or []:
                trade_date = str(item.get("date1") or item.get("trade_date") or "")
                code = str(item.get("plate_code") or plate_code or "")
                if not code or not trade_date:
                    continue
                plate_name = item.get("plate_name")
                self._upsert_trade_day(trade_date)
                self._upsert_plate(code, plate_name)
                self.conn.execute(
                    """
                    insert into plate_rotation_trend(
                        plate_code, trade_date, plate_name, rate, score, speed,
                        money_leader, money_leader_buy, money_leader_sell,
                        trade_money, volume_ration, source, raw_payload
                    )
                    values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(plate_code, trade_date, source) do update set
                        plate_name = excluded.plate_name,
                        rate = excluded.rate,
                        score = excluded.score,
                        speed = excluded.speed,
                        money_leader = excluded.money_leader,
                        money_leader_buy = excluded.money_leader_buy,
                        money_leader_sell = excluded.money_leader_sell,
                        trade_money = excluded.trade_money,
                        volume_ration = excluded.volume_ration,
                        raw_payload = excluded.raw_payload,
                        updated_at = current_timestamp
                    """,
                    (
                        code,
                        trade_date,
                        plate_name,
                        item.get("rate"),
                        item.get("score"),
                        item.get("speed"),
                        item.get("money_leader"),
                        item.get("money_leader_buy"),
                        item.get("money_leader_sell"),
                        item.get("trade_money"),
                        item.get("volume_ration") or item.get("volume_ratio"),
                        raw_source,
                        _json_text(item),
                    ),
                )
                counts["trend"] += 1

        for plate_code, rows in (data.get("reasons") or {}).items():
            for item in rows or []:
                reason_date = str(item.get("date") or item.get("reason_date") or "")
                code = str(item.get("plate_code") or plate_code or "")
                if not code or not reason_date:
                    continue
                msg_id = str(item.get("newid") or item.get("msg_id") or item.get("title") or reason_date)
                self.conn.execute(
                    """
                    insert into plate_rotation_reasons(
                        plate_code, reason_date, msg_id, plate_name, title, boomreason,
                        is_boom, limit_up_count, strength_score, leader_info,
                        source, raw_payload
                    )
                    values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(plate_code, reason_date, msg_id, source) do update set
                        plate_name = excluded.plate_name,
                        title = excluded.title,
                        boomreason = excluded.boomreason,
                        is_boom = excluded.is_boom,
                        limit_up_count = excluded.limit_up_count,
                        strength_score = excluded.strength_score,
                        leader_info = excluded.leader_info,
                        raw_payload = excluded.raw_payload,
                        updated_at = current_timestamp
                    """,
                    (
                        code,
                        reason_date,
                        msg_id,
                        item.get("plate_name"),
                        item.get("title"),
                        item.get("boomreason"),
                        item.get("isboom") if item.get("isboom") is not None else item.get("is_boom"),
                        item.get("ztnum") if item.get("ztnum") is not None else item.get("limit_up_count"),
                        item.get("qd") if item.get("qd") is not None else item.get("strength_score"),
                        item.get("lzinfo") if item.get("lzinfo") is not None else item.get("leader_info"),
                        raw_source,
                        _json_text(item),
                    ),
                )
                counts["reasons"] += 1

        default_stock_date = str(data.get("date") or ((data.get("dates") or [None])[-1] or ""))
        for plate_code, rows in (data.get("stocks") or {}).items():
            for fallback_rank, item in enumerate(rows or [], start=1):
                trade_date = str(item.get("date1") or item.get("trade_date") or default_stock_date)
                code = str(item.get("plate_code") or plate_code or "")
                stock_code = str(item.get("stock_code") or "")
                if not trade_date or not code or not stock_code:
                    continue
                stock_name = item.get("stock_name")
                self._upsert_trade_day(trade_date)
                self._upsert_stock(stock_code, stock_name)
                self._upsert_plate(code, item.get("plate_name"))
                self.conn.execute(
                    """
                    insert into plate_rotation_stocks(
                        trade_date, plate_code, stock_code, stock_name, rank_no, rank_diff,
                        change_pct, high_change_pct, open_change_pct, turnover_ratio,
                        volume_ratio, circulation_value, source, raw_payload
                    )
                    values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(trade_date, plate_code, stock_code, source) do update set
                        stock_name = excluded.stock_name,
                        rank_no = excluded.rank_no,
                        rank_diff = excluded.rank_diff,
                        change_pct = excluded.change_pct,
                        high_change_pct = excluded.high_change_pct,
                        open_change_pct = excluded.open_change_pct,
                        turnover_ratio = excluded.turnover_ratio,
                        volume_ratio = excluded.volume_ratio,
                        circulation_value = excluded.circulation_value,
                        raw_payload = excluded.raw_payload,
                        updated_at = current_timestamp
                    """,
                    (
                        trade_date,
                        code,
                        stock_code,
                        stock_name,
                        item.get("rank_no") or item.get("rank") or fallback_rank,
                        item.get("rank_diff"),
                        item.get("px_change_rate") if item.get("px_change_rate") is not None else item.get("change_pct"),
                        item.get("high_change") if item.get("high_change") is not None else item.get("high_change_pct"),
                        item.get("open_change") if item.get("open_change") is not None else item.get("open_change_pct"),
                        item.get("turnover_ratio"),
                        item.get("vol_ratio") if item.get("vol_ratio") is not None else item.get("volume_ratio"),
                        item.get("circulation_value"),
                        raw_source,
                        _json_text(item),
                    ),
                )
                counts["stocks"] += 1

        self.conn.commit()
        return counts

    def import_fuyao_limit_up_pool(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """Import Fuyao limit-up pool and enrich the main limit-up event table."""
        self._upsert_trade_day(trade_date)
        count = 0
        for item in records:
            ticker = str(item.get("ticker") or "").strip()
            if not ticker:
                continue
            stock_name = item.get("name") or item.get("stock_name")
            reason = item.get("limit_up_reason")
            limit_up_time = _hhmm_to_hhmmss(item.get("limit_up_time"))
            self._upsert_stock(ticker, stock_name)
            self.conn.execute(
                """
                insert into fuyao_limit_up_pool(
                    trade_date, ticker, thscode, stock_name, last_price,
                    price_change_ratio_pct, limit_up_reason, continue_day_text,
                    continue_day_cnt, limit_up_time, seal_money, max_seal_money,
                    is_new, is_st, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, ticker) do update set
                    thscode = excluded.thscode,
                    stock_name = excluded.stock_name,
                    last_price = excluded.last_price,
                    price_change_ratio_pct = excluded.price_change_ratio_pct,
                    limit_up_reason = excluded.limit_up_reason,
                    continue_day_text = excluded.continue_day_text,
                    continue_day_cnt = excluded.continue_day_cnt,
                    limit_up_time = excluded.limit_up_time,
                    seal_money = excluded.seal_money,
                    max_seal_money = excluded.max_seal_money,
                    is_new = excluded.is_new,
                    is_st = excluded.is_st,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    ticker,
                    item.get("thscode"),
                    stock_name,
                    item.get("last_price"),
                    item.get("price_change_ratio_pct"),
                    reason,
                    item.get("continue_day_text"),
                    item.get("continue_day_cnt"),
                    limit_up_time,
                    item.get("seal_money"),
                    item.get("max_seal_money"),
                    int(bool(item.get("is_new"))) if item.get("is_new") is not None else None,
                    int(bool(item.get("is_st"))) if item.get("is_st") is not None else None,
                    _json_text(item),
                ),
            )
            self.conn.execute(
                """
                update limit_up_events
                set
                    stock_name = coalesce(?, stock_name),
                    stock_price = coalesce(?, stock_price),
                    up_limit_desc = coalesce(?, up_limit_desc),
                    up_limit_keep_times = coalesce(?, up_limit_keep_times),
                    up_limit_time = coalesce(?, up_limit_time),
                    reason = coalesce(?, reason),
                    fengdan_money = coalesce(?, fengdan_money),
                    updated_at = current_timestamp
                where trade_date = ? and stock_code = ?
                """,
                (
                    stock_name,
                    item.get("last_price"),
                    item.get("continue_day_text"),
                    item.get("continue_day_cnt"),
                    limit_up_time,
                    reason,
                    item.get("seal_money"),
                    trade_date,
                    ticker,
                ),
            )
            if reason:
                self.conn.execute(
                    """
                    update limit_up_plate_map
                    set stock_reason = ?, updated_at = current_timestamp
                    where trade_date = ? and stock_code = ?
                    """,
                    (reason, trade_date, ticker),
                )
            count += 1
        self._store_raw_response(
            trade_date=trade_date,
            source="fuyao",
            endpoint="limit_up_pool",
            params={"date": trade_date},
            payload={"item": records},
        )
        self.conn.commit()
        return count

    def import_fuyao_limit_up_ladder(self, payload: dict[str, Any]) -> int:
        """Import Fuyao limit-up ladder matrix."""
        count = 0
        for day in payload.get("item") or []:
            raw_date = str(day.get("date") or "")
            trade_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
            if not trade_date:
                continue
            self._upsert_trade_day(trade_date)
            for board_key, stocks in (day.get("boards") or {}).items():
                for stock in stocks or []:
                    ticker = str(stock.get("ticker") or "").strip()
                    if not ticker:
                        continue
                    stock_name = stock.get("name")
                    self._upsert_stock(ticker, stock_name)
                    self.conn.execute(
                        """
                        insert into fuyao_limit_up_ladder(
                            trade_date, board_key, board_num, ticker, thscode, stock_name,
                            seal_nextday, sign_level, raw_payload
                        )
                        values(?, ?, ?, ?, ?, ?, ?, ?, ?)
                        on conflict(trade_date, board_key, ticker) do update set
                            board_num = excluded.board_num,
                            thscode = excluded.thscode,
                            stock_name = excluded.stock_name,
                            seal_nextday = excluded.seal_nextday,
                            sign_level = excluded.sign_level,
                            raw_payload = excluded.raw_payload,
                            updated_at = current_timestamp
                        """,
                        (
                            trade_date,
                            board_key,
                            stock.get("board_num"),
                            ticker,
                            stock.get("thscode"),
                            stock_name,
                            int(bool(stock.get("seal_nextday"))) if stock.get("seal_nextday") is not None else None,
                            stock.get("sign_level"),
                            _json_text(stock),
                        ),
                    )
                    count += 1
        self._store_raw_response(
            trade_date=None,
            source="fuyao",
            endpoint="limit_up_ladder",
            params={},
            payload=payload,
        )
        self.conn.commit()
        return count

    def import_fuyao_anomaly_reasons(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        self._upsert_trade_day(trade_date)
        count = 0
        for item in records:
            thscode = str(item.get("thscode") or "").strip()
            if not thscode:
                continue
            ticker = thscode.split(".", 1)[0]
            keywords = item.get("keyword_list")
            self._upsert_stock(ticker, item.get("stock_name"))
            self.conn.execute(
                """
                insert into fuyao_anomaly_reasons(
                    trade_date, thscode, ticker, stock_name, tag_name,
                    analysis_content, keyword_list, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, thscode, tag_name, analysis_content) do update set
                    ticker = excluded.ticker,
                    stock_name = excluded.stock_name,
                    keyword_list = excluded.keyword_list,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    thscode,
                    ticker,
                    item.get("stock_name"),
                    item.get("tag_name") or "",
                    item.get("analysis_content") or "",
                    _json_text(keywords if keywords is not None else []),
                    _json_text(item),
                ),
            )
            count += 1
        self._store_raw_response(
            trade_date=trade_date,
            source="fuyao",
            endpoint="anomaly_analysis_stock",
            params={"date": trade_date},
            payload={"item": records},
        )
        self.conn.commit()
        return count

    def import_fuyao_ths_index_catalog(self, tag: str, records: list[dict[str, Any]]) -> int:
        count = 0
        for item in records:
            thscode = str(item.get("thscode") or "").strip()
            if not thscode:
                continue
            self._upsert_plate(thscode, item.get("name"))
            self.conn.execute(
                """
                insert into fuyao_ths_index_catalog(tag, thscode, index_name, raw_payload)
                values(?, ?, ?, ?)
                on conflict(tag, thscode) do update set
                    index_name = excluded.index_name,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (tag, thscode, item.get("name"), _json_text(item)),
            )
            count += 1
        self.conn.commit()
        return count

    def import_fuyao_ths_index_constituents(self, index_thscode: str, records: list[dict[str, Any]]) -> int:
        count = 0
        for item in records:
            stock_thscode = str(item.get("thscode") or "").strip()
            if not stock_thscode:
                continue
            ticker = str(item.get("ticker") or stock_thscode.split(".", 1)[0])
            stock_name = item.get("name")
            self._upsert_stock(ticker, stock_name)
            self.conn.execute(
                """
                insert into fuyao_ths_index_constituents(
                    index_thscode, stock_thscode, ticker, stock_name, raw_payload
                )
                values(?, ?, ?, ?, ?)
                on conflict(index_thscode, stock_thscode) do update set
                    ticker = excluded.ticker,
                    stock_name = excluded.stock_name,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (index_thscode, stock_thscode, ticker, stock_name, _json_text(item)),
            )
            count += 1
        self.conn.commit()
        return count

    def import_fuyao_stock_snapshots(self, snapshot_date: str, records: list[dict[str, Any]]) -> int:
        self._upsert_trade_day(snapshot_date)
        count = 0
        for item in records:
            thscode = str(item.get("thscode") or "").strip()
            if not thscode:
                continue
            ticker = str(item.get("ticker") or thscode.split(".", 1)[0])
            self.conn.execute(
                """
                insert into fuyao_stock_snapshots(
                    snapshot_date, thscode, ticker, last_price, price_change,
                    price_change_ratio_pct, open_price, high_price, low_price,
                    prev_price, volume, turnover, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(snapshot_date, thscode) do update set
                    ticker = excluded.ticker,
                    last_price = excluded.last_price,
                    price_change = excluded.price_change,
                    price_change_ratio_pct = excluded.price_change_ratio_pct,
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    prev_price = excluded.prev_price,
                    volume = excluded.volume,
                    turnover = excluded.turnover,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    snapshot_date,
                    thscode,
                    ticker,
                    item.get("last_price"),
                    item.get("price_change"),
                    item.get("price_change_ratio_pct"),
                    item.get("open_price"),
                    item.get("high_price"),
                    item.get("low_price"),
                    item.get("prev_price"),
                    item.get("volume"),
                    item.get("turnover"),
                    _json_text(item),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def _upsert_trade_day(self, trade_date: str) -> None:
        self.conn.execute(
            """
            insert into trade_calendar(trade_date, is_trade_day)
            values(?, 1)
            on conflict(trade_date) do update set
                is_trade_day = excluded.is_trade_day,
                updated_at = current_timestamp
            """,
            (trade_date,),
        )

    def _upsert_stock(self, stock_code: str, stock_name: str | None) -> None:
        self.conn.execute(
            """
            insert into stocks(stock_code, stock_name)
            values(?, ?)
            on conflict(stock_code) do update set
                stock_name = coalesce(excluded.stock_name, stocks.stock_name),
                updated_at = current_timestamp
            """,
            (stock_code, stock_name),
        )

    def _upsert_plate(self, plate_code: str, plate_name: str | None) -> None:
        self.conn.execute(
            """
            insert into plates(plate_code, plate_name)
            values(?, ?)
            on conflict(plate_code) do update set
                plate_name = coalesce(excluded.plate_name, plates.plate_name),
                updated_at = current_timestamp
            """,
            (plate_code, plate_name),
        )

    def _upsert_limit_up_event(self, trade_date: str, stock: dict[str, Any]) -> None:
        # Build tags JSON: accept list directly, or split reason by "+"
        tags_raw = stock.get("tags")
        if isinstance(tags_raw, list):
            tags_json = json.dumps(tags_raw, ensure_ascii=False)
        elif isinstance(tags_raw, str) and tags_raw.startswith("["):
            tags_json = tags_raw  # already JSON
        else:
            reason = stock.get("reason") or ""
            tags_json = json.dumps([t.strip() for t in reason.split("+") if t.strip()], ensure_ascii=False) if reason else None

        self.conn.execute(
            """
            insert into limit_up_events(
                trade_date, stock_code, stock_name, stock_price, up_limit_desc,
                up_limit_keep_times, up_limit_type, up_limit_time, reason, tags,
                fengdan_money, fengdan_rate, turnover_rate, circulation_value,
                market_type, amount
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(trade_date, stock_code) do update set
                stock_name = excluded.stock_name,
                stock_price = coalesce(excluded.stock_price, limit_up_events.stock_price),
                up_limit_desc = coalesce(excluded.up_limit_desc, limit_up_events.up_limit_desc),
                up_limit_keep_times = coalesce(excluded.up_limit_keep_times, limit_up_events.up_limit_keep_times),
                up_limit_type = coalesce(excluded.up_limit_type, limit_up_events.up_limit_type),
                up_limit_time = coalesce(excluded.up_limit_time, limit_up_events.up_limit_time),
                reason = coalesce(excluded.reason, limit_up_events.reason),
                tags = coalesce(excluded.tags, limit_up_events.tags),
                fengdan_money = coalesce(excluded.fengdan_money, limit_up_events.fengdan_money),
                fengdan_rate = coalesce(excluded.fengdan_rate, limit_up_events.fengdan_rate),
                turnover_rate = coalesce(excluded.turnover_rate, limit_up_events.turnover_rate),
                circulation_value = coalesce(excluded.circulation_value, limit_up_events.circulation_value),
                market_type = coalesce(excluded.market_type, limit_up_events.market_type),
                amount = coalesce(excluded.amount, limit_up_events.amount),
                updated_at = current_timestamp
            """,
            (
                trade_date,
                str(stock.get("stock_code") or ""),
                stock.get("stock_name"),
                stock.get("stock_price"),
                stock.get("up_limit_desc"),
                stock.get("up_limit_keep_times"),
                stock.get("up_limit_type"),
                stock.get("up_limit_time"),
                stock.get("reason"),
                tags_json,
                stock.get("fengdan_money"),
                stock.get("fengdan_rate"),
                stock.get("turnover_ration_real"),
                stock.get("actualcirculation_value"),
                stock.get("market_type"),
                stock.get("amount"),
            ),
        )

    def _upsert_limit_up_plate_map(
        self,
        trade_date: str,
        stock_code: str,
        plate_code: str,
        plate_name: str | None,
        plate_score: Any,
        stock_reason: str | None,
    ) -> None:
        self.conn.execute(
            """
            insert into limit_up_plate_map(
                trade_date, stock_code, plate_code, plate_name, plate_score, stock_reason
            )
            values(?, ?, ?, ?, ?, ?)
            on conflict(trade_date, stock_code, plate_code) do update set
                plate_name = excluded.plate_name,
                plate_score = excluded.plate_score,
                stock_reason = excluded.stock_reason,
                updated_at = current_timestamp
            """,
            (trade_date, stock_code, plate_code, plate_name, plate_score, stock_reason),
        )

    def _store_raw_response(
        self,
        trade_date: str,
        source: str,
        endpoint: str,
        params: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        params_text = json.dumps(params, sort_keys=True, ensure_ascii=False)
        params_hash = hashlib.sha256(params_text.encode("utf-8")).hexdigest()
        payload_text = _json_text(payload)
        self.conn.execute(
            """
            insert into raw_api_responses(trade_date, source, endpoint, params_hash, payload)
            values(?, ?, ?, ?, ?)
            on conflict(trade_date, source, endpoint, params_hash) do update set
                payload = excluded.payload
            """,
            (trade_date, source, endpoint, params_hash, payload_text),
        )

    def import_index_daily(self, trade_date: str, indices: list[dict[str, Any]], raw_source: str = "api") -> int:
        """Import market index daily data. Returns number of rows upserted."""
        count = 0
        for idx in indices:
            index_code = idx.get("code") or idx.get("display_code", "")
            if not index_code:
                continue
            index_name = idx.get("name") or idx.get("display_name")
            close_price = idx.get("last_px")
            change_pct = idx.get("px_change_rate")
            amount = idx.get("amount")
            if amount is None:
                amount = idx.get("volume")
            self.conn.execute(
                """
                insert into market_index_daily(trade_date, index_code, index_name, close_price, change_pct, amount, raw_payload)
                values(?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, index_code) do update set
                    index_name = excluded.index_name,
                    close_price = excluded.close_price,
                    change_pct = excluded.change_pct,
                    amount = excluded.amount,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    index_code,
                    index_name,
                    close_price,
                    change_pct,
                    amount,
                    _json_text(idx),
                ),
            )
            count += 1
        self._store_raw_response(
            trade_date=trade_date,
            source=raw_source,
            endpoint="index_trends",
            params={"date": trade_date},
            payload={"indices": indices},
        )
        self.conn.commit()
        return count

    def import_sentiment_daily(self, kline_data: list[dict[str, Any]], period: int = 0, raw_source: str = "api") -> int:
        """Import sentiment kline data into sentiment_daily table. Returns number of rows upserted.

        The API returns OHLC-style sentiment index data:
        - p_open, p_high, p_low, p_close: sentiment index OHLC
        - amount: trading amount
        - date: trade date

        We also auto-populate limit_up_count from limit_up_events table
        if the data is available.
        """
        count = 0
        for item in kline_data:
            trade_date = item.get("date")
            if not trade_date:
                continue
            self._upsert_trade_day(trade_date)

            # Try to get limit_up_count from limit_up_events if not in API response
            limit_up_count = item.get("limit_up_count")
            if limit_up_count is None:
                row = self.conn.execute(
                    "select count(*) as cnt from limit_up_events where trade_date = ?",
                    (trade_date,),
                ).fetchone()
                if row:
                    limit_up_count = row["cnt"]

            self.conn.execute(
                """
                insert into sentiment_daily(trade_date, period, limit_up_count, limit_down_count, highest_board, raw_payload)
                values(?, ?, ?, ?, ?, ?)
                on conflict(trade_date, period) do update set
                    limit_up_count = coalesce(excluded.limit_up_count, sentiment_daily.limit_up_count),
                    limit_down_count = coalesce(excluded.limit_down_count, sentiment_daily.limit_down_count),
                    highest_board = coalesce(excluded.highest_board, sentiment_daily.highest_board),
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    period,
                    limit_up_count,
                    item.get("limit_down_count"),
                    item.get("highest_board"),
                    _json_text(item),
                ),
            )
            count += 1

        # Store raw response for the first date in the batch
        if kline_data:
            first_date = kline_data[0].get("date", "")
            self._store_raw_response(
                trade_date=first_date,
                source=raw_source,
                endpoint="sentiment_kline",
                params={"period": period},
                payload={"kline": kline_data},
            )
        self.conn.commit()
        return count

    def import_market_breadth(self, trade_date: str, snapshot: dict[str, Any]) -> int:
        """导入全市场涨跌家数和成交额快照。"""
        self._upsert_trade_day(trade_date)
        self.conn.execute(
            """
            insert into market_breadth_daily(
                trade_date, total_count, up_count, down_count, flat_count,
                limit_up_count, limit_down_count, natural_limit_up_count,
                natural_limit_down_count, avg_change_pct, amount, raw_payload
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(trade_date) do update set
                total_count = coalesce(excluded.total_count, market_breadth_daily.total_count),
                up_count = coalesce(excluded.up_count, market_breadth_daily.up_count),
                down_count = coalesce(excluded.down_count, market_breadth_daily.down_count),
                flat_count = coalesce(excluded.flat_count, market_breadth_daily.flat_count),
                limit_up_count = coalesce(excluded.limit_up_count, market_breadth_daily.limit_up_count),
                limit_down_count = coalesce(excluded.limit_down_count, market_breadth_daily.limit_down_count),
                natural_limit_up_count = coalesce(excluded.natural_limit_up_count, market_breadth_daily.natural_limit_up_count),
                natural_limit_down_count = coalesce(excluded.natural_limit_down_count, market_breadth_daily.natural_limit_down_count),
                avg_change_pct = coalesce(excluded.avg_change_pct, market_breadth_daily.avg_change_pct),
                amount = coalesce(excluded.amount, market_breadth_daily.amount),
                raw_payload = excluded.raw_payload,
                updated_at = current_timestamp
            """,
            (
                trade_date,
                snapshot.get("total_count"),
                snapshot.get("up_count"),
                snapshot.get("down_count"),
                snapshot.get("flat_count"),
                snapshot.get("limit_up_count"),
                snapshot.get("limit_down_count"),
                snapshot.get("natural_limit_up_count"),
                snapshot.get("natural_limit_down_count"),
                snapshot.get("avg_change_pct"),
                snapshot.get("amount"),
                _json_text(snapshot),
            ),
        )
        self.conn.commit()
        return 1

    def import_limit_down_events(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """导入跌停池数据。"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            stock_code = str(r.get("stock_code") or "")
            if not stock_code:
                continue
            self._upsert_stock(stock_code, r.get("stock_name"))
            self.conn.execute(
                """
                insert into limit_down_events(
                    trade_date, stock_code, stock_name, latest_price, change_pct,
                    amount, circulation_value, total_market_cap, turnover_rate,
                    seal_amount, last_limit_down_time, limit_down_days,
                    open_count, industry, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, stock_code) do update set
                    stock_name = excluded.stock_name,
                    latest_price = excluded.latest_price,
                    change_pct = excluded.change_pct,
                    amount = excluded.amount,
                    circulation_value = excluded.circulation_value,
                    total_market_cap = excluded.total_market_cap,
                    turnover_rate = excluded.turnover_rate,
                    seal_amount = excluded.seal_amount,
                    last_limit_down_time = excluded.last_limit_down_time,
                    limit_down_days = excluded.limit_down_days,
                    open_count = excluded.open_count,
                    industry = excluded.industry,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    stock_code,
                    r.get("stock_name"),
                    r.get("latest_price"),
                    r.get("change_pct"),
                    r.get("amount"),
                    r.get("circulation_value"),
                    r.get("total_market_cap"),
                    r.get("turnover_rate"),
                    r.get("seal_amount"),
                    r.get("last_limit_down_time"),
                    r.get("limit_down_days"),
                    r.get("open_count"),
                    r.get("industry"),
                    _json_text(r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_broken_limit_up_events(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """导入炸板池数据。"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            stock_code = str(r.get("stock_code") or "")
            if not stock_code:
                continue
            self._upsert_stock(stock_code, r.get("stock_name"))
            self.conn.execute(
                """
                insert into broken_limit_up_events(
                    trade_date, stock_code, stock_name, latest_price, change_pct,
                    limit_up_price, amount, circulation_value, total_market_cap,
                    turnover_rate, first_limit_up_time, open_count,
                    limit_up_stat, amplitude, industry, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, stock_code) do update set
                    stock_name = excluded.stock_name,
                    latest_price = excluded.latest_price,
                    change_pct = excluded.change_pct,
                    limit_up_price = excluded.limit_up_price,
                    amount = excluded.amount,
                    circulation_value = excluded.circulation_value,
                    total_market_cap = excluded.total_market_cap,
                    turnover_rate = excluded.turnover_rate,
                    first_limit_up_time = excluded.first_limit_up_time,
                    open_count = excluded.open_count,
                    limit_up_stat = excluded.limit_up_stat,
                    amplitude = excluded.amplitude,
                    industry = excluded.industry,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    stock_code,
                    r.get("stock_name"),
                    r.get("latest_price"),
                    r.get("change_pct"),
                    r.get("limit_up_price"),
                    r.get("amount"),
                    r.get("circulation_value"),
                    r.get("total_market_cap"),
                    r.get("turnover_rate"),
                    r.get("first_limit_up_time"),
                    r.get("open_count"),
                    r.get("limit_up_stat"),
                    r.get("amplitude"),
                    r.get("industry"),
                    _json_text(r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_lhb_daily(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """导入龙虎榜每日明细。"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            stock_code = str(r.get("stock_code") or "")
            reason = r.get("reason") or ""
            if not stock_code:
                continue
            self._upsert_stock(stock_code, r.get("stock_name"))
            self.conn.execute(
                """
                insert into lhb_daily(
                    trade_date, stock_code, stock_name, reason,
                    buy_amount, sell_amount, net_buy_amount, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, stock_code, reason) do update set
                    stock_name = excluded.stock_name,
                    buy_amount = excluded.buy_amount,
                    sell_amount = excluded.sell_amount,
                    net_buy_amount = excluded.net_buy_amount,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    stock_code,
                    r.get("stock_name"),
                    reason,
                    r.get("buy_amount"),
                    r.get("sell_amount"),
                    r.get("net_buy_amount"),
                    _json_text(r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_market_hot_daily(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """导入市场热点列表。"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            item_key = str(r.get("item_key") or r.get("item_name") or "")
            if not item_key:
                continue
            self.conn.execute(
                """
                insert into market_hot_daily(trade_date, item_key, item_name, score, rank_no, raw_payload)
                values(?, ?, ?, ?, ?, ?)
                on conflict(trade_date, item_key) do update set
                    item_name = excluded.item_name,
                    score = excluded.score,
                    rank_no = excluded.rank_no,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    item_key,
                    r.get("item_name"),
                    r.get("score"),
                    r.get("rank_no"),
                    _json_text(r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_movement_alerts(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """导入盘中异动提醒。"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            alert_time = str(r.get("alert_time") or "")
            stock_code = str(r.get("stock_code") or "")
            if not alert_time or not stock_code:
                continue
            self._upsert_stock(stock_code, r.get("stock_name"))
            raw_text = _json_text(r)
            raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            self.conn.execute(
                """
                insert into movement_alerts(
                    trade_date, alert_time, stock_code, stock_name, alert_type,
                    alert_text, price, change_pct, raw_hash, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, alert_time, stock_code, raw_hash) do nothing
                """,
                (
                    trade_date,
                    alert_time,
                    stock_code,
                    r.get("stock_name"),
                    r.get("alert_type"),
                    r.get("alert_text"),
                    r.get("price"),
                    r.get("change_pct"),
                    raw_hash,
                    raw_text,
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_stock_kline_daily(self, stock_code: str, records: list[dict[str, Any]]) -> int:
        """导入个股日 K 数据。"""
        stock_code = str(stock_code or "")
        if not stock_code:
            return 0
        count = 0
        for r in records:
            trade_date = r.get("trade_date")
            if not trade_date:
                continue
            self._upsert_trade_day(str(trade_date))
            self.conn.execute(
                """
                insert into stock_kline_daily(
                    stock_code, trade_date, open_price, high_price, low_price,
                    close_price, volume, amount, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(stock_code, trade_date) do update set
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    stock_code,
                    str(trade_date),
                    r.get("open_price"),
                    r.get("high_price"),
                    r.get("low_price"),
                    r.get("close_price"),
                    r.get("volume"),
                    r.get("amount"),
                    _json_text(r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_daily_review(self, review: dict[str, Any]) -> int:
        """导入自动复盘结论。"""
        trade_date = str(review.get("trade_date") or "")
        if not trade_date:
            return 0
        self._upsert_trade_day(trade_date)
        self.conn.execute(
            """
            insert into daily_reviews(
                trade_date, limit_up_stock_count, limit_up_plate_count,
                first_board_count, multi_board_count, highest_board,
                strongest_plates, core_stocks, risk_flags, opportunities,
                next_plan, markdown_path, raw_payload, summary
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(trade_date) do update set
                limit_up_stock_count = excluded.limit_up_stock_count,
                limit_up_plate_count = excluded.limit_up_plate_count,
                first_board_count = excluded.first_board_count,
                multi_board_count = excluded.multi_board_count,
                highest_board = excluded.highest_board,
                strongest_plates = excluded.strongest_plates,
                core_stocks = excluded.core_stocks,
                risk_flags = excluded.risk_flags,
                opportunities = excluded.opportunities,
                next_plan = excluded.next_plan,
                markdown_path = excluded.markdown_path,
                raw_payload = excluded.raw_payload,
                summary = excluded.summary,
                updated_at = current_timestamp
            """,
            (
                trade_date,
                review.get("limit_up_stock_count"),
                review.get("limit_up_plate_count"),
                review.get("first_board_count"),
                review.get("multi_board_count"),
                review.get("highest_board"),
                _json_text(review.get("strongest_plates") or []),
                _json_text(review.get("core_stocks") or []),
                _json_text(review.get("risk_flags") or []),
                _json_text(review.get("opportunities") or []),
                _json_text(review.get("next_plan") or []),
                review.get("markdown_path"),
                _json_text(review),
                review.get("summary"),
            ),
        )
        self.conn.commit()
        return 1

    def import_hot_stocks(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """导入热门股票人气榜数据"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            stock_code = r.get("stock_code", "")
            if not stock_code:
                continue
            self._upsert_stock(stock_code, r.get("stock_name"))
            self.conn.execute(
                """
                insert into hot_stocks(
                    trade_date, rank_no, stock_code, stock_name, latest_price,
                    change_pct, change_amount, amount, turnover_rate, source, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, stock_code) do update set
                    rank_no = excluded.rank_no,
                    stock_name = excluded.stock_name,
                    latest_price = excluded.latest_price,
                    change_pct = excluded.change_pct,
                    change_amount = excluded.change_amount,
                    amount = coalesce(excluded.amount, hot_stocks.amount),
                    turnover_rate = coalesce(excluded.turnover_rate, hot_stocks.turnover_rate),
                    source = coalesce(excluded.source, hot_stocks.source),
                    raw_payload = coalesce(excluded.raw_payload, hot_stocks.raw_payload),
                    updated_at = current_timestamp
                """,
                (trade_date, r["rank_no"], stock_code, r.get("stock_name"),
                 r.get("latest_price"), r.get("change_pct"), r.get("change_amount"),
                 r.get("amount"), r.get("turnover_rate"), r.get("source"), _json_text(r.get("raw_payload") or r)),
            )
            count += 1
        self.conn.commit()
        return count

    def import_stock_hot_ranks(
        self,
        trade_date: str,
        records: list[dict[str, Any]],
        source: str,
        period: str,
        list_type: str,
    ) -> int:
        """导入多来源个股热榜快照。"""
        self._upsert_trade_day(trade_date)
        valid_records = [
            r for r in records
            if r.get("stock_code") and r.get("rank_no") is not None
        ]
        if valid_records:
            self.conn.execute(
                """
                delete from stock_hot_ranks
                where trade_date = ? and source = ? and period = ? and list_type = ?
                """,
                (trade_date, source, period, list_type),
            )
        count = 0
        for r in valid_records:
            stock_code = str(r.get("stock_code") or "").strip()
            stock_name = r.get("stock_name")
            self._upsert_stock(stock_code, stock_name)
            self.conn.execute(
                """
                insert into stock_hot_ranks(
                    trade_date, source, period, list_type, rank_no, stock_code, stock_name,
                    latest_price, change_pct, hot_value, rank_change,
                    concept_tags, popularity_tag, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, source, period, list_type, stock_code) do update set
                    rank_no = excluded.rank_no,
                    stock_name = excluded.stock_name,
                    latest_price = excluded.latest_price,
                    change_pct = excluded.change_pct,
                    hot_value = excluded.hot_value,
                    rank_change = excluded.rank_change,
                    concept_tags = excluded.concept_tags,
                    popularity_tag = excluded.popularity_tag,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    trade_date,
                    source,
                    period,
                    list_type,
                    int(r["rank_no"]),
                    stock_code,
                    stock_name,
                    r.get("latest_price"),
                    r.get("change_pct"),
                    r.get("hot_value"),
                    r.get("rank_change"),
                    _json_text(r.get("concept_tags") or []),
                    r.get("popularity_tag"),
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_hot_boards(self, trade_date: str, records: list[dict[str, Any]], board_type: str) -> int:
        """导入热门板块数据（concept=概念板块, industry=行业板块）"""
        self._upsert_trade_day(trade_date)
        count = 0
        for r in records:
            board_code = r.get("board_code", "")
            if not board_code:
                board_code = f"ths_{r.get('board_name', '')}"
            self._upsert_plate(board_code, r.get("board_name"))
            self.conn.execute(
                """
                insert into hot_boards(trade_date, board_type, rank_no, board_code, board_name,
                    latest_price, change_pct, change_amount, total_market_cap, turnover_rate,
                    up_count, down_count, leading_stock, leading_stock_change)
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(trade_date, board_type, board_code) do update set
                    rank_no = excluded.rank_no,
                    board_name = excluded.board_name,
                    latest_price = excluded.latest_price,
                    change_pct = excluded.change_pct,
                    change_amount = excluded.change_amount,
                    total_market_cap = excluded.total_market_cap,
                    turnover_rate = excluded.turnover_rate,
                    up_count = excluded.up_count,
                    down_count = excluded.down_count,
                    leading_stock = excluded.leading_stock,
                    leading_stock_change = excluded.leading_stock_change,
                    updated_at = current_timestamp
                """,
                (trade_date, board_type, r["rank_no"], board_code, r.get("board_name"),
                 r.get("latest_price"), r.get("change_pct"), r.get("change_amount"),
                 r.get("total_market_cap"), r.get("turnover_rate"),
                 r.get("up_count"), r.get("down_count"),
                 r.get("leading_stock"), r.get("leading_stock_change")),
            )
            count += 1
        self.conn.commit()
        return count

    def import_premarket_news(self, guide_date: str, records: list[dict[str, Any]]) -> int:
        """导入盘前新闻。"""
        count = 0
        valid_records = [r for r in records if str(r.get("title") or "").strip()]
        if valid_records:
            self.conn.execute("delete from premarket_news where guide_date = ?", (guide_date,))
        for r in valid_records:
            title = str(r.get("title") or "").strip()
            source = str(r.get("source") or "news").strip()
            self.conn.execute(
                """
                insert into premarket_news(
                    guide_date, source, published_at, title, content, url, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?)
                on conflict(guide_date, source, title) do update set
                    published_at = excluded.published_at,
                    content = excluded.content,
                    url = excluded.url,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    guide_date,
                    source,
                    r.get("published_at"),
                    title,
                    r.get("content"),
                    r.get("url"),
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_stock_announcements(self, notice_date: str, records: list[dict[str, Any]]) -> int:
        """导入上市公司公告，以 art_code 为主键去重。"""
        import json
        import re

        count = 0
        for r in records:
            title = str(r.get("title") or "").strip()
            if not title:
                continue
            stock_code = str(r.get("stock_code") or "").strip()
            stock_name = r.get("stock_name")
            if stock_code:
                self._upsert_stock(stock_code, stock_name)

            source_url = str(r.get("source_url") or r.get("url") or "").strip()
            art_code = str(r.get("art_code") or "").strip()
            if not art_code and source_url:
                match = re.search(r"(AN\d{16,})", source_url)
                if match:
                    art_code = match.group(1)
            if not art_code:
                raw = r.get("raw_payload") or {}
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = {}
                if isinstance(raw, dict):
                    raw_url = str(raw.get("网址") or raw.get("url") or "").strip()
                    if raw_url:
                        source_url = source_url or raw_url
                        match = re.search(r"(AN\d{16,})", raw_url)
                        if match:
                            art_code = match.group(1)
                if not art_code:
                    match = re.search(r"(AN\d{16,})", _json_text(r))
                    if match:
                        art_code = match.group(1)
            if not art_code:
                continue

            self.conn.execute(
                """
                insert into stock_announcements(
                    art_code, notice_date, stock_code, stock_name, notice_type, title,
                    source, source_url, pdf_url, content_status, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(art_code) do update set
                    notice_date = excluded.notice_date,
                    stock_code = excluded.stock_code,
                    stock_name = excluded.stock_name,
                    notice_type = excluded.notice_type,
                    title = excluded.title,
                    source = excluded.source,
                    source_url = excluded.source_url,
                    pdf_url = coalesce(excluded.pdf_url, stock_announcements.pdf_url),
                    content_status = case
                        when stock_announcements.content_status = 'fetched' then stock_announcements.content_status
                        else excluded.content_status
                    end,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    art_code,
                    notice_date,
                    stock_code or None,
                    stock_name,
                    r.get("notice_type"),
                    title,
                    r.get("source") or "eastmoney",
                    source_url or None,
                    r.get("pdf_url"),
                    r.get("content_status") or "pending",
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_research_reports(self, records: list[dict[str, Any]], current_year: int | None = None) -> int:
        """Import individual stock research reports and their normalized fields."""
        count = 0
        for record in records:
            info_code = str(record.get("infoCode") or record.get("info_code") or "").strip()
            title = str(record.get("title") or "").strip()
            if not info_code or not title:
                continue

            stock_code = str(record.get("stockCode") or record.get("stock_code") or "").strip() or None
            stock_name = record.get("stockName") or record.get("stock_name")
            if stock_code:
                self._upsert_stock(stock_code, stock_name)

            publish_date = str(record.get("publishDate") or record.get("publish_date") or "").strip()
            if not publish_date:
                continue
            org_code = record.get("orgCode") or record.get("org_code")
            org_name = record.get("orgName") or record.get("org_name")
            org_short_name = record.get("orgSName") or record.get("org_short_name")
            industry_code = record.get("indvInduCode") or record.get("industry_code")
            industry_name = record.get("indvInduName") or record.get("industry_name")
            rating_change_code = _int_or_none(record.get("ratingChange") or record.get("rating_change_code"))
            source_url = record.get("source_url") or f"https://data.eastmoney.com/report/info/{info_code}.html"

            self.conn.execute(
                """
                insert into stock_research_reports(
                    info_code, publish_date, stock_code, stock_name, market, title,
                    org_code, org_name, org_short_name, industry_code, industry_name,
                    rating_name, previous_rating_name, rating_change_code, rating_change_name,
                    target_price_low, target_price_high, source_url, detail_status, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                on conflict(info_code) do update set
                    publish_date = excluded.publish_date,
                    stock_code = excluded.stock_code,
                    stock_name = excluded.stock_name,
                    market = excluded.market,
                    title = excluded.title,
                    org_code = excluded.org_code,
                    org_name = excluded.org_name,
                    org_short_name = excluded.org_short_name,
                    industry_code = excluded.industry_code,
                    industry_name = excluded.industry_name,
                    rating_name = excluded.rating_name,
                    previous_rating_name = excluded.previous_rating_name,
                    rating_change_code = excluded.rating_change_code,
                    rating_change_name = excluded.rating_change_name,
                    target_price_low = excluded.target_price_low,
                    target_price_high = excluded.target_price_high,
                    source_url = excluded.source_url,
                    detail_status = case
                        when stock_research_reports.detail_status = 'fetched' then stock_research_reports.detail_status
                        else excluded.detail_status
                    end,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    info_code,
                    publish_date,
                    stock_code,
                    stock_name,
                    record.get("market"),
                    title,
                    org_code,
                    org_name,
                    org_short_name,
                    industry_code,
                    industry_name,
                    record.get("emRatingName") or record.get("rating_name"),
                    record.get("lastEmRatingName") or record.get("previous_rating_name"),
                    rating_change_code,
                    record.get("ratingChangeName") or _research_rating_change_name(rating_change_code),
                    _number_or_none(record.get("indvAimPriceL") or record.get("target_price_low")),
                    _number_or_none(record.get("indvAimPriceT") or record.get("target_price_high")),
                    source_url,
                    _json_text(record.get("raw_payload") or record),
                ),
            )

            self.conn.execute("delete from stock_research_report_authors where info_code = ?", (info_code,))
            for sort_order, author in enumerate(record.get("author") or record.get("authors") or [], start=1):
                text = str(author or "").strip()
                if not text:
                    continue
                author_id, separator, author_name = text.partition(".")
                if not separator:
                    author_id, author_name = text, text
                self.conn.execute(
                    """
                    insert into stock_research_report_authors(info_code, author_id, author_name, sort_order)
                    values(?, ?, ?, ?)
                    on conflict(info_code, author_id) do update set
                        author_name = excluded.author_name,
                        sort_order = excluded.sort_order
                    """,
                    (info_code, author_id, author_name, sort_order),
                )

            self.conn.execute("delete from stock_research_report_forecasts where info_code = ?", (info_code,))
            base_year = _int_or_none(current_year) or _int_or_none(record.get("currentYear"))
            if base_year:
                forecast_fields = (
                    (base_year, "predictThisYearEps", "predictThisYearPe"),
                    (base_year + 1, "predictNextYearEps", "predictNextYearPe"),
                    (base_year + 2, "predictNextTwoYearEps", "predictNextTwoYearPe"),
                )
                for forecast_year, eps_key, pe_key in forecast_fields:
                    self.conn.execute(
                        """
                        insert into stock_research_report_forecasts(info_code, forecast_year, eps, pe)
                        values(?, ?, ?, ?)
                        """,
                        (info_code, forecast_year, _number_or_none(record.get(eps_key)), _number_or_none(record.get(pe_key))),
                    )
            count += 1
        self.conn.commit()
        return count

    def save_research_report_content(self, info_code: str, content: dict[str, Any]) -> None:
        """Save detail-page content without changing an already downloaded PDF."""
        self.conn.execute(
            """
            insert into stock_research_report_contents(
                info_code, summary_text, pdf_url, pdf_status, attach_pages,
                declared_pdf_size_kb, raw_payload
            )
            values(?, ?, ?, 'pending', ?, ?, ?)
            on conflict(info_code) do update set
                summary_text = excluded.summary_text,
                pdf_url = coalesce(excluded.pdf_url, stock_research_report_contents.pdf_url),
                attach_pages = excluded.attach_pages,
                declared_pdf_size_kb = excluded.declared_pdf_size_kb,
                raw_payload = excluded.raw_payload,
                updated_at = current_timestamp
            """,
            (
                info_code,
                content.get("summary_text"),
                content.get("pdf_url"),
                _int_or_none(content.get("attach_pages")),
                _int_or_none(content.get("declared_pdf_size_kb")),
                _json_text(content.get("raw_payload") or content),
            ),
        )
        self.conn.execute(
            """
            update stock_research_reports
            set detail_status = 'fetched', updated_at = current_timestamp
            where info_code = ?
            """,
            (info_code,),
        )
        self.conn.commit()

    def mark_research_report_pdf(self, info_code: str, **state: Any) -> None:
        """Persist PDF download state while retaining detail content."""
        pdf_status = state.get("pdf_status") or "failed"
        downloaded_at = state.get("downloaded_at")
        if pdf_status == "downloaded" and not downloaded_at:
            downloaded_at = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """
            insert into stock_research_report_contents(
                info_code, pdf_status, local_pdf_path, pdf_size, pdf_sha256, pdf_error, downloaded_at
            )
            values(?, ?, ?, ?, ?, ?, ?)
            on conflict(info_code) do update set
                pdf_status = excluded.pdf_status,
                local_pdf_path = excluded.local_pdf_path,
                pdf_size = excluded.pdf_size,
                pdf_sha256 = excluded.pdf_sha256,
                pdf_error = excluded.pdf_error,
                downloaded_at = excluded.downloaded_at,
                updated_at = current_timestamp
            """,
            (
                info_code,
                pdf_status,
                state.get("local_pdf_path"),
                _int_or_none(state.get("pdf_size")),
                state.get("pdf_sha256"),
                state.get("pdf_error"),
                downloaded_at,
            ),
        )
        self.conn.commit()

    def get_pending_research_reports(self, begin_date: str, end_date: str) -> list[dict[str, Any]]:
        """Return reports needing detail or PDF work in an inclusive date range."""
        rows = self.conn.execute(
            """
            select r.info_code, r.publish_date, r.stock_code, r.stock_name, r.source_url,
                   r.detail_status, c.pdf_url, c.pdf_status, c.declared_pdf_size_kb
            from stock_research_reports r
            left join stock_research_report_contents c on c.info_code = r.info_code
            where date(r.publish_date) between date(?) and date(?)
              and (r.detail_status != 'fetched' or c.info_code is null or c.pdf_status not in ('downloaded', 'unavailable'))
            order by r.publish_date desc, r.info_code desc
            """,
            (begin_date, end_date),
        ).fetchall()
        return [dict(row) for row in rows]

    def import_announcement_content(self, art_code: str, content_data: dict[str, Any]) -> bool:
        """保存公告正文，更新公告索引状态。"""
        content_text = str(content_data.get("content_text") or "").strip()
        if not content_text:
            return False
        self.conn.execute(
            """
            insert into stock_announcement_contents(
                art_code, notice_title, notice_date, published_at, page_size,
                content_text, pdf_url, source_url, raw_payload
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(art_code) do update set
                notice_title = excluded.notice_title,
                notice_date = excluded.notice_date,
                published_at = excluded.published_at,
                page_size = excluded.page_size,
                content_text = excluded.content_text,
                pdf_url = excluded.pdf_url,
                source_url = excluded.source_url,
                raw_payload = excluded.raw_payload,
                fetched_at = current_timestamp,
                updated_at = current_timestamp
            """,
            (
                art_code,
                content_data.get("notice_title"),
                content_data.get("notice_date"),
                content_data.get("published_at"),
                content_data.get("page_size", 1),
                content_text,
                content_data.get("pdf_url"),
                content_data.get("source_url"),
                _json_text(content_data.get("raw_payload") or content_data),
            ),
        )
        self.conn.execute(
            """
            update stock_announcements
            set content_status = 'fetched',
                pdf_url = coalesce(?, pdf_url),
                source_url = coalesce(?, source_url),
                updated_at = current_timestamp
            where art_code = ?
            """,
            (content_data.get("pdf_url"), content_data.get("source_url"), art_code),
        )
        self.conn.commit()
        return True

    def mark_announcement_failed(self, art_code: str) -> None:
        """标记公告正文抓取失败。"""
        self.conn.execute(
            """
            update stock_announcements
            set content_status = 'failed', updated_at = current_timestamp
            where art_code = ? and content_status != 'fetched'
            """,
            (art_code,),
        )
        self.conn.commit()

    def get_pending_announcements(self, notice_date: str, limit: int = 50) -> list[dict[str, Any]]:
        """获取待抓取正文的公告列表。"""
        rows = self.conn.execute(
            """
            select art_code, stock_code, stock_name, notice_type, title, source_url
            from stock_announcements
            where notice_date = ? and content_status = 'pending'
            order by
                case when notice_type in ('业绩预告','业绩快报','重大资产重组','增持','减持','回购','风险警示')
                     then 0 else 1 end,
                art_code
            limit ?
            """,
            (notice_date, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def import_us_stock_quotes(self, quote_date: str, records: list[dict[str, Any]]) -> int:
        """导入隔夜美股核心个股行情。"""
        count = 0
        valid_records = [r for r in records if str(r.get("symbol") or "").strip()]
        if valid_records:
            self.conn.execute("delete from us_stock_quotes where quote_date = ?", (quote_date,))
        for r in valid_records:
            symbol = str(r.get("symbol") or "").strip().upper()
            self.conn.execute(
                """
                insert into us_stock_quotes(
                    quote_date, symbol, stock_name, sector, latest_price,
                    change_pct, change_amount, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(quote_date, symbol) do update set
                    stock_name = excluded.stock_name,
                    sector = excluded.sector,
                    latest_price = excluded.latest_price,
                    change_pct = excluded.change_pct,
                    change_amount = excluded.change_amount,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    quote_date,
                    symbol,
                    r.get("stock_name"),
                    r.get("sector"),
                    r.get("latest_price"),
                    r.get("change_pct"),
                    r.get("change_amount"),
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_premarket_guide(self, guide: dict[str, Any]) -> int:
        """导入生成后的盘前指引。"""
        guide_date = str(guide.get("guide_date") or "")
        if not guide_date:
            return 0
        self.conn.execute(
            """
            insert into premarket_guides(
                guide_date, review_date, headline, market_tone, focus_plates,
                watch_points, risk_points, catalyst_news, announcements,
                us_markets, raw_payload
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(guide_date) do update set
                review_date = excluded.review_date,
                headline = excluded.headline,
                market_tone = excluded.market_tone,
                focus_plates = excluded.focus_plates,
                watch_points = excluded.watch_points,
                risk_points = excluded.risk_points,
                catalyst_news = excluded.catalyst_news,
                announcements = excluded.announcements,
                us_markets = excluded.us_markets,
                raw_payload = excluded.raw_payload,
                updated_at = current_timestamp
            """,
            (
                guide_date,
                guide.get("review_date"),
                guide.get("headline"),
                guide.get("market_tone"),
                _json_text(guide.get("focus_plates") or []),
                _json_text(guide.get("watch_points") or []),
                _json_text(guide.get("risk_points") or []),
                _json_text(guide.get("catalyst_news") or []),
                _json_text(guide.get("announcements") or []),
                _json_text(guide.get("us_markets") or []),
                _json_text(guide),
            ),
        )
        self.conn.commit()
        return 1

    def import_plate_trends(self, records: list[dict[str, Any]]) -> int:
        """导入本地派生的板块强度趋势。"""
        count = 0
        for r in records:
            plate_code = str(r.get("plate_code") or "")
            trade_date = str(r.get("trade_date") or "")
            if not plate_code or not trade_date:
                continue
            plate_name = r.get("plate_name")
            self._upsert_trade_day(trade_date)
            self._upsert_plate(plate_code, plate_name)
            self.conn.execute(
                """
                insert into plate_trends(
                    plate_code, trade_date, plate_name, open_price, high_price,
                    low_price, close_price, change_pct, amount, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(plate_code, trade_date) do update set
                    plate_name = excluded.plate_name,
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    change_pct = excluded.change_pct,
                    amount = excluded.amount,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    plate_code,
                    trade_date,
                    plate_name,
                    r.get("open_price"),
                    r.get("high_price"),
                    r.get("low_price"),
                    r.get("close_price"),
                    r.get("change_pct"),
                    r.get("amount"),
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_plate_index_daily(self, records: list[dict[str, Any]]) -> int:
        """导入真实板块指数日 K 数据。"""
        count = 0
        for r in records:
            plate_code = str(r.get("plate_code") or "")
            trade_date = str(r.get("trade_date") or "")
            source = str(r.get("source") or "")
            if not plate_code or not trade_date or not source:
                continue
            plate_name = r.get("plate_name")
            self._upsert_trade_day(trade_date)
            self._upsert_plate(plate_code, plate_name)
            self.conn.execute(
                """
                insert into plate_index_daily(
                    plate_code, trade_date, plate_name, board_type, source,
                    open_price, high_price, low_price, close_price, change_pct,
                    volume, amount, raw_payload
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(plate_code, trade_date, source) do update set
                    plate_name = excluded.plate_name,
                    board_type = excluded.board_type,
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    change_pct = excluded.change_pct,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    plate_code,
                    trade_date,
                    plate_name,
                    r.get("board_type"),
                    source,
                    r.get("open_price"),
                    r.get("high_price"),
                    r.get("low_price"),
                    r.get("close_price"),
                    r.get("change_pct"),
                    r.get("volume"),
                    r.get("amount"),
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_plate_reasons(self, records: list[dict[str, Any]]) -> int:
        """导入本地汇总的板块原因。"""
        count = 0
        for r in records:
            plate_code = str(r.get("plate_code") or "")
            if not plate_code:
                continue
            plate_name = r.get("plate_name")
            self._upsert_plate(plate_code, plate_name)
            self.conn.execute(
                """
                insert into plate_reasons(plate_code, plate_name, reason, raw_payload)
                values(?, ?, ?, ?)
                on conflict(plate_code) do update set
                    plate_name = excluded.plate_name,
                    reason = excluded.reason,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    plate_code,
                    plate_name,
                    r.get("reason"),
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def import_stock_info_snapshots(self, records: list[dict[str, Any]]) -> int:
        """导入核心个股的本地资料快照。"""
        count = 0
        for r in records:
            stock_code = str(r.get("stock_code") or "")
            snapshot_date = str(r.get("snapshot_date") or r.get("trade_date") or "")
            if not stock_code or not snapshot_date:
                continue
            stock_name = r.get("stock_name")
            self._upsert_trade_day(snapshot_date)
            self._upsert_stock(stock_code, stock_name)
            self.conn.execute(
                """
                insert into stock_info_snapshots(stock_code, snapshot_date, stock_name, raw_payload)
                values(?, ?, ?, ?)
                on conflict(stock_code, snapshot_date) do update set
                    stock_name = excluded.stock_name,
                    raw_payload = excluded.raw_payload,
                    updated_at = current_timestamp
                """,
                (
                    stock_code,
                    snapshot_date,
                    stock_name,
                    _json_text(r.get("raw_payload") or r),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def log_data_job(
        self,
        job_name: str,
        trade_date: str | None,
        status: str,
        message: str | None = None,
        details: dict[str, Any] | list[Any] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> int:
        """记录一次采集或派生任务。"""
        self.conn.execute(
            """
            insert into data_jobs(job_name, trade_date, status, message, details, started_at, finished_at)
            values(?, ?, ?, ?, ?, ?, ?)
            """,
            (job_name, trade_date, status, message, _json_text(details) if details is not None else None, started_at, finished_at),
        )
        self.conn.commit()
        return 1

    def _parse_hot_plate(self, item: Any) -> tuple[str, str, float | None] | None:
        if isinstance(item, list) and len(item) >= 2:
            score = item[2] if len(item) >= 3 else None
            return str(item[0]), str(item[1]), score
        if isinstance(item, dict):
            plate_code = item.get("plate_code") or item.get("code")
            plate_name = item.get("plate_name") or item.get("name")
            if plate_code and plate_name:
                return str(plate_name), str(plate_code), item.get("score") or item.get("plate_score")
        return None
