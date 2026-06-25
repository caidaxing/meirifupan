"""Generate pre-market guidance from yesterday review and overnight catalysts."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from db import MarketDB
from fetch_missing_data import DEFAULT_DB_PATH
from premarket_analysis import (
    build_risk_points as build_diagnosis_risk_points,
    build_strategy_points,
    classify_hot_stock_setups,
    diagnose_market_state,
)


AI_KEYWORDS = ("AI", "算力", "服务器", "英伟达", "NVDA", "芯片", "半导体", "存储", "光模块", "CPO")
ROBOT_KEYWORDS = ("机器人", "特斯拉", "自动驾驶", "工业母机")
AUTO_KEYWORDS = ("汽车", "新能源车", "锂电", "固态电池", "储能")
CONSUMER_KEYWORDS = ("消费", "食品", "旅游", "零售", "白酒")
FINANCE_KEYWORDS = ("金融", "券商", "银行", "保险")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_row_to_dict(row) for row in rows]


def _json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _pct_text(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):+.2f}%"


def _amount_text(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{round(float(value) / 100000000):,}亿"


def _infer_theme(text: str) -> str | None:
    upper = text.upper()
    groups = [
        ("AI算力", AI_KEYWORDS),
        ("机器人", ROBOT_KEYWORDS),
        ("新能源车", AUTO_KEYWORDS),
        ("消费", CONSUMER_KEYWORDS),
        ("金融", FINANCE_KEYWORDS),
    ]
    for theme, keywords in groups:
        if any(keyword.upper() in upper for keyword in keywords):
            return theme
    return None


def resolve_review_date(conn: sqlite3.Connection, guide_date: str, review_date: str | None = None) -> str:
    if review_date:
        return review_date
    row = conn.execute(
        """
        select max(trade_date) as trade_date
        from limit_up_events
        where trade_date < ?
        """,
        (guide_date,),
    ).fetchone()
    if row and row["trade_date"]:
        return row["trade_date"]
    row = conn.execute(
        """
        select max(trade_date) as trade_date
        from daily_reviews
        where trade_date < ?
        """,
        (guide_date,),
    ).fetchone()
    if row and row["trade_date"]:
        return row["trade_date"]
    raise RuntimeError(f"{guide_date} 之前没有可用复盘数据")


def _market_row(conn: sqlite3.Connection, review_date: str) -> dict[str, Any]:
    row = conn.execute(
        """
        select total_count, up_count, down_count, flat_count, limit_up_count,
               limit_down_count, natural_limit_up_count, natural_limit_down_count,
               avg_change_pct, amount
        from market_breadth_daily
        where trade_date = ?
        """,
        (review_date,),
    ).fetchone()
    result = _row_to_dict(row) if row else {}
    if result:
        broken_row = conn.execute(
            "select count(*) as total from broken_limit_up_events where trade_date = ?",
            (review_date,),
        ).fetchone()
        limit_down_row = conn.execute(
            "select count(*) as total from limit_down_events where trade_date = ?",
            (review_date,),
        ).fetchone()
        result["broken_limit_up_count"] = broken_row["total"] if broken_row else 0
        if not result.get("limit_down_count") and limit_down_row:
            result["limit_down_count"] = limit_down_row["total"]
    return result


def _prev_trade_date(conn: sqlite3.Connection, review_date: str) -> str | None:
    row = conn.execute(
        """
        select max(trade_date) as trade_date
        from limit_up_events
        where trade_date < ?
        """,
        (review_date,),
    ).fetchone()
    return row["trade_date"] if row and row["trade_date"] else None


def _high_position_effect(conn: sqlite3.Connection, review_date: str) -> dict[str, Any]:
    """Evaluate whether yesterday's high-position stocks still paid tomorrow's risk."""
    prev_date = _prev_trade_date(conn, review_date)
    if not prev_date:
        return {
            "prev_date": None,
            "total": 0,
            "advanced": 0,
            "maintained": 0,
            "failed": 0,
            "limit_down_failed": 0,
            "failed_names": [],
            "summary": "缺少上一交易日高位股数据，先用当日情绪和趋势反馈判断。",
        }

    prev_rows = conn.execute(
        """
        select stock_code, stock_name, up_limit_keep_times
        from limit_up_events
        where trade_date = ? and up_limit_keep_times >= 2
        """,
        (prev_date,),
    ).fetchall()
    cur_rows = conn.execute(
        """
        select stock_code, stock_name, up_limit_keep_times
        from limit_up_events
        where trade_date = ?
        """,
        (review_date,),
    ).fetchall()
    cur_map = {row["stock_code"]: row for row in cur_rows}

    advanced = 0
    maintained = 0
    failed: list[sqlite3.Row] = []
    for row in prev_rows:
        cur = cur_map.get(row["stock_code"])
        if cur and (cur["up_limit_keep_times"] or 0) > (row["up_limit_keep_times"] or 0):
            advanced += 1
        elif cur:
            maintained += 1
        else:
            failed.append(row)

    failed_codes = [row["stock_code"] for row in failed]
    limit_down_failed = 0
    if failed_codes:
        placeholders = ",".join("?" for _ in failed_codes)
        limit_down_failed = conn.execute(
            f"""
            select count(*) as total
            from limit_down_events
            where trade_date = ? and stock_code in ({placeholders})
            """,
            (review_date, *failed_codes),
        ).fetchone()["total"]

    total = len(prev_rows)
    advance_rate = round(advanced / total * 100, 1) if total else 0
    fail_rate = round(len(failed) / total * 100, 1) if total else 0
    if total == 0:
        summary = "上一交易日没有明显高位梯队，短线高度参考意义较弱。"
    elif limit_down_failed:
        summary = f"高位晋级率 {advance_rate}% ，且 {limit_down_failed} 只失败高位股跌停，接力风险偏高。"
    elif fail_rate >= 55:
        summary = f"高位晋级率 {advance_rate}% ，失败率 {fail_rate}% ，高位赚钱效应转弱。"
    elif advance_rate >= 55:
        summary = f"高位晋级率 {advance_rate}% ，高位股仍有正反馈。"
    else:
        summary = f"高位晋级率 {advance_rate}% ，反馈一般，先看空间板承接。"

    return {
        "prev_date": prev_date,
        "total": total,
        "advanced": advanced,
        "maintained": maintained,
        "failed": len(failed),
        "advance_rate": advance_rate,
        "fail_rate": fail_rate,
        "limit_down_failed": limit_down_failed,
        "failed_names": [row["stock_name"] for row in failed[:8]],
        "summary": summary,
    }


def _latest_close_is_new_high(conn: sqlite3.Connection, stock_code: str, review_date: str, days: int = 8) -> bool:
    rows = conn.execute(
        """
        select trade_date, close_price
        from stock_kline_daily
        where stock_code = ? and trade_date <= ? and close_price is not null
        order by trade_date desc
        limit ?
        """,
        (stock_code, review_date, days),
    ).fetchall()
    if len(rows) < 2:
        return False
    latest = rows[0]["close_price"]
    previous_high = max(row["close_price"] for row in rows[1:] if row["close_price"] is not None)
    return latest is not None and latest >= previous_high


def _trend_hot_status(conn: sqlite3.Connection, review_date: str, limit: int = 20) -> dict[str, Any]:
    """Evaluate whether popular trend stocks are extending, splitting, or adjusting."""
    stocks = _hot_stocks(conn, review_date, limit)
    if not stocks:
        return {
            "status": "unknown",
            "summary": "缺少热门股数据，趋势抱团状态暂时无法判断。",
            "avg_change_pct": 0,
            "up_count": 0,
            "down_count": 0,
            "heavy_fall_count": 0,
            "new_high_count": 0,
            "stocks": [],
        }

    changes = [float(item.get("change_pct") or 0) for item in stocks]
    avg_change = round(sum(changes) / len(changes), 2)
    up_count = sum(1 for value in changes if value > 0)
    down_count = sum(1 for value in changes if value < 0)
    heavy_fall_count = sum(1 for value in changes if value <= -5)
    strong_rise_count = sum(1 for value in changes if value >= 5)
    new_high_count = sum(
        1
        for item in stocks[:12]
        if _latest_close_is_new_high(conn, str(item.get("stock_code") or ""), review_date)
    )

    if heavy_fall_count >= 4 or down_count >= 14 or avg_change <= -1.5:
        status = "adjusting"
        summary = f"热门趋势股平均涨幅 {_pct_text(avg_change)}，{heavy_fall_count} 只跌超 5%，抱团方向在调整。"
    elif avg_change >= 1.5 and up_count >= max(10, down_count * 2) and (strong_rise_count >= 4 or new_high_count >= 4):
        status = "strong"
        summary = f"热门趋势股平均涨幅 {_pct_text(avg_change)}，上涨 {up_count} 只，趋势核心仍有赚钱效应。"
    else:
        status = "mixed"
        summary = f"热门趋势股平均涨幅 {_pct_text(avg_change)}，上涨 {up_count} 只、下跌 {down_count} 只，资金分化。"

    return {
        "status": status,
        "summary": summary,
        "avg_change_pct": avg_change,
        "up_count": up_count,
        "down_count": down_count,
        "heavy_fall_count": heavy_fall_count,
        "strong_rise_count": strong_rise_count,
        "new_high_count": new_high_count,
        "stocks": stocks[:10],
    }


def _focus_plates(conn: sqlite3.Connection, review_date: str, limit: int = 6) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select h.board_code, h.board_name, h.rank_no, h.change_pct, h.up_count,
               h.down_count, h.leading_stock,
               (
                   select count(*)
                   from limit_up_plate_map m
                   where m.trade_date = h.trade_date and m.plate_code = h.board_code
               ) as limit_up_count
        from hot_boards h
        where h.trade_date = ? and h.board_type = 'concept'
        order by h.rank_no asc
        limit ?
        """,
        (review_date, limit),
    ).fetchall()
    result = []
    for row in rows:
        item = _row_to_dict(row)
        item["plate_code"] = item.get("board_code")
        item["plate_name"] = item.get("board_name")
        item["reason"] = f"昨日板块排名第 {item['rank_no']}，涨幅 {_pct_text(item.get('change_pct'))}，涨停 {item.get('limit_up_count') or 0} 只。"
        result.append(item)
    if result:
        return result

    rows = conn.execute(
        """
        select m.plate_code as board_code, m.plate_name as board_name,
               count(distinct m.stock_code) as limit_up_count,
               max(e.up_limit_keep_times) as highest_board,
               null as rank_no, null as change_pct, null as up_count,
               null as down_count, null as leading_stock
        from limit_up_plate_map m
        left join limit_up_events e
          on e.trade_date = m.trade_date and e.stock_code = m.stock_code
        where m.trade_date = ?
        group by m.plate_code, m.plate_name
        order by limit_up_count desc, highest_board desc
        limit ?
        """,
        (review_date, limit),
    ).fetchall()
    result = []
    for row in rows:
        item = _row_to_dict(row)
        item["plate_code"] = item.get("board_code")
        item["plate_name"] = item.get("board_name")
        item["reason"] = f"昨日涨停 {item.get('limit_up_count') or 0} 只，最高 {item.get('highest_board') or '-'} 板。"
        result.append(item)
    if result:
        return result

    rows = conn.execute(
        """
        select plate_code as board_code, plate_name as board_name, rank_no, score,
               null as change_pct, null as up_count, null as down_count,
               null as leading_stock,
               (
                   select count(*)
                   from limit_up_plate_map m
                   where m.trade_date = p.trade_date and m.plate_code = p.plate_code
               ) as limit_up_count
        from plate_hot_rank p
        where p.trade_date = ?
        order by rank_no asc
        limit ?
        """,
        (review_date, limit),
    ).fetchall()
    return [
        {
            **_row_to_dict(row),
            "plate_code": row["board_code"],
            "plate_name": row["board_name"],
            "reason": f"昨日涨停热度靠前，涨停 {row['limit_up_count'] or 0} 只。",
        }
        for row in rows
    ]


