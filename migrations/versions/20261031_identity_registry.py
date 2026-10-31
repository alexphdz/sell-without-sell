"""Identity registry tables

Revision ID: 20261031_identity_registry
Revises: 20241031_foundation_baseline
Create Date: 2026-10-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "20261031_identity_registry"
down_revision: Union[str, None] = "20241031_foundation_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "identity_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_entity_source"),
    )

    op.create_table(
        "identity_identifiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("identity_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identifier_type", sa.String(32), nullable=False),
        sa.Column("normalized_value", sa.String(320), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("identifier_type", "normalized_value", name="uq_identifier_value"),
    )
    op.create_index("ix_identifier_entity", "identity_identifiers", ["entity_id"])

    op.create_table(
        "identity_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("identity_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.String(320), nullable=False),
        sa.Column("provenance", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entity_id", "normalized_alias", "provenance", name="uq_alias"),
    )
    op.create_index("ix_alias_normalized", "identity_aliases", ["normalized_alias"])

    op.create_table(
        "identity_source_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("identity_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_record_id", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "source_record_id", name="uq_source_link"),
    )
    op.create_index("ix_source_link_entity", "identity_source_links", ["entity_id"])

    op.create_table(
        "identity_conflicts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("identifier_type", sa.String(32), nullable=False),
        sa.Column("normalized_value_hash", sa.String(64), nullable=False),
        sa.Column("existing_entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("incoming_source_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("identity_conflicts")
    op.drop_table("identity_source_links")
    op.drop_table("identity_aliases")
    op.drop_table("identity_identifiers")
    op.drop_table("identity_entities")
