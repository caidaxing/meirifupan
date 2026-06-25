# Premarket Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把盘前指引从“昨日强势复述”改成“行情状态、赚钱效应、风险条件、次日策略”的判断型 agent。

**Architecture:** 新增一个独立的盘前诊断模块，先从市场广度、高位晋级、热门趋势股、亏钱反馈里判断行情状态，再让 `generate_premarket.py` 生成盘前文本和观察条件。接口继续使用 `/api/premarket`，前端在现有盘前页面展示新增诊断字段。

**Tech Stack:** Python, SQLite, FastAPI, React, TypeScript, unittest, Vite.

---

### Task 1: Add Premarket Diagnosis Rules

**Files:**
- Create: `src/premarket_analysis.py`
- Test: `tests/test_premarket_analysis.py`

**Steps:**
1. Write tests for退潮防守、高潮防分歧、修复观察三类状态。
2. Run the new tests and verify they fail because the module does not exist.
3. Implement diagnosis functions with plain dict inputs.
4. Run the new tests and verify they pass.

### Task 2: Feed Real Data Into Diagnosis

**Files:**
- Modify: `src/generate_premarket.py`

**Steps:**
1. Add query helpers for high-position effect, trend-hot status, and loss feedback.
2. Use the diagnosis result to build headline, watch points, risk points, and next-day strategy.
3. Keep existing news, announcements, US market, hot stock, and focus plate data.

### Task 3: Expose And Display New Fields

**Files:**
- Modify: `server/services/review_queries.py`
- Modify: `web/src/types/index.ts`
- Modify: `web/src/components/PremarketGuideView.tsx`

**Steps:**
1. Return new diagnosis fields from `/api/premarket`.
2. Add TypeScript types.
3. Add compact panels for行情状态、赚钱效应、次日策略.

### Task 4: Verify

**Commands:**
- `python3 -m unittest tests.test_premarket_analysis`
- `python3 -m unittest tests.test_market_db`
- `cd web && npm run build`
