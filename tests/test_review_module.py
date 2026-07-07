import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class ReviewModuleTests(unittest.TestCase):
    def _build_review_db(self, db_path: Path):
        from db import MarketDB

        db = MarketDB(db_path)
        db.init_schema()
        db.import_uplimit_day(
            {
                "date": "2026-06-23",
                "uplimit_reason": [
                    {
                        "plate_code": "801001",
                        "plate_name": "chip",
                        "plate_score": 100,
                        "stocks": [
                            {
                                "stock_code": "600001",
                                "stock_name": "Chip One",
                                "up_limit_desc": "first-board",
                                "up_limit_keep_times": 1,
                                "up_limit_time": "09:40",
                                "reason": "chip",
                            }
                        ],
                    }
                ],
                "uplimit_hot": [["chip", "801001", 100]],
                "plate_rank": [],
            },
            raw_source="unit-test",
        )
        db.import_uplimit_day(
            {
                "date": "2026-06-24",
                "uplimit_reason": [
                    {
                        "plate_code": "801001",
                        "plate_name": "chip",
                        "plate_score": 100,
                        "stocks": [
                            {
                                "stock_code": "600001",
                                "stock_name": "Chip One",
                                "stock_price": 12.34,
                                "up_limit_desc": "2-board",
                                "up_limit_keep_times": 2,
                                "up_limit_time": "09:31",
                                "reason": "advanced packaging",
                                "fengdan_money": 120000000,
                                "amount": 800000000,
                                "actualcirculation_value": 3000000000,
                                "turnover_ration_real": 12.3,
                            }
                        ],
                    },
                    {
                        "plate_code": "801002",
                        "plate_name": "robot",
                        "plate_score": 80,
                        "stocks": [
                            {
                                "stock_code": "600002",
                                "stock_name": "Robot One",
                                "up_limit_desc": "first-board",
                                "up_limit_keep_times": 1,
                                "up_limit_time": "10:02",
                                "reason": "large order",
                                "fengdan_money": 50000000,
                                "amount": 300000000,
                            }
                        ],
                    },
                ],
                "uplimit_hot": [["chip", "801001", 100], ["robot", "801002", 80]],
                "plate_rank": [],
            },
            raw_source="unit-test",
        )
        db.import_lhb_daily(
            "2026-06-24",
            [
                {
                    "stock_code": "600001",
                    "stock_name": "Chip One",
                    "reason": "daily turnover",
                    "buy_amount": 200000000,
                    "sell_amount": 50000000,
                    "net_buy_amount": 150000000,
                }
            ],
        )
        db.import_movement_alerts(
            "2026-06-24",
            [
                {
                    "alert_time": "10:15:00",
                    "stock_code": "600002",
                    "stock_name": "Robot One",
                    "alert_type": "quick rise",
                    "alert_text": "price moved quickly",
                    "price": 9.87,
                    "change_pct": 7.8,
                }
            ],
        )
        db.close()

    def test_make_review_payload_has_standard_envelope(self):
        from server.services.review_queries import make_review_payload

        payload = make_review_payload(
            "2026-06-24",
            status="partial",
            summary={"total": 1},
            filters={"plates": ["chip"]},
            items=[{"stock_code": "600001"}],
            warnings=["missing realtime quote"],
        )

        self.assertEqual("2026-06-24", payload["date"])
        self.assertEqual("partial", payload["status"])
        self.assertIn("updated_at", payload)
        self.assertEqual({"total": 1}, payload["summary"])
        self.assertEqual({"plates": ["chip"]}, payload["filters"])
        self.assertEqual([{"stock_code": "600001"}], payload["items"])
        self.assertEqual(["missing realtime quote"], payload["warnings"])

    def test_limit_up_reasons_group_stocks_by_plate(self):
        from server.services.review_queries import get_review_limit_up_reasons

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            self._build_review_db(db_path)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                payload = get_review_limit_up_reasons(conn, "2026-06-24")
            finally:
                conn.close()

        self.assertEqual("ok", payload["status"])
        self.assertEqual(2, payload["summary"]["limit_up_count"])
        self.assertEqual(1, payload["summary"]["first_board_count"])
        self.assertEqual(1, payload["summary"]["multi_board_count"])
        self.assertEqual(2, payload["summary"]["highest_board"])
        self.assertEqual(["chip", "robot"], payload["filters"]["plates"])
        self.assertEqual("chip", payload["items"][0]["plate_name"])
        self.assertEqual(1, payload["items"][0]["limit_up_count"])
        self.assertEqual([{"reason": "advanced packaging", "count": 1}], payload["items"][0]["reasons"])
        self.assertEqual("600001", payload["items"][0]["stocks"][0]["stock_code"])
        self.assertEqual(["chip"], payload["items"][0]["stocks"][0]["concepts"])
        self.assertEqual(120000000, payload["items"][0]["stocks"][0]["seal_amount"])

    def test_limit_up_tiers_promotions_lhb_and_alerts_have_payloads(self):
        from server.services.review_queries import (
            get_review_lhb,
            get_review_limit_up_tiers,
            get_review_movement_alerts,
            get_review_price_tiers,
            get_review_promotions,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            self._build_review_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                tiers = get_review_limit_up_tiers(conn, "2026-06-24")
                promotions = get_review_promotions(conn, "2026-06-24")
                lhb = get_review_lhb(conn, "2026-06-24")
                alerts = get_review_movement_alerts(conn, "2026-06-24")
                price_tiers = get_review_price_tiers(conn, "2026-06-24", days=10)
            finally:
                conn.close()

        self.assertEqual("ok", tiers["status"])
        self.assertEqual(2, tiers["summary"]["limit_up_count"])
        self.assertEqual(2, tiers["items"][0]["level"])
        self.assertEqual("600001", tiers["items"][0]["stocks"][0]["stock_code"])

        self.assertEqual("ok", promotions["status"])
        self.assertEqual("2026-06-23", promotions["summary"]["base_date"])
        self.assertEqual(1, promotions["items"][0]["advanced"])

        self.assertEqual("ok", lhb["status"])
        self.assertEqual(150000000, lhb["summary"]["net_buy_amount"])
        self.assertEqual(1, lhb["summary"]["distinct_stock_count"])
        self.assertEqual(1, lhb["summary"]["limit_up_stock_count"])
        self.assertEqual(1, lhb["summary"]["net_buy_count"])
        self.assertEqual(0, lhb["summary"]["net_sell_count"])
        self.assertEqual("600001", lhb["items"][0]["stock_code"])
        self.assertTrue(lhb["items"][0]["is_limit_up"])
        self.assertEqual("2-board", lhb["items"][0]["board_label"])

        self.assertEqual("ok", alerts["status"])
        self.assertEqual(1, alerts["summary"]["alert_count"])
        self.assertEqual("600002", alerts["items"][0]["stock_code"])

        self.assertEqual("partial", price_tiers["status"])
        self.assertTrue(price_tiers["warnings"])

    def test_price_tiers_use_each_stocks_available_window(self):
        from db import MarketDB
        from server.services.review_queries import get_review_price_tiers

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            db = MarketDB(db_path)
            db.init_schema()
            db.import_stock_kline_daily("600010", [
                {"trade_date": "2026-06-11", "close_price": 10, "amount": 1000},
                {"trade_date": "2026-06-25", "close_price": 15, "amount": 1500},
            ])
            db.import_stock_kline_daily("600011", [
                {"trade_date": "2026-06-12", "close_price": 20, "amount": 2000},
                {"trade_date": "2026-06-25", "close_price": 28, "amount": 2800},
            ])
            db.close()

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                payload = get_review_price_tiers(conn, "2026-06-25", days=10)
            finally:
                conn.close()

        self.assertEqual("ok", payload["status"])
        self.assertEqual(2, payload["summary"]["stock_count"])
        stocks = [stock for tier in payload["items"] for stock in tier["stocks"]]
        self.assertEqual({"600010", "600011"}, {stock["stock_code"] for stock in stocks})
        self.assertTrue(any(stock["change_pct"] == 50 for stock in stocks))

    def test_plate_rotation_payload_includes_selected_detail(self):
        from db import MarketDB
        from server.services.review_queries import get_review_plate_rotation

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            db = MarketDB(db_path)
            db.init_schema()
            conn = db.conn
            conn.execute(
                """
                insert into plate_rotation_rank(trade_date, plate_code, plate_name, rank_no, rate, score, source)
                values('2026-06-24', '801001', 'chip', 1, 5.5, 100, 'quant_yjj')
                """
            )
            conn.execute(
                """
                insert into plate_rotation_trend(plate_code, trade_date, plate_name, rate, score, source)
                values('801001', '2026-06-24', 'chip', 5.5, 100, 'quant_yjj')
                """
            )
            conn.execute(
                """
                insert into plate_rotation_reasons(
                    plate_code, reason_date, msg_id, plate_name, title, boomreason,
                    is_boom, limit_up_count, strength_score, source
                )
                values('801001', '2026-06-24', 'msg-1', 'chip', 'chip boom', 'demand', 1, 3, 88, 'quant_yjj')
                """
            )
            conn.execute(
                """
                insert into plate_rotation_stocks(
                    trade_date, plate_code, stock_code, stock_name, rank_no,
                    change_pct, source
                )
                values('2026-06-24', '801001', '600001', 'Chip One', 1, 6.6, 'quant_yjj')
                """
            )
            conn.commit()
            db.close()

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                payload = get_review_plate_rotation(conn, "2026-06-24", days=8, top_n=12, plate_code="801001")
            finally:
                conn.close()

        self.assertEqual("ok", payload["status"])
        self.assertEqual("801001", payload["detail"]["plate_code"])
        self.assertEqual(1, len(payload["detail"]["trend"]))
        self.assertEqual(1, len(payload["detail"]["reasons"]))
        self.assertEqual(1, len(payload["detail"]["stocks"]))

    def test_review_api_exposes_limit_up_reasons_route(self):
        source = (ROOT / "server" / "api" / "review.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/api/review/limit-up-reasons")', source)
        self.assertIn('@router.get("/api/review/limit-up-tiers")', source)
        self.assertIn('@router.get("/api/review/price-tiers")', source)
        self.assertIn('@router.get("/api/review/promotions")', source)
        self.assertIn('@router.get("/api/review/plate-rotation")', source)
        self.assertIn('@router.get("/api/review/lhb")', source)
        self.assertIn('@router.get("/api/review/movement-alerts")', source)
        self.assertIn('@router.get("/api/emotion/modules")', source)

    def test_emotion_modules_payload_contains_quantzz_style_tabs(self):
        from server.services.review_queries import get_emotion_modules

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            self._build_review_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                payload = get_emotion_modules(conn, "2026-06-24", days=60)
            finally:
                conn.close()

        labels = [item["label"] for item in payload["modules"]]
        self.assertEqual(
            ["情绪周期", "情绪日内", "情绪周期VIP", "情绪周期-年", "空间板", "人气", "人气对比", "情绪热度单页"],
            labels,
        )
        self.assertEqual("cycle", payload["modules"][0]["key"])
        self.assertIn("score", payload["modules"][0]["summary"])
        self.assertIn("highest_board", payload["modules"][4]["summary"])
        self.assertIn("top20_count", payload["modules"][5]["summary"])

    def test_limit_up_reason_page_has_workbench_controls(self):
        source = (ROOT / "web" / "src" / "components" / "review" / "ReviewWorkbench.tsx").read_text(encoding="utf-8")
        self.assertIn("搜索题材、股票、代码、原因", source)
        self.assertIn("按热度排序", source)
        self.assertIn("按涨停数排序", source)
        self.assertIn("只看核心股", source)

    def test_emotion_review_has_quantzz_style_subtabs(self):
        source = (ROOT / "web" / "src" / "components" / "EmotionReview.tsx").read_text(encoding="utf-8")
        for label in ["情绪周期", "情绪日内", "情绪周期VIP", "情绪周期-年", "空间板", "人气", "人气对比", "情绪热度单页"]:
            self.assertIn(label, source)

    def test_promotion_page_has_matrix_controls(self):
        source = (ROOT / "web" / "src" / "components" / "review" / "ReviewWorkbench.tsx").read_text(encoding="utf-8")
        self.assertIn("只看晋级成功", source)
        self.assertIn("昨日梯队", source)
        self.assertIn("今日结果", source)
        self.assertIn("断板名单", source)


    def test_limit_up_reason_page_shows_each_stock_reason_as_full_row(self):
        source = (ROOT / "web" / "src" / "components" / "review" / "ReviewWorkbench.tsx").read_text(encoding="utf-8")
        self.assertIn("<strong>涨停原因</strong>", source)
        self.assertIn("title={formatValue(stock.reason)}", source)

        styles = (ROOT / "web" / "src" / "styles" / "globals.css").read_text(encoding="utf-8")
        self.assertIn(".review-stock-list-with-reason > span i", styles)
        self.assertIn("grid-column: 1 / -1;", styles)
        self.assertIn("white-space: normal;", styles)
        self.assertIn(".review-stock-list-with-reason > span i strong", styles)


if __name__ == "__main__":
    unittest.main()
