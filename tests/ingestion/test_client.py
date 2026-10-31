"""Tests for the frontier HTTP client."""

from __future__ import annotations

import pytest
import httpx
from pytest_httpx import HTTPXMock

from kipu_pay.core.exceptions import ConfigurationError
from kipu_pay.ingestion.client import FrontierClient, validate_source_url


class TestValidateSourceUrl:
    def test_https_allowed(self):
        assert validate_source_url("https://example.com/v1") == "https://example.com/v1"

    def test_http_allowed_non_strict(self):
        assert validate_source_url("http://localhost:8000/v1") == "http://localhost:8000/v1"

    def test_http_rejected_strict(self):
        with pytest.raises(ConfigurationError):
            validate_source_url("http://example.com/v1", strict=True)

    def test_file_scheme_rejected(self):
        with pytest.raises(ConfigurationError):
            validate_source_url("file:///etc/passwd")

    def test_metadata_service_rejected(self):
        with pytest.raises(ConfigurationError):
            validate_source_url("https://169.254.169.254/latest/meta-data")

    def test_invalid_url_no_scheme(self):
        with pytest.raises(ConfigurationError):
            validate_source_url("example.com")

    def test_trailing_slash_stripped(self):
        client = FrontierClient(base_url="https://example.com/v1/", token="tok")
        assert client.base_url == "https://example.com/v1"


class TestClientInit:
    def test_missing_token(self):
        with pytest.raises(ConfigurationError):
            FrontierClient(base_url="https://example.com/v1", token="")

    def test_invalid_url(self):
        with pytest.raises(ConfigurationError):
            FrontierClient(base_url="not-a-url", token="tok")


class TestClientRequests:
    async def test_bearer_header_attached(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=200, json={})
        client = FrontierClient(base_url="https://api.example.com/v1", token="my-secret")
        status, body, headers = await client.get("/test")
        assert status == 200
        request = httpx_mock.get_request(url="https://api.example.com/v1/test")
        assert request.headers["Authorization"] == "Bearer my-secret"
        await client.close()

    async def test_401_no_retry(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=401)
        client = FrontierClient(base_url="https://api.example.com/v1", token="tok", max_retries=3)
        status, body, headers = await client.get("/test")
        assert status == 401
        # Only one request (no retries for 401)
        assert len(httpx_mock.get_requests()) == 1
        await client.close()

    async def test_403_no_retry(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=403)
        client = FrontierClient(base_url="https://api.example.com/v1", token="tok")
        status, body, headers = await client.get("/test")
        assert status == 403
        await client.close()

    async def test_404_no_retry(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=404)
        client = FrontierClient(base_url="https://api.example.com/v1", token="tok")
        status, body, headers = await client.get("/test")
        assert status == 404
        await client.close()

    async def test_500_retries_then_success(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=500)
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=200, json={"ok": True})
        client = FrontierClient(
            base_url="https://api.example.com/v1",
            token="tok",
            max_retries=3,
            retry_backoff_base=0.01,
        )
        status, body, headers = await client.get("/test")
        assert status == 200
        assert len(httpx_mock.get_requests()) == 2
        await client.close()

    async def test_503_retries_exhausted(self, httpx_mock: HTTPXMock):
        for i in range(4):
            httpx_mock.add_response(
                url="https://api.example.com/v1/test",
                status_code=503,
                is_optional=(i == 3),  # 4th response never consumed (3 retries max)
            )
        client = FrontierClient(
            base_url="https://api.example.com/v1",
            token="tok",
            max_retries=3,
            retry_backoff_base=0.01,
        )
        with pytest.raises(Exception):
            await client.get("/test")
        await client.close()

    async def test_429_respects_retry_after(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            status_code=429,
            headers={"retry-after": "0"},
        )
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=200, json={})
        client = FrontierClient(
            base_url="https://api.example.com/v1",
            token="tok",
            max_retries=3,
            retry_backoff_base=0.01,
        )
        status, body, headers = await client.get("/test")
        assert status == 200
        await client.close()

    async def test_etag_conditional_request(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            status_code=304,
            headers={"etag": '"abc123"'},
        )
        client = FrontierClient(base_url="https://api.example.com/v1", token="tok")
        status, body, headers = await client.get("/test", etag='"abc123"')
        assert status == 304
        request = httpx_mock.get_request(url="https://api.example.com/v1/test")
        assert request.headers["If-None-Match"] == '"abc123"'
        await client.close()

    async def test_connection_timeout_retries(self, httpx_mock: HTTPXMock):
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        httpx_mock.add_response(url="https://api.example.com/v1/test", status_code=200, json={})
        client = FrontierClient(
            base_url="https://api.example.com/v1",
            token="tok",
            max_retries=3,
            retry_backoff_base=0.01,
        )
        status, body, headers = await client.get("/test")
        assert status == 200
        await client.close()

    async def test_redirects_disabled(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            status_code=302,
            headers={"Location": "https://evil.com/steal"},
        )
        client = FrontierClient(base_url="https://api.example.com/v1", token="tok")
        status, body, headers = await client.get("/test")
        assert status == 302  # Not followed automatically
        await client.close()

    async def test_rate_limit_enforced(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://api.example.com/v1/a", status_code=200, json={})
        httpx_mock.add_response(url="https://api.example.com/v1/b", status_code=200, json={})
        client = FrontierClient(
            base_url="https://api.example.com/v1",
            token="tok",
            max_requests_per_minute=6000,  # very high to avoid waiting in tests
        )
        await client.get("/a")
        await client.get("/b")
        assert len(httpx_mock.get_requests()) == 2
        await client.close()
