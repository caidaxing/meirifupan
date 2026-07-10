"""Database schema DDL and migration helpers."""

from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
            pragma foreign_keys = on;

            create table if not exists trade_calendar (
                trade_date text primary key,
                is_trade_day integer not null default 1,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists stocks (
                stock_code text primary key,
                stock_name text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists plates (
                plate_code text primary key,
                plate_name text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists users (
                id integer primary key autoincrement,
                username text not null unique,
                password_hash text not null,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                last_login_at text
            );

            create table if not exists auth_sessions (
                token text primary key,
                user_id integer not null,
                created_at text not null default current_timestamp,
                expires_at text not null,
                revoked_at text,
                foreign key(user_id) references users(id)
            );

            create table if not exists raw_api_responses (
                id integer primary key autoincrement,
                trade_date text,
                source text not null,
                endpoint text not null,
                params_hash text not null,
                payload text not null,
                created_at text not null default current_timestamp,
                unique(trade_date, source, endpoint, params_hash)
            );

            create table if not exists limit_up_events (
                trade_date text not null,
                stock_code text not null,
                stock_name text,
                stock_price real,
                up_limit_desc text,
                up_limit_keep_times integer,
                up_limit_type text,
                up_limit_time text,
                reason text,
                tags text,
                fengdan_money real,
                fengdan_rate real,
                turnover_rate real,
                circulation_value real,
                market_type text,
                amount real,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, stock_code)
            );

            create table if not exists limit_up_plate_map (
                trade_date text not null,
                stock_code text not null,
                plate_code text not null,
                plate_name text,
                plate_score real,
                stock_reason text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, stock_code, plate_code)
            );

            create table if not exists plate_hot_rank (
                trade_date text not null,
                plate_code text not null,
                plate_name text,
                score real,
                rank_no integer not null,
                source text not null default 'uplimit_hot',
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, plate_code, source)
            );

            create table if not exists plate_daily (
                trade_date text not null,
                plate_code text not null,
                plate_name text,
                rank_no integer,
                score real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, plate_code)
            );

            create table if not exists plate_trends (
                plate_code text not null,
                trade_date text not null,
                plate_name text,
                open_price real,
                high_price real,
                low_price real,
                close_price real,
                change_pct real,
                amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(plate_code, trade_date)
            );

            create table if not exists plate_index_daily (
                plate_code text not null,
                trade_date text not null,
                plate_name text,
                board_type text,
                source text,
                open_price real,
                high_price real,
                low_price real,
                close_price real,
                change_pct real,
                volume real,
                amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(plate_code, trade_date, source)
            );

            create table if not exists plate_reasons (
                plate_code text primary key,
                plate_name text,
                reason text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists lhb_daily (
                trade_date text not null,
                stock_code text not null,
                stock_name text,
                reason text,
                buy_amount real,
                sell_amount real,
                net_buy_amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, stock_code, reason)
            );

            create table if not exists movement_alerts (
                trade_date text not null,
                alert_time text not null,
                stock_code text not null,
                stock_name text,
                alert_type text,
                alert_text text,
                price real,
                change_pct real,
                raw_hash text not null,
                raw_payload text,
                created_at text not null default current_timestamp,
                primary key(trade_date, alert_time, stock_code, raw_hash)
            );

            create table if not exists market_index_daily (
                trade_date text not null,
                index_code text not null,
                index_name text,
                close_price real,
                change_pct real,
                amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, index_code)
            );

            create table if not exists sentiment_daily (
                trade_date text not null,
                period integer not null default 0,
                limit_up_count integer,
                limit_down_count integer,
                highest_board integer,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, period)
            );

            create table if not exists market_breadth_daily (
                trade_date text primary key,
                total_count integer,
                up_count integer,
                down_count integer,
                flat_count integer,
                limit_up_count integer,
                limit_down_count integer,
                natural_limit_up_count integer,
                natural_limit_down_count integer,
                avg_change_pct real,
                amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists limit_down_events (
                trade_date text not null,
                stock_code text not null,
                stock_name text,
                latest_price real,
                change_pct real,
                amount real,
                circulation_value real,
                total_market_cap real,
                turnover_rate real,
                seal_amount real,
                last_limit_down_time text,
                limit_down_days integer,
                open_count integer,
                industry text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, stock_code)
            );

            create table if not exists broken_limit_up_events (
                trade_date text not null,
                stock_code text not null,
                stock_name text,
                latest_price real,
                change_pct real,
                limit_up_price real,
                amount real,
                circulation_value real,
                total_market_cap real,
                turnover_rate real,
                first_limit_up_time text,
                open_count integer,
                limit_up_stat text,
                amplitude real,
                industry text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, stock_code)
            );

            create table if not exists market_hot_daily (
                trade_date text not null,
                item_key text not null,
                item_name text,
                score real,
                rank_no integer,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, item_key)
            );

            create table if not exists stock_kline_daily (
                stock_code text not null,
                trade_date text not null,
                open_price real,
                high_price real,
                low_price real,
                close_price real,
                volume real,
                amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(stock_code, trade_date)
            );

            create table if not exists stock_trends (
                stock_code text not null,
                trade_date text not null,
                point_time text not null,
                price real,
                volume real,
                amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                primary key(stock_code, trade_date, point_time)
            );

            create table if not exists stock_info_snapshots (
                stock_code text not null,
                snapshot_date text not null,
                stock_name text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(stock_code, snapshot_date)
            );

            create table if not exists daily_reviews (
                trade_date text primary key,
                limit_up_stock_count integer,
                limit_up_plate_count integer,
                first_board_count integer,
                multi_board_count integer,
                highest_board integer,
                strongest_plates text,
                core_stocks text,
                risk_flags text,
                opportunities text,
                next_plan text,
                markdown_path text,
                raw_payload text,
                summary text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists data_jobs (
                id integer primary key autoincrement,
                job_name text not null,
                trade_date text,
                status text not null,
                message text,
                details text,
                started_at text,
                finished_at text,
                created_at text not null default current_timestamp
            );

            create table if not exists premarket_news (
                guide_date text not null,
                source text not null,
                published_at text,
                title text not null,
                content text,
                url text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(guide_date, source, title)
            );

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

            create table if not exists stock_research_reports (
                info_code text primary key,
                publish_date text not null,
                stock_code text,
                stock_name text,
                market text,
                title text not null,
                org_code text,
                org_name text,
                org_short_name text,
                industry_code text,
                industry_name text,
                rating_name text,
                previous_rating_name text,
                rating_change_code integer,
                rating_change_name text,
                target_price_low real,
                target_price_high real,
                source_url text,
                detail_status text not null default 'pending',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists stock_research_report_authors (
                info_code text not null,
                author_id text not null,
                author_name text,
                sort_order integer not null default 0,
                primary key(info_code, author_id),
                foreign key(info_code) references stock_research_reports(info_code) on delete cascade
            );

            create table if not exists stock_research_report_forecasts (
                info_code text not null,
                forecast_year integer not null,
                eps real,
                pe real,
                primary key(info_code, forecast_year),
                foreign key(info_code) references stock_research_reports(info_code) on delete cascade
            );

            create table if not exists stock_research_report_contents (
                info_code text primary key,
                summary_text text,
                pdf_url text,
                local_pdf_path text,
                pdf_status text not null default 'pending',
                attach_pages integer,
                declared_pdf_size_kb integer,
                pdf_size integer,
                pdf_sha256 text,
                pdf_error text,
                downloaded_at text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                foreign key(info_code) references stock_research_reports(info_code) on delete cascade
            );

            create table if not exists us_stock_quotes (
                quote_date text not null,
                symbol text not null,
                stock_name text,
                sector text,
                latest_price real,
                change_pct real,
                change_amount real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(quote_date, symbol)
            );

            create table if not exists premarket_guides (
                guide_date text primary key,
                review_date text,
                headline text,
                market_tone text,
                focus_plates text,
                watch_points text,
                risk_points text,
                catalyst_news text,
                announcements text,
                us_markets text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );

            create table if not exists plate_rotation_rank (
                trade_date text not null,
                plate_code text not null,
                plate_name text,
                rank_no integer not null,
                rate real,
                score real,
                speed real,
                money_leader real,
                money_leader_buy real,
                money_leader_sell real,
                trade_money real,
                volume_ration real,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, plate_code, source)
            );

            create table if not exists plate_rotation_trend (
                plate_code text not null,
                trade_date text not null,
                plate_name text,
                rate real,
                score real,
                speed real,
                money_leader real,
                money_leader_buy real,
                money_leader_sell real,
                trade_money real,
                volume_ration real,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(plate_code, trade_date, source)
            );

            create table if not exists plate_rotation_reasons (
                plate_code text not null,
                reason_date text not null,
                msg_id text not null,
                plate_name text,
                title text,
                boomreason text,
                is_boom integer,
                limit_up_count integer,
                strength_score real,
                leader_info text,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(plate_code, reason_date, msg_id, source)
            );

            create table if not exists plate_rotation_stocks (
                trade_date text not null,
                plate_code text not null,
                stock_code text not null,
                stock_name text,
                rank_no integer,
                rank_diff integer,
                change_pct real,
                high_change_pct real,
                open_change_pct real,
                turnover_ratio real,
                volume_ratio real,
                circulation_value real,
                source text not null default 'quant_yjj',
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, plate_code, stock_code, source)
            );

            create table if not exists fuyao_limit_up_pool (
                trade_date text not null,
                ticker text not null,
                thscode text,
                stock_name text,
                last_price real,
                price_change_ratio_pct real,
                limit_up_reason text,
                continue_day_text text,
                continue_day_cnt integer,
                limit_up_time text,
                seal_money real,
                max_seal_money real,
                is_new integer,
                is_st integer,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, ticker)
            );

            create table if not exists fuyao_limit_up_ladder (
                trade_date text not null,
                board_key text not null,
                board_num integer,
                ticker text not null,
                thscode text,
                stock_name text,
                seal_nextday integer,
                sign_level integer,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, board_key, ticker)
            );

            create table if not exists fuyao_anomaly_reasons (
                trade_date text not null,
                thscode text not null,
                ticker text,
                stock_name text,
                tag_name text,
                analysis_content text,
                keyword_list text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, thscode, tag_name, analysis_content)
            );

            create table if not exists fuyao_ths_index_catalog (
                tag text not null,
                thscode text not null,
                index_name text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(tag, thscode)
            );

            create table if not exists fuyao_ths_index_constituents (
                index_thscode text not null,
                stock_thscode text not null,
                ticker text,
                stock_name text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(index_thscode, stock_thscode)
            );

            create table if not exists fuyao_stock_snapshots (
                snapshot_date text not null,
                thscode text not null,
                ticker text,
                last_price real,
                price_change real,
                price_change_ratio_pct real,
                open_price real,
                high_price real,
                low_price real,
                prev_price real,
                volume real,
                turnover real,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(snapshot_date, thscode)
            );

            create index if not exists idx_limit_up_events_date_time
                on limit_up_events(trade_date, up_limit_time);
            create index if not exists idx_limit_up_plate_map_date_plate
                on limit_up_plate_map(trade_date, plate_code);
            create index if not exists idx_plate_hot_rank_date_rank
                on plate_hot_rank(trade_date, rank_no);
            create index if not exists idx_plate_daily_date_rank
                on plate_daily(trade_date, rank_no);
            create index if not exists idx_plate_index_daily_date
                on plate_index_daily(trade_date);
            create index if not exists idx_raw_api_responses_endpoint
                on raw_api_responses(endpoint, trade_date);
            create index if not exists idx_movement_alerts_date_time
                on movement_alerts(trade_date, alert_time);
            create index if not exists idx_lhb_daily_date
                on lhb_daily(trade_date);
            create index if not exists idx_stock_kline_daily_date
                on stock_kline_daily(trade_date);
            create index if not exists idx_market_breadth_date
                on market_breadth_daily(trade_date);
            create index if not exists idx_limit_down_events_date
                on limit_down_events(trade_date);
            create index if not exists idx_broken_limit_up_events_date
                on broken_limit_up_events(trade_date);
            create index if not exists idx_premarket_news_date
                on premarket_news(guide_date, published_at);
            create index if not exists idx_stock_announcements_date
                on stock_announcements(notice_date);
            create index if not exists idx_stock_announcements_stock_date
                on stock_announcements(stock_code, notice_date);
            create index if not exists idx_stock_announcements_type_date
                on stock_announcements(notice_type, notice_date);
            create index if not exists idx_stock_research_reports_date
                on stock_research_reports(publish_date);
            create index if not exists idx_stock_research_reports_stock_date
                on stock_research_reports(stock_code, publish_date);
            create index if not exists idx_stock_research_reports_org_date
                on stock_research_reports(org_code, publish_date);
            create index if not exists idx_stock_research_reports_rating_date
                on stock_research_reports(rating_name, publish_date);
            create index if not exists idx_us_stock_quotes_date
                on us_stock_quotes(quote_date, change_pct);
            create index if not exists idx_plate_rotation_rank_date_rank
                on plate_rotation_rank(trade_date, source, rank_no);
            create index if not exists idx_plate_rotation_trend_plate_date
                on plate_rotation_trend(plate_code, source, trade_date);
            create index if not exists idx_plate_rotation_stocks_plate_date_rank
                on plate_rotation_stocks(trade_date, plate_code, source, rank_no);
            create index if not exists idx_fuyao_limit_up_pool_date_time
                on fuyao_limit_up_pool(trade_date, limit_up_time);
            create index if not exists idx_fuyao_anomaly_reasons_date
                on fuyao_anomaly_reasons(trade_date);
            create index if not exists idx_fuyao_ths_index_catalog_tag
                on fuyao_ths_index_catalog(tag, index_name);

            create table if not exists hot_stocks (
                trade_date text not null,
                rank_no integer not null,
                stock_code text not null,
                stock_name text,
                latest_price real,
                change_pct real,
                change_amount real,
                amount real,
                turnover_rate real,
                source text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, stock_code)
            );

            create table if not exists stock_hot_ranks (
                trade_date text not null,
                source text not null,
                period text not null,
                list_type text not null,
                rank_no integer not null,
                stock_code text not null,
                stock_name text,
                latest_price real,
                change_pct real,
                hot_value real,
                rank_change integer,
                concept_tags text,
                popularity_tag text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, source, period, list_type, stock_code)
            );

            create table if not exists hot_boards (
                trade_date text not null,
                board_type text not null,
                rank_no integer not null,
                board_code text not null,
                board_name text,
                latest_price real,
                change_pct real,
                change_amount real,
                total_market_cap real,
                turnover_rate real,
                up_count integer,
                down_count integer,
                leading_stock text,
                leading_stock_change real,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(trade_date, board_type, board_code)
            );

            create index if not exists idx_hot_stocks_date_rank
                on hot_stocks(trade_date, rank_no);
            create index if not exists idx_stock_hot_ranks_date_source_rank
                on stock_hot_ranks(trade_date, source, period, list_type, rank_no);
            create index if not exists idx_hot_boards_date_type_rank
                on hot_boards(trade_date, board_type, rank_no);
            """


def ensure_table_columns(conn: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    """Add missing columns to an existing table."""
    existing = {
        row["name"]
        for row in conn.execute(f"pragma table_info({table_name})").fetchall()
    }
    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table_name} add column {name} {column_type}")


def ensure_daily_review_columns(conn: sqlite3.Connection) -> None:
    """Add new report columns when upgrading an existing database."""
    ensure_table_columns(conn, "daily_reviews", {
        "risk_flags": "text",
        "opportunities": "text",
        "next_plan": "text",
        "markdown_path": "text",
        "raw_payload": "text",
    })


def ensure_data_job_columns(conn: sqlite3.Connection) -> None:
    """Add job tracking columns when upgrading an existing database."""
    ensure_table_columns(conn, "data_jobs", {
        "details": "text",
        "started_at": "text",
        "finished_at": "text",
    })


def ensure_market_breadth_columns(conn: sqlite3.Connection) -> None:
    """Add breadth metrics needed by review-home trend charts."""
    ensure_table_columns(conn, "market_breadth_daily", {
        "natural_limit_up_count": "integer",
        "natural_limit_down_count": "integer",
        "avg_change_pct": "real",
    })


def ensure_hot_stock_columns(conn: sqlite3.Connection) -> None:
    """Add richer hot-rank fields for popularity emotion analysis."""
    ensure_table_columns(conn, "hot_stocks", {
        "amount": "real",
        "turnover_rate": "real",
        "source": "text",
        "raw_payload": "text",
    })


def ensure_stock_hot_rank_table(conn: sqlite3.Connection) -> None:
    """Create multi-source hot-rank table for THS and future providers."""
    conn.executescript(
        """
        create table if not exists stock_hot_ranks (
            trade_date text not null,
            source text not null,
            period text not null,
            list_type text not null,
            rank_no integer not null,
            stock_code text not null,
            stock_name text,
            latest_price real,
            change_pct real,
            hot_value real,
            rank_change integer,
            concept_tags text,
            popularity_tag text,
            raw_payload text,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp,
            primary key(trade_date, source, period, list_type, stock_code)
        );
        create index if not exists idx_stock_hot_ranks_date_source_rank
            on stock_hot_ranks(trade_date, source, period, list_type, rank_no);
        """
    )


def ensure_premarket_columns(conn: sqlite3.Connection) -> None:
    """Add columns for pre-market guide data when upgrading old databases."""
    ensure_table_columns(conn, "premarket_guides", {
        "review_date": "text",
        "headline": "text",
        "market_tone": "text",
        "focus_plates": "text",
        "watch_points": "text",
        "risk_points": "text",
        "catalyst_news": "text",
        "announcements": "text",
        "us_markets": "text",
        "raw_payload": "text",
    })


def ensure_plate_rotation_tables(conn: sqlite3.Connection) -> None:
    """Create plate rotation tables when upgrading deployed databases."""
    conn.executescript(
        """
        create table if not exists plate_rotation_rank (
            trade_date text not null,
            plate_code text not null,
            plate_name text,
            rank_no integer not null,
            rate real,
            score real,
            speed real,
            money_leader real,
            money_leader_buy real,
            money_leader_sell real,
            trade_money real,
            volume_ration real,
            source text not null default 'quant_yjj',
            raw_payload text,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp,
            primary key(trade_date, plate_code, source)
        );
        create table if not exists plate_rotation_trend (
            plate_code text not null,
            trade_date text not null,
            plate_name text,
            rate real,
            score real,
            speed real,
            money_leader real,
            money_leader_buy real,
            money_leader_sell real,
            trade_money real,
            volume_ration real,
            source text not null default 'quant_yjj',
            raw_payload text,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp,
            primary key(plate_code, trade_date, source)
        );
        create table if not exists plate_rotation_reasons (
            plate_code text not null,
            reason_date text not null,
            msg_id text not null,
            plate_name text,
            title text,
            boomreason text,
            is_boom integer,
            limit_up_count integer,
            strength_score real,
            leader_info text,
            source text not null default 'quant_yjj',
            raw_payload text,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp,
            primary key(plate_code, reason_date, msg_id, source)
        );
        create table if not exists plate_rotation_stocks (
            trade_date text not null,
            plate_code text not null,
            stock_code text not null,
            stock_name text,
            rank_no integer,
            rank_diff integer,
            change_pct real,
            high_change_pct real,
            open_change_pct real,
            turnover_ratio real,
            volume_ratio real,
            circulation_value real,
            source text not null default 'quant_yjj',
            raw_payload text,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp,
            primary key(trade_date, plate_code, stock_code, source)
        );
        create index if not exists idx_plate_rotation_rank_date_rank
            on plate_rotation_rank(trade_date, source, rank_no);
        create index if not exists idx_plate_rotation_trend_plate_date
            on plate_rotation_trend(plate_code, source, trade_date);
        create index if not exists idx_plate_rotation_stocks_plate_date_rank
            on plate_rotation_stocks(trade_date, plate_code, source, rank_no);
        """
    )


def ensure_limit_up_tags_column(conn: sqlite3.Connection) -> None:
    """Add tags column to limit_up_events for structured reason tags."""
    ensure_table_columns(conn, "limit_up_events", {"tags": "text"})


def ensure_auth_tables(conn: sqlite3.Connection) -> None:
    """Create local auth tables when upgrading deployed databases."""
    conn.executescript(
        """
        create table if not exists users (
            id integer primary key autoincrement,
            username text not null unique,
            password_hash text not null,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp,
            last_login_at text
        );
        create table if not exists auth_sessions (
            token text primary key,
            user_id integer not null,
            created_at text not null default current_timestamp,
            expires_at text not null,
            revoked_at text,
            foreign key(user_id) references users(id)
        );
        create index if not exists idx_auth_sessions_user
            on auth_sessions(user_id, expires_at);
        """
    )


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run all schema migrations after initial table creation."""
    ensure_auth_tables(conn)
    ensure_daily_review_columns(conn)
    ensure_data_job_columns(conn)
    ensure_market_breadth_columns(conn)
    ensure_hot_stock_columns(conn)
    ensure_stock_hot_rank_table(conn)
    ensure_premarket_columns(conn)
    ensure_plate_rotation_tables(conn)
    ensure_limit_up_tags_column(conn)
    migrate_stock_announcements(conn)
    conn.commit()


