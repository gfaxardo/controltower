"""
204 — CF-H2C: Merge alembic heads (191 + 203)

Merges:
- 191_omniview_v2_serving_snapshot (OV2 serving snapshots)
- 203_yango_driver_identity_audit_day (CF-H2C shadow/audit tables)

Both branches are additive and independent.
No data migration needed.
"""

from alembic import op

revision = "204_merge_cf_h2c_heads"
down_revision = ("191_omniview_v2_serving_snapshot", "203_yango_driver_identity_audit_day")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
