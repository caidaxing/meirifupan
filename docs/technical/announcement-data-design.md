# 公告数据存储与采集方案

> 设计文档 | 最后更新: 2026-07-06

本文档说明 A 股公告数据怎么获取、怎么留存、怎么关联股票、怎么给前端展示。核心原则是：**列表、正文、解读、附件分开存**，不做一张难维护的大表。

## 1. 目标

公告模块要支持这些能力：

- 按日期查看公告列表。
- 按股票查看公告列表。
- 在复盘页、盘前页里关联涨停股、人气股、板块核心股。
- 点击公告后展示正文原文。
- 保留东财页面和 PDF 链接。
- 后续可以对业绩预告、并购重组、减持、增持、重大合同等公告做结构化解读。

## 2. 数据来源

### 2.1 公告列表

当前主来源：

```text
AkShare / 东方财富 stock_notice_report
底层接口: https://np-anotice-stock.eastmoney.com/api/security/ann
```

能拿到：

```text
代码
名称
公告标题
公告类型
公告日期
网址
```

示例：

```json
{
  "代码": "300497",
  "名称": "富祥股份",
  "公告标题": "富祥股份:2026年半年度业绩预告",
  "公告类型": "业绩预告",
  "公告日期": "2026-06-18",
  "网址": "https://data.eastmoney.com/notices/detail/300497/AN202606181823665476.html"
}
```

### 2.2 公告正文

公告详情页不是静态正文，正文来自东财接口：

```text
https://np-cnotice-stock.eastmoney.com/api/content/ann
```

请求参数：

```text
art_code=AN202606181823665476
client_source=web
page_index=1
```

能拿到：

```text
art_code
notice_title
notice_date
eitime
page_size
notice_content
attach_url_web
attach_list
raw_payload
```

其中 `notice_content` 是公告正文纯文本，`attach_url_web` 是 PDF 链接。

### 2.3 PDF 附件

正文接口会返回 PDF 链接，例如：

```text
https://pdf.dfcfw.com/pdf/H2_AN202606181823665476_1.pdf?1781797724000.pdf
```

注意：直接用脚本请求 PDF 链接时，东财可能返回反爬 HTML，而不是真 PDF。因此第一阶段只保证存 `pdf_url`，PDF 本地下载做成可选能力。

## 3. 存储分层

不要把所有数据塞进 `stock_announcements`。建议分四层：

| 层级 | 表/文件 | 用途 |
|---|---|---|
| 公告索引 | `stock_announcements` | 列表、筛选、关联股票 |
| 公告正文 | `stock_announcement_contents` | 原文、PDF 链接、接口原始数据 |
| 公告解读 | `stock_announcement_insights` | 摘要、影响方向、提取指标 |
| 附件文件 | `data/announcements/...` | 可选存 TXT/JSON/PDF |

这样做的好处：

- 列表查询轻，不被长正文拖慢。
- 正文可以按需抓取和缓存。
- 解读结果可以反复生成，不污染原文。
- PDF 文件不塞进 SQLite，避免数据库变大。

## 3.1 推荐存放位置

公告底层数据放在项目本地 `data/` 目录下：

```text
data/
  market_review.db              # SQLite 主库，存索引、正文、解读、路径
  announcements/                # 公告原始文件留存
    300030/
      2026-06-29/
        AN202606291826550774.json
        AN202606291826550774.txt
        AN202606291826550774.pdf
```

理由：

- `data/` 已经是项目的真实数据目录，和 `market_review.db`、历史 `uplimit` JSON 同级。
- `.gitignore` 已经忽略 `data/`，不会把大量正文、PDF、数据库误提交到代码仓库。
- `.dockerignore` 也忽略 `data/`，构建镜像时不会把本地数据打进去。
- SQLite 负责查询和关联，文件系统负责保存较大的原文、JSON、PDF。

不建议放的位置：

| 位置 | 不建议原因 |
|---|---|
| `docs/` | 这是项目文档目录，不适合放每日增长的真实数据 |
| `reports/` | 这里更适合放生成的复盘报告，不适合放公告底稿 |
| `web/public/` | 会暴露给前端静态访问，不适合存原始数据 |
| 一张 SQLite 大表 | 正文、PDF、AI 解读混在一起会导致查询慢、迁移难 |

底层数据保留策略：

- 公告列表原始行：保存在 `stock_announcements.raw_payload`。
- 正文接口原始 JSON：保存在 `stock_announcement_contents.raw_payload`，同时可落 `data/announcements/.../{art_code}.json`。
- 公告正文纯文本：保存在 `stock_announcement_contents.content_text`，同时可落 `data/announcements/.../{art_code}.txt`。
- PDF：只在确认文件头是 `%PDF` 时落 `data/announcements/.../{art_code}.pdf`；否则只保留 `pdf_url` 和失败状态。
- AI 解读：单独保存在 `stock_announcement_insights`，不能覆盖原文。

