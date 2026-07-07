"""Realtime intraday emotion data for the Quantzz-style sentiment tabs."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils import clean, stock_code, to_float, to_int, to_text

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

TAB_LABELS: list[tuple[str, str]] = [
    ("cycle", "情绪周期"),
    ("intraday", "情绪日内"),
    ("cycle_vip", "情绪周期VIP"),
    ("cycle_year", "情绪周期-年"),
    ("space_board", "空间板"),
    ("popularity", "人气"),
    ("popularity_compare", "人气对比"),
    ("heat_single", "情绪热度单页"),
]


def _as_records(frame_or_rows: Any) -> list[dict[str, Any]]:
    if frame_or_rows is None:
        return []
    if isinstance(frame_or_rows, list):
        return [dict(row) for row in frame_or_rows if isinstance(row, dict)]
    if hasattr(frame_or_rows, "to_dict"):
        return [dict(row) for row in frame_or_rows.to_dict(orient="records")]
    return []


def _pick(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and clean(row.get(name)) is not None:
            return row.get(name)
    return None


def _market_from_spot(spot_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    changes = [to_float(_pick(row, "涨跌幅", "change_pct", "price_change_ratio_pct")) for row in spot_rows]
    valid_changes = [value for value in changes if value is not None]
    amounts = [to_float(_pick(row, "成交额", "amount", "trade_amount")) or 0 for row in spot_rows]

    total = len(valid_changes)
    up_count = sum(1 for value in valid_changes if value > 0)
    down_count = sum(1 for value in valid_changes if value < 0)
    flat_count = sum(1 for value in valid_changes if value == 0)
    limit_up_count = sum(1 for value in valid_changes if value >= 9.8)
    limit_down_count = sum(1 for value in valid_changes if value <= -9.8)
    avg_change = round(sum(valid_changes) / total, 2) if total else None

    ranked = sorted(
        spot_rows,
        key=lambda row: to_float(_pick(row, "成交额", "amount", "trade_amount")) or 0,
        reverse=True,
    )
    hot_items = []
    for rank_no, row in enumerate(ranked[:80], start=1):
        hot_items.append({
            "rank_no": rank_no,
            "stock_code": stock_code(_pick(row, "代码", "stock_code", "ticker", "thscode")),
            "stock_name": to_text(_pick(row, "名称", "stock_name", "name")),
            "latest_price": to_float(_pick(row, "最新价", "latest_price", "last_price")),
            "change_pct": to_float(_pick(row, "涨跌幅", "change_pct", "price_change_ratio_pct")),
            "amount": to_float(_pick(row, "成交额", "amount", "trade_amount")),
            "turnover_rate": to_float(_pick(row, "换手率", "turnover_rate", "turnover_ration_real")),
        })

    market = {
        "total_count": total,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "up_rate": round(up_count / total * 100, 2) if total else None,
        "down_rate": round(down_count / total * 100, 2) if total else None,
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "avg_change_pct": avg_change,
        "amount": sum(amounts),
    }
    return market, hot_items


def _normalize_limit_up_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for index, row in enumerate(items, start=1):
        code = stock_code(_pick(row, "stock_code", "ticker", "代码", "thscode"))
        if not code:
            continue
        board = to_int(_pick(row, "up_limit_keep_times", "continue_day_cnt", "连板数")) or 1
        normalized.append({
            "rank_no": index,
            "stock_code": code,
            "stock_name": to_text(_pick(row, "stock_name", "name", "名称")),
            "change_pct": to_float(_pick(row, "change_pct", "涨跌幅", "price_change_ratio_pct")),
            "up_limit_keep_times": board,
            "up_limit_desc": to_text(_pick(row, "up_limit_desc", "continue_day_text", "涨停统计")),
            "up_limit_time": to_text(_pick(row, "up_limit_time", "limit_up_time", "首次封板时间", "最后封板时间")),
            "reason": to_text(_pick(row, "reason", "limit_up_reason", "所属行业")),
            "fengdan_money": to_float(_pick(row, "fengdan_money", "seal_money", "封板资金", "封单资金")),
            "amount": to_float(_pick(row, "amount", "成交额")),
            "turnover_rate": to_float(_pick(row, "turnover_rate", "turnover_ration_real", "换手率")),
        })
    normalized.sort(key=lambda row: (-(row.get("up_limit_keep_times") or 0), row.get("up_limit_time") or "99:99:99"))
    for rank_no, row in enumerate(normalized, start=1):
        row["rank_no"] = rank_no
    return normalized


def _normalize_simple_stock_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for index, row in enumerate(items, start=1):
        code = stock_code(_pick(row, "stock_code", "ticker", "代码", "thscode"))
        if not code:
            continue
        normalized.append({
            "rank_no": index,
            "stock_code": code,
            "stock_name": to_text(_pick(row, "stock_name", "name", "名称")),
            "change_pct": to_float(_pick(row, "change_pct", "涨跌幅", "price_change_ratio_pct")),
            "amount": to_float(_pick(row, "amount", "成交额")),
            "reason": to_text(_pick(row, "reason", "industry", "所属行业")),
        })
    return normalized


def _normalize_movement_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in items:
        code = stock_code(_pick(row, "stock_code", "ticker", "代码", "thscode"))
        alert_time = to_text(_pick(row, "alert_time", "时间"))
        if not code or not alert_time:
            continue
        normalized.append({
            "alert_time": alert_time,
            "stock_code": code,
            "stock_name": to_text(_pick(row, "stock_name", "name", "名称")),
            "alert_type": to_text(_pick(row, "alert_type", "type", "异动类型")),
            "alert_text": to_text(_pick(row, "alert_text", "板块", "reason")),
            "change_pct": to_float(_pick(row, "change_pct", "涨跌幅")),
            "amount": to_float(_pick(row, "amount", "成交额")),
        })
    return sorted(normalized, key=lambda row: row.get("alert_time") or "", reverse=True)


def _score_market(market: dict[str, Any], limit_up_count: int, limit_down_count: int, broken_count: int, highest_board: int) -> tuple[float, str]:
    up_rate = to_float(market.get("up_rate")) or 0
    score = 50
    score += min(limit_up_count, 120) * 0.18
    score += min(highest_board, 8) * 2.2
    score += (up_rate - 50) * 0.35
    score -= min(limit_down_count, 80) * 0.5
    score -= min(broken_count, 80) * 0.22
    score = max(0, min(100, round(score, 1)))
    if score >= 75:
        return score, "强势"
    if score >= 60:
        return score, "偏强"
    if score >= 45:
        return score, "震荡"
    return score, "偏弱"


def _module(key: str, label: str, status: str, summary: dict[str, Any], items: list[dict[str, Any]], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "summary": summary,
        "items": items,
        "warnings": warnings or [],
    }


def build_realtime_emotion_payload(
    *,
    trade_date: str,
    as_of: str,
    spot_rows: list[dict[str, Any]] | Any,
    limit_up_items: list[dict[str, Any]],
    limit_down_items: list[dict[str, Any]],
    broken_items: list[dict[str, Any]],
    movement_items: list[dict[str, Any]],
    source_status: dict[str, str] | None = None,
    prev_hot_items: list[dict[str, Any]] | None = None,
    yearly_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    spot_records = _as_records(spot_rows)
    market, hot_items = _market_from_spot(spot_records)
    limit_ups = _normalize_limit_up_items(limit_up_items)
    limit_downs = _normalize_simple_stock_rows(limit_down_items)
    brokens = _normalize_simple_stock_rows(broken_items)
    movements = _normalize_movement_items(movement_items)

    market["limit_up_count"] = len(limit_ups) or market["limit_up_count"]
    market["limit_down_count"] = len(limit_downs) or market["limit_down_count"]
    highest_board = max([item.get("up_limit_keep_times") or 0 for item in limit_ups] or [0])
    score, level = _score_market(market, len(limit_ups), len(limit_downs), len(brokens), highest_board)
    seal_success_rate = round(len(limit_ups) / (len(limit_ups) + len(brokens)) * 100, 2) if limit_ups or brokens else None
    broken_rate = round(len(brokens) / (len(limit_ups) + len(brokens)) * 100, 2) if limit_ups or brokens else None
    warnings = []
    if len(limit_downs) >= 20:
        warnings.append("跌停数量偏高，注意日内风险释放")
    if broken_rate is not None and broken_rate >= 35:
        warnings.append("炸板率偏高，追高容错下降")
    if (to_float(market.get("up_rate")) or 0) < 35:
        warnings.append("红盘率偏低，市场承接不足")

    heat_row = {
        "date": trade_date,
        "as_of": as_of,
        "limit_up_count": market["limit_up_count"],
        "limit_down_count": market["limit_down_count"],
        "highest_board": highest_board,
        "up_rate": market.get("up_rate"),
        "broken_rate": broken_rate,
        "hot_top20_heavy_fall_count": sum(1 for item in hot_items[:20] if (to_float(item.get("change_pct")) or 0) <= -5),
    }
    yearly_rows = list(yearly_items or []) + [heat_row]
    prev_rank_by_code = {
        str(item.get("stock_code") or ""): item.get("rank_no")
        for item in prev_hot_items or []
        if item.get("stock_code")
    }
    compare_items = []
    for item in hot_items[:50]:
        prev_rank = prev_rank_by_code.get(item["stock_code"])
        compare = dict(item)
        compare["prev_rank_no"] = prev_rank
        compare["rank_change"] = None if prev_rank is None else int(prev_rank) - int(item["rank_no"])
        compare_items.append(compare)

    board_items = [item for item in limit_ups if item.get("up_limit_keep_times") == highest_board] if highest_board else []
    status = "normal" if source_status and any(value == "ok" for value in source_status.values()) else "empty"
    modules = [
        _module(
            "cycle",
            "情绪周期",
            status,
            {
                "score": score,
                "level": level,
                "up_rate": market.get("up_rate"),
                "limit_up_count": market["limit_up_count"],
                "limit_down_count": market["limit_down_count"],
                "highest_board": highest_board,
                "broken_limit_up_count": len(brokens),
            },
            [heat_row],
            warnings,
        ),
        _module("intraday", "情绪日内", "normal" if movements else "empty", {"alert_count": len(movements)}, movements),
        _module(
            "cycle_vip",
            "情绪周期VIP",
            status,
            {
                "seal_success_rate": seal_success_rate,
                "broken_rate": broken_rate,
                "limit_up_count": len(limit_ups),
                "broken_limit_up_count": len(brokens),
                "limit_down_count": len(limit_downs),
            },
            _build_board_rows(limit_ups),
            warnings,
        ),
        _module(
            "cycle_year",
            "情绪周期-年",
            "normal" if yearly_rows else "empty",
            {
                "days": len(yearly_rows),
                "max_limit_up_count": max([to_float(row.get("limit_up_count")) or 0 for row in yearly_rows] or [0]),
                "max_highest_board": max([to_float(row.get("highest_board")) or 0 for row in yearly_rows] or [0]),
                "avg_up_rate": _avg([to_float(row.get("up_rate")) for row in yearly_rows]),
            },
            yearly_rows,
        ),
        _module(
            "space_board",
            "空间板",
            "normal" if board_items else "empty",
            {"highest_board": highest_board, "stock_count": len(board_items)},
            board_items,
            warnings if highest_board >= 7 else [],
        ),
        _module(
            "popularity",
            "人气",
            "normal" if hot_items else "empty",
            {
                "top20_count": len(hot_items[:20]),
                "avg_change_pct": _avg([to_float(item.get("change_pct")) for item in hot_items[:20]]),
                "heavy_fall_count": sum(1 for item in hot_items[:20] if (to_float(item.get("change_pct")) or 0) <= -5),
            },
            hot_items,
        ),
        _module(
            "popularity_compare",
            "人气对比",
            "normal" if compare_items else "empty",
            {
                "current_count": len(compare_items),
                "prev_count": len(prev_hot_items or []),
                "new_count": sum(1 for item in compare_items if item.get("prev_rank_no") is None),
            },
            compare_items,
        ),
        _module(
            "heat_single",
            "情绪热度单页",
            status,
            {
                **market,
                "score": score,
                "level": level,
                "broken_limit_up_count": len(brokens),
                "as_of": as_of,
            },
            [heat_row],
            [f"{name}: {state}" for name, state in (source_status or {}).items() if state != "ok"],
        ),
    ]
    return {
        "date": trade_date,
        "as_of": as_of,
        "mode": "realtime",
        "refresh_seconds": 45,
        "source_status": source_status or {},
        "market": market,
        "modules": modules,
    }


def _avg(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _build_board_rows(limit_ups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in limit_ups:
        grouped.setdefault(int(item.get("up_limit_keep_times") or 1), []).append(item)
    rows = []
    for level in sorted(grouped.keys(), reverse=True):
        items = grouped[level]
        rows.append({
            "level": level,
            "total": len(items),
            "advanced": len(items),
            "maintained": 0,
            "failed": 0,
            "advancement_rate": 100,
            "stocks": items[:20],
        })
    return rows


def _safe_collect(source_status: dict[str, str], name: str, fn: Callable[[], Any], default: Any) -> Any:
    try:
        value = fn()
        source_status[name] = "ok"
        return value
    except Exception as exc:
        source_status[name] = f"failed: {exc}"
        return default


def _flatten_ak_limit_up(day_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for plate in day_data.get("uplimit_reason") or []:
        for stock in plate.get("stocks") or []:
            item = dict(stock)
            item.setdefault("reason", stock.get("reason") or plate.get("plate_name"))
            rows.append(item)
    return rows


def _merge_fuyao_limit_up(ak_rows: list[dict[str, Any]], fuyao_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code = {str(item.get("ticker") or "").strip(): item for item in fuyao_rows if item.get("ticker")}
    if not ak_rows:
        return [
            {
                "stock_code": item.get("ticker"),
                "stock_name": item.get("name"),
                "change_pct": item.get("price_change_ratio_pct"),
                "up_limit_keep_times": item.get("continue_day_cnt"),
                "up_limit_desc": item.get("continue_day_text"),
                "up_limit_time": item.get("limit_up_time"),
                "reason": item.get("limit_up_reason"),
                "fengdan_money": item.get("seal_money"),
                "amount": item.get("amount"),
            }
            for item in fuyao_rows
        ]
    merged = []
    for row in ak_rows:
        item = dict(row)
        fuyao = by_code.get(str(row.get("stock_code") or "").strip())
        if fuyao:
            item["stock_name"] = fuyao.get("name") or item.get("stock_name")
            item["change_pct"] = fuyao.get("price_change_ratio_pct") or item.get("change_pct")
            item["up_limit_keep_times"] = fuyao.get("continue_day_cnt") or item.get("up_limit_keep_times")
            item["up_limit_desc"] = fuyao.get("continue_day_text") or item.get("up_limit_desc")
            item["up_limit_time"] = fuyao.get("limit_up_time") or item.get("up_limit_time")
            item["reason"] = fuyao.get("limit_up_reason") or item.get("reason")
            item["fengdan_money"] = fuyao.get("seal_money") or item.get("fengdan_money")
        merged.append(item)
    return merged


def _previous_hot_items(db_path: str | os.PathLike[str] | None, trade_date: str) -> list[dict[str, Any]]:
    if not db_path:
        return []
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            select stock_code, stock_name, rank_no, change_pct, amount
            from hot_stocks
            where trade_date = (
                select max(trade_date) from hot_stocks where trade_date < ?
            )
            order by rank_no
            limit 100
            """,
            (trade_date,),
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def collect_realtime_emotion(date: str | None = None, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    from fetch_missing_data import fetch_broken_limit_up_records, fetch_limit_down_records, fetch_movement_records, fetch_spot_snapshot
    from fetch_uplimit import fetch_akshare_uplimit_day

    now = datetime.now(SHANGHAI_TZ)
    trade_date = date or now.strftime("%Y-%m-%d")
    as_of = now.strftime("%Y-%m-%d %H:%M:%S")
    source_status: dict[str, str] = {}

    spot_rows = _safe_collect(source_status, "akshare_spot", lambda: _as_records(fetch_spot_snapshot()), [])
    ak_limit_data = _safe_collect(source_status, "akshare_limit_up", lambda: fetch_akshare_uplimit_day(trade_date), {})
    ak_limit_rows = _flatten_ak_limit_up(ak_limit_data)
    limit_down_rows = _safe_collect(source_status, "akshare_limit_down", lambda: fetch_limit_down_records(trade_date), [])
    broken_rows = _safe_collect(source_status, "akshare_broken_limit_up", lambda: fetch_broken_limit_up_records(trade_date), [])
    movement_rows = _safe_collect(source_status, "akshare_movements", lambda: fetch_movement_records(limit_per_type=60), [])

    def fetch_fuyao_rows() -> list[dict[str, Any]]:
        from fuyao_client import FuyaoClient

        return FuyaoClient().limit_up_pool(trade_date)

    fuyao_rows = _safe_collect(source_status, "fuyao_limit_up", fetch_fuyao_rows, [])
    limit_up_rows = _merge_fuyao_limit_up(ak_limit_rows, fuyao_rows)
    prev_hot = _previous_hot_items(db_path, trade_date)

    return build_realtime_emotion_payload(
        trade_date=trade_date,
        as_of=as_of,
        spot_rows=spot_rows,
        limit_up_items=limit_up_rows,
        limit_down_items=limit_down_rows,
        broken_items=broken_rows,
        movement_items=movement_rows,
        source_status=source_status,
        prev_hot_items=prev_hot,
    )
