"""Pydantic models for registry results and identity resolution."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import Field

from kipu_pay.core.models import KipuBaseModel


class RegistryResult(KipuBaseModel):
    """Summary of a registry build/import run."""

    entities_created: int = 0
    entities_existing: int = 0
    identifiers_created: int = 0
    aliases_created: int = 0
    source_links_created: int = 0
    conflicts_recorded: int = 0
    slack_uids_mapped: int = 0
    errors: list[str] = Field(default_factory=list)


class ResolutionStatus(str, Enum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class ConfidenceLevel(str, Enum):
    STRONG = "strong"
    CONTEXTUAL = "contextual"
    WEAK = "weak"
    NONE = "none"


class ResolutionContext(KipuBaseModel):
    """Context accompanying a mention to be resolved."""

    source_type: str = ""  # chat | document | table
    source_record_id: str = ""
    channel_name: str | None = None
    author_slack_uid: str | None = None
    expected_source_id: str | None = None  # e.g. known cliente_id from a FK


class ResolutionResult(KipuBaseModel):
    """Structured result of resolving a single mention."""

    status: ResolutionStatus
    entity_id: uuid.UUID | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.NONE
    candidate_entity_ids: list[uuid.UUID] = Field(default_factory=list)
    detail: str = ""