def _hot_stocks(conn: sqlite3.Connection, review_date: str, limit: int = 8) -> list[dict[str, Any]]:
    source_row = conn.execute(
        """
        select count(*) as total
        from hot_stocks
        where trade_date = ? and source like 'eastmoney%'
        """,
        (review_date,),
    ).fetchone()
    source_filter = "source like 'eastmoney%'" if source_row and source_row["total"] else "1 = 1"
    return _rows(conn.execute(
        f"""
        select rank_no, stock_code, stock_name, latest_price, change_pct, amount, turnover_rate, source
        from hot_stocks
        where trade_date = ? and {source_filter}
        order by rank_no asc
        limit ?
        """,
        (review_date, limit),
    ).fetchall())


def _stock_sector_tags(conn: sqlite3.Connection, review_date: str, stock_code: str) -> list[str]:
    tags: list[str] = []
    rows = conn.execute(
        """
        select concept_tags
        from stock_hot_ranks
        where trade_date = ? and stock_code = ?
        order by
            case source when 'ths_hot' then 0 when 'shortline_hot' then 1 else 2 end,
            rank_no asc
        limit 3
        """,
        (review_date, stock_code),
    ).fetchall()
    for row in rows:
        for tag in _json_list(row["concept_tags"]):
            text = str(tag or "").strip()
            if text and text not in tags:
                tags.append(text)

    plate_rows = conn.execute(
        """
        select plate_name
        from limit_up_plate_map
        where trade_date = ? and stock_code = ?
        order by plate_score desc
        limit 5
        """,
        (review_date, stock_code),
    ).fetchall()
    for row in plate_rows:
        text = str(row["plate_name"] or "").strip()
        if text and text not in tags:
            tags.append(text)
    return tags[:6]


