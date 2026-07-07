# Fuyao Data Source Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Fuyao a first-class data source for limit-up, ladder, anomaly, and THS index data.

**Architecture:** Add a small REST client, store Fuyao data in dedicated SQLite tables, and wire a non-blocking Fuyao step into the daily update flow. Existing Quantzz and AkShare paths stay intact.

**Tech Stack:** Python stdlib HTTP, SQLite, unittest/pytest, current FastAPI backend.

---

### Task 1: Fuyao Schema and Import Tests

**Files:**
- Modify: `tests/test_market_db.py`
- Modify: `src/db.py`

**Steps:**
1. Add a failing test that expects Fuyao tables to exist.
2. Add a failing test that imports Fuyao limit-up pool rows and updates `limit_up_events`.
3. Implement the new tables and import methods in `MarketDB`.
4. Run `python3 -m pytest tests/test_market_db.py`.

### Task 2: Fuyao Client Tests and Implementation

**Files:**
- Create: `tests/test_fuyao_client.py`
- Create: `src/fuyao_client.py`

**Steps:**
1. Add a failing test for request URL, `X-api-key`, and data extraction.
2. Add a failing test for paged limit-up pool aggregation.
3. Implement the client with methods for limit-up pool, ladder, anomaly, THS index catalog, constituents, and snapshots.
4. Run `python3 -m pytest tests/test_fuyao_client.py`.

### Task 3: Collector and Daily Update

**Files:**
- Create: `src/fuyao_collect.py`
- Modify: `src/daily_update.py`
- Test: `tests/test_fuyao_client.py`

**Steps:**
1. Add a failing test for a fake-client collection run.
2. Implement `collect_fuyao_daily`.
3. Wire it into `daily_update.py` as a separate step after limit-up main data.
4. Run focused Python tests, then frontend build if touched.
