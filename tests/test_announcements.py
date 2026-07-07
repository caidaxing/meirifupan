import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class AnnouncementQueryTests(unittest.TestCase):
    def _build_db(self, db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            create table stock_announcements (
                notice_date text not null,
                stock_code text,
                stock_name text,
                notice_type text,
                title text not null,
                url text,
                raw_payload text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                primary key(notice_date, title)
            )
            """
        )
        conn.execute(
            """
            insert into stock_announcements(
                notice_date, stock_code, stock_name, notice_type, title, url, raw_payload
            )
            values(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-29",
                "300030",
                "阳普医疗",
                "股东大会",
                "阳普医疗:2026年第一次临时股东会决议公告",
                "",
                json.dumps(
                    {
                        "网址": "https://data.eastmoney.com/notices/detail/300030/AN202606291826550774.html",
                        "公告编号": "2026-030",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.execute(
            """
            insert into stock_announcements(
                notice_date, stock_code, stock_name, notice_type, title, url, raw_payload
            )
            values(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-29",
                "300497",
                "富祥股份",
                "业绩预告",
                "富祥股份:2026年半年度业绩预告",
                "https://data.eastmoney.com/notices/detail/300497/AN202606181823665476.html",
                "{}",
            ),
        )
        conn.execute(
            """
            insert into stock_announcements(
                notice_date, stock_code, stock_name, notice_type, title, url, raw_payload
            )
            values(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-29",
                "A25262",
                "宇特光电",
                "北交所上市审核会议公告",
                "北京证券交易所上市委员会2026年第67次审议会议公告",
                "https://data.eastmoney.com/notices/detail/A25262/AN202607031826708447.html",
                "{}",
            ),
        )
        conn.commit()
        return conn

    def test_list_announcements_extracts_art_code_from_url_or_raw_payload(self):
        from server.services.announcement_queries import list_announcements

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                payload = list_announcements(conn, "2026-06-29")
            finally:
                conn.close()

        self.assertEqual("2026-06-29", payload["date"])
        self.assertEqual("ok", payload["status"])
        self.assertEqual(2, payload["summary"]["total"])
        self.assertEqual("AN202606181823665476", payload["items"][0]["art_code"])
        self.assertEqual("AN202606291826550774", payload["items"][1]["art_code"])
        self.assertEqual("股东大会", payload["items"][1]["notice_type"])
        self.assertIn("/300030/AN202606291826550774.html", payload["items"][1]["source_url"])

    def test_list_announcements_hides_ipo_related_rows_by_default(self):
        from server.services.announcement_queries import list_announcements

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                default_payload = list_announcements(conn, "2026-06-29")
                full_payload = list_announcements(conn, "2026-06-29", include_ipo=True)
            finally:
                conn.close()

        self.assertEqual({"300030", "300497"}, {item["stock_code"] for item in default_payload["items"]})
        self.assertEqual({"300030", "300497", "A25262"}, {item["stock_code"] for item in full_payload["items"]})

    def test_list_announcements_reports_total_before_limit(self):
        from server.services.announcement_queries import list_announcements

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                payload = list_announcements(conn, "2026-06-29", limit=1)
            finally:
                conn.close()

        self.assertEqual(2, payload["summary"]["total"])
        self.assertEqual(1, payload["summary"]["returned"])
        self.assertEqual(1, len(payload["items"]))

    def test_get_announcement_detail_fetches_and_caches_original_text(self):
        from server.services.announcement_queries import get_announcement_detail

        def fake_fetcher(art_code: str):
            self.assertEqual("AN202606291826550774", art_code)
            return {
                "notice_title": "阳普医疗:2026年第一次临时股东会决议公告",
                "notice_content": "证券代码：300030\n\n本次股东会未出现否决议案的情况。",
                "attach_url_web": "https://pdf.example.com/AN202606291826550774.pdf",
                "eitime": "2026-06-29 18:26:55",
                "raw": {"ok": True},
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conn = self._build_db(root / "market.db")
            try:
                detail = get_announcement_detail(
                    conn,
                    "AN202606291826550774",
                    cache_root=root / "announcements",
                    fetcher=fake_fetcher,
                )
            finally:
                conn.close()

            text_path = Path(detail["text_path"])
            json_path = Path(detail["json_path"])
            self.assertTrue(text_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual("300030", detail["stock_code"])
            self.assertIn("未出现否决议案", detail["content_text"])
            self.assertEqual("https://pdf.example.com/AN202606291826550774.pdf", detail["pdf_url"])

            conn = self._build_db(root / "market2.db")
            try:
                cached = get_announcement_detail(
                    conn,
                    "AN202606291826550774",
                    cache_root=root / "announcements",
                    fetcher=lambda _: (_ for _ in ()).throw(AssertionError("should read cache")),
                )
            finally:
                conn.close()

        self.assertEqual(detail["content_text"], cached["content_text"])

    def test_announcement_fetch_uses_certified_ssl_context(self):
        import server.services.announcement_queries as announcement_queries

        with patch.object(announcement_queries.certifi, "where", return_value="/tmp/cacert.pem"), \
                patch.object(announcement_queries.ssl, "create_default_context") as create_context:
            announcement_queries.make_ssl_context()

        create_context.assert_called_once_with(cafile="/tmp/cacert.pem")
