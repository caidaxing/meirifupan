# 数据存储说明

## 当前存储方式

项目现在使用 SQLite 存储市场数据，数据库文件为：

```text
data/market_review.db
```

旧的 JSON 文件仍保留在 `data/uplimit/`，只作为历史原始文件和迁移来源。新的抓取流程会直接写入数据库。

## 数据分层

| 层级 | 表 | 作用 |
|------|------|------|
| 原始层 | `raw_api_responses` | 保存接口原始返回，方便追溯和重算 |
| 基础层 | `trade_calendar`、`stocks`、`plates` | 保存交易日、股票、板块基础信息 |
| 事件层 | `limit_up_events`、`limit_up_plate_map` | 保存涨停事件和股票-板块关系 |
| 排名层 | `plate_hot_rank`、`plate_daily` | 保存热门板块和板块排名 |
| 扩展数据层 | `plate_trends`、`plate_reasons`、`market_breadth_daily`、`limit_down_events`、`broken_limit_up_events`、`lhb_daily`、`movement_alerts`、`market_index_daily`、`sentiment_daily`、`market_hot_daily`、`stock_kline_daily`、`stock_trends`、`stock_info_snapshots` | 保存后续复盘和看盘会用到的数据 |
| 分析层 | `daily_reviews` | 后续保存自动复盘结论 |
| 任务层 | `data_jobs` | 后续记录采集、分析、推送任务 |

## 为什么拆成多张表

接口返回的涨停数据是“板块里套股票”。同一只股票可能属于多个板块，如果直接累加会重复统计。

现在改成：

```text
limit_up_events       一只股票一天只保存一条涨停事件
limit_up_plate_map    一只股票一天可以关联多个板块
```

这样既能得到真实涨停数量，也能分析题材扩散情况。

## 当前数据覆盖

当前数据库已经完成一轮近 20 个交易日回补。本地可识别交易日为 20 个：

```text
2026-05-11 ~ 2026-06-05
```

主要数据量：

| 表 | 数量 |
|------|------:|
| `trade_calendar` | 20 |
| `stocks` | 1543 |
| `plates` | 730 |
| `limit_up_events` | 1539 |
| `limit_up_plate_map` | 18099 |
| `plate_hot_rank` | 379 |
| `plate_daily` | 518 |
| `plate_trends` | 3117 |
| `plate_reasons` | 259 |
| `limit_down_events` | 255 |
| `broken_limit_up_events` | 475 |
| `lhb_daily` | 1965 |
| `market_index_daily` | 80 |
| `sentiment_daily` | 18 |
| `market_breadth_daily` | 1 |
| `movement_alerts` | 754 |
| `market_hot_daily` | 101 |
| `stock_kline_daily` | 127 |
| `stock_info_snapshots` | 240 |
| `daily_reviews` | 20 |

涨停、跌停、炸板、龙虎榜、大盘指数、核心股日 K、自动复盘覆盖 `2026-05-11 ~ 2026-06-05`。`plate_trends`、`plate_reasons`、`stock_info_snapshots` 是从本地涨停和复盘数据派生出来的，不伪装成外部行情源。全市场涨跌家数、盘中异动、板块异动热点属于实时快照，目前只保存最新交易日，不会把今天的快照硬填到过去日期。

`stock_trends` 是分钟/分时级别数据。当前复盘只要求日线维度以上，所以这张表保留为空，不进入回补流程。

可用 `python src/db_inventory.py` 查看所有表的行数。

## 数据获取方式

当前主数据源由 `src/api_client.py` 封装接口。

已经接入并落库：

| 数据 | 方法 | 入库表 |
|------|------|------|
| 交易日历 | `get_trade_days()` | `trade_calendar` |
| 涨停原因 | `get_uplimit_reason()` | `limit_up_events`、`limit_up_plate_map`、`stocks`、`plates` |
| 涨停热门板块 | `get_uplimit_hot()` | `plate_hot_rank` |
| 板块排名 | `get_plate_rank()` | `plate_daily` |

本地派生数据：

| 数据 | 来源 | 目标表 |
|------|------|------|
| 板块趋势 | 本地涨停板块映射聚合，`close_price` 表示当日板块涨停数量 | `plate_trends` |
| 板块热门原因 | 本地涨停股原因、代表股和活跃天数汇总 | `plate_reasons` |
| 核心股资料快照 | 自动复盘核心股、板块、日 K、龙虎榜汇总 | `stock_info_snapshots` |

已建表但不进入当前复盘回补：

| 数据 | 原因 | 目标表 |
|------|------|------|
| 个股分时 | 复盘只看日线维度以上，分时属于盘中看盘，不补历史 | `stock_trends` |

`src/fetch_missing_data.py` 已补充一批公开行情数据：

| 数据 | 来源 | 入库表 |
|------|------|------|
| 全市场涨跌家数、成交额 | AkShare 全 A 实时快照 | `market_breadth_daily` |
| 成交额排行热门股票 | AkShare 全 A 实时快照 | `hot_stocks` |
| 跌停池 | AkShare 跌停池 | `limit_down_events` |
| 炸板池 | AkShare 炸板池 | `broken_limit_up_events` |
| 龙虎榜 | AkShare 龙虎榜 | `lhb_daily` |
| 板块异动热点 | AkShare 板块异动 | `market_hot_daily` |
| 盘中异动 | AkShare 个股异动 | `movement_alerts` |
| 核心个股日 K | AkShare 个股历史行情，含备用接口 | `stock_kline_daily` |
| 自动复盘结论 | 本地统计规则 | `daily_reviews` |

## 常用命令

迁移历史 JSON：

```bash
python src/migrate_json_to_db.py
```

抓取最近交易日并直接写入数据库：

```bash
python src/fetch_uplimit.py
```

查看数据库覆盖情况：

```bash
python src/db_inventory.py
```

补齐复盘缺失数据：

```bash
python src/fetch_missing_data.py
```

派生板块趋势、板块原因和核心股快照：

```bash
python src/derive_review_data.py
```

回补最近 20 个本地可识别交易日：

```bash
python src/fetch_daily_review.py --days 20 --kline-limit 5
```

只补某一天可历史回补的数据：

```bash
python src/fetch_missing_data.py --date 2026-06-05 --historical-only
```

只刷新最新实时快照：

```bash
python src/fetch_missing_data.py --date 2026-06-05 --realtime-only --kline-limit 0
```

运行测试：

```bash
python -m unittest tests/test_market_db.py -v
```