def _stock_setup_candidates(conn: sqlite3.Connection, review_date: str, limit: int = 40) -> list[dict[str, Any]]:
    """Build a candidate list of popular stocks with sector tags."""
    candidates: dict[str, dict[str, Any]] = {}
    for item in _hot_stocks(conn, review_date, limit):
        code = str(item.get("stock_code") or "")
        if not code:
            continue
        candidates[code] = {**item, "sectors": _stock_sector_tags(conn, review_date, code)}

    rows = conn.execute(
        """
        select rank_no, stock_code, stock_name, latest_price, change_pct,
               hot_value, rank_change, concept_tags, source, period, list_type
        from stock_hot_ranks
        where trade_date = ?
          and source in ('ths_hot', 'shortline_hot')
          and period in ('day', 'hour')
        order by
          case source when 'ths_hot' then 0 when 'shortline_hot' then 1 else 2 end,
          case period when 'day' then 0 else 1 end,
          rank_no asc
        limit ?
        """,
        (review_date, limit),
    ).fetchall()
    for row in rows:
        item = _row_to_dict(row)
        code = str(item.get("stock_code") or "")
        if not code:
            continue
        tags = _json_list(item.pop("concept_tags", None))
        existing = candidates.get(code)
        if existing:
            sectors = existing.get("sectors") or []
            for tag in tags:
                text = str(tag or "").strip()
                if text and text not in sectors:
                    sectors.append(text)
            existing["sectors"] = sectors[:6]
            continue
        item["sectors"] = tags[:6] or _stock_sector_tags(conn, review_date, code)
        candidates[code] = item

    return sorted(
        candidates.values(),
        key=lambda item: (
            item.get("rank_no") is None,
            item.get("rank_no") or 9999,
            -abs(float(item.get("change_pct") or 0)),
        ),
    )[:limit]


