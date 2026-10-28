"""series_id and reminder_sent_at on appointments

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("series_id", sa.String(length=64), nullable=True))
    op.add_column("appointments", sa.Column("reminder_sent_at", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "reminder_sent_at")
    op.drop_column("appointments", "series_id")
