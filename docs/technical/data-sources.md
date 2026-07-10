# 数据渠道全景

> 维护文档 | 最后更新: 2026-07-03

本文档记录项目所有数据获取渠道的来源、方式、认证、可靠性和调度。新增或变更数据源时请同步更新本文档。

---

## 一、总览

| 来源 | 渠道数 | 认证方式 | 可靠性 |
|------|--------|----------|--------|
| **Quantzz API** (`api.zizizaizai.com`) | 9 | Bearer token（邮箱密码登录） | Token 会过期；SSL 已禁用验证 |
| **Fuyao API** (`fuyao.aicubes.cn`) | 6 | API key（`X-api-key` header） | 可选，无 key 自动跳过 |
| **AkShare / 东方财富** | 12 | 公开 | 最稳定的免费源；部分接口有 IP 封禁风险 |
| **AkShare / 同花顺** | 4 | 公开 | 行业板块、概念板块、板块K线 |
| **AkShare / 新浪** | 2 | 公开 | 交易日历兜底、实时行情 |
| **AkShare / CCTV** | 1 | 公开 | 新闻兜底链末端 |
| **财联社** (`cls.cn`) | 1 | 签名请求（SHA1+MD5） | 主新闻源；版本号门控 |
| **腾讯** (`qt.gtimg.cn`) | 1 | 公开 | 美股兜底 |
| **东财 emappdata** | 1 | 公开（硬编码 ID） | 人气股兜底 |
| **同花顺热搜** (`dq.10jqka.com.cn`) | 1 | 公开（伪造 UA/Referer） | 4 种排行变体 |
| **本地派生** | 4 | 无 | 纯 SQL 聚合 |

---

## 二、按领域分述

### 1. 涨停数据

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 1 | **Fuyao API** | 涨停池（原因、封单、连板） | REST API | API key | 无 key 或失败时降级 Quantzz | limit_up_events, limit_up_plate_map | 每日 17:30 |
| 2 | Quantzz | 涨停原因、涨停梯队、热门板块、板块排名 | REST API | Bearer token | Fuyao 不可用时触发；401 时降级 AkShare | limit_up_events, limit_up_plate_map, plate_hot_rank, plate_daily | 降级触发 |
| 3 | AkShare / 东财 `stock_zt_pool_em` | 涨停池：代码、名称、价格、封板时间、连板数、封单额 | AkShare 封装 | 公开 | 最终兜底 | limit_up_events, limit_up_plate_map | 兜底触发 |
| 3b | Fuyao API | 涨停梯队、异动分析 | REST API | API key | 无 key 跳过 | fuyao_limit_up_ladder, fuyao_anomaly_reasons | 每日 17:30 |

### 2. 大盘结构

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 4 | AkShare / 新浪 `stock_zh_a_spot` | 全 A 股实时快照：价格、涨跌幅、成交额、换手率 | AkShare 封装 | 公开 | 无 | market_breadth_daily, hot_stocks | 每日 17:30 + 盘中实时 |
| 5 | AkShare / 东财 `stock_market_fund_flow` | 全市场成交额（主力净流入推算） | AkShare 封装 | 公开 | 重试 3 次后直连东财 push2his | market_breadth_daily | 每日 17:30 |
| 6 | AkShare / 东财 `stock_zh_index_daily` | 四大指数日 K（上证、深成、创业板、北证50） | AkShare 封装 | 公开 | 无 | market_index_daily | 每日 17:30 |
| 7 | Quantzz `/v3/market/index/trends` | 指数实时趋势 | REST API | Bearer token | 无 | market_index_daily | 每日 17:30 |

### 3. 跌停 & 炸板

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 8 | AkShare / 东财 `stock_zt_pool_dtgc_em` | 跌停池：代码、价格、涨跌幅、封板时间、开板次数、行业 | AkShare 封装 | 公开 | 无 | limit_down_events | 每日 17:30 + 盘中实时 |
| 9 | AkShare / 东财 `stock_zt_pool_zbgc_em` | 炸板池：代码、价格、首次封板时间、开板次数、振幅、行业 | AkShare 封装 | 公开 | 无 | broken_limit_up_events | 每日 17:30 + 盘中实时 |

