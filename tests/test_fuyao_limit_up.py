import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db import MarketDB
from fuyao_limit_up import enrich_day_data_with_fuyao, shanghai_midnight_ms, update_limit_up_reasons


class FuyaoLimitUpTests(unittest.TestCase):
    def test_enrich_day_data_replaces_industry_reason(self):
        day_data = {
            "date": "2026-06-25",
            "uplimit_reason": [
                {
                    "plate_code": "akshare_元件",
                    "plate_name": "元件",
                    "stocks": [
                        {"stock_code": "000823", "stock_name": "超声电子", "reason": "元件"},
                    ],
                }
            ],
        }
        items = [
            {
                "ticker": "000823",
                "name": "超声电子",
                "limit_up_reason": "转债摘牌+PCB+覆铜板+算力硬件",
                "continue_day_text": "2连板",
                "continue_day_cnt": 2,
                "limit_up_time": "09:32",
                "last_price": 25.87,
                "seal_money": 155335590,
            }
        ]

        count = enrich_day_data_with_fuyao(day_data, items)

        stock = day_data["uplimit_reason"][0]["stocks"][0]
        self.assertEqual(1, count)
        self.assertEqual("转债摘牌+PCB+覆铜板+算力硬件", stock["reason"])
        self.assertEqual("2连板", stock["up_limit_desc"])
        self.assertEqual("09:32:00", stock["up_limit_time"])

    def test_update_limit_up_reasons_updates_event_and_plate_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            db = MarketDB(db_path)
            db.init_schema()
            db.import_uplimit_day(
                {
                    "date": "2026-06-25",
                    "uplimit_reason": [
                        {
                            "plate_code": "akshare_元件",
                            "plate_name": "元件",
                            "plate_score": 1,
                            "stocks": [
                                {
                                    "stock_code": "000823",
                                    "stock_name": "超声电子",
                                    "reason": "元件",
                                }
                            ],
                        }
                    ],
                    "uplimit_hot": [["元件", "akshare_元件", 1]],
                },
                raw_source="test",
            )
            db.close()

            count = update_limit_up_reasons(
                db_path,
                "2026-06-25",
                [
                    {
                        "ticker": "000823",
                        "name": "超声电子",
                        "limit_up_reason": "转债摘牌+PCB+覆铜板+算力硬件",
                    }
                ],
            )

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            event = conn.execute("select reason from limit_up_events").fetchone()
            plate_map = conn.execute("select stock_reason from limit_up_plate_map").fetchone()
            conn.close()

            self.assertEqual(1, count)
            self.assertEqual("转债摘牌+PCB+覆铜板+算力硬件", event["reason"])
            self.assertEqual("转债摘牌+PCB+覆铜板+算力硬件", plate_map["stock_reason"])

    def test_shanghai_midnight_ms(self):
        self.assertEqual(1782316800000, shanghai_midnight_ms("2026-06-25"))


if __name__ == "__main__":
    unittest.main()
