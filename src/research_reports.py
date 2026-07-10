"""Eastmoney individual stock research report client and PDF downloader."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable


LIST_URL = "https://reportapi.eastmoney.com/report/list2"
REPORT_PAGE_URL = "https://data.eastmoney.com/report/info/{info_code}.html"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _json_request(url: str, payload: dict[str, Any], opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://data.eastmoney.com",
            "Referer": "https://data.eastmoney.com/report/stock.jshtml",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        if opener is None:
            response_context = urllib.request.urlopen(request, timeout=20, context=_ssl_context())
        else:
            response_context = opener(request, timeout=20)
        with response_context as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Failed to fetch Eastmoney research report list") from exc
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise RuntimeError("Eastmoney research report response has no list data")
    return data


def fetch_research_report_list(
    begin_date: str,
    end_date: str,
    page_size: int = 50,
    *,
    opener: Callable[..., Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch all individual stock research reports in an inclusive date range."""
    page_size = max(1, min(int(page_size), 50))
    all_rows: list[dict[str, Any]] = []
    page_no = 1
    total_pages = 1
    while page_no <= total_pages:
        payload = {
            "beginTime": begin_date,
            "endTime": end_date,
            "industryCode": "*",
            "industry": "*",
            "ratingChange": "*",
            "rating": "*",
            "orgCode": "*",
            "code": "*",
            "rcode": "",
            "pageNo": page_no,
            "pageSize": page_size,
        }
        response = _json_request(LIST_URL, payload, opener=opener)
        all_rows.extend(row for row in response["data"] if isinstance(row, dict))
        total_pages = int(response.get("TotalPage") or response.get("totalPage") or 1)
        page_no += 1
    return all_rows, int(response.get("currentYear") or 0)


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_script = False
        self.scripts: list[str] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self.in_script = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.in_script:
            self.scripts.append("".join(self._parts))
            self.in_script = False
            self._parts = []


def parse_research_report_detail(html: str) -> dict[str, Any]:
    """Parse the JSON object assigned to the detail page's ``zwinfo`` variable."""
    parser = _ScriptParser()
    parser.feed(html)
    raw: dict[str, Any] | None = None
    for script in parser.scripts:
        marker = re.search(r"\bvar\s+zwinfo\s*=", script)
        if not marker:
            continue
        start = script.find("{", marker.end())
        if start < 0:
            continue
        try:
            candidate, _ = json.JSONDecoder().raw_decode(script[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            raw = candidate
            break
    if raw is None:
        raise ValueError("Research report detail has no zwinfo JSON")

    info_code = str(raw.get("info_code") or raw.get("infoCode") or "").strip()
    if not info_code:
        raise ValueError("Research report detail has no info_code")
    return {
        "info_code": info_code,
        "summary_text": str(raw.get("notice_content") or raw.get("content_text") or "").strip(),
        "pdf_url": raw.get("attach_url") or raw.get("attach_url_web") or raw.get("pdf_url"),
        "attach_pages": _to_int(raw.get("attach_pages") or raw.get("page_size")),
        "declared_pdf_size_kb": _to_int(raw.get("attach_size")),
        "notice_title": raw.get("notice_title"),
        "notice_date": raw.get("notice_date"),
        "published_at": raw.get("eitime") or raw.get("published_at"),
        "raw_payload": raw,
    }


def fetch_research_report_detail(
    info_code: str,
    *,
    url: str | None = None,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Fetch and parse one report detail page."""
    page_url = url or REPORT_PAGE_URL.format(info_code=info_code)
    request = urllib.request.Request(
        page_url,
        headers={"Referer": "https://data.eastmoney.com/report/stock.jshtml", "User-Agent": USER_AGENT},
    )
    try:
        if opener is None:
            response_context = urllib.request.urlopen(request, timeout=20, context=_ssl_context())
        else:
            response_context = opener(request, timeout=20)
        with response_context as response:
            html = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Failed to fetch research report detail: {info_code}") from exc
    return parse_research_report_detail(html)


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def download_research_report_pdf(
    url: str,
    target: str | Path,
    declared_size_kb: int | None = None,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Download and atomically publish a validated PDF, returning file metadata."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"Referer": "https://data.eastmoney.com/", "User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    try:
        if opener is None:
            response_context = urllib.request.urlopen(request, timeout=20, context=_ssl_context())
        else:
            response_context = opener(request, timeout=20)
        with response_context as response:
            headers = getattr(response, "headers", {})
            content_type = ""
            if hasattr(headers, "get_content_type"):
                content_type = headers.get_content_type()
            else:
                content_type = str(headers.get("Content-Type", "")).split(";", 1)[0].strip()
            if content_type.lower() != "application/pdf":
                raise ValueError(f"Unexpected PDF content type: {content_type or 'missing'}")
            with partial.open("wb") as output:
                first_chunk = True
                while True:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break
                    if first_chunk and not chunk.startswith(b"%PDF-"):
                        output.close()
                        if _download_pdf_with_curl(url, partial):
                            file_bytes = partial.read_bytes()
                            size = len(file_bytes)
                            digest = hashlib.sha256(file_bytes)
                            break
                        raise ValueError("Downloaded file does not start with %PDF-")
                    first_chunk = False
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                if size <= 0:
                    raise ValueError("Downloaded PDF is empty")
            if declared_size_kb is not None and abs(size - int(declared_size_kb) * 1024) > 2048:
                raise ValueError(f"PDF size mismatch: {size} bytes vs {declared_size_kb} KB")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return {
        "local_pdf_path": str(target),
        "pdf_size": size,
        "pdf_sha256": digest.hexdigest(),
    }


def _download_pdf_with_curl(url: str, partial: Path) -> bool:
    """Retry Eastmoney PDF downloads with curl when its anti-bot layer rejects urllib."""
    curl = shutil.which("curl")
    if not curl or "pdf.dfcfw.com" not in url:
        return False
    partial.unlink(missing_ok=True)
    try:
        subprocess.run(
            [
                curl,
                "-L",
                "--fail",
                "--silent",
                "--show-error",
                "--compressed",
                "--output",
                str(partial),
                "-H",
                "Referer: https://data.eastmoney.com/",
                "-H",
                f"User-Agent: {USER_AGENT}",
                url,
            ],
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        partial.unlink(missing_ok=True)
        return False
    with partial.open("rb") as stream:
        return stream.read(5) == b"%PDF-"
