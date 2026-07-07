import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class RealtimeEmotionTests(unittest.TestCase):
    def test_realtime_payload_uses_live_market_inputs(self):
        from server.services.realtime_emotion import build_realtime_emotion_payload

        payload = build_realtime_emotion_payload(
            trade_date="2026-07-03",
            as_of="2026-07-03 10:31:20",
            spot_rows=[
                {"代码": "600001", "名称": "强势股份", "涨跌幅": 10.01, "成交额": 210000000, "换手率": 12.3},
                {"代码": "600002", "名称": "回撤科技", "涨跌幅": -7.6, "成交额": 180000000, "换手率": 9.1},
                {"代码": "600003", "名称": "平盘制造", "涨跌幅": 0, "成交额": 90000000, "换手率": 2.1},
            ],
            limit_up_items=[
                {
                    "stock_code": "600001",
                    "stock_name": "强势股份",
                    "change_pct": 10.01,
                    "up_limit_keep_times": 3,
                    "reason": "机器人",
                    "fengdan_money": 32000000,
                    "amount": 210000000,
                }
            ],
            limit_down_items=[
                {"stock_code": "600002", "stock_name": "回撤科技", "change_pct": -10.0}
            ],
            broken_items=[
                {"stock_code": "600004", "stock_name": "炸板电子", "change_pct": 6.8}
            ],
            movement_items=[
                {
                    "alert_time": "10:30:01",
                    "stock_code": "600001",
                    "stock_name": "强势股份",
                    "alert_type": "封涨停板",
                    "alert_text": "机器人",
                    "change_pct": 10.01,
                }
            ],
            source_status={"akshare_spot": "ok", "fuyao_limit_up": "ok"},
        )

        self.assertEqual(payload["mode"], "realtime")
        self.assertEqual(payload["date"], "2026-07-03")
        self.assertEqual(payload["as_of"], "2026-07-03 10:31:20")
        self.assertEqual(payload["market"]["total_count"], 3)
        self.assertEqual(payload["market"]["up_count"], 1)
        self.assertEqual(payload["market"]["down_count"], 1)
        self.assertEqual(payload["market"]["limit_up_count"], 1)
        self.assertEqual(payload["market"]["limit_down_count"], 1)
        self.assertEqual(
            [module["label"] for module in payload["modules"]],
            ["情绪周期", "情绪日内", "情绪周期VIP", "情绪周期-年", "空间板", "人气", "人气对比", "情绪热度单页"],
        )
        intraday = next(module for module in payload["modules"] if module["key"] == "intraday")
        self.assertEqual(intraday["items"][0]["alert_type"], "封涨停板")
        space_board = next(module for module in payload["modules"] if module["key"] == "space_board")
        self.assertEqual(space_board["summary"]["highest_board"], 3)
        self.assertEqual(space_board["items"][0]["reason"], "机器人")

    def test_backend_exposes_realtime_emotion_route(self):
        source = (ROOT / "server" / "api" / "review.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/api/emotion/realtime")', source)
        self.assertIn("collect_realtime_emotion", source)

    def test_frontend_requests_realtime_emotion_and_refreshes(self):
        client = (ROOT / "web" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        hook = (ROOT / "web" / "src" / "hooks" / "useReview.ts").read_text(encoding="utf-8")
        app = (ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("fetchEmotionRealtime", client)
        self.assertIn("/emotion/realtime", client)
        self.assertIn("useEmotionRealtime", hook)
        self.assertIn("setInterval", hook)
        self.assertIn("useEmotionRealtime", app)


if __name__ == "__main__":
    unittest.main()
