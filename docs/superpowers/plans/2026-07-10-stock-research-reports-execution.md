# 个股研报采集与展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 A 股复盘系统中采集最近 30 天个股研报并下载 PDF，同时通过新闻资讯下的“个股研报”Tab 展示。

**Architecture:** 使用 SQLite 的研报索引、分析师、盈利预测、详情/PDF 四张表；采集器调用东方财富列表 POST 接口和详情页，先写原始数据，再以临时文件下载并校验 PDF。FastAPI 提供日期、列表、详情和本地 PDF 接口，React 复用新闻资讯的 Tab 和列表/详情布局。

**Tech Stack:** Python 3、SQLite、FastAPI、React、TypeScript、Vite、现有 `data_jobs` 调度记录。

## Global Constraints

- PDF 必须下载到 `data/research_reports/YYYY/MM/DD/{info_code}.pdf`，不能只保存外部地址。
- 首轮回补最近 30 个自然日；增量任务每日 `07:30` 和 `19:30`。
- 使用 `info_code` 幂等；单篇失败不能中断整批。
- 保留列表接口和详情页 `zwinfo` 原始 JSON。
- 研报放在新闻资讯内的“个股研报”Tab，不新增一级侧栏。

### Task 1: Add research report schema and persistence

**Files:**
- Modify: `src/db/schema.py`
- Modify: `src/db/__init__.py`
- Test: `tests/test_research_reports.py`

**Interfaces:**
- Produce `MarketDB.import_research_reports(records, current_year) -> int`.
- Produce `MarketDB.import_research_report_detail(info_code, detail_data) -> bool`.
- Produce `MarketDB.get_research_report_pending(limit) -> list[dict]`.

- [ ] Write tests for schema creation, idempotent import, author rows, forecast rows, and detail status.
- [ ] Run `PYTHONPATH=src python -m pytest -q tests/test_research_reports.py` and confirm the new tests fail before implementation.
- [ ] Add the four tables, indexes, and migrations to `init_schema()`.
- [ ] Implement upsert methods and ensure every stock code is also inserted into `stocks`.
- [ ] Run the focused tests and then `python -m pytest -q tests/test_market_db.py tests/test_research_reports.py`.
- [ ] Commit as `feat: add research report storage`.

### Task 2: Build the collector and PDF downloader

**Files:**
- Create: `src/fetch_research_reports.py`
- Modify: `src/daily_scheduler.py`
- Test: `tests/test_fetch_research_reports.py`

**Interfaces:**
- Produce `fetch_report_list(begin_date, end_date, page_no=1, page_size=50) -> dict`.
- Produce `parse_report_detail(html, info_code) -> dict`.
- Produce `download_pdf(url, target_path, declared_size_kb=None) -> dict`.
- Produce `run_research_report_update(db_path, begin_date, end_date, concurrency=3) -> dict`.

- [ ] Add fixture tests for list mapping, `zwinfo` JSON extraction, invalid PDF headers, and atomic `.part` handling.
- [ ] Run the focused collector tests and confirm they fail before implementation.
- [ ] Implement POST JSON pagination, detail parsing, retry/timeout behavior, PDF header validation, SHA-256, and per-item failure capture.
- [ ] Implement a CLI supporting `--begin-date`, `--end-date`, `--db`, `--download-pdfs`, and a 30-day default.
- [ ] Add `research_reports_update` to the scheduler with default times `07:30,19:30` and log counts into `data_jobs`.
- [ ] Run collector tests and a one-report live smoke test without starting the full 30-day backfill yet.
- [ ] Commit as `feat: collect stock research reports and pdfs`.

### Task 3: Add backend research report APIs

**Files:**
- Create: `server/services/research_report_queries.py`
- Modify: `server/api/review.py`
- Modify: `server/main.py`
- Test: `tests/test_research_report_queries.py`

**Interfaces:**
- Produce `list_research_report_dates(conn) -> list[str]`.
- Produce `list_research_reports(conn, date, query=None, rating=None, org=None, limit=200) -> dict`.
- Produce `get_research_report_detail(conn, info_code) -> dict`.

- [ ] Test date aggregation, keyword/rating/organization filters, detail response, and missing/local PDF errors.
- [ ] Run focused API tests and confirm they fail before implementation.
- [ ] Register `GET /api/research-reports/dates`, `GET /api/research-reports`, `GET /api/research-reports/{info_code}`, and `GET /api/research-reports/{info_code}/pdf`.
- [ ] Serve only a database-approved relative PDF path below the configured research report directory.
- [ ] Run API tests and existing announcement/news tests.
- [ ] Commit as `feat: expose research report APIs`.

### Task 4: Add the frontend research report Tab

**Files:**
- Modify: `web/src/api/client.ts`
- Modify: `web/src/hooks/useReview.ts`
- Modify: `web/src/types/index.ts`
- Modify: `web/src/components/AnnouncementView.tsx`
- Create: `web/src/components/ResearchReportView.tsx`
- Modify: `web/src/styles/globals.css`
- Test: `web` build and responsive browser smoke checks

**Interfaces:**
- Add typed client calls for research report dates, list, and detail.
- Add `useResearchReports(date, query, rating, org)` and `useResearchReportDetail(infoCode)`.
- Replace the existing `research` placeholder with `ResearchReportView` and pass it the selected date and report hooks.

- [ ] Add TypeScript types for report list, authors, forecasts, detail, and PDF status.
- [ ] Add client and hook calls with abort handling and empty/error states.
- [ ] Build the Tab controls, list, detail panel, local PDF button, and mobile single-column layout.
- [ ] Add only the required research report styles, reusing existing news/announcement tokens.
- [ ] Run `npm run build` in `web/`.
- [ ] Check desktop and mobile widths for no clipping or oversized controls.
- [ ] Commit as `feat: add research report view`.

### Task 5: Run the 30-day backfill and verify

**Files:**
- Data output: `data/research_reports/`
- Database: `data/market_review.db`

- [ ] Back up the SQLite database before the backfill.
- [ ] Run the 30-day collector with PDF download enabled and keep the job summary.
- [ ] Query counts for reports, details, downloaded PDFs, failed PDFs, and duplicate `info_code` values.
- [ ] Randomly inspect at least five reports and verify their PDF headers and local paths.
- [ ] Run the full Python test suite, frontend build, and `pragma integrity_check`.
- [ ] Update the data-source and API documentation with actual command and endpoint names.
- [ ] Commit documentation/data-source changes if needed.

