"""Minimal fallback implementation of the subset of httpx used in tests."""
from __future__ import annotations

import asyncio
import json as _json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import error, parse, request


class HTTPStatusError(Exception):
    """Exception raised when an HTTP response status indicates failure."""

    def __init__(self, message: str, request: Optional["Request"] = None, response: Optional["Response"] = None) -> None:
        super().__init__(message)
        self.request = request
        self.response = response


@dataclass
class Request:
    """Simple container for request data used by the stub."""

    method: str
    url: str
    headers: Dict[str, str]
    content: Optional[bytes]


class Response:
    """HTTP response wrapper compatible with httpx subset."""

    def __init__(self, status_code: int, content: bytes, headers: Optional[Dict[str, str]] = None, request_obj: Optional["Request"] = None) -> None:
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}
        self.request = request_obj

    def json(self) -> Any:
        return _json.loads(self._content.decode("utf-8"))

    def text(self) -> str:
        return self._content.decode("utf-8")

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise HTTPStatusError(f"Request failed with status code {self.status_code}", request=self.request, response=self)


class AsyncClient:
    """Very small subset of httpx.AsyncClient used by the project."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, D401
        # Nothing to clean up for urllib usage.
        return None

    async def post(self, url: str, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Response:  # noqa: A003
        def _do_request() -> Response:
            query = parse.urlencode(params or {})
            full_url = f"{url}?{query}" if query else url
            data: Optional[bytes] = None
            req_headers = dict(headers or {})
            if json is not None:
                data = _json.dumps(json).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")
            req = request.Request(full_url, data=data, headers=req_headers, method="POST")
            req_obj = Request(method="POST", url=full_url, headers=req_headers, content=data)
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    return Response(resp.status, resp.read(), dict(resp.headers), req_obj)
            except error.HTTPError as exc:
                return Response(exc.code, exc.read(), dict(exc.headers or {}), req_obj)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_request)


__all__ = [
    "AsyncClient",
    "HTTPStatusError",
    "Request",
    "Response",
]
