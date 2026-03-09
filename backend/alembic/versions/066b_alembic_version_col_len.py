"""
Amplía alembic_version.version_num de VARCHAR(32) a VARCHAR(64).
Necesario para revisiones largas como 067_mv_driver_segments_weekly_join_config (36 chars).
"""
from alembic import op
import sqlalchemy as sa

revision = "066b_alembic_version_col"
down_revision = "066_supply_refresh_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.VARCHAR(length=32),
        type_=sa.VARCHAR(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.VARCHAR(length=64),
        type_=sa.VARCHAR(length=32),
        existing_nullable=False,
    )
