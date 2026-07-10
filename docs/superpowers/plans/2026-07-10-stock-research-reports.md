# Stock Research Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect and retain 30 days of Eastmoney stock research reports with local PDFs, expose them through the API, and replace the research placeholder with a working responsive page.

**Architecture:** Add four normalized SQLite tables and a focused source client that paginates metadata, parses the structured `zwinfo` detail object, and atomically downloads validated PDFs. A separate update orchestrator writes job status and supports resumable backfills; FastAPI serves list/detail/local-PDF endpoints, and the existing News Center owns the research report tab.

**Tech Stack:** Python 3.11, SQLite, standard-library `urllib`, FastAPI, React 18, TypeScript, Vite, pytest/unittest.

## Global Constraints

- Scope is stock research reports only; do not add industry, strategy, macro, IPO, or broker morning reports.
- Backfill exactly the most recent 30 calendar days, inclusive of the execution date.
- Download every available PDF into `data/research_reports/YYYY/MM/DD/{info_code}.pdf`.
- Preserve list and detail source payloads in SQLite.
- Store relative PDF paths and never serve an unverified `.part` file.
- Keep the research UI inside `新闻资讯 > 个股研报`.
- Daily incremental runs execute at `07:30` and `19:30` and recheck two calendar days.

---

### Task 1: Research Report Schema and Persistence

**Files:**
- Modify: `src/db/schema.py`
- Modify: `src/db/__init__.py`
- Create: `tests/test_research_reports.py`

**Interfaces:**
- Consumes: existing `MarketDB.init_schema()` and `MarketDB._upsert_stock()`.
- Produces: `MarketDB.import_research_reports(records, current_year) -> int`, `MarketDB.save_research_report_content(info_code, content) -> None`, `MarketDB.mark_research_report_pdf(info_code, **state) -> None`, and `MarketDB.get_pending_research_reports(begin_date, end_date) -> list[dict]`.

- [ ] **Step 1: Write failing schema and persistence tests**

```python
def test_research_report_tables_and_idempotent_import(self):
    db = MarketDB(self.db_path)
    db.init_schema()
    count = db.import_research_reports([SAMPLE_LIST_ROW], current_year=2026)
    count_again = db.import_research_reports([SAMPLE_LIST_ROW], current_year=2026)
    self.assertEqual(1, count)
    self.assertEqual(1, count_again)
    self.assertEqual(1, db.conn.execute("select count(*) from stock_research_reports").fetchone()[0])
    self.assertEqual(2, db.conn.execute("select count(*) from stock_research_report_authors").fetchone()[0])
    self.assertEqual(3, db.conn.execute("select count(*) from stock_research_report_forecasts").fetchone()[0])
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python -m pytest tests/test_research_reports.py -q`

Expected: failure because the tables and import methods do not exist.

- [ ] **Step 3: Add the four tables and indexes**

Add `stock_research_reports`, `stock_research_report_authors`, `stock_research_report_forecasts`, and `stock_research_report_contents` to the schema script. Use `info_code` as the report key and foreign keys with `on delete cascade` for child rows. Add indexes for `(publish_date)`, `(stock_code, publish_date)`, `(org_code, publish_date)`, and `(rating_name, publish_date)`.

- [ ] **Step 4: Implement idempotent persistence methods**

Map `infoCode`, stock, organization, industry, rating, target prices, authors, and current/next/two-year forecasts. Upsert the report row, replace that report's authors and forecasts in the same transaction, retain downloaded PDF state when list metadata refreshes, and write the stock to `stocks`.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_research_reports.py -q`

Expected: all Task 1 tests pass.

### Task 2: Eastmoney Client, Detail Parser, and PDF Downloader

**Files:**
- Create: `src/research_reports.py`
- Create: `src/research_report_update.py`
- Modify: `tests/test_research_reports.py`

**Interfaces:**
- Consumes: Task 1 `MarketDB` methods.
- Produces: `fetch_research_report_list(begin_date, end_date, page_size=50) -> tuple[list[dict], int]`, `parse_research_report_detail(html) -> dict`, `download_research_report_pdf(url, target, declared_size_kb=None) -> dict`, and `run_research_report_update(...) -> dict`.

- [ ] **Step 1: Add failing parser, pagination, and PDF tests**

