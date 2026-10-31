"""Foundation baseline

Revision ID: 20241031_foundation_baseline
Revises:
Create Date: 2024-10-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20241031_foundation_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Foundation baseline: no tables yet. Domain tables added in later modules.
    pass


def downgrade() -> None:
    pass
