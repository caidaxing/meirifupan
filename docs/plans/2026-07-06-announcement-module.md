# Announcement Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first usable announcement module: list announcements by date, open one announcement, fetch/cache original text, and show it in the frontend.

**Architecture:** Keep announcement list data in SQLite and original text cache under `data/announcements/`. Add a backend service and API routes under the existing FastAPI app. Enable the existing `news` sidebar module and render announcement cards plus a detail drawer in React.

**Tech Stack:** Python 3.11, FastAPI, SQLite, React 19, TypeScript, Vite.

---

### Task 1: Product Plan

**Files:**
- Create: `docs/product/announcement-module-product-plan.md`

**Steps:**
1. Document where the announcement module lives in frontend navigation.
2. Document first version scope: announcement list, detail drawer, original text cache.
3. Document later scope: AI summary, filters, stock pages, PDF download handling.

### Task 2: Backend Service Tests

**Files:**
- Create: `tests/test_announcements.py`
- Create: `server/services/announcement_queries.py`

**Steps:**
1. Write failing tests for listing announcements from `stock_announcements`.
2. Write failing tests for parsing `art_code` from `source_url`/raw `网址`.
3. Write failing tests for fetching and caching a detail payload with an injected fake fetcher.
4. Run: `python -m pytest tests/test_announcements.py -q`.

### Task 3: Backend API

**Files:**
- Modify: `server/api/review.py`
- Modify: `server/services/announcement_queries.py`

**Steps:**
1. Add `GET /api/announcements?date=YYYY-MM-DD`.
2. Add `GET /api/announcements/{art_code}`.
3. Keep implementation compatible with the current `stock_announcements` table.
4. Run announcement tests and full backend tests.

### Task 4: Frontend API and Hook

**Files:**
- Modify: `web/src/types/index.ts`
- Modify: `web/src/api/client.ts`
- Modify: `web/src/hooks/useReview.ts`

**Steps:**
1. Add announcement list/detail types.
2. Add API client functions.
3. Add hooks for list and detail loading.
4. Run `npm run build`.

### Task 5: Frontend Page

**Files:**
- Modify: `web/src/components/Sidebar.tsx`
- Create: `web/src/components/AnnouncementView.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles/globals.css`

**Steps:**
1. Enable `news` sidebar item.
2. Render `AnnouncementView` for module `news`.
3. Show date list, announcement cards, and detail drawer.
4. Keep visual style aligned with current dense review UI.
5. Run `npm run build`.

### Task 6: Verification

**Commands:**
- `PYTHONPYCACHEPREFIX=.pytest_cache/pycache python -m compileall server src tests`
- `python -m pytest tests`
- `cd web && npm run build`
- Restart local server on `8766`.
- Verify `/api/announcements?date=2026-06-30` and `/api/announcements/{art_code}`.