```python
def test_parse_detail_extracts_summary_and_pdf(self):
    detail = parse_research_report_detail(DETAIL_HTML)
    self.assertEqual("AP202607101826859348", detail["info_code"])
    self.assertIn("盈利增长显著提速", detail["summary_text"])
    self.assertTrue(detail["pdf_url"].endswith(".pdf?1783670340000.pdf"))

def test_download_pdf_is_atomic_and_hashed(self):
    result = download_research_report_pdf(PDF_URL, target, opener=fake_pdf_opener)
    self.assertTrue(target.exists())
    self.assertFalse(target.with_suffix(".pdf.part").exists())
    self.assertEqual(hashlib.sha256(PDF_BYTES).hexdigest(), result["pdf_sha256"])
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m pytest tests/test_research_reports.py -q`

Expected: import failure for `research_reports` and `research_report_update`.

- [ ] **Step 3: Implement list pagination**

POST JSON to `https://reportapi.eastmoney.com/report/list2` with `code`, `industryCode`, `ratingChange`, `rating`, and `orgCode` set to `*`, plus `beginTime`, `endTime`, `pageNo`, and `pageSize`. Continue through `TotalPage`; reject responses without a list-valued `data` field.

- [ ] **Step 4: Implement structured detail parsing**

Use `html.parser.HTMLParser` to collect script bodies. Locate a script containing `var zwinfo=`, find the first `{`, and decode one JSON object using `json.JSONDecoder().raw_decode`. Return normalized `info_code`, `summary_text`, `pdf_url`, attachment fields, timestamps, and the complete object as `raw_payload`.

- [ ] **Step 5: Implement validated atomic PDF download**

Stream to `{target}.part`, require HTTP success, `application/pdf`, `%PDF-` at the start, positive byte count, and no more than 2 KB difference from `declared_size_kb`. Calculate SHA-256 while streaming, then use `Path.replace()` to atomically publish the final file. Delete `.part` on failure.

- [ ] **Step 6: Implement resumable update orchestration and CLI**

The CLI supports `--days 30`, `--begin-date`, `--end-date`, `--db`, `--data-root`, `--workers 3`, and `--strict`. Import all list rows first, then process pending details/PDFs with three workers, persist each result independently, and log `research_reports_update` to `data_jobs` with totals and failed IDs.

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_research_reports.py -q`

Expected: schema, parser, downloader, and orchestration tests pass.

### Task 3: Research Report API

**Files:**
- Create: `server/services/research_report_queries.py`
- Create: `server/api/research_reports.py`
- Modify: `server/main.py`
- Modify: `tests/test_research_reports.py`

**Interfaces:**
- Consumes: the four Task 1 tables and `server.services.review_queries.get_connection()`.
- Produces: `/api/research-reports/dates`, `/api/research-reports`, `/api/research-reports/{info_code}`, and `/api/research-reports/{info_code}/pdf`.

- [ ] **Step 1: Add failing service and route tests**

```python
def test_list_reports_filters_and_counts_downloaded_pdf(self):
    payload = list_research_reports(conn, "2026-07-10", rating="买入")
    self.assertEqual(1, payload["summary"]["total"])
    self.assertEqual(1, payload["summary"]["pdf_downloaded"])

def test_local_pdf_path_rejects_missing_file(self):
    with self.assertRaises(FileNotFoundError):
        resolve_research_report_pdf(conn, "AP-MISSING", data_root)
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m pytest tests/test_research_reports.py -q`

Expected: imports for research report query services fail.

- [ ] **Step 3: Implement date, list, detail, and PDF query services**

List queries filter by exact report date, keyword, rating, and organization. Detail queries join content, authors, and forecasts. PDF resolution requires `pdf_status='downloaded'`, resolves the relative path under the configured data root, rejects path traversal, and checks `%PDF-` before returning the path.

- [ ] **Step 4: Register FastAPI routes**

Return `FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type="inline")` for the local PDF route. Map missing report to 404, unfinished PDF to 409, and a missing/corrupt local file to 404.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_research_reports.py -q`

Expected: API query and file resolution tests pass.

### Task 4: Stock Research Report Frontend

**Files:**
- Create: `web/src/components/ResearchReportView.tsx`
- Modify: `web/src/components/AnnouncementView.tsx`
- Modify: `web/src/api/client.ts`
- Modify: `web/src/hooks/useReview.ts`
- Modify: `web/src/types/index.ts`
- Modify: `web/src/styles/globals.css`

**Interfaces:**
- Consumes: Task 3 API payloads.
- Produces: a working `个股研报` tab with filters, list, detail, local PDF action, and mobile single-column behavior.

- [ ] **Step 1: Add TypeScript payload types and API functions**

Define `ResearchReportItem`, `ResearchReportListData`, `ResearchReportDetail`, `ResearchReportAuthor`, and `ResearchReportForecast`. Add `fetchResearchReportDates`, `fetchResearchReports`, and `fetchResearchReportDetail` to `client.ts`.

