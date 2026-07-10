import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


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
