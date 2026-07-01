# 复盘模块第一阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做出复盘模块第一阶段：7 个子 Tab 的页面框架，以及已有数据能支撑的基础页面。

**Architecture:** 后端先新增复盘模块聚合接口，接口返回统一 envelope；前端新增 `ReviewWorkbench` 作为复盘入口，内部用 7 个子 Tab 承载页面。第一阶段不补全市场 K 线，不做交易所异动精确计算，缺口通过 `warnings` 显示。

**Tech Stack:** FastAPI、SQLite、React、TypeScript、Vite、Python unittest。

---

## 1. 文档依据

开发必须遵守：

| 文档 | 用途 |
| --- | --- |
| `docs/review-module-implementation-spec.md` | 定义要做什么 |
| `docs/review-module-development-standards.md` | 定义开发规范 |
| `docs/review-module-data-feasibility.md` | 定义第一阶段范围和数据缺口 |

## 2. 第一阶段范围

第一阶段做：

1. 复盘模块 7 子 Tab。
2. 涨停原因基础版。
3. 涨停梯队基础版。
4. 晋级基础版。
5. 题材轮动基础版。
6. 龙虎榜基础版。
7. 普通异动基础版。
8. 涨幅梯队占位和缺口提示。

第一阶段不做：

1. 完整全市场涨幅梯队。
2. 交易所异动精确触发价。
3. 龙虎榜脑图。
4. 席位历史详情。
5. 股票详情抽屉完整 K 线。

## 3. 文件计划

### 3.1 后端

| 文件 | 动作 | 说明 |
| --- | --- | --- |
| `server/services/review_queries.py` | 修改 | 增加复盘模块查询函数 |
| `server/api/review.py` | 修改 | 增加 `/api/review/*` 子接口 |
| `tests/test_review_module.py` | 新增 | 测试复盘聚合函数 |

### 3.2 前端

| 文件 | 动作 | 说明 |
| --- | --- | --- |
| `web/src/types/index.ts` | 修改 | 增加复盘模块类型 |
| `web/src/api/client.ts` | 修改 | 增加复盘模块请求函数 |
| `web/src/hooks/useReview.ts` | 修改 | 增加复盘模块 hooks |
| `web/src/components/LimitUpReview.tsx` | 修改 | 改成复盘工作台入口或引入新入口 |
| `web/src/components/review/ReviewWorkbench.tsx` | 新增 | 复盘模块总入口 |
| `web/src/components/review/ReviewSubTabs.tsx` | 新增 | 7 个子 Tab |
| `web/src/components/review/LimitUpReasonPage.tsx` | 新增 | 涨停原因基础版 |
| `web/src/components/review/LimitUpTierPage.tsx` | 新增 | 涨停梯队基础版 |
| `web/src/components/review/PriceTierPage.tsx` | 新增 | 涨幅梯队占位 |
| `web/src/components/review/PromotionPage.tsx` | 新增 | 晋级基础版 |
| `web/src/components/review/PlateRotationReviewPage.tsx` | 新增 | 题材轮动基础版 |
| `web/src/components/review/LhbReviewPage.tsx` | 新增 | 龙虎榜基础版 |
| `web/src/components/review/MovementAlertPage.tsx` | 新增 | 普通异动基础版 |

## 4. 后端任务

### Task 1: 后端 envelope 和空数据约定

**Files:**
- Modify: `server/services/review_queries.py`
- Test: `tests/test_review_module.py`

- [ ] **Step 1: 写失败测试**

测试目标：复盘接口 payload 必须包含 `date/status/summary/filters/items/warnings`。

命令：

```bash
python -m unittest tests/test_review_module.py -v
```

期望：失败，因为测试文件和函数还不存在。

- [ ] **Step 2: 增加公共 envelope helper**

在 `server/services/review_queries.py` 增加：

```python
def make_review_payload(date: str, summary: dict, items: list, filters: dict | None = None, warnings: list[str] | None = None, status: str = "ok") -> dict:
    return {
        "date": date,
        "status": status,
        "summary": summary,
        "filters": filters or {},
        "items": items,
        "warnings": warnings or [],
    }
```

- [ ] **Step 3: 跑测试**

命令：

```bash
python -m unittest tests/test_review_module.py -v
```

期望：通过新增 envelope 测试。

### Task 2: 涨停原因接口数据

**Files:**
- Modify: `server/services/review_queries.py`
- Modify: `server/api/review.py`
- Test: `tests/test_review_module.py`

- [ ] **Step 1: 写失败测试**

测试目标：`get_review_limit_up_reasons(conn, date)` 返回题材分组，且股票包含代码、名称、原因、板高、时间。

- [ ] **Step 2: 实现查询函数**

函数名：

```python
get_review_limit_up_reasons(conn: sqlite3.Connection, date: str) -> dict
```

数据来源：

```text
limit_up_events
limit_up_plate_map
plate_hot_rank
```

- [ ] **Step 3: 增加 API**

路径：

```text
GET /api/review/limit-up-reasons?date=YYYY-MM-DD
```

- [ ] **Step 4: 跑测试**

命令：

```bash
python -m unittest tests/test_review_module.py -v
```

### Task 3: 涨停梯队接口数据

**Files:**
- Modify: `server/services/review_queries.py`
- Modify: `server/api/review.py`
- Test: `tests/test_review_module.py`

- [ ] **Step 1: 写失败测试**

测试目标：`get_review_limit_up_tiers(conn, date)` 返回按板高分层的数据，并包含炸板层 warnings 或 items。

- [ ] **Step 2: 实现查询函数**