## 4. 表结构设计

### 4.1 公告索引表

当前已有 `stock_announcements`，建议扩展为：

```sql
create table if not exists stock_announcements (
    art_code text primary key,
    notice_date text not null,
    stock_code text,
    stock_name text,
    notice_type text,
    title text not null,
    source text not null default 'eastmoney',
    source_url text,
    pdf_url text,
    content_status text not null default 'pending',
    raw_payload text,
    created_at text not null default current_timestamp,
    updated_at text not null default current_timestamp
);

create index if not exists idx_stock_announcements_date
    on stock_announcements(notice_date);

create index if not exists idx_stock_announcements_stock
    on stock_announcements(stock_code, notice_date);

create index if not exists idx_stock_announcements_type
    on stock_announcements(notice_type, notice_date);
```

字段说明：

| 字段 | 说明 |
|---|---|
| `art_code` | 公告唯一 ID，例如 `AN202606181823665476` |
| `notice_date` | 公告日期 |
| `stock_code` | 股票代码 |
| `stock_name` | 股票名称 |
| `notice_type` | 公告类型，例如业绩预告、股东大会决议公告 |
| `title` | 公告标题 |
| `source` | 数据来源，默认 `eastmoney` |
| `source_url` | 东财公告页面 |
| `pdf_url` | PDF 链接 |
| `content_status` | 正文抓取状态：`pending` / `fetched` / `failed` |
| `raw_payload` | 列表接口原始数据 |

兼容现状：如果短期不想迁移主键，可以保留原来的 `primary key(notice_date, title)`，但必须补 `art_code` 并加唯一索引。

### 4.2 公告正文表

