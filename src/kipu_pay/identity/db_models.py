"""SQLAlchemy ORM models for the persistent identity registry."""

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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class IdentityBase(DeclarativeBase):
    """Declarative base for identity registry tables."""


class IdentityEntity(IdentityBase):
    __tablename__ = "identity_entities"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_entity_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="person")
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    identifiers: Mapped[list["IdentityIdentifier"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    aliases: Mapped[list["IdentityAlias"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    source_links: Mapped[list["IdentitySourceLink"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class IdentityIdentifier(IdentityBase):
    __tablename__ = "identity_identifiers"
    __table_args__ = (
        UniqueConstraint("identifier_type", "normalized_value", name="uq_identifier_value"),
        Index("ix_identifier_entity", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_entities.id", ondelete="CASCADE"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(320), nullable=False)
    original_value: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped[IdentityEntity] = relationship(back_populates="identifiers")


class IdentityAlias(IdentityBase):
    __tablename__ = "identity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "normalized_alias", "provenance", name="uq_alias"),
        Index("ix_alias_normalized", "normalized_alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_entities.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(320), nullable=False)
    provenance: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped[IdentityEntity] = relationship(back_populates="aliases")


class IdentitySourceLink(IdentityBase):
    __tablename__ = "identity_source_links"
    __table_args__ = (
        UniqueConstraint("source_type", "source_record_id", name="uq_source_link"),
        Index("ix_source_link_entity", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_entities.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped[IdentityEntity] = relationship(back_populates="source_links")


class IdentityConflict(IdentityBase):
    __tablename__ = "identity_conflicts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    identifier_type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    existing_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    incoming_source_reference: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