### 4. 板块 & 轮动

> ⚠️ Fuyao 无板块轮动端点（已确认），继续使用 Quantzz。Fuyao 有指数行情快照和历史 K 线，可用于板块指数展示。

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 10 | Quantzz `/market/plates/17/rank*` | 板块轮动排名（多日）、趋势、原因、成分股 | REST API | Bearer token | rank/days 失败降级 rank | plate_rotation_* | 每日 17:30 |
| 11 | AkShare / 同花顺 `stock_board_concept/industry_name_ths` | 板块名称列表（用于符号解析） | AkShare 封装 | 公开 | 无 | 仅查询用 | 按需 |
| 12 | AkShare / 同花顺 `stock_board_*_index_ths` | 板块指数日 K（OHLCV） | AkShare 封装 | 公开 | 跳过解析失败的板块 | plate_index_daily | 每日 17:30 |
| 13 | AkShare / 东财 `stock_board_concept_name_em` | 概念板块排名（价格、涨跌幅、市值、领涨股） | AkShare 封装 | 公开 | 降级到同花顺概念列表 | hot_boards (concept) | 每日 17:30 |
| 14 | AkShare / 同花顺 `stock_board_industry_summary_ths` | 行业板块排名（涨跌幅、涨跌家数、领涨股） | AkShare 封装 | 公开 | 无需兜底 | hot_boards (industry) | 每日 17:30 |

### 5. 热门 & 人气

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 15 | AkShare / 东财 `stock_hot_rank_em` | 东财人气榜 TOP100（价格、涨跌幅、成交额） | AkShare 封装 | 公开 | 降级到 emappdata 直连 | hot_stocks | 每日 17:30 |
| 16 | 东财 emappdata 直连 | 人气排名（仅代码+排名） | POST 直连 | 公开（硬编码 ID） | 兜底；用 DB 和新浪补全价格 | hot_stocks | 兜底触发 |
| 17 | 同花顺热搜 `dq.10jqka.com.cn` | 同花顺热搜榜：日/小时、普通/飙升；热度值、排名变化、概念标签 | REST GET（伪造 UA） | 公开 | 无 | stock_hot_ranks (ths_hot) | 每日 17:30 |
| 18 | 派生：短线热榜 | 综合短线热度排名（涨停+同花顺+东财加权，扣减炸板/跌停） | 本地 SQL 计算 | 无 | 无 | stock_hot_ranks (shortline_hot) | 每日 17:30 |
| 18b | **Fuyao** `/api/a-share/special-data/hot-stock-list` | 热股榜单（日/小时，含热度、排名变化、标签） | REST API | API key | 无 key 跳过 | 待接入 | 待接入 |
| 18c | **Fuyao** `/api/a-share/special-data/skyrocket-list` | 飙升榜（日/小时） | REST API | API key | 无 key 跳过 | 待接入 | 待接入 |
| 18d | **Fuyao** `/api/a-share/special-data/hot-stock-list-history` | 历史热股排行（指定日期） | REST API | API key | 无 key 跳过 | 待接入 | 待接入 |
| 18e | **Fuyao** `/api/a-share/special-data/hot-stock-rank-trend` | 个股排名走势（日期范围） | REST API | API key | 无 key 跳过 | 待接入 | 待接入 |

### 6. 情绪数据

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 19 | Quantzz `/v2/api/sentiment/kline/day/{period}` | 情绪 K 线（涨停数、跌停数、最高板） | REST API | Bearer token | 无 | sentiment_daily | 每日 17:30 |
| 20 | Quantzz `/v3/api/sentiment/market/hot/day` | 市场热度数据 | REST API | Bearer token | 无 | 仅用于 uplimit 流程 | 每日 17:30 |

### 7. 异动

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 21 | AkShare / 东财 `stock_changes_em` | 9 类异动（大笔买入/卖出、火箭发射、高台跳水等），每类最多 80 条 | AkShare 封装 | 公开 | 跳过失败类型继续 | movement_alerts | 每日 17:30 + 盘中实时 |
| 22 | Quantzz `/market/movement/alerts` | Quantzz 异动数据 | REST API | Bearer token | 无 | movement_alerts | 每日 17:30 |