```sql
create table if not exists stock_announcement_contents (
    art_code text primary key,
    notice_title text,
    notice_date text,
    published_at text,
    page_size integer,
    content_text text,
    pdf_url text,
    source_url text,
    raw_payload text,
    fetched_at text not null default current_timestamp,
    created_at text not null default current_timestamp,
    updated_at text not null default current_timestamp,
    foreign key(art_code) references stock_announcements(art_code)
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| `art_code` | 对应公告 ID |
| `notice_title` | 正文接口返回的标题 |
| `notice_date` | 正文接口返回的公告日期 |
| `published_at` | 东财接口里的 `eitime`，发布时间 |
| `page_size` | 公告正文分页数 |
| `content_text` | 公告正文纯文本 |
| `pdf_url` | 正文接口返回的 PDF 链接 |
| `source_url` | 东财公告页面 |
| `raw_payload` | 正文接口原始 JSON |
| `fetched_at` | 抓取时间 |

### 4.3 公告解读表

```sql
create table if not exists stock_announcement_insights (
    art_code text primary key,
    stock_code text,
    notice_type text,
    summary text,
    key_points text,
    impact_level text,
    sentiment text,
    extracted_metrics text,
    related_themes text,
    generated_at text not null default current_timestamp,
    raw_payload text,
    foreign key(art_code) references stock_announcements(art_code)
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| `summary` | 一句话摘要 |
| `key_points` | JSON 数组，关键要点 |
| `impact_level` | `high` / `medium` / `low` |
| `sentiment` | `positive` / `neutral` / `negative` |
| `extracted_metrics` | JSON，对业绩、减持、回购等提取结构化指标 |
| `related_themes` | JSON，相关方向，例如新能源、并购、机器人 |

示例：

```json
{
  "summary": "2026年上半年预计扭亏为盈，净利润1.65亿-2.145亿元。",
  "key_points": [
    "归母净利润预计盈利1.65亿-2.145亿元",
    "同比增长2487%-3204%",
    "主要原因是VC/FEC产品量价齐增",
    "新能源业务成为核心增长引擎"
  ],
  "impact_level": "high",
  "sentiment": "positive",
  "extracted_metrics": {
    "net_profit_min": 165000000,
    "net_profit_max": 214500000,
    "yoy_min_pct": 2487,
    "yoy_max_pct": 3204
  },
  "related_themes": ["新能源", "电解液添加剂", "医药制造"]
}
```

## 5. 文件存储方案

正文可以存数据库，也可以同时落文件，便于人工排查。

建议路径：

```text
data/announcements/
  300030/
    2026-06-29/
      AN202606291826550774.json
      AN202606291826550774.txt
      AN202606291826550774.pdf
```

文件说明：

| 文件 | 是否必须 | 说明 |
|---|---|---|
| `.json` | 可选 | 正文接口原始返回 |
| `.txt` | 可选 | 公告正文纯文本 |
| `.pdf` | 可选 | 下载成功才保存 |

数据库里可以补路径字段：

```text
content_text_path
content_json_path
pdf_local_path
```

第一阶段建议先不加路径字段，先保证数据库里的 `content_text` 和 `raw_payload` 可用。

## 6. 数据获取流程

### 6.1 每日公告列表采集

入口：

```text
fetch_premarket.py -> fetch_announcement_records()
```

流程：

1. 调用 `ak.stock_notice_report(symbol="全部", date=YYYYMMDD)`。
2. 提取字段：代码、名称、公告标题、公告类型、公告日期、网址。
3. 从 `网址` 里解析 `art_code`。
4. 写入 `stock_announcements`。
5. `content_status` 初始为 `pending`。

伪代码：

```python
def fetch_announcement_records(notice_date):
    rows = ak.stock_notice_report(symbol="全部", date=yyyymmdd(notice_date))
    for row in rows:
        source_url = row["网址"]
        art_code = parse_art_code(source_url)
        yield {
            "art_code": art_code,
            "notice_date": notice_date,
            "stock_code": row["代码"],
            "stock_name": row["名称"],
            "notice_type": row["公告类型"],
            "title": row["公告标题"],
            "source_url": source_url,
            "content_status": "pending",
            "raw_payload": row,
        }
```

### 6.2 公告正文按需抓取

触发时机：

- 用户点击“展开原文”。
- 盘前任务对重点公告预抓取。
- 后台批处理补全文本。

流程：

1. 根据 `art_code` 查 `stock_announcement_contents`。
2. 如果已有 `content_text`，直接返回。
3. 如果没有，调用正文接口。
4. 写入 `stock_announcement_contents`。
5. 回写 `stock_announcements.content_status = 'fetched'`。

正文接口：

```text
GET https://np-cnotice-stock.eastmoney.com/api/content/ann
    ?art_code=AN202606181823665476
    &client_source=web
    &page_index=1
```

如果 `page_size > 1`，需要循环拉取 `page_index = 1..page_size`，再合并正文。

### 6.3 PDF 处理

正文接口会返回 `attach_url_web`，但脚本直连可能被反爬。

处理策略：

1. 必须存 `pdf_url`。
2. 尝试下载 PDF。
3. 下载后检查文件头是否为 `%PDF`。
4. 如果不是 PDF，不保存本地文件，记录 `pdf_download_status = failed`。
5. 页面仍保留“打开 PDF 链接”。

伪代码：

```python
def download_pdf(pdf_url):
    response = requests.get(pdf_url, headers=headers)
    if not response.content.startswith(b"%PDF"):
        return {"status": "failed", "reason": "not_pdf"}
    save_file(response.content)
    return {"status": "saved"}
```

## 7. 股票关联方式

### 7.1 直接关联

公告自带股票代码，直接关联：

```sql
select *
from stock_announcements a
where a.stock_code = ?;
```

### 7.2 和复盘数据关联

关联涨停股：

```sql
select a.*, e.up_limit_keep_times, e.reason
from stock_announcements a
join limit_up_events e
  on e.trade_date = a.notice_date
 and e.stock_code = a.stock_code
where a.notice_date = ?;
```

关联人气股：

```sql
select a.*, h.rank_no, h.hot_value
from stock_announcements a
join stock_hot_ranks h
  on h.trade_date = a.notice_date
 and h.stock_code = a.stock_code
where a.notice_date = ?;
```

### 7.3 和盘前日期关联

盘前指引通常是：

```text
guide_date = 今天
review_date = 上一交易日
```

因此公告列表应按 `review_date` 查：

```sql
select *
from stock_announcements
where notice_date = :review_date;
```

如果后续能稳定拿到公告发布时间，可以进一步做“盘后公告”：

```text
上一交易日 15:00 之后发布的公告
到当前盘前时间之前发布的公告
```

## 8. API 设计

### 8.1 日期公告列表

```text
GET /api/announcements?date=2026-07-03
```

返回：

```json
{
  "date": "2026-07-03",
  "items": [
    {
      "art_code": "AN202606181823665476",
      "stock_code": "300497",
      "stock_name": "富祥股份",
      "notice_type": "业绩预告",
      "title": "富祥股份:2026年半年度业绩预告",
      "source_url": "https://data.eastmoney.com/notices/detail/300497/AN202606181823665476.html",
      "pdf_url": "https://pdf.dfcfw.com/pdf/H2_AN202606181823665476_1.pdf?1781797724000.pdf",
      "content_status": "fetched"
    }
  ]
}
```

### 8.2 股票公告列表

```text
GET /api/stocks/300497/announcements
```

### 8.3 公告详情

```text
GET /api/announcements/AN202606181823665476
```

返回：

```json
{
  "art_code": "AN202606181823665476",
  "stock_code": "300497",
  "stock_name": "富祥股份",
  "notice_type": "业绩预告",
  "title": "富祥股份:2026年半年度业绩预告",
  "published_at": "2026-06-18 15:44:29",
  "content_text": "...",
  "pdf_url": "...",
  "source_url": "...",
  "insight": {
    "summary": "2026年上半年预计扭亏为盈，净利润1.65亿-2.145亿元。",
    "sentiment": "positive",
    "impact_level": "high"
  }
}
```

## 9. 前端展示方案

### 9.1 公告列表卡片

```text
富祥股份 300497
业绩预告 | 2026-06-18 | 15:44
富祥股份:2026年半年度业绩预告

预计净利润 1.65亿-2.145亿，同比 +2487%-3204%

[展开原文] [东财页面] [PDF]
```

### 9.2 公告详情抽屉

点击“展开原文”后，右侧抽屉展示：

```text
标题
股票代码 / 股票名称 / 公告类型 / 发布时间
摘要和关键点
正文原文
底部按钮：东财页面 / PDF
```

### 9.3 排序优先级

列表不应该简单按股票代码排序，建议优先级：

1. 当天涨停股相关公告。
2. 人气榜前排股票公告。
3. 高影响公告类型：业绩预告、并购重组、增持、减持、回购、重大合同、股权激励、监管函。
4. 普通股东大会、调研活动。
5. IPO 申报稿、法律意见书等低交易相关性公告。

## 10. 落地步骤

### 第 1 步：修公告列表字段

- 从 `网址` 解析 `art_code`。
- 将 `网址` 写入 `source_url`。
- 将正文接口返回的 `attach_url_web` 后续写入 `pdf_url`。

### 第 2 步：新增正文表

新增 `stock_announcement_contents`，保存原文和正文接口 JSON。

### 第 3 步：写正文抓取函数

新增：

```text
fetch_announcement_content(art_code)
```

功能：

- 请求东财正文接口。
- 处理分页。
- 保存正文。
- 更新 `content_status`。

### 第 4 步：加详情 API

新增：

```text
GET /api/announcements
GET /api/announcements/{art_code}
GET /api/stocks/{stock_code}/announcements
```

### 第 5 步：前端展示

- 公告列表卡片。
- 右侧原文抽屉。
- PDF / 东财页面按钮。

### 第 6 步：结构化解读

先从规则提取开始：

- 业绩预告：净利润区间、同比增速、扭亏/预增/预减。
- 减持：股东、减持比例、减持方式、时间区间。
- 增持：主体、金额、目的。
- 回购：金额区间、价格上限、用途。
- 并购重组：标的、交易金额、支付方式、进度。

后续再接 AI 摘要，写入 `stock_announcement_insights`。

## 11. 当前已验证样本

### 阳普医疗股东大会决议公告

```text
stock_code: 300030
stock_name: 阳普医疗
notice_type: 股东大会决议公告
title: 阳普医疗:2026年第一次临时股东会决议公告
art_code: AN202606291826550774
content_chars: 1797
```

正文接口可获取原文，已验证能保存为：

```text
data/announcements/300030/2026-06-29/AN202606291826550774.txt
data/announcements/300030/2026-06-29/AN202606291826550774.json
```

PDF 链接可获取，但脚本直连可能返回反爬 HTML，不能直接当成 PDF 保存。

### 富祥股份业绩预告

```text
stock_code: 300497
stock_name: 富祥股份
notice_type: 业绩预告
title: 富祥股份:2026年半年度业绩预告
art_code: AN202606181823665476
content_chars: 1475
```

正文里可提取：

```text
业绩预告期间：2026年1月1日至2026年6月30日
归母净利润：盈利 16,500 万元 - 21,450 万元
同比增长：2487% - 3204%
性质：扭亏为盈
原因：VC/FEC 产品量价齐增，新能源业务成为核心增长引擎
```

## 12. 结论

这个方案能做到：

- 公告列表长期留存。
- 公告原文长期留存。
- 原始接口 JSON 留存，方便以后重算。
- 解读结果单独留存，不污染原文。
- PDF 不塞数据库，下载成功才落文件。
- 每条公告可以稳定关联到股票、复盘日期、涨停股、人气股。

优先做列表字段修正和正文表，之后再做前端原文抽屉和结构化解读。
