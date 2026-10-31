"""pipeline jobs table

Revision ID: 20261101_pipeline_jobs
Revises: 20261101_pseudonym_mappings
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_pipeline_jobs"
down_revision: Union[str, None] = "20261101_pseudonym_mappings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chats_count", sa.Integer, nullable=True),
        sa.Column("docs_count", sa.Integer, nullable=True),
        sa.Column("tables_count", sa.Integer, nullable=True),
        sa.Column("seconds", sa.Float, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pipeline_jobs")
