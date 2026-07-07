"""爬取近15个交易日的涨停数据"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import QuantAPI
from db import MarketDB
from fuyao_limit_up import enrich_day_data_with_fuyao, fetch_limit_up_pool, update_limit_up_reasons
from utils import clean, compact_time, is_blank, stock_code, to_float, to_int, to_text


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "market_review.db")


def _safe_plate_code(name: str) -> str:
    return "akshare_" + name.replace(" ", "_")


def _dataframe_records(df: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in df.to_dict(orient="records")]


def _is_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "401" in text or "unauthorized" in text


def fetch_akshare_uplimit_day(date: str) -> dict[str, Any]:
    """Use Eastmoney limit-up pool as a free fallback when Quant auth fails."""
    import akshare as ak

    df = ak.stock_zt_pool_em(date=date.replace("-", ""))
    records = _dataframe_records(df)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        industry = to_text(row.get("所属行业")) or "未分组"
        grouped.setdefault(industry, []).append(row)

    plates = []
    hot_plates = []
    for plate_name, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        plate_code = _safe_plate_code(plate_name)
        stocks = []
        for row in rows:
            stocks.append({
                "stock_code": stock_code(row.get("代码")),
                "stock_name": to_text(row.get("名称")),
                "stock_price": to_float(row.get("最新价")),
                "up_limit_desc": to_text(row.get("涨停统计")),
                "up_limit_keep_times": to_int(row.get("连板数")) or 1,
                "up_limit_type": "akshare_limit_up",
                "up_limit_time": compact_time(row.get("首次封板时间") or row.get("最后封板时间")),
                "reason": plate_name,
                "fengdan_money": to_float(row.get("封板资金")),
                "turnover_ration_real": to_float(row.get("换手率")),
                "actualcirculation_value": to_float(row.get("流通市值")),
                "amount": to_float(row.get("成交额")),
                "market_type": to_text(row.get("所属行业")),
                "raw": row,
            })
        plates.append({
            "plate_code": plate_code,
            "plate_name": plate_name,
            "plate_score": len(stocks),
            "stocks": stocks,
        })
        hot_plates.append([plate_name, plate_code, len(stocks)])

    return {
        "date": date,
        "uplimit_reason": plates,
        "uplimit_hot": hot_plates[:20],
        "plate_rank": [
            {"plate_code": item[1], "plate_name": item[0], "score": item[2]}
            for item in hot_plates[:30]
        ],
    }


def load_token():
    """从浏览器 localStorage 读取 token（需要先登录）"""
    token_file = os.path.join(os.path.dirname(__file__), "..", "config", "token.json")
    if os.path.exists(token_file):
        with open(token_file) as f:
            data = json.load(f)
            return data.get("token")
    return None


def save_token(token: str):
    """保存 token 到文件"""
    token_file = os.path.join(os.path.dirname(__file__), "..", "config", "token.json")
    with open(token_file, "w") as f:
        json.dump({"token": token, "saved_at": datetime.now().isoformat()}, f, indent=2)


def fetch_sentiment_data(api: QuantAPI, db: MarketDB, days: int = 15):
    """Fetch sentiment kline data for recent trading days.

    The sentiment kline API returns OHLC data for the sentiment index.
    We call it with a date from ~20 days ago to ensure we get all 15 trading days,
    then import into sentiment_daily table.
    """
    print(f"\n{'='*50}")
    print(f"Fetching sentiment kline data (period=0, last {days} days)...")
    print(f"{'='*50}")

    # Call with a date from ~20 days ago to get full coverage
    start_date = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
    result = api.get_sentiment_kline(start_date, period=0)

    if result.get("code") != 20000 or not result.get("data"):
        print("  [WARN] No sentiment data returned from API")
        return 0

    kline_data = result["data"]
    print(f"  API returned {len(kline_data)} records")

    # Show date range
    if kline_data:
        first_date = kline_data[0].get("date")
        last_date = kline_data[-1].get("date")
        print(f"  Date range: {first_date} ~ {last_date}")

    # Import into database
    count = db.import_sentiment_daily(kline_data, period=0, raw_source="api")
    print(f"  [OK] Imported {count} sentiment records into sentiment_daily")

    return count


def fetch_fuyao_uplimit_day(date: str) -> dict[str, Any] | None:
    """Use Fuyao limit-up pool as primary source. Returns None if unavailable."""
    api_key = os.environ.get("FUYAO_API_KEY")
    if not api_key:
        return None
    try:
        items = fetch_limit_up_pool(api_key, date)
    except Exception as exc:
        print(f"    Fuyao 涨停池请求失败: {exc}")
        return None
    if not items:
        return None

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        reason = item.get("limit_up_reason") or "未分组"
        grouped.setdefault(reason, []).append(item)

    plates = []
    hot_plates = []
    for reason, rows in sorted(grouped.items(), key=lambda x: -len(x[1])):
        plate_code = _safe_plate_code(reason)
        stocks = []
        for row in rows:
            ticker = str(row.get("ticker") or "").strip()
            if not ticker:
                continue
            limit_up_time = row.get("limit_up_time")
            if limit_up_time and len(str(limit_up_time)) == 5:
                limit_up_time = f"{limit_up_time}:00"
            stocks.append({
                "stock_code": stock_code(ticker),
                "stock_name": to_text(row.get("stock_name")),
                "stock_price": to_float(row.get("last_price")),
                "up_limit_desc": to_text(row.get("continue_day_text")),
                "up_limit_keep_times": to_int(row.get("continue_day_cnt")) or 1,
                "up_limit_type": "fuyao_limit_up",
                "up_limit_time": to_text(limit_up_time),
                "reason": reason,
                "fengdan_money": to_float(row.get("seal_money")),
                "fengdan_rate": to_float(row.get("max_seal_money")),
                "turnover_rate": to_float(row.get("turnover")),
                "circulation_value": None,
                "amount": None,
                "market_type": None,
            })
        if stocks:
            plates.append({
                "plate_code": plate_code,
                "plate_name": reason,
                "plate_score": len(stocks),
                "stocks": stocks,
            })
            hot_plates.append([reason, plate_code, len(stocks)])

    total_stocks = sum(len(p["stocks"]) for p in plates)
    print(f"    ✅ Fuyao: {len(plates)} 个板块, {total_stocks} 只涨停股")
    return {
        "date": date,
        "uplimit_reason": plates,
        "uplimit_hot": hot_plates[:20],
        "plate_rank": [
            {"plate_code": item[1], "plate_name": item[0], "score": item[2]}
            for item in hot_plates[:30]
        ],
    }


def fetch_uplimit_data(api: QuantAPI, date: str, db: MarketDB):
    """爬取某一天的涨停数据（优先级: Fuyao → Quantzz → AkShare）"""
    print(f"\n{'='*50}")
    print(f"爬取 {date} 的涨停数据...")
    print(f"{'='*50}")

    # 1. 优先 Fuyao
    print("  [1/3] 涨停数据...")
    day_data = fetch_fuyao_uplimit_day(date)
    raw_source = "fuyao.limit_up_pool"

    # 2. Fuyao 不可用时降级 Quantzz
    if day_data is None:
        print("    Fuyao 不可用，尝试 Quantzz...")
        try:
            reason_data = api.get_uplimit_reason(date, page_size=200)
            if reason_data.get("code") == 20000 and reason_data.get("data"):
                plates = reason_data["data"]
                total_stocks = sum(len(p.get("stocks", [])) for p in plates)
                print(f"    ✅ Quantzz: {len(plates)} 个板块, {total_stocks} 只涨停股")
            else:
                plates = []
                print(f"    ⚠️  Quantzz 无数据")
            day_data = {
                "date": date,
                "uplimit_reason": plates,
                "uplimit_hot": [],
                "plate_rank": [],
            }
            raw_source = "quantzz.api"

            # 补充 Quantzz 热门板块和板块排名
            print("  [2/3] 涨停梯队...")
            hot_data = api.get_uplimit_hot(date, limit=20)
            if hot_data.get("code") == 20000 and hot_data.get("data"):
                day_data["uplimit_hot"] = hot_data["data"].get("plate", [])
                print(f"    ✅ {len(day_data['uplimit_hot'])} 个热门板块")
            else:
                print(f"    ⚠️  无数据")

            print("  [3/3] 板块排名...")
            try:
                rank_data = api.get_plate_rank(date, limit=30)
                if rank_data.get("code") == 20000 and rank_data.get("data"):
                    day_data["plate_rank"] = rank_data["data"]
                    print(f"    ✅ {len(day_data['plate_rank'])} 个板块")
                else:
                    print(f"    ⚠️  无数据")
            except Exception as e:
                print(f"    ⚠️  板块排名失败: {e}")

        except Exception as exc:
            if not _is_auth_error(exc):
                raise
            # 3. Quantzz 也失败时降级 AkShare
            print(f"    ⚠️  Quantzz 失败，改用 AkShare 兜底: {exc}")
            day_data = fetch_akshare_uplimit_day(date)
            raw_source = "akshare.stock_zt_pool_em"

    # 用 Fuyao 数据补充原因字段（如果主源不是 Fuyao）
    if raw_source != "fuyao.limit_up_pool":
        _enrich_day_data_from_fuyao(date, day_data)

    db.import_uplimit_day(day_data, raw_source=raw_source)
    print(f"  💾 已写入数据库: {db.db_path}")
    return day_data


def _enrich_day_data_from_fuyao(date: str, day_data: dict[str, Any]) -> None:
    api_key = os.environ.get("FUYAO_API_KEY")
    if not api_key:
        return
    try:
        items = fetch_limit_up_pool(api_key, date)
        count = enrich_day_data_with_fuyao(day_data, items)
        print(f"    Fuyao enriched limit-up reasons: {count}")
    except Exception as exc:
        print(f"    Fuyao reason enrichment failed: {exc}")


def _backfill_db_from_fuyao(date: str, db_path: str | os.PathLike[str]) -> None:
    api_key = os.environ.get("FUYAO_API_KEY")
    if not api_key:
        return
    try:
        items = fetch_limit_up_pool(api_key, date)
        count = update_limit_up_reasons(db_path, date, items)
        print(f"    Fuyao backfilled limit-up reasons: {count}")
    except Exception as exc:
        print(f"    Fuyao reason backfill failed: {exc}")


def main():
    # 加载 token
    token = load_token()
    if not token:
        print("❌ 未找到 token，请先在浏览器登录数据平台获取")
        print("   或手动将 token 保存到 config/token.json")
        return

    api = QuantAPI(token)

    # 获取交易日历
    today = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print("获取交易日历...")
    trade_days = api.get_trade_days(end_date, days=20)  # 多取几天，确保有15个交易日
    if not trade_days:
        print("❌ 获取交易日历失败")
        return

    # 取最近15个交易日
    recent_days = trade_days[-15:]
    print(f"最近15个交易日: {recent_days[0]} ~ {recent_days[-1]}")

    db = MarketDB(DEFAULT_DB_PATH)
    db.init_schema()

    # 逐日爬取涨停数据
    all_data = []
    try:
        for day in recent_days:
            date_str = day if isinstance(day, str) else day.get("date", day)
            try:
                day_data = fetch_uplimit_data(api, date_str, db)
                all_data.append(day_data)
            except Exception as e:
                print(f"  ❌ 爬取 {date_str} 失败: {e}")

        # 采集情绪K线数据
        try:
            fetch_sentiment_data(api, db, days=15)
        except Exception as e:
            print(f"  [ERROR] Failed to fetch sentiment data: {e}")

        # 采集大盘指数数据（实时数据，仅当天）
        print(f"\n{'='*50}")
        print("采集大盘指数数据...")
        try:
            index_result = api.get_index_trends()
            if index_result.get("code") == 200 and index_result.get("data"):
                indices = index_result["data"]
                today_str = datetime.now().strftime("%Y-%m-%d")
                count = db.import_index_daily(today_str, indices, raw_source="api")
                print(f"  ✅ 已写入 {count} 条指数数据 ({today_str})")
                for idx in indices:
                    print(f"    {idx['name']}: {idx['last_px']} ({idx['px_change_rate']}%)")
            else:
                print(f"  ⚠️  无指数数据或接口返回异常")
        except Exception as e:
            print(f"  ❌ 采集指数数据失败: {e}")
    finally:
        db.close()

    print(f"\n{'='*50}")
    print(f"✅ 完成！共爬取 {len(all_data)} 个交易日")
    print(f"📁 数据库: {DEFAULT_DB_PATH}")


if __name__ == "__main__":
    main()
