"""Generate structured daily review reports from the local market database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MarketDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "market_review.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [_row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def _row(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return _row_to_dict(row) if row else None


def _fmt_money(value: float | int | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 100000000:
        return f"{value / 100000000:.1f}亿"
    if abs(value) >= 10000:
        return f"{value / 10000:.0f}万"
    return f"{value:.0f}"


def _safe_int(value: Any, default: int = 0) -> int:
    return int(value) if value is not None else default


def _brief_text(value: Any, max_len: int = 120) -> str:
    text = str(value or "").replace("\r", "\n").strip()
    if not text:
        return ""
    first = next((part.strip() for part in text.split("\n") if part.strip()), "")
    if len(first) <= max_len:
        return first
    return first[:max_len].rstrip() + "..."


def get_default_date(db_path: str | Path = DEFAULT_DB_PATH) -> str:
    conn = _connect(db_path)
    try:
        row = conn.execute("select max(trade_date) as trade_date from limit_up_events").fetchone()
        if not row or not row["trade_date"]:
            raise RuntimeError("数据库里还没有涨停数据")
        return row["trade_date"]
    finally:
        conn.close()


def build_review_payload(trade_date: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        stats = _row(
            conn,
            """
            select
                (select count(distinct stock_code) from limit_up_events where trade_date = ?) as limit_up_stock_count,
                (select count(distinct plate_code) from limit_up_plate_map where trade_date = ?) as limit_up_plate_count,
                sum(case when coalesce(up_limit_desc, '') like '%首板%' then 1 else 0 end) as first_board_count,
                sum(case when coalesce(up_limit_desc, '') not like '%首板%' then 1 else 0 end) as multi_board_count,
                coalesce(max(up_limit_keep_times), 1) as highest_board
            from limit_up_events
            where trade_date = ?
            """,
            (trade_date, trade_date, trade_date),
        ) or {}
        if _safe_int(stats.get("limit_up_stock_count")) == 0:
            raise RuntimeError(f"{trade_date} 没有涨停数据，无法生成复盘")

        prev = _row(
            conn,
            """
            select trade_date, count(distinct stock_code) as limit_up_stock_count
            from limit_up_events
            where trade_date = (select max(trade_date) from limit_up_events where trade_date < ?)
            """,
            (trade_date,),
        ) or {"trade_date": None, "limit_up_stock_count": 0}

        breadth = _row(
            conn,
            """
            select total_count, up_count, down_count, flat_count, limit_up_count, limit_down_count, amount
            from market_breadth_daily
            where trade_date = ?
            """,
            (trade_date,),
        ) or {
            "total_count": 0,
            "up_count": 0,
            "down_count": 0,
            "flat_count": 0,
            "limit_up_count": stats.get("limit_up_stock_count"),
            "limit_down_count": None,
            "amount": None,
        }
        limit_down_total = _row(
            conn,
            "select count(*) as total from limit_down_events where trade_date = ?",
            (trade_date,),
        )["total"]
        broken_total = _row(
            conn,
            "select count(*) as total from broken_limit_up_events where trade_date = ?",
            (trade_date,),
        )["total"]
        if not breadth.get("limit_down_count") and limit_down_total:
            breadth["limit_down_count"] = limit_down_total
        up_rate = (
            round((breadth.get("up_count") or 0) / breadth["total_count"] * 100, 1)
            if breadth.get("total_count")
            else None
        )

        strongest_plates = _rows(
            conn,
            """
            select
                p.plate_code,
                p.plate_name,
                count(distinct p.stock_code) as limit_up_count,
                max(coalesce(r.score, p.plate_score, 0)) as score,
                group_concat(distinct e.stock_name) as stock_names
            from limit_up_plate_map p
            left join limit_up_events e
                on p.trade_date = e.trade_date and p.stock_code = e.stock_code
            left join plate_hot_rank r
                on p.trade_date = r.trade_date and p.plate_code = r.plate_code and r.source = 'uplimit_hot'
            where p.trade_date = ?
            group by p.plate_code, p.plate_name
            order by limit_up_count desc, score desc
            limit 6
            """,
            (trade_date,),
        )
        for plate in strongest_plates:
            count = _safe_int(plate.get("limit_up_count"))
            if count >= 8:
                stage = "主线"
            elif count >= 4:
                stage = "活跃"
            else:
                stage = "观察"
            plate["stage"] = stage
            plate["stocks"] = (plate.pop("stock_names") or "").split(",")[:8]

        core_stocks = _rows(
            conn,
            """
            select
                e.stock_code, e.stock_name, e.up_limit_keep_times,
                e.up_limit_time, e.fengdan_money, e.reason,
                (
                    select p.plate_name
                    from limit_up_plate_map p
                    where p.trade_date = e.trade_date and p.stock_code = e.stock_code
                    order by coalesce(p.plate_score, 0) desc
                    limit 1
                ) as primary_plate
            from limit_up_events e
            where e.trade_date = ?
            order by coalesce(e.up_limit_keep_times, 1) desc,
                     coalesce(e.fengdan_money, 0) desc,
                     e.up_limit_time asc
            limit 12
            """,
            (trade_date,),
        )

        indices = _rows(
            conn,
            """
            select index_code, index_name, close_price, change_pct
            from market_index_daily
            where trade_date = ?
            order by index_code
            """,
            (trade_date,),
        )

        lhb_buy = _rows(
            conn,
            """
            select stock_code, stock_name, reason, net_buy_amount
            from lhb_daily
            where trade_date = ? and coalesce(net_buy_amount, 0) > 0
            order by net_buy_amount desc
            limit 5
            """,
            (trade_date,),
        )

        risk_flags = build_risk_flags(
            stats=stats,
            prev=prev,
            breadth=breadth,
            up_rate=up_rate,
            limit_down_total=limit_down_total,
            broken_total=broken_total,
        )
        opportunities = build_opportunities(strongest_plates, core_stocks, lhb_buy)
        next_plan = build_next_plan(stats, strongest_plates, risk_flags)
        summary = build_summary(
            trade_date=trade_date,
            stats=stats,
            prev=prev,
            strongest_plates=strongest_plates,
            breadth=breadth,
            up_rate=up_rate,
            limit_down_total=limit_down_total,
            broken_total=broken_total,
        )

        return {
            "trade_date": trade_date,
            "limit_up_stock_count": _safe_int(stats.get("limit_up_stock_count")),
            "limit_up_plate_count": _safe_int(stats.get("limit_up_plate_count")),
            "first_board_count": _safe_int(stats.get("first_board_count")),
            "multi_board_count": _safe_int(stats.get("multi_board_count")),
            "highest_board": _safe_int(stats.get("highest_board"), 1),
            "prev_trade_date": prev.get("trade_date"),
            "prev_limit_up_stock_count": _safe_int(prev.get("limit_up_stock_count")),
            "breadth": {
                **breadth,
                "up_rate": up_rate,
                "limit_down_total": limit_down_total,
                "broken_limit_up_total": broken_total,
            },
            "indices": indices,
            "strongest_plates": strongest_plates,
            "core_stocks": core_stocks,
            "lhb_net_buy": lhb_buy,
            "risk_flags": risk_flags,
            "opportunities": opportunities,
            "next_plan": next_plan,
            "summary": summary,
            "markdown_path": None,
        }
    finally:
        conn.close()


def build_summary(
    trade_date: str,
    stats: dict[str, Any],
    prev: dict[str, Any],
    strongest_plates: list[dict[str, Any]],
    breadth: dict[str, Any],
    up_rate: float | None,
    limit_down_total: int,
    broken_total: int,
) -> str:
    total = _safe_int(stats.get("limit_up_stock_count"))
    prev_total = _safe_int(prev.get("limit_up_stock_count"))
    delta = total - prev_total if prev_total else 0
    strongest = strongest_plates[0]["plate_name"] if strongest_plates else "暂无明显主线"
    direction = "增加" if delta > 0 else "减少" if delta < 0 else "持平"
    breadth_text = f"，红盘率 {up_rate:.1f}%" if up_rate is not None else ""
    return (
        f"{trade_date} 涨停 {total} 只，较前一交易日{direction} {abs(delta)} 只，"
        f"最高板 {stats.get('highest_board') or 1} 板，主线集中在 {strongest}"
        f"{breadth_text}。跌停 {breadth.get('limit_down_count') or limit_down_total} 只，"
        f"炸板 {broken_total} 只，明天重点看主线延续和高位分歧。"
    )


def build_risk_flags(
    stats: dict[str, Any],
    prev: dict[str, Any],
    breadth: dict[str, Any],
    up_rate: float | None,
    limit_down_total: int,
    broken_total: int,
) -> list[str]:
    risks = []
    total = _safe_int(stats.get("limit_up_stock_count"))
    prev_total = _safe_int(prev.get("limit_up_stock_count"))
    if prev_total and total < prev_total * 0.7:
        risks.append(f"涨停数较前一交易日明显收缩：{prev_total} -> {total}。")
    if broken_total >= max(20, total * 0.45):
        risks.append(f"炸板数量偏高：{broken_total} 只，说明封板稳定性一般。")
    limit_down_count = _safe_int(breadth.get("limit_down_count")) or limit_down_total
    if limit_down_count >= 20:
        risks.append(f"跌停数量偏多：{limit_down_count} 只，亏钱效应需要警惕。")
    if up_rate is not None and up_rate < 45:
        risks.append(f"红盘率偏低：{up_rate:.1f}%，市场宽度不足。")
    if _safe_int(stats.get("highest_board"), 1) <= 3:
        risks.append("连板高度不高，高标带动性还不够强。")
    if not risks:
        risks.append("暂未看到明显系统性风险，但高位股仍要观察分歧承接。")
    return risks


def build_opportunities(
    strongest_plates: list[dict[str, Any]],
    core_stocks: list[dict[str, Any]],
    lhb_buy: list[dict[str, Any]],
) -> list[str]:
    opportunities = []
    for plate in strongest_plates[:3]:
        stocks = "、".join(plate.get("stocks") or [])
        suffix = f"，代表股：{stocks}" if stocks else ""
        opportunities.append(
            f"{plate['plate_name']}：{plate.get('limit_up_count', 0)} 只涨停，状态为{plate.get('stage', '观察')}{suffix}。"
        )
    if lhb_buy:
        top = lhb_buy[0]
        opportunities.append(f"龙虎榜净买入靠前：{top['stock_name']}，净买 {_fmt_money(top['net_buy_amount'])}。")
    if not opportunities and core_stocks:
        top = core_stocks[0]
        opportunities.append(f"核心观察股：{top['stock_name']}，{top.get('up_limit_keep_times') or 1} 板。")
    return opportunities


def build_next_plan(
    stats: dict[str, Any],
    strongest_plates: list[dict[str, Any]],
    risk_flags: list[str],
) -> list[str]:
    plan = []
    if strongest_plates:
        plan.append(f"优先观察 {strongest_plates[0]['plate_name']} 是否继续扩散，确认主线持续性。")
    if _safe_int(stats.get("highest_board"), 1) >= 5:
        plan.append("高标进入情绪锚定区，明天先看最高板反馈，再决定进攻强度。")
    else:
        plan.append("高度还没完全打开，明天更适合看首板和二板的强度确认。")
    if len(risk_flags) >= 2 and "暂未看到明显系统性风险" not in risk_flags[0]:
        plan.append("若早盘继续出现跌停或炸板扩大，降低追高，优先保留现金。")
    else:
        plan.append("若主线前排继续强势，低位补涨和换手核心可以作为观察重点。")
    return plan


def render_markdown(review: dict[str, Any]) -> str:
    lines = [
        "---",
        f"date: {review['trade_date']}",
        "tags: [复盘, A股, 短线]",
        "---",
        "",
        f"# A股复盘 {review['trade_date']}",
        "",
        "## 一句话结论",
        "",
        review["summary"],
        "",
        "## 盘面数据",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 涨停 | {review['limit_up_stock_count']} |",
        f"| 首板 / 连板 | {review['first_board_count']} / {review['multi_board_count']} |",
        f"| 最高板 | {review['highest_board']} |",
        f"| 跌停 | {review['breadth'].get('limit_down_count') or review['breadth'].get('limit_down_total')} |",
        f"| 炸板 | {review['breadth'].get('broken_limit_up_total')} |",
        f"| 红盘率 | {review['breadth'].get('up_rate') if review['breadth'].get('up_rate') is not None else '-'}% |",
        f"| 成交额 | {_fmt_money(review['breadth'].get('amount'))} |",
        "",
        "## 主线板块",
        "",
    ]
    for plate in review["strongest_plates"]:
        stocks = "、".join(plate.get("stocks") or [])
        lines.append(f"- **{plate['plate_name']}**：{plate.get('limit_up_count', 0)} 只涨停，{plate.get('stage', '观察')}。{stocks}")
    lines.extend(["", "## 核心个股", ""])
    for stock in review["core_stocks"][:10]:
        lines.append(
            f"- {stock['stock_name']}（{stock['stock_code']}）：{stock.get('up_limit_keep_times') or 1}板，"
            f"{stock.get('primary_plate') or '-'}，{_brief_text(stock.get('reason'))}"
        )
    lines.extend(["", "## 风险点", ""])
    lines.extend([f"- {item}" for item in review["risk_flags"]])
    lines.extend(["", "## 机会观察", ""])
    lines.extend([f"- {item}" for item in review["opportunities"]])
    lines.extend(["", "## 明日计划", ""])
    lines.extend([f"- {item}" for item in review["next_plan"]])
    lines.extend(["", "---", "*报告由「发家致富」系统自动生成。*"])
    return "\n".join(lines) + "\n"


def write_markdown(review: dict[str, Any], output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{review['trade_date']}-复盘.md"
    path.write_text(render_markdown(review), encoding="utf-8")
    return path


def generate_daily_review(
    trade_date: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    if trade_date is None:
        trade_date = get_default_date(db_path)
    review = build_review_payload(trade_date, db_path)
    markdown_path = write_markdown(review, output_dir)
    review["markdown_path"] = str(markdown_path)

    db = MarketDB(db_path)
    db.init_schema()
    try:
        db.import_daily_review(review)
    finally:
        db.close()
    return review


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 A 股每日复盘结论")
    parser.add_argument("--date", help="交易日期，格式 YYYY-MM-DD；不传则使用最新交易日")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="Markdown 输出目录")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = parser.parse_args()

    review = generate_daily_review(args.date, args.db, args.out)
    if args.json:
        print(json.dumps(review, ensure_ascii=False, indent=2))
    else:
        print(f"已生成复盘: {review['trade_date']}")
        print(f"报告文件: {review['markdown_path']}")
        print(review["summary"])


if __name__ == "__main__":
    main()
