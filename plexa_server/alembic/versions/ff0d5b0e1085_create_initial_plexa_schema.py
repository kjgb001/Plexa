"""create initial plexa schema

Revision ID: ff0d5b0e1085
Revises: 20260508_01
Create Date: 2026-05-08 12:47:12.159220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff0d5b0e1085'
down_revision: Union[str, Sequence[str], None] = '20260508_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
