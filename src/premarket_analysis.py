"""Premarket market-state diagnosis rules.

The goal is to decide the trading climate before naming sectors. A strong
sector in a weak climate is often a sell point, not a buy signal.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rate(part: Any, total: Any) -> float:
    total_num = _num(total)
    if total_num <= 0:
        return 0.0
    return round(_num(part) / total_num * 100, 1)


def _append_unique(items: list[str], text: str) -> None:
    if text and text not in items:
        items.append(text)


def diagnose_market_state(
    market: dict[str, Any],
    high_position: dict[str, Any],
    trend_hot: dict[str, Any],
) -> dict[str, Any]:
    """Diagnose the next-day trading climate from market and profit-effect data."""
    total_count = _num(market.get("total_count"))
    up_rate = _rate(market.get("up_count"), total_count)
    avg_change = _num(market.get("avg_change_pct"))
    limit_up = _num(market.get("limit_up_count"))
    limit_down = _num(market.get("limit_down_count"))
    broken = _num(market.get("broken_limit_up_count"))

    high_total = _num(high_position.get("total"))
    high_advanced = _num(high_position.get("advanced"))
    high_failed = _num(high_position.get("failed"))
    high_limit_down_failed = _num(high_position.get("limit_down_failed"))
    high_advance_rate = _rate(high_advanced, high_total)
    high_fail_rate = _rate(high_failed, high_total)

    trend_status = str(trend_hot.get("status") or "unknown")
    trend_avg = _num(trend_hot.get("avg_change_pct"))
    trend_heavy_fall = _num(trend_hot.get("heavy_fall_count"))
    trend_down = _num(trend_hot.get("down_count"))

    reasons: list[str] = []
    risk_flags: list[str] = []
    score = 0

    if up_rate >= 60 and avg_change >= 0.5:
        score += 2
        reasons.append("市场广度偏强")
    elif up_rate <= 35 or avg_change <= -0.5:
        score -= 2
        reasons.append("市场广度偏弱")
    else:
        reasons.append("市场广度中性")

    if limit_up >= 120 and limit_down <= 5:
        score += 2
        _append_unique(risk_flags, "涨停数量过多，次日容易从高潮转分歧")
    elif limit_up >= 70 and limit_down <= 10:
        score += 1
        reasons.append("涨停家数仍能支撑修复")
    elif limit_down >= 15 or broken >= 55:
        score -= 2
        _append_unique(risk_flags, "跌停或炸板扩散，亏钱效应偏重")

    if high_total > 0 and high_advance_rate >= 60 and high_limit_down_failed == 0:
        score += 2
        reasons.append("高位个股仍有赚钱效应")
    elif high_total > 0 and (high_fail_rate >= 55 or high_limit_down_failed > 0):
        score -= 2
        _append_unique(risk_flags, "高位个股开始伤人")
    elif high_total > 0:
        reasons.append("高位个股反馈一般")

    if trend_status == "strong":
        score += 1
        reasons.append("热门趋势股仍在走强")
    elif trend_status == "adjusting" or trend_heavy_fall >= 4 or trend_down >= 14 or trend_avg <= -1.5:
        score -= 2
        reasons.append("热门趋势股在调整")
        _append_unique(risk_flags, "热门趋势股调整，抱团方向要防补跌")
    elif trend_status == "mixed":
        reasons.append("热门趋势股分化")

    climax = limit_up >= 120 and up_rate >= 65 and avg_change >= 0.8
    if climax and score >= 4:
        state_code = "climax"
        state_label = "高潮后防分歧"
        strategy_mode = "防分歧"
        advice = "情绪很强，但次日更重要的是看核心能否承接，不适合无脑追后排。"
    elif score <= -3:
        state_code = "risk_off"
        state_label = "退潮防守"
        strategy_mode = "防守"
        advice = "先控制仓位，等高位和热门趋势股止跌后再加大主动性。"
    elif score >= 4:
        state_code = "risk_on"
        state_label = "进攻窗口"
        strategy_mode = "进攻"
        advice = "赚钱效应仍在，可以围绕最强核心做确认，不追没有辨识度的后排。"
    elif score >= 1:
        state_code = "repair"
        state_label = "修复观察"
        strategy_mode = "轻仓试错"
        advice = "有修复基础，但先等竞价和开盘承接确认，再决定是否加仓。"
    else:
        state_code = "mixed"
        state_label = "混沌震荡"
        strategy_mode = "观察"
        advice = "方向不清，适合等市场自己选主线，少做临盘冲动交易。"

    if not risk_flags:
        _append_unique(risk_flags, "没有明显系统性风险，但仍要防消息高开兑现")

    return {
        "state_code": state_code,
        "state_label": state_label,
        "strategy_mode": strategy_mode,
        "score": score,
        "advice": advice,
        "reasons": reasons,
        "risk_flags": risk_flags,
        "metrics": {
            "up_rate": up_rate,
            "avg_change_pct": round(avg_change, 2),
            "limit_up_count": int(limit_up),
            "limit_down_count": int(limit_down),
            "broken_limit_up_count": int(broken),
            "high_advance_rate": high_advance_rate,
            "high_fail_rate": high_fail_rate,
            "trend_avg_change_pct": round(trend_avg, 2),
            "trend_heavy_fall_count": int(trend_heavy_fall),
        },
    }


def build_strategy_points(
    diagnosis: dict[str, Any],
    high_position: dict[str, Any],
    trend_hot: dict[str, Any],
    focus_plates: list[dict[str, Any]],
    us_markets: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build actionable premarket watch points from the diagnosis."""
    points = [
        {
            "title": "先定策略模式",
            "reason": f"{diagnosis.get('state_label')}，今天按“{diagnosis.get('strategy_mode')}”处理。",
            "trigger": diagnosis.get("advice") or "先看竞价和开盘承接，再决定动作。",
        },
        {
            "title": "热门趋势股反馈",
            "reason": trend_hot.get("summary") or "看昨日人气前排和趋势核心是否继续承接。",
            "trigger": "如果趋势核心继续破位或放量下跌，今天不做趋势抱团的追高。",
        },
        {
            "title": "高位个股赚钱效应",
            "reason": high_position.get("summary") or "看昨日高位股是否继续给正反馈。",
            "trigger": "如果空间板和高位断板股继续补跌，连板接力先降预期。",
        },
    ]

    if focus_plates:
        plate = focus_plates[0]
        plate_name = plate.get("plate_name") or plate.get("board_name") or "昨日强势方向"
        points.append({
            "title": f"题材只看核心：{plate_name}",
            "reason": "题材不是因为昨天强就能追，只有核心股承接好、后排不乱跌才有意义。",
            "trigger": "先看前排是否主动换手走强；如果只有消息刺激高开，宁愿等回落确认。",
        })

    mapped = next((item for item in us_markets if item.get("mapped_theme") and _num(item.get("change_pct")) > 1), None)
    if mapped:
        points.append({
            "title": f"隔夜映射只做验证：{mapped.get('mapped_theme')}",
            "reason": f"{mapped.get('stock_name') or mapped.get('symbol')} 隔夜偏强，但外盘只能当催化，不能替代 A 股承接。",
            "trigger": "相关 A 股核心如果竞价不强或开盘冲高回落，就按兑现处理。",
        })

    return points[:6]


