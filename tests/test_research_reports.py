import json
import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


SAMPLE_LIST_ROW = {
    "infoCode": "AP202607101826859348",
    "title": "全球半导体显示龙头，LCD稳健与AMOLED成长双轮驱动",
    "stockCode": "000725",
    "stockName": "京东方A",
    "orgCode": "80000189",
    "orgName": "金元证券股份有限公司",
    "orgSName": "金元证券",
    "publishDate": "2026-07-10 00:00:00.000",
    "indvInduCode": "1038",
    "indvInduName": "光学光电子",
    "emRatingName": "增持",
    "lastEmRatingName": "",
    "ratingChange": 2,
    "indvAimPriceT": "",
    "indvAimPriceL": "",
    "predictThisYearEps": "0.2600000000",
    "predictThisYearPe": "30.8700000000",
    "predictNextYearEps": "0.3100000000",
    "predictNextYearPe": "26.6500000000",
    "predictNextTwoYearEps": "0.4500000000",
    "predictNextTwoYearPe": "18.2100000000",
    "author": ["11000496632.贾晓庆", "11000496633.李研究"],
}


class ResearchReportStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "market.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_research_report_tables_and_idempotent_import(self):
        from db import MarketDB

        db = MarketDB(self.db_path)
        db.init_schema()
        count = db.import_research_reports([SAMPLE_LIST_ROW], current_year=2026)
        count_again = db.import_research_reports([SAMPLE_LIST_ROW], current_year=2026)

        self.assertEqual(1, count)
        self.assertEqual(1, count_again)
        self.assertEqual(1, db.conn.execute("select count(*) from stock_research_reports").fetchone()[0])
        self.assertEqual(2, db.conn.execute("select count(*) from stock_research_report_authors").fetchone()[0])
        self.assertEqual(3, db.conn.execute("select count(*) from stock_research_report_forecasts").fetchone()[0])
        stock = db.conn.execute("select stock_name from stocks where stock_code = '000725'").fetchone()
        self.assertEqual("京东方A", stock[0])

        rows = db.conn.execute(
            "select forecast_year, eps, pe from stock_research_report_forecasts order by forecast_year"
        ).fetchall()
        self.assertEqual([2026, 2027, 2028], [row[0] for row in rows])
        self.assertEqual(0.26, rows[0][1])
        self.assertEqual(18.21, rows[2][2])
        db.close()

    def test_parse_detail_extracts_summary_and_pdf(self):
        from research_reports import parse_research_report_detail

        html = '''<html><script>
        var zwinfo= {"info_code":"AP202607101826859348","notice_content":"盈利增长显著提速。",
        "attach_url":"https://pdf.example/AP202607101826859348.pdf?x=1","attach_pages":"4",
        "attach_size":"603","eitime":"2026-07-10 07:59:00"};
        </script></html>'''
        detail = parse_research_report_detail(html)

        self.assertEqual("AP202607101826859348", detail["info_code"])
        self.assertIn("盈利增长显著提速", detail["summary_text"])
        self.assertTrue(detail["pdf_url"].endswith(".pdf?x=1"))
        self.assertEqual(4, detail["attach_pages"])
        self.assertEqual(603, detail["declared_pdf_size_kb"])

    def test_download_pdf_is_atomic_and_hashed(self):
        from research_reports import download_research_report_pdf

        pdf_bytes = b"%PDF-1.4\n1 0 obj\nendobj\n"

        class Response:
            headers = {"Content-Type": "application/pdf"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size=-1):
                if size == -1:
                    data, self._data = getattr(self, "_data", pdf_bytes), b""
                    return data
                data, self._data = getattr(self, "_data", pdf_bytes), b""
                if not data:
                    return b""
                self._data = data[size:]
                return data[:size]

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.pdf"
            result = download_research_report_pdf(
                "https://pdf.example/report.pdf",
                target,
                opener=lambda _request, timeout=20: Response(),
            )

            self.assertTrue(target.exists())
            self.assertFalse(target.with_suffix(".pdf.part").exists())
            self.assertEqual(hashlib.sha256(pdf_bytes).hexdigest(), result["pdf_sha256"])
            self.assertEqual(len(pdf_bytes), result["pdf_size"])

    def test_download_pdf_rejects_non_pdf_and_removes_part(self):
        from research_reports import download_research_report_pdf

        class Response:
            headers = {"Content-Type": "text/html"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size=-1):
                return b"not a pdf"

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.pdf"
            with self.assertRaises(ValueError):
                download_research_report_pdf(
                    "https://pdf.example/report.pdf",
                    target,
                    opener=lambda _request, timeout=20: Response(),
                )
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix(".pdf.part").exists())

    def test_save_content_and_pdf_state_keep_raw_payload(self):
        from db import MarketDB

        db = MarketDB(self.db_path)
        db.init_schema()
        db.import_research_reports([SAMPLE_LIST_ROW], current_year=2026)
        content = {
            "info_code": SAMPLE_LIST_ROW["infoCode"],
            "summary_text": "盈利增长显著提速。",
            "pdf_url": "https://pdf.example/AP202607101826859348.pdf",
            "attach_pages": 4,
            "declared_pdf_size_kb": 603,
            "raw_payload": {"info_code": SAMPLE_LIST_ROW["infoCode"], "ok": True},
        }
        db.save_research_report_content(content["info_code"], content)
        db.mark_research_report_pdf(
            content["info_code"],
            pdf_status="downloaded",
            local_pdf_path="2026/07/10/AP202607101826859348.pdf",
            pdf_size=617909,
            pdf_sha256="abc123",
            pdf_error=None,
        )

        row = db.conn.execute(
            "select summary_text, pdf_url, pdf_status, local_pdf_path, pdf_size, pdf_sha256, raw_payload "
            "from stock_research_report_contents where info_code = ?",
            (content["info_code"],),
        ).fetchone()
        self.assertEqual("盈利增长显著提速。", row[0])
        self.assertEqual("https://pdf.example/AP202607101826859348.pdf", row[1])
        self.assertEqual("downloaded", row[2])
        self.assertEqual("2026/07/10/AP202607101826859348.pdf", row[3])
        self.assertEqual(617909, row[4])
        self.assertEqual("abc123", row[5])
        self.assertTrue(json.loads(row[6])["ok"])
        db.close()

    def test_pending_reports_are_selected_by_date_and_missing_detail(self):
        from db import MarketDB

        db = MarketDB(self.db_path)
        db.init_schema()
        second = dict(SAMPLE_LIST_ROW)
        second["infoCode"] = "AP202607091826859348"
        second["publishDate"] = "2026-07-09 00:00:00.000"
        db.import_research_reports([SAMPLE_LIST_ROW, second], current_year=2026)
        pending = db.get_pending_research_reports("2026-07-09", "2026-07-10")

        self.assertEqual({"AP202607101826859348", "AP202607091826859348"}, {row["info_code"] for row in pending})
        db.close()


if __name__ == "__main__":
    unittest.main()