def migrate_stock_announcements(conn: sqlite3.Connection) -> None:
    """Upgrade announcements to the stable art_code based schema."""
    import json
    import re

    cols = {r[1] for r in conn.execute("pragma table_info(stock_announcements)").fetchall()}
    if not cols:
        return

    pk_cols = [r[1] for r in conn.execute("pragma table_info(stock_announcements)").fetchall() if r[5] > 0]
    needs_rebuild = "art_code" not in cols or pk_cols != ["art_code"]

    if not needs_rebuild:
        conn.executescript(
            """
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
            create index if not exists idx_stock_announcements_date
                on stock_announcements(notice_date);
            create index if not exists idx_stock_announcements_stock_date
                on stock_announcements(stock_code, notice_date);
            create index if not exists idx_stock_announcements_type_date
                on stock_announcements(notice_type, notice_date);
            """
        )
        return

    conn.execute("pragma foreign_keys = off")
    conn.execute(
        """
        create table if not exists stock_announcements_new (
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
        )
        """
    )

    select_cols = ["notice_date", "stock_code", "stock_name", "notice_type", "title", "raw_payload", "created_at", "updated_at"]
    optional_cols = {
        "art_code": "art_code",
        "source": "source",
        "source_url": "source_url",
        "url": "url",
        "pdf_url": "pdf_url",
        "content_status": "content_status",
    }
    for col in optional_cols:
        if col in cols:
            select_cols.append(col)
    rows = conn.execute(f"select {', '.join(select_cols)} from stock_announcements").fetchall()
    for row in rows:
        data = dict(zip(select_cols, row))
        raw_payload = data.get("raw_payload")
        raw = {}
        if raw_payload:
            try:
                parsed = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                raw = parsed if isinstance(parsed, dict) else {}
            except Exception:
                raw = {}

        source_url = data.get("source_url") or data.get("url") or raw.get("网址") or raw.get("url") or ""
        art_code = data.get("art_code")
        if not art_code and source_url:
            match = re.search(r"(AN\d{16,})", str(source_url))
            if match:
                art_code = match.group(1)
        if not art_code and raw_payload:
            match = re.search(r"(AN\d{16,})", str(raw_payload))
            if match:
                art_code = match.group(1)
        if not art_code:
            continue

        conn.execute(
            """
            insert into stock_announcements_new(
                art_code, notice_date, stock_code, stock_name, notice_type, title,
                source, source_url, pdf_url, content_status, raw_payload, created_at, updated_at
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(art_code) do update set
                notice_date = excluded.notice_date,
                stock_code = excluded.stock_code,
                stock_name = excluded.stock_name,
                notice_type = excluded.notice_type,
                title = excluded.title,
                source = excluded.source,
                source_url = excluded.source_url,
                pdf_url = excluded.pdf_url,
                content_status = excluded.content_status,
                raw_payload = excluded.raw_payload,
                updated_at = excluded.updated_at
            """,
            (
                art_code,
                data.get("notice_date"),
                data.get("stock_code"),
                data.get("stock_name"),
                data.get("notice_type"),
                data.get("title"),
                data.get("source") or "eastmoney",
                source_url or None,
                data.get("pdf_url"),
                data.get("content_status") or "pending",
                raw_payload,
                data.get("created_at"),
                data.get("updated_at"),
            ),
        )

    conn.execute("drop table stock_announcements")
    conn.execute("alter table stock_announcements_new rename to stock_announcements")
    conn.executescript(
        """
        create index if not exists idx_stock_announcements_date
            on stock_announcements(notice_date);
        create index if not exists idx_stock_announcements_stock_date
            on stock_announcements(stock_code, notice_date);
        create index if not exists idx_stock_announcements_type_date
            on stock_announcements(notice_type, notice_date);
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
        """
    )
    conn.execute("pragma foreign_keys = on")
