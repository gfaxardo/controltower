"""
208 — CF-H2D: Merge heads (204_obs + 207_scheduler)

down_revision: 204_yego_lima_observability, 207_cf_h2d_scheduler_watermark
"""

from alembic import op

revision = "208_merge_cf_h2d_heads"
down_revision = ("204_yego_lima_observability", "207_cf_h2d_scheduler_watermark")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
