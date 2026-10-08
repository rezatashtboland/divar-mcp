"""Async HTTP client for divar.ir: browser headers, rate limit, retries, TTL cache."""

from __future__ import annotations

import asyncio
from typing import Literal

import httpx
from cachetools import TTLCache
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .. import config

CacheBucket = Literal["cities", "search", "detail"]

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class _RetryableStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class DivarUnavailableError(Exception):
    """Raised when divar.ir cannot be reached or refuses the request."""

    def __init__(self, message_fa: str, message_en: str) -> None:
        super().__init__(message_fa)
        self.message_fa = message_fa
        self.message_en = message_en

    def user_message(self) -> str:
        return self.message_en if config.language() == "en" else self.message_fa


class HttpClient:
    def __init__(
        self,
        rate_rps: float = config.RATE_LIMIT_RPS,
        max_retries: int = config.MAX_RETRIES,
        timeout: float = config.DEFAULT_TIMEOUT,
        wait_base: float = 1.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=config.default_headers(),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._min_interval = 1.0 / rate_rps if rate_rps > 0 else 0.0
        self._max_retries = max_retries
        self._wait_base = wait_base
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._caches: dict[str, TTLCache[str, str]] = {
            "cities": TTLCache(maxsize=16, ttl=config.CITIES_CACHE_TTL),
            "search": TTLCache(maxsize=128, ttl=config.SEARCH_CACHE_TTL),
            "detail": TTLCache(maxsize=256, ttl=config.DETAIL_CACHE_TTL),
        }

    async def get_text(self, url: str, cache: CacheBucket | None = None) -> str:
        """GET a URL as text with retries, rate limiting and optional TTL caching."""
        bucket = self._caches[cache] if cache else None
        if bucket is not None and url in bucket:
            return str(bucket[url])
        try:
            text = await self._fetch_with_retry(url)
        except (httpx.HTTPError, _RetryableStatusError) as exc:
            raise self._error_for(exc) from exc
        if bucket is not None:
            bucket[url] = text
        return text

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait = self._min_interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = loop.time()

    async def _fetch_with_retry(self, url: str) -> str:
        retryer = AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._wait_base, max=10),
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
            reraise=True,
        )
        async for attempt in retryer:
            with attempt:
                await self._throttle()
                response = await self._client.get(url)
                if response.status_code in _RETRY_STATUSES:
                    raise _RetryableStatusError(response.status_code)
                response.raise_for_status()
                return response.text
        raise DivarUnavailableError(
            "دیوار در دسترس نیست.", "divar.ir is unavailable."
        )  # pragma: no cover

    def _error_for(self, exc: Exception) -> DivarUnavailableError:
        if isinstance(exc, _RetryableStatusError):
            return DivarUnavailableError(
                f"دیوار موقتاً در دسترس نیست (کد {exc.status_code}).",
                f"divar.ir is temporarily unavailable (HTTP {exc.status_code}).",
            )
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 404:
                return DivarUnavailableError(
                    "صفحه‌ی موردنظر در دیوار پیدا نشد.",
                    "The requested page was not found on divar.ir.",
                )
            if status == 403:
                return DivarUnavailableError(
                    "دیوار این درخواست را مسدود کرد. کمی بعد دوباره امتحان کنید.",
                    "divar.ir blocked this request. Try again later.",
                )
            return DivarUnavailableError(
                f"خطای دیوار با کد {status}.", f"divar.ir returned HTTP {status}."
            )
        return DivarUnavailableError(
            "اتصال به دیوار برقرار نشد. اینترنت را بررسی کنید.",
            "Could not reach divar.ir. Check your network connection.",
        )


_default_client: HttpClient | None = None


def get_default_client() -> HttpClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpClient()
    return _default_client
