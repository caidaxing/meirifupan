import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PremarketAnalysisTests(unittest.TestCase):
    def test_diagnosis_turns_defensive_when_trend_and_high_position_are_weak(self):
        from premarket_analysis import diagnose_market_state

        diagnosis = diagnose_market_state(
            market={
                "total_count": 5200,
                "up_count": 1200,
                "down_count": 3850,
                "avg_change_pct": -0.72,
                "limit_up_count": 38,
                "limit_down_count": 21,
                "broken_limit_up_count": 66,
            },
            high_position={
                "total": 7,
                "advanced": 1,
                "failed": 6,
                "limit_down_failed": 2,
                "failed_names": ["高位A", "高位B"],
            },
            trend_hot={
                "status": "adjusting",
                "avg_change_pct": -2.4,
                "up_count": 4,
                "down_count": 16,
                "heavy_fall_count": 6,
                "new_high_count": 1,
            },
        )

        self.assertEqual("risk_off", diagnosis["state_code"])
        self.assertEqual("防守", diagnosis["strategy_mode"])
        self.assertIn("热门趋势股在调整", diagnosis["reasons"])
        self.assertTrue(any("高位" in item for item in diagnosis["risk_flags"]))

    def test_diagnosis_treats_extreme_strength_as_climax_risk(self):
        from premarket_analysis import diagnose_market_state

        diagnosis = diagnose_market_state(
            market={
                "total_count": 5200,
                "up_count": 4100,
                "down_count": 900,
                "avg_change_pct": 1.18,
                "limit_up_count": 152,
                "limit_down_count": 2,
                "broken_limit_up_count": 19,
            },
            high_position={
                "total": 9,
                "advanced": 7,
                "failed": 1,
                "limit_down_failed": 0,
                "failed_names": [],
            },
            trend_hot={
                "status": "strong",
                "avg_change_pct": 3.1,
                "up_count": 17,
                "down_count": 3,
                "heavy_fall_count": 0,
                "new_high_count": 8,
            },
        )

        self.assertEqual("climax", diagnosis["state_code"])
        self.assertEqual("防分歧", diagnosis["strategy_mode"])
        self.assertTrue(any("高潮" in item for item in diagnosis["risk_flags"]))

    def test_strategy_points_use_market_state_before_plate_names(self):
        from premarket_analysis import build_strategy_points, diagnose_market_state

        diagnosis = diagnose_market_state(
            market={
                "total_count": 5200,
                "up_count": 2800,
                "down_count": 2250,
                "avg_change_pct": 0.28,
                "limit_up_count": 78,
                "limit_down_count": 7,
                "broken_limit_up_count": 31,
            },
            high_position={
                "total": 8,
                "advanced": 4,
                "failed": 3,
                "limit_down_failed": 0,
                "failed_names": ["老龙A"],
            },
            trend_hot={
                "status": "mixed",
                "avg_change_pct": 0.6,
                "up_count": 11,
                "down_count": 9,
                "heavy_fall_count": 1,
                "new_high_count": 3,
            },
        )

        points = build_strategy_points(
            diagnosis,
            high_position={"summary": "高位晋级一般，失败股暂未明显补跌。"},
            trend_hot={"summary": "热门趋势股分化，先看核心股是否能重新走强。"},
            focus_plates=[{"plate_name": "芯片"}],
            us_markets=[],
        )

        self.assertGreaterEqual(len(points), 3)
        self.assertEqual("先定策略模式", points[0]["title"])
        self.assertIn("修复观察", points[0]["reason"])
        self.assertTrue(any("热门趋势股" in item["title"] for item in points))


if __name__ == "__main__":
    unittest.main()
