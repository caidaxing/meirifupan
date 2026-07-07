import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class NewsQueryTests(unittest.TestCase):
    def _build_db(self, db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            create table premarket_news (
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
            )
            """
        )
        conn.executemany(
            """
            insert into premarket_news(guide_date, source, published_at, title, content, url, raw_payload)
            values(?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-07-03",
                    "cls",
                    "2026-07-03 08:50:00",
                    "半导体产业链消息活跃",
                    "先进封装、存储芯片方向出现催化。",
                    "https://example.com/1",
                    "{}",
                ),
                (
                    "2026-07-03",
                    "eastmoney",
                    "2026-07-03 07:20:00",
                    "海外算力股集体走强",
                    "英伟达和数据中心方向表现强。",
                    "https://example.com/2",
                    "{}",
                ),
                (
                    "2026-07-02",
                    "cls",
                    "2026-07-02 08:30:00",
                    "旧日期新闻",
                    "不应该出现在 7 月 3 日结果里。",
                    "https://example.com/3",
                    "{}",
                ),
            ],
        )
        conn.commit()
        return conn

    def test_list_news_returns_daily_items_with_source_summary(self):
        from server.services.news_queries import list_news

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                payload = list_news(conn, "2026-07-03")
            finally:
                conn.close()

        self.assertEqual("2026-07-03", payload["date"])
        self.assertEqual("ok", payload["status"])
        self.assertEqual(2, payload["summary"]["total"])
        self.assertEqual(2, payload["summary"]["returned"])
        self.assertEqual(
            [{"source": "cls", "count": 1}, {"source": "eastmoney", "count": 1}],
            payload["summary"]["sources"],
        )
        self.assertEqual("半导体产业链消息活跃", payload["items"][0]["title"])
        self.assertEqual("海外算力股集体走强", payload["items"][1]["title"])

    def test_list_news_filters_by_keyword(self):
        from server.services.news_queries import list_news

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                payload = list_news(conn, "2026-07-03", query="算力")
            finally:
                conn.close()

        self.assertEqual(1, payload["summary"]["total"])
        self.assertEqual("海外算力股集体走强", payload["items"][0]["title"])

    def test_list_news_falls_back_to_next_available_guide_date(self):
        from server.services.news_queries import list_news

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            conn.execute(
                """
                insert into premarket_news(guide_date, source, published_at, title, content, url, raw_payload)
                values(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-07-06",
                    "cls",
                    "2026-07-06 08:45:00",
                    "周一盘前消息",
                    "承接上一交易日复盘。",
                    "https://example.com/4",
                    "{}",
                ),
            )
            conn.commit()
            try:
                payload = list_news(conn, "2026-07-04")
            finally:
                conn.close()

        self.assertEqual("2026-07-04", payload["requested_date"])
        self.assertEqual("2026-07-06", payload["date"])
        self.assertEqual("2026-07-06", payload["summary"]["data_date"])
        self.assertEqual("next_available", payload["summary"]["date_mode"])
        self.assertEqual("周一盘前消息", payload["items"][0]["title"])


if __name__ == "__main__":
    unittest.main()
