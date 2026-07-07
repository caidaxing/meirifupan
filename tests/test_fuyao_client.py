import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class FakeOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def __call__(self, req, context=None, timeout=None):
        self.requests.append(req)
        return FakeResponse(self.payloads.pop(0))


class FuyaoClientTests(unittest.TestCase):
    def test_ssl_context_uses_certifi_when_available(self):
        import fuyao_client

        with patch.object(fuyao_client.certifi, "where", return_value="/tmp/cacert.pem"), \
                patch.object(fuyao_client.ssl, "create_default_context") as create_context:
            fuyao_client.make_ssl_context()

        create_context.assert_called_once_with(cafile="/tmp/cacert.pem")

    def test_get_adds_api_key_and_returns_data(self):
        from fuyao_client import FuyaoClient

        opener = FakeOpener([
            {"code": 0, "message": "success", "data": {"item": [{"ticker": "000001"}]}}
        ])
        client = FuyaoClient("secret-key", base_url="https://example.test", opener=opener)

        data = client.get("/api/demo", {"b": 2, "a": "深发展"})

        req = opener.requests[0]
        self.assertEqual("secret-key", req.headers["X-api-key"])
        self.assertEqual([{"ticker": "000001"}], data["item"])
        parsed = urlparse(req.full_url)
        query = parse_qs(parsed.query)
        self.assertEqual("/api/demo", parsed.path)
        self.assertEqual(["2"], query["b"])
        self.assertEqual(["深发展"], query["a"])

    def test_client_loads_api_key_from_project_env_file(self):
        import fuyao_client
        from fuyao_client import FuyaoClient

        opener = FakeOpener([
            {"code": 0, "message": "success", "data": {"item": []}}
        ])
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("FUYAO_API_KEY=file-key\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch.object(fuyao_client, "PROJECT_ROOT", Path(tmp)):
                client = FuyaoClient(base_url="https://example.test", opener=opener)
                client.get("/api/demo")

        self.assertEqual("file-key", opener.requests[0].headers["X-api-key"])

    def test_limit_up_pool_fetches_all_pages(self):
        from fuyao_client import FuyaoClient

        opener = FakeOpener([
            {
                "code": 0,
                "message": "success",
                "data": {
                    "pagination": {"page": 1, "pages": 2},
                    "item": [{"ticker": "000001"}],
                },
            },
            {
                "code": 0,
                "message": "success",
                "data": {
                    "pagination": {"page": 2, "pages": 2},
                    "item": [{"ticker": "000002"}],
                },
            },
        ])
        client = FuyaoClient("secret-key", base_url="https://example.test", opener=opener)

        items = client.limit_up_pool("2026-06-30", page_size=1)

        self.assertEqual(["000001", "000002"], [item["ticker"] for item in items])
        self.assertEqual(2, len(opener.requests))
        first_query = parse_qs(urlparse(opener.requests[0].full_url).query)
        second_query = parse_qs(urlparse(opener.requests[1].full_url).query)
        self.assertEqual(["1"], first_query["page"])
        self.assertEqual(["2"], second_query["page"])
        self.assertEqual(["1782748800000"], first_query["date_ms"])

    def test_collect_fuyao_daily_persists_limit_up_ladder_and_anomaly_data(self):
        from db import MarketDB
        from fuyao_collect import collect_fuyao_daily

        class FakeClient:
            def __init__(self):
                self.anomaly_batches = []

            def limit_up_pool(self, date):
                return [
                    {
                        "thscode": "000603.SZ",
                        "ticker": "000603",
                        "name": "盛达资源",
                        "limit_up_reason": "中报预增+白银",
                        "limit_up_time": "09:35",
                    }
                ]

            def limit_up_ladder(self):
                return {
                    "item": [
                        {
                            "date": "20260630",
                            "boards": {
                                "two_board": [
                                    {
                                        "thscode": "000603.SZ",
                                        "ticker": "000603",
                                        "name": "盛达资源",
                                        "board_num": 2,
                                    }
                                ]
                            },
                        }
                    ]
                }

            def anomaly_analysis_stock(self, thscodes):
                self.anomaly_batches.append(list(thscodes))
                return [
                    {
                        "thscode": "000603.SZ",
                        "stock_name": "盛达资源",
                        "analysis_content": "贵金属板块异动",
                        "keyword_list": ["白银"],
                        "tag_name": "大涨",
                    }
                ]

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            db = MarketDB(db_path)
            db.init_schema()
            db.close()

            fake = FakeClient()
            counts = collect_fuyao_daily("2026-06-30", db_path, client=fake, include_indexes=False)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            limit_up = conn.execute("select count(*) as total from fuyao_limit_up_pool").fetchone()
            ladder = conn.execute("select count(*) as total from fuyao_limit_up_ladder").fetchone()
            anomaly = conn.execute("select analysis_content from fuyao_anomaly_reasons").fetchone()
            conn.close()

        self.assertEqual(1, counts["limit_up_pool"])
        self.assertEqual(1, counts["limit_up_ladder"])
        self.assertEqual(1, counts["anomaly_reasons"])
        self.assertEqual(1, limit_up["total"])
        self.assertEqual(1, ladder["total"])
        self.assertEqual("贵金属板块异动", anomaly["analysis_content"])
        self.assertEqual([["000603.SZ"]], fake.anomaly_batches)


if __name__ == "__main__":
    unittest.main()