### 8. 龙虎榜

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 23 | AkShare / 东财 `stock_lhb_detail_em` | 龙虎榜明细：个股、原因、买卖额、净买额 | AkShare 封装 | 公开 | 无 | lhb_daily | 每日 17:30 |
| 24 | Quantzz `/market/lhb/list` | Quantzz 龙虎榜 | REST API | Bearer token | 无 | lhb_daily | 每日 17:30 |
| 24b | **Fuyao** `/api/a-share/special-data/dragon-tiger-list` | 龙虎榜（含机构/游资拆分、净买入额） | REST API | API key | 无 key 跳过 | 待接入 | 待接入 |

### 9. 个股 K 线

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 25 | AkShare / 东财/新浪 `stock_zh_a_hist` / `stock_zh_a_daily` | 核心股日 K（OHLCV），每日约 30 只 | AkShare 封装 | 公开 | hist 失败降级 daily | stock_kline_daily | 每日 17:30 |
| 26 | Quantzz `/open/kline/d/{code}` | Quantzz 个股日 K | REST API | Bearer token | 无 | stock_kline_daily | 每日 17:30 |

### 10. 新闻 & 公告

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 27 | 财联社 `cls.cn/v1/roll/get_roll_list` | 财联社电报（标题、内容、时间、URL） | REST GET（SHA1+MD5 签名） | 公开（签名） | 降级东财/新浪/CCTV | premarket_news | 盘前 08:30 |
| 28 | AkShare / 东财 `stock_info_global_em` | 东财全球快讯 | AkShare 封装 | 公开 | 降级新浪 | premarket_news | 盘前 08:30 |
| 29 | AkShare / 新浪 `stock_info_global_sina` | 新浪财经新闻 | AkShare 封装 | 公开 | 降级 CCTV | premarket_news | 盘前 08:30 |
| 30 | AkShare / CCTV `news_cctv` | CCTV 新闻联播 | AkShare 封装 | 公开 | 链末端 | premarket_news | 盘前 08:30 |
| 31 | AkShare / 东财 `stock_notice_report` | A 股公司公告（个股、类型、标题、URL） | AkShare 封装 | 公开 | 失败返回空 | stock_announcements | 盘前 08:30 |

### 10.1 个股研报

| 来源 | 采集内容 | 方式 | 认证 | 存储 |
|---|---|---|---|---|
| 东方财富 `reportapi.eastmoney.com/report/list2` | 个股研报列表、股票、机构、分析师、评级、盈利预测 | POST JSON 分页 | 公开 | `stock_research_reports`、`stock_research_report_authors`、`stock_research_report_forecasts` |
| 东方财富 `data.eastmoney.com/report/info/{info_code}.html` | 研报摘要、详情原始 JSON、PDF 地址 | HTML 中解析 `zwinfo` | 公开 | `stock_research_report_contents` |
| 东方财富 `pdf.dfcfw.com` | 研报 PDF 原文 | 下载后校验并原子落盘 | 公开 | `data/research_reports/YYYY/MM/DD/{info_code}.pdf` |

首轮回补最近 30 个自然日；增量任务每日 `07:30`、`19:30` 执行，每次覆盖最近 2 个自然日并补抓失败项。

### 11. 隔夜美股

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 32 | AkShare / 东财 `stock_us_famous_spot_em` | 美股知名股（6 大板块 14 只） | AkShare 封装 | 公开 | 降级腾讯 | us_stock_quotes | 盘前 08:30 |
| 33 | 腾讯 `qt.gtimg.cn` | 14 只核心美股行情 | REST GET（GBK 解码） | 公开 | IS the fallback | us_stock_quotes | 兜底触发 |

### 12. 交易日历

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 34 | Quantzz `/market/trade/days` | 交易日列表 | REST API | Bearer token | 降级 AkShare 新浪日历 | trade_calendar | 每日 17:30 |
| 35 | AkShare / 新浪 `tool_trade_date_hist_sina` | 历史交易日历 | AkShare 封装 | 公开 | 降级本地 DB 日期 | trade_calendar | 兜底触发 |

