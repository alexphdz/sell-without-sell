"""Tests for resource discovery with mocked upstream."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kipu_pay.ingestion.client import FrontierClient
from kipu_pay.ingestion.discovery import ResourceDiscovery


@pytest.fixture
async def discovery(httpx_mock: HTTPXMock):
    client = FrontierClient(base_url="https://api.example.com/v1", token="tok")
    disc = ResourceDiscovery(client)
    yield disc
    await client.close()


async def test_discover_record_index(httpx_mock: HTTPXMock, discovery):
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={"chats": 5, "docs": 2, "tables": 1}, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)
    index, descriptors = await discovery.discover_all()
    assert index == {"chats": 5, "docs": 2, "tables": 1}
    assert any(d.resource_type == "record_index" for d in descriptors)


async def test_discover_channels_and_dates(httpx_mock: HTTPXMock, discovery):
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={}, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=["general", "support"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/general", json=["2024-01-01", "2024-01-02"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/support", json=["2024-01-01"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)
    index, descriptors = await discovery.discover_all()
    msgs = [d for d in descriptors if d.resource_type == "chat_messages"]
    assert len(msgs) == 3
    assert all(m.source_path.startswith("/chats/") for m in msgs)
    # Verify name-based paths
    assert any(m.source_path == "/chats/general/2024-01-01" for m in msgs)
    assert any(m.source_path == "/chats/support/2024-01-01" for m in msgs)


async def test_discover_channels_with_id_vs_name(httpx_mock: HTTPXMock, discovery):
    """Regression: channel API routes use *name*, not Slack *id*."""
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={}, is_reusable=True)
    httpx_mock.add_response(
        url="https://api.example.com/v1/chats/channels",
        json=[
            {"id": "C0ABC123", "name": "soporte-cobros", "purpose": {"value": "test"}},
            {"id": "C0DEF456", "name": "soporte-tarjetas"},
        ],
        is_reusable=True,
    )
    # Dates endpoints must be called with NAME, not ID
    httpx_mock.add_response(url="https://api.example.com/v1/chats/soporte-cobros", json=["2024-01-01"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/soporte-tarjetas", json=["2024-01-02"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)

    index, descriptors = await discovery.discover_all()
    msgs = [d for d in descriptors if d.resource_type == "chat_messages"]
    assert len(msgs) == 2

    # Verify paths use names
    paths = {m.source_path for m in msgs}
    assert "/chats/soporte-cobros/2024-01-01" in paths
    assert "/chats/soporte-tarjetas/2024-01-02" in paths

    # Verify IDs are preserved in metadata
    cobros = [m for m in msgs if m.metadata.get("channel_name") == "soporte-cobros"][0]
    assert cobros.metadata.get("channel_id") == "C0ABC123"

    # Ensure the old broken ID-based path was NEVER called
    id_requests = [r for r in httpx_mock.get_requests() if "/chats/C0" in str(r.url)]
    assert len(id_requests) == 0, "Discovery must not use Slack ID for API paths"


async def test_discover_channel_dates_404_fails(httpx_mock: HTTPXMock, discovery):
    """A channel advertised in /chats/channels but whose dates 404 is a hard failure."""
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={}, is_reusable=True)
    httpx_mock.add_response(
        url="https://api.example.com/v1/chats/channels",
        json=[{"id": "C0X", "name": "general"}],
        is_reusable=True,
    )
    httpx_mock.add_response(url="https://api.example.com/v1/chats/general", status_code=404, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_optional=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_optional=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_optional=True)

    with pytest.raises(RuntimeError):
        await discovery.discover_all()


async def test_discover_docs_and_tables(httpx_mock: HTTPXMock, discovery):
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={}, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=["doc1.pdf", "doc2.html"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=["clientes.csv", "transacciones.xml"], is_reusable=True)
    index, descriptors = await discovery.discover_all()
    docs = [d for d in descriptors if d.resource_type == "document"]
    tables = [d for d in descriptors if d.resource_type == "table"]
    assert len(docs) == 2
    assert len(tables) == 2
    assert docs[0].source_path == "/docs/doc1.pdf"


async def test_discover_empty_catalogs(httpx_mock: HTTPXMock, discovery):
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={}, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)
    index, descriptors = await discovery.discover_all()
    assert index == {}
    assert len(descriptors) == 2  # record_index + chat_users


async def test_discover_duplicate_items(httpx_mock: HTTPXMock, discovery):
    httpx_mock.add_response(url="https://api.example.com/v1/record_index", json={}, is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/channels", json=["a", "a"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/a", json=["2024-01-01"], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/chats/users", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/docs", json=[], is_reusable=True)
    httpx_mock.add_response(url="https://api.example.com/v1/tables", json=[], is_reusable=True)
    index, descriptors = await discovery.discover_all()
    msgs = [d for d in descriptors if d.resource_type == "chat_messages"]
    assert len(msgs) == 2
