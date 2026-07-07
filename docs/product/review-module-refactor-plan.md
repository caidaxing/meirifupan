# 复盘模块逻辑重构方案

> 版本: v1.0 | 日期: 2026-07-03 | 状态: 已确认

---

## 一、问题诊断

对复盘模块全链路（数据流水线 → 后端评分 → API → 前端 Hooks）进行代码审计，发现 14 个逻辑问题，其中 2 个严重、6 个中等。

### 严重问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | **情绪评分：上证指数涨跌幅 0% 时误用其他指数** | 上证平收时（常见），情绪评分被创业板/深成指干扰，评分失真 |
| 2 | **流水线：关键步骤失败后仍执行派生/生成** | 涨停数据采集失败时，系统基于陈旧/空数据生成复盘报告，看起来有效实则错误 |

### 中等问题

| # | 问题 | 影响 |
|---|------|------|
| 3 | 跌停数查询结果为 0 时，Python truthiness 导致回退到默认值 3 | 涨停/跌停比计算不准 |
| 4 | 前端 Promise.all 一个请求失败导致全部数据丢失 | 情绪趋势接口瞬断时，整个复盘页面报错 |
| 5 | 实时轮询双重定时器 | 盘中模式可能发送重复请求 |
| 6 | 流水线每个 helper 各开一次 DB 连接 | 6 次 init_schema() DDL 执行，浪费且有锁竞争风险 |

---

## 二、修复方案

### 修复 1：情绪评分 — 上证指数 0% 误判

**文件**：`server/services/emotion_scorer.py`

**原逻辑**：
```python
market_change = 0.0
for idx in indices:
    if idx.get("index_code") in ("000001.SS", "1A0001"):
        market_change = idx.get("change_pct") or 0.0
        break
if market_change == 0.0 and indices:  # ← 平收时误触发
    market_change = indices[0].get("change_pct") or 0.0
```

**问题**：当上证 genuinely 收平（0.0%），`market_change == 0.0` 为 True，代码错误地用第一个指数（可能是创业板 +2%）替代。

**修复**：用 `None` 做"未找到"哨兵：
```python
market_change = None
for idx in indices:
    if idx.get("index_code") in ("000001.SS", "1A0001"):
        market_change = idx.get("change_pct")
        break
if market_change is None and indices:
    market_change = indices[0].get("change_pct") or 0.0
elif market_change is None:
    market_change = 0.0
```

### 修复 2：流水线 — 关键步骤失败保护

**文件**：`src/daily_update.py`

**原逻辑**：13 个步骤顺序执行，`strict=False` 时失败仅记录日志，下游步骤照常运行。

**修复**：在"派生数据"和"生成复盘"之前检查关键步骤状态：
```python
critical_steps = {"涨停主数据", "情绪数据", "历史口径数据", "题材轮动"}
critical_failed = any(
    s["name"] in critical_steps and s["status"] != "success"
    for s in summary["steps"]
)
if critical_failed:
    # 标记派生/生成为 skipped
else:
    # 正常执行
```

### 修复 3：跌停数 truthiness

**文件**：`server/services/emotion_scorer.py`

**原逻辑**：`row["event_count"] or row["breadth_count"] or DEFAULT` — 当 event_count 为 0 时（falsy），跳过。

**修复**：显式 `is not None` 判断：
```python
if event_count is not None and event_count > 0:
    limit_down = event_count
elif breadth_count is not None and breadth_count > 0:
    limit_down = breadth_count
```

### 修复 4：前端 Promise.all 部分失败

**文件**：`web/src/hooks/useReview.ts`

**原逻辑**：4 个请求用 `Promise.all`，任一失败全部丢失。

**修复**：非关键请求加独立 catch，仅 `fetchReview` 失败才报错：
```python
const safe = <T>(p: Promise<T>, fallback: T): Promise<T> =>
  p.catch(e => { if (e.name !== 'AbortError') console.error(e); return fallback })

Promise.all([
  fetchReview(date, ctrl.signal),  // critical
  safe(fetchEmotionTrend(...), []),
  safe(fetchMarketOverviewTrend(...), []),
  safe(fetchPlateRotation(...), null),
])
```

### 修复 5：实时轮询双重定时器

**文件**：`web/src/hooks/useReview.ts`

**原逻辑**：mount 时同时调用 `load(true)` 和 `setInterval(load, refreshMs)`，首次响应前可能重复请求。

**修复**：移除初始 `setInterval`，仅在首次响应后调度：
```python
load(true)
// Interval is scheduled inside load()'s .then() handler
```

### 修复 6：流水线 DB 连接复用

**文件**：`src/daily_update.py`

**原逻辑**：每个 helper（`_fetch_sentiment`, `_fetch_uplimit`, `_fetch_hot_stocks`, `_fetch_hot_boards`）各创建 MarketDB 实例，共 6 次 `init_schema()`。

**修复**：主函数创建一个共享实例传入 helper：
```python
db = MarketDB(db_path)
db.init_schema()
# 传 db 给 helper 而非 db_path
run_step("涨停主数据", lambda: _fetch_uplimit(api, db, target_day), summary)
```

---

## 三、验证方式

1. `python -m pytest tests/ -x -q` — 全部 73 测试通过
2. `cd web && npm run build` — 前端构建成功
3. 服务重启后 `/api/health` 返回 ok

---

## 四、实施状态

| 修复 | 状态 |
|------|------|
| 修复 1：情绪评分 0% 误判 | ✅ 已完成 |
| 修复 2：流水线关键步骤保护 | ✅ 已完成 |
| 修复 3：跌停数 truthiness | ✅ 已完成 |
| 修复 4：Promise.all 部分失败 | ✅ 已完成 |
| 修复 5：双重定时器 | ✅ 已完成 |
| 修复 6：DB 连接复用 | ✅ 已完成 |