### 13. Fuyao 补充数据

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 36 | Fuyao `/limit-up-ladder` | 涨停梯队（晋级/淘汰） | REST API | API key | 无 key 跳过 | fuyao_limit_up_ladder | 每日 17:30 |
| 37 | Fuyao `/anomaly-analysis-stock` | 个股异动分析（标签、内容、关键词） | REST API | API key | 无 key 跳过 | fuyao_anomaly_reasons | 每日 17:30 |
| 38 | Fuyao `/prices/snapshot` | 涨停股价格快照 | REST API | API key | 无 key 跳过 | fuyao_stock_snapshots | 每日 17:30 |
| 39 | Fuyao `/ths-index-list` | 同花顺指数目录（概念、行业） | REST API | API key | 无 key 跳过 | fuyao_ths_index_catalog | 每日 17:30 |
| 40 | Fuyao `/ths-stock-list` | 同花顺指数成分股 | REST API | API key | 无 key 跳过 | fuyao_ths_index_constituents | 每日 17:30 |

### 14. 盘中实时情绪

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 41 | 综合实时 | 大盘涨跌、涨停/跌停/炸板、异动、人气股、连板梯队、情绪评分 | 调用 AkShare + Fuyao 多源合并 | 公开 + API key | 每个源独立失败，source_status 追踪 | 仅内存（API 返回） | 盘中按需（45s 刷新） |

### 15. 本地派生

| # | 来源 | 采集内容 | 方式 | 认证 | 兜底策略 | 存储表 | 调度 |
|---|------|----------|------|------|----------|--------|------|
| 42 | 派生：板块趋势 | 板块涨停数趋势、封单额、代表股 | SQL 聚合 | 无 | 无 | plate_trends | 每日 17:30 |
| 43 | 派生：板块原因 | 板块涨停原因汇总 | SQL 聚合 | 无 | 无 | plate_reasons | 每日 17:30 |
| 44 | 派生：个股快照 | 核心股综合快照（复盘+涨停+板块+K线+龙虎榜） | SQL 多表 JOIN | 无 | 无 | stock_info_snapshots | 每日 17:30 |

---

## 三、调度汇总

| 时间 | 任务 | 入口 |
|------|------|------|
| **08:30** | 盘前更新（新闻、公告、美股、生成盘前指引） | `premarket_update.py` → `daily_scheduler.py` |
| **17:30** | 每日更新（15 步流水线：涨停、Fuyao、情绪、历史数据、实时数据、大盘趋势、热门股、热门板块、题材轮动、短线热榜、板块K线、派生数据、生成复盘） | `daily_update.py` → `daily_scheduler.py` |
| **盘中按需** | 实时情绪（服务端端点，45s 刷新） | `server/services/realtime_emotion.py` |
| **按需** | 历史回填（20 天复盘数据） | `fetch_daily_review.py` |

---

## 四、认证配置

| 来源 | 配置位置 | 环境变量 | 配置文件 |
|------|----------|----------|----------|
| Quantzz | `config/token.json` 或环境变量 | `QUANTZZ_TOKEN`, `QUANTZZ_EMAIL`, `QUANTZZ_PASSWORD` | `config/quantzz_token.json` |
| Fuyao | `.env` 文件 | `FUYAO_API_KEY` | `.env` |
| 其他 | 无需配置 | 无 | 无 |

---

## 五、已知风险

| 风险 | 影响范围 | 缓解措施 |
|------|----------|----------|
| 东财 push2 IP 封禁 | 涨停数据、人气榜 | 有 AkShare → 直连东财两级兜底 |
| Quantzz token 过期 | 9 个端点全部受影响 | 401 检测后自动降级 AkShare |
| 同花顺热搜 UA 检测 | 热搜榜 4 个变体 | 伪造 UA + Referer；无兜底 |
| 财联社签名变更 | 新闻源 | 降级东财/新浪/CCTV 三级兜底 |
| Fuyao API 不可用 | 补充数据（梯队、异动分析） | 无 key 时自动跳过，不影响主流程 |
