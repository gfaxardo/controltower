"""
206 — CF-H2C.1: Merge branch heads (202_yego_lima_taxonomy_v2 + 205)

Merges:
- 202_yego_lima_taxonomy_v2 (Lima Growth taxonomy v2)
- 205_yango_driver_identity_map_shadow (CF-H2C.1 driver identity)

Both branches are additive and independent.
No data migration needed.
"""

from alembic import op

revision = "206_merge_cf_h2c1_heads"
down_revision = ("202_yego_lima_taxonomy_v2", "205_yango_driver_identity_map_shadow")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
