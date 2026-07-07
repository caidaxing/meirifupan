# 复盘模块开发规范

本文是复盘模块开发前的统一规范。后续所有复盘模块代码、接口、类型、页面、测试和文档都按本文执行。若后续需要改规范，先改本文，再改代码。

## 1. 开发原则

### 1.1 先规范，后编码

开发顺序固定为：

```text
需求文档
数据可行性评估
开发规范
实现计划
测试
代码
验证
文档更新
```

任何新增页面、接口、采集任务都要先写清楚：

1. 做什么。
2. 需要什么字段。
3. 字段从哪里来。
4. 缺字段时怎么降级。
5. 怎么验证。

### 1.2 不把外部页面当成产品边界

Quantzz 页面只作为参考。我们复刻的是能力，不复刻品牌、样式和代码。

页面结构可以参考，但最终以本项目自己的使用场景为准：

```text
盘后复盘
盘前准备
盘中观察
数据留存
```

### 1.3 前端不直接关心外部数据源

前端只能调用本项目后端接口。

不允许前端直接请求：

```text
Quantzz
扶摇
AkShare
东方财富
同花顺
其他第三方接口
```

外部数据源全部封装在后端采集层或服务层。

### 1.4 接口稳定优先

后端接口返回结构一旦被前端使用，字段名不要随意改。必须改时：

1. 先兼容旧字段。
2. 前端切换到新字段。
3. 确认无引用后再删除旧字段。

## 2. 命名规范

### 2.1 日期字段

统一使用：

| 字段 | 用途 |
| --- | --- |
| `date` | 接口请求和响应中的当前日期 |
| `trade_date` | 数据库存储中的交易日 |
| `base_date` | 晋级模块的基准日 |
| `target_date` | 晋级模块的观察日 |
| `start_date` | 区间开始日 |
| `end_date` | 区间结束日 |

日期格式统一：

```text
YYYY-MM-DD
```

### 2.2 股票字段

统一使用：

| 字段 | 用途 |
| --- | --- |
| `stock_code` | 当前项目兼容字段，通常为 `600519` |
| `ticker` | 纯代码，和 `stock_code` 同义时优先保留 `stock_code` |
| `thscode` | 标准代码，例如 `600519.SH` |
| `stock_name` | 股票名称 |
| `market_tag` | 沪、深、创、科、北 |

第一阶段允许 `thscode` 为空，但接口结构必须预留。

### 2.3 题材字段

统一使用：

| 字段 | 用途 |
| --- | --- |
| `plate_code` | 题材或板块代码 |
| `plate_name` | 题材或板块名称 |
| `plate_type` | 概念、行业、地域、风格等 |
| `plate_score` | 题材强度分 |

不要混用 `board_name`、`concept_name`、`plate` 作为同一含义的字段。外部字段进入后端后统一转换为 `plate_*`。

### 2.4 百分比和金额

后端返回原始数值，前端负责格式化。

| 类型 | 后端单位 | 前端展示 |
| --- | --- | --- |
| 百分比 | `10.23` | `10.23%` |
| 金额 | 元 | 万、亿自动格式化 |
| 成交量 | 股 | 万股、亿股自动格式化 |

字段名约定：

```text
*_pct       百分比
*_amount    金额
*_volume    成交量
*_count     数量
*_rate      比率
```

## 3. 后端接口规范

### 3.1 路由前缀

复盘模块新增接口统一放在：

```text
/api/review/*
```

已有接口可以继续保留：

```text
/api/review
/api/insights
/api/plate-rotation
```

但新的复盘子页面优先使用新的聚合接口。

### 3.2 标准响应结构

所有复盘子接口都返回：