def _space_stocks(conn: sqlite3.Connection, review_date: str, limit: int = 5) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        """
        select stock_code, stock_name, up_limit_keep_times, up_limit_desc,
               up_limit_time, reason, fengdan_money, fengdan_rate
        from limit_up_events
        where trade_date = ?
        order by up_limit_keep_times desc, up_limit_time asc
        limit ?
        """,
        (review_date, limit),
    ).fetchall())


def _news(conn: sqlite3.Connection, guide_date: str, limit: int = 12) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        """
        select source, published_at, title, content, url
        from premarket_news
        where guide_date = ?
        order by coalesce(published_at, '') desc
        limit ?
        """,
        (guide_date, limit),
    ).fetchall())


def _announcements(conn: sqlite3.Connection, notice_date: str, limit: int = 12) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        """
        select stock_code, stock_name, notice_date, notice_type, title, url
        from stock_announcements
        where notice_date = ?
        order by stock_code is null, stock_code, title
        limit ?
        """,
        (notice_date, limit),
    ).fetchall())


def _us_markets(conn: sqlite3.Connection, guide_date: str, limit: int = 10) -> list[dict[str, Any]]:
    rows = _rows(conn.execute(
        """
        select symbol, stock_name, sector, latest_price, change_pct, change_amount
        from us_stock_quotes
        where quote_date = ?
        order by abs(coalesce(change_pct, 0)) desc
        limit ?
        """,
        (guide_date, limit),
    ).fetchall())
    for item in rows:
        text = f"{item.get('symbol', '')} {item.get('stock_name', '')} {item.get('sector', '')}"
        item["mapped_theme"] = _infer_theme(text)
    return rows