- [ ] **Step 2: Add hooks**

Implement `useResearchReportDates()`, `useResearchReports(date, filters)`, and `useResearchReportDetail(infoCode)`, each aborting stale requests and exposing `{data, loading, error}`.

- [ ] **Step 3: Build `ResearchReportView`**

Render count/date/search/rating/institution controls above a report list and detail panel. The detail includes summary, analysts, target price, a three-year EPS/PE table, attachment metadata, PDF state, and an anchor to `/api/research-reports/{info_code}/pdf` only when downloaded.

- [ ] **Step 4: Replace the placeholder tab**

Rename `研报线索` to `个股研报`, remove its placeholder configuration, and render `ResearchReportView` when the research tab is active. Keep the module tabs above all controls.

- [ ] **Step 5: Add responsive styles**

Use the existing announcement visual language with report-specific classes. Desktop uses `minmax(320px, 420px) minmax(0, 1fr)`; below 760 px use one column, 40 px controls, no fixed input height beyond the control itself, and normal wrapping for long titles and institution names.

- [ ] **Step 6: Build the frontend**

Run: `npm run build`

Working directory: `web/`

Expected: TypeScript and Vite build succeed.

### Task 5: Scheduled Incremental Updates

**Files:**
- Modify: `src/daily_scheduler.py`
- Modify: `tests/test_market_db.py`
- Modify: `.env.example`
- Modify: `docs/technical/data-sources.md`

**Interfaces:**
- Consumes: Task 2 `run_research_report_update()`.
- Produces: fixed daily research update runs with `RESEARCH_REPORT_UPDATE_ATS=07:30,19:30`.

- [ ] **Step 1: Write failing scheduler tests**

```python
def test_research_report_schedule_runs_twice_daily(self):
    schedule = {"research_reports_update": ["07:30", "19:30"]}
    self.assertEqual(["research_reports_update"], due_task_names(schedule, datetime(2026, 7, 10, 7, 30)))
```

- [ ] **Step 2: Run scheduler tests and confirm failure where integration is absent**

Run: `python -m pytest tests/test_market_db.py -q`

- [ ] **Step 3: Wire the task into the scheduler**

Parse `RESEARCH_REPORT_UPDATE_ATS`, add `research_reports_update` to the daily schedule, and call `run_research_report_update(backfill_days=2, db_path=db_path)` when due. Include the configured times in startup logging.

- [ ] **Step 4: Document the data source and schedule**

Add the Eastmoney list/detail/PDF endpoints, four tables, local PDF path, and daily times to the existing data-source documentation and `.env.example`.

- [ ] **Step 5: Run scheduler and focused tests**

Run: `python -m pytest tests/test_market_db.py tests/test_research_reports.py -q`

Expected: all focused backend tests pass.

### Task 6: Live Backfill and End-to-End Verification

**Files:**
- Modify only if verification exposes a defect in files already listed above.
- Runtime data: `data/market_review.db`, `data/research_reports/`.

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: 30 days of local research report metadata/details/PDFs and a verified local page.

- [ ] **Step 1: Back up the database**

Run: `cp data/market_review.db data/backup/market_review.before-research-reports-$(date +%Y%m%d-%H%M%S).db`

- [ ] **Step 2: Run the 30-day backfill**

Run: `PYTHONPATH=src python src/research_report_update.py --days 30 --db data/market_review.db --data-root data/research_reports --workers 3 --strict`

Expected: summary reports list count, detail successes, PDF successes, byte total, and any failed report IDs.

- [ ] **Step 3: Verify database and files**

Run SQL counts for all four tables, group PDF status, assert no duplicate `info_code`, run `pragma integrity_check`, verify every downloaded path exists and starts with `%PDF-`, and randomly inspect at least five records.

- [ ] **Step 4: Run the full automated suite**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 5: Run frontend build and start the local service**

Run: `npm run build` in `web/`, then restart the local app on port 8766 using the repository's current launch method.

Expected: `/api/health`, research dates/list/detail/PDF, and the SPA return 200.

- [ ] **Step 6: Check desktop and mobile layouts**

Capture the `个股研报` tab at 1440x900 and 390x844. Confirm no horizontal overflow, controls remain compact, list/detail stack on mobile, and a downloaded PDF opens from the local API.

- [ ] **Step 7: Review and commit implementation**

Run `git diff --check`, inspect `git status --short`, stage only research-report implementation files and the plan, then commit with `feat: add stock research reports`.