```json
{
  "date": "2026-06-24",
  "status": "ok",
  "updated_at": "2026-06-24T17:30:00+08:00",
  "summary": {},
  "filters": {},
  "items": [],
  "warnings": []
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `date` | 是 | 当前交易日 |
| `status` | 是 | `ok`、`partial`、`empty`、`error` |
| `updated_at` | 否 | 数据更新时间 |
| `summary` | 是 | 页面顶部汇总 |
| `filters` | 是 | 可用筛选项 |
| `items` | 是 | 主数据 |
| `warnings` | 是 | 数据缺失、降级说明 |

### 3.3 状态定义

| 状态 | 含义 |
| --- | --- |
| `ok` | 核心数据完整 |
| `partial` | 页面可展示，但有部分字段缺失 |
| `empty` | 当日无数据 |
| `error` | 数据无法正常读取 |

页面可以展示 `partial`，但必须显示 `warnings`。

### 3.4 错误处理

后端不要把外部接口错误原样抛给前端。

统一转换为：

```json
{
  "detail": {
    "message": "No review data for date 2026-06-24",
    "code": "REVIEW_DATA_NOT_FOUND"
  }
}
```

错误码使用大写下划线：

```text
REVIEW_DATA_NOT_FOUND
INVALID_DATE
SOURCE_UNAVAILABLE
DATABASE_ERROR
```

### 3.5 接口列表

第一阶段需要的接口：

| 接口 | 页面 | 说明 |
| --- | --- | --- |
| `/api/review/workbench` | 公共 | 复盘模块总状态 |
| `/api/review/limit-up-reasons` | 涨停原因 | 题材分组涨停明细 |
| `/api/review/limit-up-tiers` | 涨停梯队 | 题材 x 连板矩阵 |
| `/api/review/price-tiers` | 涨幅梯队 | 10/20/30 天涨幅分层 |
| `/api/review/promotions` | 晋级 | 昨日涨停今日反馈 |
| `/api/review/plate-rotation` | 题材轮动 | 多日题材强度 |
| `/api/review/lhb` | 龙虎榜 | 龙虎榜资金与席位 |
| `/api/review/movement-alerts` | 异动 | 交易所异动风险 |

### 3.6 参数规范

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `date` | string | 必填 | 交易日 |
| `days` | int | 10 | 窗口天数 |
| `top_n` | int | 12 | 展示数量 |
| `plate_code` | string | 空 | 题材过滤 |
| `stock_code` | string | 空 | 股票过滤 |
| `view` | string | 空 | 页面视图 |
| `trigger_filter` | string | `all` | 异动筛选 |

参数校验在 API 层完成。

## 4. 后端代码规范

### 4.1 文件职责

复盘模块按这个边界写：

| 文件 | 职责 |
| --- | --- |
| `server/api/review.py` | 只放路由，不写复杂 SQL |
| `server/services/review_queries.py` | 数据库查询 |
| `server/services/review_workbench.py` | 复盘模块聚合和计算 |
| `src/db.py` | 表结构和入库 |
| `src/api_client.py` | Quantzz 客户端 |
| `src/fuyao_client.py` | 扶摇客户端，后续新增 |

如果一个函数超过 80 行，优先拆小函数。

### 4.2 查询函数命名

统一格式：

```python
get_review_limit_up_reasons(...)
get_review_limit_up_tiers(...)
get_review_price_tiers(...)
get_review_promotions(...)
get_review_plate_rotation(...)
get_review_lhb(...)
get_review_movement_alerts(...)
```

### 4.3 计算函数命名

统一格式：

```python
build_limit_up_reason_payload(...)
build_limit_up_tier_matrix(...)
calculate_price_tiers(...)
calculate_promotion_feedback(...)
build_plate_rotation_payload(...)
summarize_lhb(...)
calculate_movement_trigger_risk(...)
```

### 4.4 SQL 规范

1. SQL 放在查询函数里，不放 API 路由里。
2. SQL 参数必须使用占位符，不能字符串拼接。
3. 返回字段用明确别名，尽量和前端类型一致。
4. 查询结果统一转成普通 `dict`。
5. 多处复用的日期查询走公共函数。

## 5. 前端规范

### 5.1 页面结构

复盘模块入口：

```text
web/src/components/review/ReviewWorkbench.tsx
```

建议目录：

```text
web/src/components/review/
  ReviewWorkbench.tsx
  ReviewSubTabs.tsx
  ReviewDataStatus.tsx
  LimitUpReasonPage.tsx
  LimitUpTierPage.tsx
  PriceTierPage.tsx
  PromotionPage.tsx
  PlateRotationReviewPage.tsx
  LhbReviewPage.tsx
  MovementAlertPage.tsx
  StockDrawer.tsx