函数名：

```python
get_review_limit_up_tiers(conn: sqlite3.Connection, date: str, top_n: int = 12) -> dict
```

数据来源：

```text
limit_up_events
limit_up_plate_map
plate_hot_rank
broken_limit_up_events
```

- [ ] **Step 3: 增加 API**

路径：

```text
GET /api/review/limit-up-tiers?date=YYYY-MM-DD&top_n=12
```

### Task 4: 晋级基础版接口

**Files:**
- Modify: `server/services/review_queries.py`
- Modify: `server/api/review.py`
- Test: `tests/test_review_module.py`

- [ ] **Step 1: 写失败测试**

测试目标：`get_review_promotions(conn, date)` 使用前一交易日做分母，返回总晋级率和按板高统计。

- [ ] **Step 2: 实现查询函数**

函数名：

```python
get_review_promotions(conn: sqlite3.Connection, date: str) -> dict
```

数据来源：

```text
limit_up_events
broken_limit_up_events
limit_down_events
```

- [ ] **Step 3: 增加 API**

路径：

```text
GET /api/review/promotions?date=YYYY-MM-DD
```

### Task 5: 龙虎榜和普通异动基础接口

**Files:**
- Modify: `server/services/review_queries.py`
- Modify: `server/api/review.py`
- Test: `tests/test_review_module.py`

- [ ] **Step 1: 写失败测试**

测试目标：龙虎榜返回股票级列表和净买入汇总；普通异动返回类型汇总和列表。

- [ ] **Step 2: 实现龙虎榜函数**

函数名：

```python
get_review_lhb(conn: sqlite3.Connection, date: str) -> dict
```

数据来源：

```text
lhb_daily
limit_up_events
limit_up_plate_map
```

- [ ] **Step 3: 实现普通异动函数**

函数名：

```python
get_review_movement_alerts(conn: sqlite3.Connection, date: str) -> dict
```

数据来源：

```text
movement_alerts
```

- [ ] **Step 4: 增加 API**

路径：

```text
GET /api/review/lhb?date=YYYY-MM-DD
GET /api/review/movement-alerts?date=YYYY-MM-DD
```

## 5. 前端任务

### Task 6: TypeScript 类型和 API 客户端

**Files:**
- Modify: `web/src/types/index.ts`
- Modify: `web/src/api/client.ts`
- Modify: `web/src/hooks/useReview.ts`

- [ ] **Step 1: 增加类型**

新增：

```typescript
ReviewApiEnvelope
ReviewLimitUpReasonData
ReviewLimitUpTierData
ReviewPromotionData
ReviewLhbData
ReviewMovementAlertData
```

- [ ] **Step 2: 增加 API 函数**

新增：

```typescript
fetchReviewLimitUpReasons
fetchReviewLimitUpTiers
fetchReviewPromotions
fetchReviewLhb
fetchReviewMovementAlerts
```

- [ ] **Step 3: 增加 hooks**

新增：

```typescript
useReviewLimitUpReasons
useReviewLimitUpTiers
useReviewPromotions
useReviewLhb
useReviewMovementAlerts
```

### Task 7: 复盘工作台和 7 子 Tab

**Files:**
- Create: `web/src/components/review/ReviewWorkbench.tsx`
- Create: `web/src/components/review/ReviewSubTabs.tsx`
- Modify: `web/src/components/LimitUpReview.tsx`

- [ ] **Step 1: 新增 ReviewSubTabs**

子 Tab：

```text
涨停原因
涨停梯队
涨幅梯队
晋级
题材轮动
龙虎榜
异动
```

- [ ] **Step 2: 新增 ReviewWorkbench**

内部维护子 Tab 状态，按 Tab 渲染页面组件。

- [ ] **Step 3: 修改 LimitUpReview**

用 `ReviewWorkbench` 替代原来的折叠块堆叠结构。

### Task 8: 基础页面组件

**Files:**
- Create: `web/src/components/review/LimitUpReasonPage.tsx`
- Create: `web/src/components/review/LimitUpTierPage.tsx`
- Create: `web/src/components/review/PriceTierPage.tsx`
- Create: `web/src/components/review/PromotionPage.tsx`
- Create: `web/src/components/review/PlateRotationReviewPage.tsx`
- Create: `web/src/components/review/LhbReviewPage.tsx`
- Create: `web/src/components/review/MovementAlertPage.tsx`

- [ ] **Step 1: 涨停原因基础页**

展示题材分组和涨停股票表。

- [ ] **Step 2: 涨停梯队基础页**

展示按板高分组的梯队。

- [ ] **Step 3: 涨幅梯队占位页**

展示数据缺口说明和后续补数计划。

- [ ] **Step 4: 晋级基础页**

展示总晋级率、按板高晋级率、失败股票。

- [ ] **Step 5: 题材轮动基础页**

复用现有 `PlateRotationData`。

- [ ] **Step 6: 龙虎榜基础页**

展示股票级龙虎榜。

- [ ] **Step 7: 普通异动基础页**

展示异动类型汇总和异动列表。

## 6. 验证

后端：

```bash
python -m unittest tests/test_review_module.py -v
python -m unittest tests/test_market_db.py -v
```

前端：

```bash
cd web
npm run build
```

页面：

```text
启动本地服务
打开复盘页面
检查 7 个子 Tab 是否都能切换
检查有数据页面不白屏
检查缺数据页面有明确说明
```

## 7. 文档更新

开发完成后更新：

```text
docs/review-module-data-feasibility.md
docs/api-reference.md
docs/frontend.md
```
