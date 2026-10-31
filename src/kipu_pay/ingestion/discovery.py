"""Dynamic resource discovery from the FRONTIER Sources API."""

from __future__ import annotations

import json
from typing import Any

from kipu_pay.ingestion.client import FrontierClient
from kipu_pay.ingestion.models import ResourceDescriptor, ResourceType
from kipu_pay.core.logging import get_logger

logger = get_logger(__name__)


def _extract_id(item: Any, key: str = "id") -> str | None:
    """Safely extract an identifier from a catalog item (string or dict)."""
    if isinstance(item, dict):
        val = item.get(key)
        if val is None:
            return None
        return str(val)
    if isinstance(item, str):
        return item
    return str(item)


def _extract_name(item: Any) -> str | None:
    """Extract name from a catalog item (dict with 'name' or string)."""
    if isinstance(item, dict):
        val = item.get("name")
        if val is None:
            return None
        return str(val)
    if isinstance(item, str):
        return item
    return str(item)


class ResourceDiscovery:
    """Discover all available source resources from upstream catalogs."""

    def __init__(self, client: FrontierClient) -> None:
        self._client = client

    async def discover_all(self) -> tuple[dict[str, Any], list[ResourceDescriptor]]:
        """Return (record_index, list of all resource descriptors).

        Channel paths use the channel *name* (e.g. ``soporte-cobros``) because
        the FRONTIER API routes are ``/chats/{name}`` and ``/chats/{name}/{date}``.
        The Slack internal ``id`` is preserved in descriptor metadata.
        """
        record_index = await self._fetch_json("/record_index")
        descriptors: list[ResourceDescriptor] = []

        descriptors.append(
            ResourceDescriptor(
                resource_type=ResourceType.RECORD_INDEX,
                source_path="/record_index",
                identifier="record_index",
                content_type="application/json",
            )
        )

        # Chat channels → dates → messages
        channels = await self._fetch_json("/chats/channels", allow_404=False)
        if isinstance(channels, list):
            for channel in channels:
                ch_name = _extract_name(channel)
                ch_id = _extract_id(channel, key="id")
                if not ch_name:
                    logger.warning("channel_missing_name", raw=repr(channel)[:200])
                    continue
                # Dates endpoint: 404 here means the channel advertises
                # itself in /chats/channels but has no dates endpoint.
                dates = await self._fetch_json(
                    f"/chats/{ch_name}", allow_404=False
                )
                if isinstance(dates, list):
                    for date in dates:
                        date_str = _extract_id(date, key="date")
                        if not date_str:
                            date_str = str(date)
                        descriptors.append(
                            ResourceDescriptor(
                                resource_type=ResourceType.CHAT_MESSAGES,
                                source_path=f"/chats/{ch_name}/{date_str}",
                                identifier=f"chat_{ch_name}_{date_str}",
                                content_type="application/json",
                                metadata={
                                    "channel_id": ch_id or "",
                                    "channel_name": ch_name,
                                },
                            )
                        )

        # Chat users
        users = await self._fetch_json("/chats/users")
        if users is not None:
            descriptors.append(
                ResourceDescriptor(
                    resource_type=ResourceType.CHAT_USERS,
                    source_path="/chats/users",
                    identifier="chat_users",
                    content_type="application/json",
                )
            )

        # Documents
        docs = await self._fetch_json("/docs")
        if isinstance(docs, list):
            for doc in docs:
                doc_id = _extract_id(doc, key="id")
                if not doc_id:
                    continue
                doc_meta = doc if isinstance(doc, dict) else {}
                content_type = "application/octet-stream"
                fmt = doc_meta.get("format", "").lower()
                if fmt == "html":
                    content_type = "text/html"
                elif fmt == "pdf":
                    content_type = "application/pdf"
                elif fmt == "markdown":
                    content_type = "text/markdown"
                descriptors.append(
                    ResourceDescriptor(
                        resource_type=ResourceType.DOCUMENT,
                        source_path=f"/docs/{doc_id}",
                        identifier=f"doc_{doc_id}",
                        content_type=content_type,
                    )
                )

        # Tables
        tables = await self._fetch_json("/tables")
        if isinstance(tables, list):
            for table in tables:
                table_name = _extract_name(table)
                if not table_name:
                    continue
                table_meta = table if isinstance(table, dict) else {}
                charset = table_meta.get("charset")
                content_type = "text/csv"
                fmt = table_meta.get("format", "").lower()
                if fmt == "xml":
                    content_type = "application/xml"
                elif fmt == "csv":
                    content_type = "text/csv"
                descriptors.append(
                    ResourceDescriptor(
                        resource_type=ResourceType.TABLE,
                        source_path=f"/tables/{table_name}",
                        identifier=f"table_{table_name}",
                        content_type=content_type,
                        charset=charset,
                    )
                )

        return record_index, descriptors

    async def _fetch_json(
        self, path: str, *, allow_404: bool = True
    ) -> Any:
        """Fetch JSON from path; raise on unexpected errors.

        By default a 404 returns ``[]`` (useful for optional endpoints).
        Pass ``allow_404=False`` when the endpoint *must* exist; a 404
        then raises ``RuntimeError`` so the orchestrator can fail the
        snapshot.
        """
        status, body, _headers = await self._client.get(path)
        if status == 200:
            return json.loads(body.decode("utf-8"))
        if status == 404:
            if allow_404:
                return []
            raise RuntimeError(
                f"Discovery failed for {path}: HTTP 404 (endpoint not found)"
            )
        raise RuntimeError(f"Discovery failed for {path}: HTTP {status}")
