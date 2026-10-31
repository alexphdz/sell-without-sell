"""SQLAlchemy ORM models for pseudonym persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PseudonymBase(DeclarativeBase):
    """Declarative base for pseudonym tables."""


class EntityPseudonym(PseudonymBase):
    __tablename__ = "entity_pseudonyms"
    __table_args__ = (
        UniqueConstraint("entity_id", "category", name="uq_entity_pseudonym"),
        Index("ix_pseudonym_entity", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    pseudonym: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UnknownPersonPseudonym(PseudonymBase):
    """Scoped pseudonyms for unresolved/unknown people detected in text."""

    __tablename__ = "unknown_person_pseudonyms"
    __table_args__ = (
        UniqueConstraint("scope_hash", "category", name="uq_unknown_pseudonym"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    pseudonym: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EquivalenceGroup(PseudonymBase):
    """Conservative grouping of registry entities that share strong corroborated identifiers."""

    __tablename__ = "equivalence_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    primary_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_ids: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