def _build_market_tone(market: dict[str, Any]) -> str:
    if not market:
        return "缺少昨日大盘广度数据，先按复盘强弱和隔夜消息做观察。"
    up_count = market.get("up_count") or 0
    down_count = market.get("down_count") or 0
    limit_up = market.get("limit_up_count") or 0
    limit_down = market.get("limit_down_count") or 0
    amount = _amount_text(market.get("amount"))
    avg = _pct_text(market.get("avg_change_pct"))
    if limit_down >= max(8, limit_up * 0.4):
        return f"昨日成交额 {amount}，平均涨幅 {avg}，但跌停 {limit_down} 只，早盘先看风险释放。"
    if up_count > down_count and limit_up >= 50:
        return f"昨日成交额 {amount}，上涨家数多于下跌家数，涨停 {limit_up} 只，情绪有修复基础。"
    return f"昨日成交额 {amount}，平均涨幅 {avg}，涨停 {limit_up} 只、跌停 {limit_down} 只，先看主线能否继续聚焦。"


def _build_legacy_watch_points(
    focus_plates: list[dict[str, Any]],
    hot_stocks: list[dict[str, Any]],
    space_stocks: list[dict[str, Any]],
    news: list[dict[str, Any]],
    announcements: list[dict[str, Any]],
    us_markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    top_plate = focus_plates[0] if focus_plates else None
    if top_plate:
        points.append({
            "title": f"主线延续：{top_plate.get('plate_name') or top_plate.get('board_name')}",
            "reason": top_plate.get("reason") or "昨日板块热度靠前。",
            "trigger": "开盘后看板块前排是否继续高开并有换手承接。",
        })
    if space_stocks:
        stock = space_stocks[0]
        points.append({
            "title": f"空间板反馈：{stock.get('stock_name')}",
            "reason": f"昨日最高连板为 {stock.get('up_limit_desc') or str(stock.get('up_limit_keep_times')) + '板'}，它决定短线高度能不能继续打开。",
            "trigger": "如果高位股低开后快速走弱，先降低连板接力预期。",
        })
    if hot_stocks:
        names = "、".join(item.get("stock_name") or item.get("stock_code") for item in hot_stocks[:3])
        points.append({
            "title": "人气股承接",
            "reason": f"昨日人气前排是 {names}，这些不一定都涨停，但更能反映资金关注。",
            "trigger": "看前排人气股是否比普通涨停股更强，决定今天是看趋势还是看连板。",
        })
    mapped = [item for item in us_markets if item.get("mapped_theme") and (item.get("change_pct") or 0) > 1]
    if mapped:
        item = mapped[0]
        points.append({
            "title": f"隔夜美股映射：{item.get('mapped_theme')}",
            "reason": f"{item.get('stock_name') or item.get('symbol')} 隔夜涨幅 {_pct_text(item.get('change_pct'))}，美股强势可能给 A 股相关方向提供早盘催化。",
            "trigger": "只看竞价和开盘 15 分钟是否兑现到 A 股核心股，不追单一消息。",
        })
    important_notice = announcements[0] if announcements else None
    if important_notice:
        points.append({
            "title": f"公告催化：{important_notice.get('stock_name') or important_notice.get('stock_code') or '重点公告'}",
            "reason": important_notice.get("title") or "昨晚有重点公告。",
            "trigger": "先看公告股是否带动同板块，不只看单只高开。",
        })
    important_news = news[0] if news else None
    if important_news and not mapped:
        points.append({
            "title": "新闻催化",
            "reason": important_news.get("title") or "隔夜有重点消息。",
            "trigger": "消息要落到板块和核心股强弱上，弱兑现就不硬做。",
        })
    return points[:6]


def _build_risk_points(market: dict[str, Any], us_markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    limit_down = market.get("limit_down_count") if market else None
    avg = market.get("avg_change_pct") if market else None
    if limit_down is not None and limit_down >= 8:
        risks.append({
            "title": "亏钱反馈没有完全消失",
            "reason": f"昨日跌停 {limit_down} 只，早盘如果高位股继续补跌，先防守。",
        })
    if avg is not None and avg < -0.5:
        risks.append({
            "title": "市场平均涨幅偏弱",
            "reason": f"昨日全市场平均涨幅 {_pct_text(avg)}，说明赚钱效应没有扩散。",
        })
    weak_us = [item for item in us_markets if (item.get("change_pct") or 0) <= -2]
    if weak_us:
        item = weak_us[0]
        risks.append({
            "title": "隔夜外盘拖累",
            "reason": f"{item.get('stock_name') or item.get('symbol')} 跌幅 {_pct_text(item.get('change_pct'))}，相关映射方向早盘容易先分歧。",
        })
    if not risks:
        risks.append({
            "title": "不要只因为消息追高",
            "reason": "盘前消息只决定观察方向，真正能不能做要看开盘承接和板块合力。",
        })
    return risks[:4]


def _build_next_day_strategy(diagnosis: dict[str, Any]) -> dict[str, Any]:
    mode = diagnosis.get("strategy_mode") or "观察"
    state_code = diagnosis.get("state_code")
    if state_code == "risk_off":
        should_do = ["控制仓位", "只看核心股止跌", "等亏钱效应收敛"]
        avoid = ["追高后排题材", "高位接力", "趋势破位股低吸"]
    elif state_code == "climax":
        should_do = ["看核心承接", "等第一次分歧后的强回流", "减少后排冲动交易"]
        avoid = ["高潮次日无脑加仓", "追一字板后排", "忽视炸板扩散"]
    elif state_code == "risk_on":
        should_do = ["围绕最强核心确认", "优先看主动换手", "让强度自己筛选方向"]
        avoid = ["追杂毛补涨", "买没有辨识度的消息股"]
    elif state_code == "repair":
        should_do = ["轻仓试错", "等竞价和开盘承接确认", "优先看核心而非后排"]
        avoid = ["开盘直接满仓", "只因昨日涨幅排名买入"]
    else:
        should_do = ["观察市场选方向", "少做临盘冲动", "只处理确定性高的核心"]
        avoid = ["频繁切换题材", "追消息高开"]
    return {
        "mode": mode,
        "should_do": should_do,
        "avoid": avoid,
        "confirmation": [
            "热门趋势股是否止跌或继续新高",
            "高位股是否继续给正反馈",
            "跌停和炸板是否继续扩散",
        ],
    }


def _extend_points_with_stock_setups(
    watch_points: list[dict[str, Any]],
    risk_points: list[dict[str, Any]],
    stock_setups: dict[str, list[dict[str, Any]]],
) -> None:
    pullbacks = stock_setups.get("pullback_watch") or []
    chase_risks = stock_setups.get("chase_risk") or []
    news_hot = stock_setups.get("news_hot") or []
    if pullbacks:
        names = "、".join(item.get("stock_name") or item.get("stock_code") for item in pullbacks[:3])
        watch_points.append({
            "title": "大幅回撤低吸观察",
            "reason": f"{names} 等热门股出现大幅回撤，只有板块没有退潮、个股先止跌时才看低吸。",
            "trigger": "优先看缩量企稳、核心股先修复；继续放量杀跌就不接。",
        })
    if news_hot:
        names = "、".join(item.get("stock_name") or item.get("stock_code") for item in news_hot[:3])
        watch_points.append({
            "title": "新闻热点快速确认",
            "reason": f"{names} 与盘前新闻催化贴合，适合开盘先验证强度。",
            "trigger": "竞价强、板块联动、前排主动换手时再快速确认；孤立高开不算。",
        })
    if chase_risks:
        names = "、".join(item.get("stock_name") or item.get("stock_code") for item in chase_risks[:3])
        risk_points.append({
            "title": "今日大涨明日防追高",
            "reason": f"{names} 等热门股今日涨幅较大，明天如果高开无承接，容易变成兑现点。",
        })


def _build_headline(
    focus_plates: list[dict[str, Any]],
    us_markets: list[dict[str, Any]],
    market_tone: str,
    diagnosis: dict[str, Any] | None = None,
) -> str:
    plate = (focus_plates[0].get("plate_name") or focus_plates[0].get("board_name")) if focus_plates else "核心方向"
    mapped = next((item for item in us_markets if item.get("mapped_theme") and (item.get("change_pct") or 0) > 1), None)
    if diagnosis:
        state_label = diagnosis.get("state_label") or "行情待确认"
        mode = diagnosis.get("strategy_mode") or "观察"
        if diagnosis.get("state_code") == "risk_off":
            return f"盘前判断为{state_label}，今天先按{mode}处理，等亏钱效应收敛"
        if diagnosis.get("state_code") == "climax":
            return f"盘前判断为{state_label}，今天重点防后排分歧和高开兑现"
        if diagnosis.get("state_code") in {"repair", "mixed"}:
            return f"盘前判断为{state_label}，先看{plate}、趋势核心和高位股能否给正反馈"
    if mapped:
        return f"盘前先看 {plate}，隔夜{mapped.get('stock_name') or mapped.get('symbol')}强化{mapped.get('mapped_theme')}线索"
    if "风险" in market_tone or "跌停" in market_tone:
        return f"盘前先看 {plate} 的修复力度，同时防高位分歧"
    return f"盘前先看 {plate} 能否从昨日强势延续到早盘承接"


def generate_premarket_guide(
    guide_date: str | None = None,
    review_date: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    guide_date = guide_date or datetime.now().strftime("%Y-%m-%d")
    db = MarketDB(db_path)
    db.init_schema()
    try:
        conn = db.conn
        resolved_review_date = resolve_review_date(conn, guide_date, review_date)
        market = _market_row(conn, resolved_review_date)
        focus_plates = _focus_plates(conn, resolved_review_date)
        hot_stocks = _hot_stocks(conn, resolved_review_date)
        space_stocks = _space_stocks(conn, resolved_review_date)
        high_position = _high_position_effect(conn, resolved_review_date)
        trend_hot = _trend_hot_status(conn, resolved_review_date)
        news = _news(conn, guide_date)
        announcements = _announcements(conn, resolved_review_date)
        us_markets = _us_markets(conn, guide_date)
        stock_setups = classify_hot_stock_setups(_stock_setup_candidates(conn, resolved_review_date), news)
        market_tone = _build_market_tone(market)
        market_state = diagnose_market_state(market, high_position, trend_hot)
        watch_points = build_strategy_points(market_state, high_position, trend_hot, focus_plates, us_markets)
        risk_points = build_diagnosis_risk_points(market_state)
        legacy_risks = _build_risk_points(market, us_markets)
        seen_risk_titles = {item.get("title") for item in risk_points}
        for item in legacy_risks:
            if item.get("title") not in seen_risk_titles:
                risk_points.append(item)
                seen_risk_titles.add(item.get("title"))
        _extend_points_with_stock_setups(watch_points, risk_points, stock_setups)
        guide = {
            "guide_date": guide_date,
            "review_date": resolved_review_date,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "headline": _build_headline(focus_plates, us_markets, market_tone, market_state),
            "market_tone": market_tone,
            "market_snapshot": market,
            "market_state": market_state,
            "high_position_effect": high_position,
            "trend_hot_status": trend_hot,
            "next_day_strategy": _build_next_day_strategy(market_state),
            "stock_setups": stock_setups,
            "focus_plates": focus_plates,
            "hot_stocks": hot_stocks,
            "space_stocks": space_stocks,
            "watch_points": watch_points,
            "risk_points": risk_points,
            "catalyst_news": news,
            "announcements": announcements,
            "us_markets": us_markets,
        }
        db.import_premarket_guide(guide)
        return guide
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成盘前指引")
    parser.add_argument("--date", help="盘前指引日期，默认今天")
    parser.add_argument("--review-date", help="使用哪一天的复盘作为基础，默认取上一交易日")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    args = parser.parse_args()
    guide = generate_premarket_guide(args.date, args.review_date, args.db)
    print(f"{guide['guide_date']} 盘前指引已生成: {guide['headline']}")


if __name__ == "__main__":
    main()
