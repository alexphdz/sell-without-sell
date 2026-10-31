"""Authenticated frontier HTTP client with retry, rate-limit, and ETag support."""

from __future__ import annotations

import asyncio
import ipaddress
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from kipu_pay.core.exceptions import ConfigurationError
from kipu_pay.core.logging import get_logger

logger = get_logger(__name__)

# Known frontier production origin (allowlisted for development)
_ALLOWED_HOSTS = frozenset(
    {
        "reto-pii-fuentes-production.up.railway.app",
        "localhost",
        "127.0.0.1",
    }
)


def _is_private_or_unsafe(hostname: str) -> bool:
    """Return True if hostname resolves to private/loopback/link-local."""
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
    except ValueError:
        # Not an IP — skip IP-level checks; rely on host allowlist
        return False


def validate_source_url(url: str, *, strict: bool = False) -> str:
    """Validate a frontier source URL to mitigate SSRF.

    - Require HTTPS in strict/production mode.
    - Reject file://, ftp://, etc.
    - Reject private IP addresses.
    - Reject metadata-service endpoints.
    - In non-strict mode, localhost/127.0.0.1 allowed for tests.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if not scheme or not hostname:
        raise ConfigurationError("Invalid source URL: missing scheme or host.")

    if scheme not in {"https", "http"}:
        raise ConfigurationError(f"Invalid source URL scheme: {scheme}")

    if strict and scheme != "https":
        raise ConfigurationError("Production source URL must use HTTPS.")

    if hostname in {"169.254.169.254", "metadata.google.internal", "metadata"}:
        raise ConfigurationError("Metadata-service destinations are not allowed.")

    if _is_private_or_unsafe(hostname) and hostname not in {"localhost", "127.0.0.1"}:
        raise ConfigurationError(f"Private network destination not allowed: {hostname}")

    if strict and hostname not in _ALLOWED_HOSTS:
        raise ConfigurationError(f"Untrusted source host: {hostname}")

    return url


class FrontierClient:
    """Async HTTP client for FRONTIER Sources API."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        max_concurrent: int = 5,
        max_requests_per_minute: int = 300,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
        retry_max_delay: float = 30.0,
        strict_url: bool = False,
    ) -> None:
        self.base_url = validate_source_url(base_url.rstrip("/"), strict=strict_url)
        if not token:
            raise ConfigurationError("Frontier API token is required.")
        self._token = token
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.retry_max_delay = retry_max_delay
        self.timeout = timeout

        # Concurrency
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Rate limit: token bucket-ish via last-request tracking
        self._max_rpm = max_requests_per_minute
        self._min_interval = 60.0 / max_requests_per_minute
        self._last_request_time: float = 0.0
        self._rate_lock = asyncio.Lock()

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,  # SSRF defense: manual redirect handling only
            )
        return self._client

    async def _rate_limit(self) -> None:
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

    def _headers(self, etag: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json, */*",
        }
        if etag:
            headers["If-None-Match"] = etag
        return headers

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        etag: str | None = None,
    ) -> tuple[int, bytes, dict[str, Any]]:
        """Execute one HTTP request respecting rate limits."""
        await self._rate_limit()
        client = await self._get_client()
        url = f"{self.base_url}{path}"
        response = await client.request(
            method,
            url,
            headers=self._headers(etag=etag),
        )
        # Capture headers as plain dict for downstream use
        response_headers = dict(response.headers)
        body = response.content
        status = response.status_code
        # Do not keep response object alive
        await response.aclose()
        return status, body, response_headers

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        etag: str | None = None,
    ) -> tuple[int, bytes, dict[str, Any]]:
        """Request with bounded exponential backoff for transient failures."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._semaphore:
                    status, body, headers = await self._do_request(
                        method, path, etag=etag
                    )
                # Do not retry terminal client errors
                if status in (401, 403, 404):
                    return status, body, headers
                # Rate limit: respect Retry-After if provided
                if status == 429:
                    retry_after = headers.get("retry-after")
                    delay = float(retry_after) if retry_after else self.retry_backoff_base * (2 ** (attempt - 1))
                    delay = min(delay, self.retry_max_delay)
                    logger.warning("rate_limit_hit", path=path, attempt=attempt, delay=delay)
                    await asyncio.sleep(delay)
                    continue
                # Server errors and transient conditions -> retry
                if status >= 500:
                    delay = min(self.retry_backoff_base * (2 ** (attempt - 1)), self.retry_max_delay)
                    logger.warning("server_error_retry", path=path, status=status, attempt=attempt)
                    await asyncio.sleep(delay)
                    continue
                return status, body, headers
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                delay = min(self.retry_backoff_base * (2 ** (attempt - 1)), self.retry_max_delay)
                logger.warning("transient_error_retry", path=path, attempt=attempt, error=str(exc))
                await asyncio.sleep(delay)
            except Exception as exc:
                last_error = exc
                raise

        # Retries exhausted
        raise last_error or RuntimeError(f"Request failed after {self.max_retries} retries: {path}")

    async def get(
        self,
        path: str,
        *,
        etag: str | None = None,
    ) -> tuple[int, bytes, dict[str, Any]]:
        """GET a resource; returns (status, body_bytes, headers_dict)."""
        return await self._request_with_retry("GET", path, etag=etag)

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            logger.info("frontier_client_closed")
