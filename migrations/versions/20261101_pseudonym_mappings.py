"""Pseudonym persistence tables.

Revision ID: 20261101_pseudonym_mappings
Revises: 20261031_identity_registry
Create Date: 2026-11-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261101_pseudonym_mappings"
down_revision: Union[str, None] = "20261031_identity_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entity_pseudonyms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("pseudonym", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("entity_id", "category", name="uq_entity_pseudonym"),
        sa.Index("ix_pseudonym_entity", "entity_id"),
    )

    op.create_table(
        "unknown_person_pseudonyms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("pseudonym", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("scope_hash", "category", name="uq_unknown_pseudonym"),
    )

    op.create_table(
        "equivalence_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("primary_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_ids", sa.Text, nullable=False, default=""),
        sa.Column("reason", sa.Text, nullable=False, default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("equivalence_groups")
    op.drop_table("unknown_person_pseudonyms")
    op.drop_table("entity_pseudonyms")