```

公共小组件如果只有复盘模块使用，放在 `web/src/components/review/` 下。跨模块使用，再移动到 `web/src/components/`。

### 5.2 前端类型

复盘模块类型统一写在：

```text
web/src/types/review.ts
```

如果短期不拆文件，也可以先放在 `web/src/types/index.ts`，但新增类型要用 `Review` 前缀避免混乱。

示例：

```typescript
export interface ReviewApiEnvelope<TSummary, TItem> {
  date: string
  status: 'ok' | 'partial' | 'empty' | 'error'
  updated_at?: string | null
  summary: TSummary
  filters: Record<string, unknown>
  items: TItem[]
  warnings: string[]
}
```

### 5.3 API 客户端

复盘模块请求统一写在：

```text
web/src/api/client.ts
```

函数命名：

```typescript
fetchReviewWorkbench(...)
fetchReviewLimitUpReasons(...)
fetchReviewLimitUpTiers(...)
fetchReviewPriceTiers(...)
fetchReviewPromotions(...)
fetchReviewPlateRotation(...)
fetchReviewLhb(...)
fetchReviewMovementAlerts(...)
```

### 5.4 UI 风格

当前项目是工作台，不做营销页。

页面要求：

1. 信息密度高，但不要拥挤。
2. 使用表格、矩阵、折线、标签，不用大面积装饰卡片。
3. 子页面之间保持统一顶部结构。
4. 重要数字用颜色，但不要只靠颜色表达含义。
5. 移动端可以简化，但不能文字重叠。

### 5.5 空状态

每个子页面必须有空状态：

```text
暂无数据
数据部分缺失
当前日期没有该类数据
```

不要让页面白屏。

## 6. 数据规范

### 6.1 原始数据保留

新增采集任务必须保留原始返回：

```text
raw_payload
```

用于追查字段变化和重算。

### 6.2 数据新鲜度

展示数据时必须能知道：

| 字段 | 说明 |
| --- | --- |
| `trade_date` | 数据所属交易日 |
| `updated_at` | 本地更新时间 |
| `source` | 数据来源 |

第一版如果没有 `updated_at`，接口要在 `warnings` 里说明。

### 6.3 降级规则

缺字段时按这个顺序处理：

1. 从本地已有表计算。
2. 从备用数据源补。
3. 返回 `null`，前端显示 `-`。
4. 在 `warnings` 写明缺失字段。

禁止用假数据填充缺失字段。

## 7. 测试规范

### 7.1 后端测试

新增后端行为必须先写测试。

测试文件放在：

```text
tests/
```

命名：

```text
tests/test_review_workbench.py
tests/test_review_promotions.py
tests/test_review_price_tiers.py
```

每个聚合函数至少覆盖：

1. 正常数据。
2. 空数据。
3. 部分字段缺失。
4. 日期边界。

### 7.2 前端测试

如果当前项目没有前端测试框架，第一阶段至少做：

1. TypeScript 构建检查。
2. 页面手动截图验证。
3. API 返回 mock 的最小渲染检查，后续再补自动化。

### 7.3 验证命令

每次开发结束前至少运行：

```bash
python -m unittest tests/test_market_db.py -v
```

如果新增测试，运行对应测试文件：

```bash
python -m unittest tests/test_review_workbench.py -v
```

前端改动后运行：

```bash
cd web
npm run build
```

## 8. 文档规范

每个开发阶段都要在 `docs/plans/` 下留文档。

文件名：

```text
YYYY-MM-DD-review-module-阶段名.md
```

每份文档包含：

1. 本次目标。
2. 涉及文件。
3. 新增接口。
4. 数据库变化。
5. 前端变化。
6. 测试结果。
7. 未解决问题。

## 9. 提交规范

如果需要提交 Git，提交信息使用：

```text
feat: add review workbench shell
feat: add review limit-up reasons endpoint
test: cover review promotion feedback
docs: add review module development standards
```

每次提交只做一类事情。

## 10. 第一阶段执行口径

第一阶段只做“复盘模块框架 + 已有数据能直接支撑的页面”。

可以做：

```text
复盘 7 子 Tab
涨停原因
涨停梯队
晋级基础版
题材轮动基础版
龙虎榜基础版
普通异动基础版
缺失数据提示
```

先不做：

```text
交易所异动精确触发价
完整涨幅梯队全市场计算
龙虎榜脑图
席位历史详情
股票详情抽屉完整 K 线
```

这些不删除，只放入后续阶段。
