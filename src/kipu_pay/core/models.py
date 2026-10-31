"""Shared base models and data types."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KipuBaseModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        extra="ignore",
    )


class JobStatus(str, Enum):
    """Background job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingJob(KipuBaseModel):
    """Generic background job descriptor."""

    id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(default=JobStatus.PENDING)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(KipuBaseModel):
    """Participant API health contract."""

    status: str = "ok"
    team: str
    version: str
    models: list[str] = Field(default_factory=list)
