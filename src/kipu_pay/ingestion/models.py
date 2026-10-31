"""Pydantic models for ingestion resources, manifests, and snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import ConfigDict, Field

from kipu_pay.core.models import KipuBaseModel, utc_now


class ResourceType(str, Enum):
    """Supported frontier source resource types."""

    RECORD_INDEX = "record_index"
    CHAT_CHANNELS = "chat_channels"
    CHAT_USERS = "chat_users"
    CHAT_MESSAGES = "chat_messages"
    DOCUMENT = "document"
    TABLE = "table"


class ResourceDescriptor(KipuBaseModel):
    """Lightweight descriptor discovered from upstream catalogs."""

    model_config = ConfigDict(use_enum_values=True)

    resource_type: ResourceType
    source_path: str
    identifier: str
    content_type: str | None = None
    charset: str | None = None
    expected_size: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedResource(KipuBaseModel):
    """Result of downloading or cache-reusing a single resource."""

    model_config = ConfigDict(use_enum_values=True)

    descriptor: ResourceDescriptor
    status: str  # "downloaded", "cached", "failed"
    size_bytes: int = 0
    sha256: str = ""
    etag: str | None = None
    error: str | None = None


class SnapshotManifest(KipuBaseModel):
    """Validated snapshot manifest."""

    snapshot_id: str
    status: str  # "complete", "incomplete", "failed"
    source_base_url: str
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    record_index: dict[str, Any]
    record_index_final: dict[str, Any] | None = None
    resources: list[RetrievedResource] = Field(default_factory=list)
    total_resources: int = 0
    downloaded: int = 0
    cached: int = 0
    failed: int = 0
    total_bytes: int = 0
    duration_seconds: float | None = None

    def to_disk_dict(self) -> dict[str, Any]:
        """Serialize without internal Pydantic metadata; safe for JSON."""
        return self.model_dump(mode="json")
