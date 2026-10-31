"""Canonical record models and extraction context for normalization."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from kipu_pay.core.models import KipuBaseModel


class ChatRecord(KipuBaseModel):
    """Canonical chat message record."""

    model_config = ConfigDict(extra="ignore")

    id: str
    thread_id: str
    author: str
    ts: str
    text: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class DocumentRecord(KipuBaseModel):
    """Canonical document record."""

    model_config = ConfigDict(extra="ignore")

    id: str
    format: str  # pdf, html, markdown
    filename: str
    title: str | None = None
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TableRecord(KipuBaseModel):
    """Canonical table row record."""

    model_config = ConfigDict(extra="ignore")

    id: str
    table: str
    columns: dict[str, str | None] = Field(default_factory=dict)


class ExtractionContext(KipuBaseModel):
    """Internal provenance and auxiliary metadata for a canonical record."""

    model_config = ConfigDict(extra="allow")

    snapshot_id: str
    source_resource_id: str
    source_format: str
    source_record_position: int | None = None
    original_user_uid: str | None = None
    channel_name: str | None = None
    source_filename: str | None = None
    parser_warnings: list[str] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizationManifest(KipuBaseModel):
    """Manifest describing a completed normalization run."""

    snapshot_id: str
    status: str  # "complete", "failed", "incomplete"
    chats_count: int = 0
    docs_count: int = 0
    tables_count: int = 0
    extraction_errors: list[dict[str, Any]] = Field(default_factory=list)
    reconciliation_missing: list[str] = Field(default_factory=list)
    reconciliation_unexpected: list[str] = Field(default_factory=list)
    duration_seconds: float | None = None


class NormalizedDataset(KipuBaseModel):
    """Result of normalizing a snapshot."""

    snapshot_id: str
    manifest: NormalizationManifest
    chats: list[ChatRecord] = Field(default_factory=list)
    docs: list[DocumentRecord] = Field(default_factory=list)
    tables: list[TableRecord] = Field(default_factory=list)
    contexts: list[ExtractionContext] = Field(default_factory=list)
