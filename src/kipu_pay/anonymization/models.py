"""Detection result models for PII spans and classification."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import Field

from kipu_pay.core.models import KipuBaseModel


class DetectionCategory(str, Enum):
    PERSON = "person"
    EMAIL = "email"
    PHONE = "phone"
    NATIONAL_ID = "national_id"
    ADDRESS = "address"
    DOB = "dob"
    OCCUPATION = "occupation"
    NEIGHBORHOOD = "neighborhood"
    BIRTH_YEAR = "birth_year"
    PLATE = "plate"
    ORGANIZATION = "organization"
    BRAND = "brand"
    PLACE = "place"
    PUBLIC_FIGURE = "public_figure"
    REPORTS_TO = "reports_to"
    ACCOUNT = "account"
    PASSPORT = "passport"
    HANDLE = "handle"
    QUASI_ID = "quasi_id"
    UNKNOWN = "unknown"


class Action(str, Enum):
    REPLACE = "replace"
    GENERALIZE = "generalize"
    KEEP = "keep"
    REVIEW = "review"


class DetectionSpan(KipuBaseModel):
    """A validated PII span within a single text surface."""

    start: int
    end: int
    surface_path: str
    category: DetectionCategory
    matched_text: str
    entity_id: uuid.UUID | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: str = "strong"  # strong | contextual | weak
    detector: str = ""
    action: Action = Action.REPLACE
    generalization: str | None = None  # e.g. "profesional de medios"


class DetectionResult(KipuBaseModel):
    """Per-record detection output."""

    record_id: str
    spans: list[DetectionSpan] = Field(default_factory=list)
    kept_entities: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_count: int = 0
    ambiguous_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    llm_calls: int = 0
    llm_fallbacks: int = 0