def build_risk_points(diagnosis: dict[str, Any]) -> list[dict[str, str]]:
    """Turn diagnosis risk flags into UI-ready risk points."""
    return [
        {
            "title": flag.split("，", 1)[0],
            "reason": flag,
        }
        for flag in diagnosis.get("risk_flags") or []
    ]


def classify_hot_stock_setups(
    stocks: list[dict[str, Any]],
    news_items: list[dict[str, Any]],
    limit: int = 6,
) -> dict[str, list[dict[str, Any]]]:
    """Group popular stocks into pullback, chase-risk and news-catalyst buckets."""
    pullback_watch: list[dict[str, Any]] = []
    chase_risk: list[dict[str, Any]] = []
    news_hot: list[dict[str, Any]] = []

    for stock in stocks:
        stock_name = str(stock.get("stock_name") or stock.get("stock_code") or "")
        stock_code = str(stock.get("stock_code") or "")
        if not stock_name and not stock_code:
            continue

        change_pct = _num(stock.get("change_pct"))
        sectors = _stock_sectors(stock)
        base = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "rank_no": stock.get("rank_no"),
            "change_pct": round(change_pct, 2),
            "sectors": sectors,
        }

        if change_pct <= -5:
            pullback_watch.append({
                **base,
                "reason": f"热门股大幅回撤 {_signed_pct(change_pct)}，如果所属方向没有退潮，可以放入低吸观察。",
                "action_hint": "低吸观察：只看缩量止跌、核心股先修复，不接继续放量杀跌。",
            })

        if change_pct >= 7:
            chase_risk.append({
                **base,
                "reason": f"今日涨幅 {_signed_pct(change_pct)}，短线获利盘较重。",
                "action_hint": "明天不追：高开无承接、后排跟不上时按兑现风险处理。",
            })

        matched_news = _matched_news(stock_name, sectors, news_items)
        if matched_news:
            news_hot.append({
                **base,
                "reason": f"新闻催化：{matched_news[0]}",
                "action_hint": "新闻热点：竞价强、板块联动、前排主动换手时才快速确认。",
            })

    pullback_watch.sort(key=lambda item: (item.get("change_pct") or 0, item.get("rank_no") or 999))
    chase_risk.sort(key=lambda item: (-(item.get("change_pct") or 0), item.get("rank_no") or 999))
    news_hot.sort(key=lambda item: (item.get("rank_no") or 999, -abs(item.get("change_pct") or 0)))

    return {
        "pullback_watch": _dedupe_setup_items(pullback_watch)[:limit],
        "chase_risk": _dedupe_setup_items(chase_risk)[:limit],
        "news_hot": _dedupe_setup_items(news_hot)[:limit],
    }


def _stock_sectors(stock: dict[str, Any]) -> list[str]:
    raw = stock.get("sectors") or stock.get("plates") or stock.get("concept_tags") or []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.replace("，", ",").split(",")]
    sectors = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in sectors:
            sectors.append(text)
    return sectors[:6]


def _matched_news(stock_name: str, sectors: list[str], news_items: list[dict[str, Any]]) -> list[str]:
    matched: list[str] = []
    needles = [stock_name, *sectors]
    for news in news_items:
        title = str(news.get("title") or "")
        content = str(news.get("content") or "")
        text = f"{title} {content}".upper()
        if any(needle and str(needle).upper() in text for needle in needles):
            matched.append(title[:80])
    return matched


def _dedupe_setup_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("stock_code") or item.get("stock_name"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _signed_pct(value: float) -> str:
    return f"{value:+.2f}%"
