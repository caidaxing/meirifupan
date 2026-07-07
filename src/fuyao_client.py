"""Fuyao REST API client."""

from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from fuyao_limit_up import BASE_URL, shanghai_midnight_ms

try:
    import certifi
except Exception:  # pragma: no cover - depends on local Python install
    class _MissingCertifi:
        @staticmethod
        def where() -> str | None:
            return None

    certifi = _MissingCertifi()


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_ssl_context() -> ssl.SSLContext:
    cafile = certifi.where()
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def load_api_key_from_env_file() -> str:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "FUYAO_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


class FuyaoClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        opener=None,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.environ.get("FUYAO_API_KEY", "") or load_api_key_from_env_file()
        if not self.api_key:
            raise ValueError("FUYAO_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"X-api-key": self.api_key})
        ctx = make_ssl_context()
        with self.opener(req, context=ctx, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("code") != 0:
            raise RuntimeError(f"Fuyao API returned code={payload.get('code')}: {payload.get('message')}")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    def limit_up_pool(self, date: str, *, page_size: int = 200) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get(
                "/api/a-share/special-data/limit-up-pool",
                {
                    "date_ms": shanghai_midnight_ms(date),
                    "page": page,
                    "size": page_size,
                    "sort_field": "limit_up_time",
                    "sort_dir": "asc",
                },
            )
            items.extend(data.get("item") or [])
            pagination = data.get("pagination") or {}
            pages = int(pagination.get("pages") or 1)
            if page >= pages:
                return items
            page += 1

    def limit_up_ladder(self) -> dict[str, Any]:
        return self.get("/api/a-share/special-data/limit-up-ladder")

    def anomaly_analysis_stock(self, thscodes: Iterable[str]) -> list[dict[str, Any]]:
        codes = [str(code).strip().upper() for code in thscodes if str(code).strip()]
        if not codes:
            return []
        data = self.get(
            "/api/a-share/special-data/anomaly-analysis-stock",
            {"thscodes": ",".join(codes[:50])},
        )
        return list(data.get("item") or [])

    def ths_index_list(self, tag: str = "cn_concept") -> list[dict[str, Any]]:
        data = self.get("/api/a-share-index/catalog/ths-index-list", {"tag": tag})
        return list(data.get("item") or [])

    def ths_stock_list(self, thscode: str) -> list[dict[str, Any]]:
        data = self.get("/api/a-share-index/constituents/ths-stock-list", {"thscode": thscode})
        return list(data.get("item") or [])

    def stock_snapshot(self, thscodes: Iterable[str] | None = None, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        params: dict[str, Any]
        if thscodes is not None:
            codes = [str(code).strip().upper() for code in thscodes if str(code).strip()]
            if not codes:
                return []
            params = {"thscodes": ",".join(codes)}
        else:
            params = {"limit": limit, "offset": offset}
        data = self.get("/api/a-share/prices/snapshot", params)
        return list(data.get("item") or [])
