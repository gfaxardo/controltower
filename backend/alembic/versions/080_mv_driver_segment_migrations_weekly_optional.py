"""
Optional: materialized view for migration analytics when dataset is large (>1M rows).
Replicates ops.v_driver_segment_migrations_weekly with indexes on week_start, from_segment, to_segment.
Additive and reversible.
"""
from alembic import op

revision = "080_mv_driver_segment_migrations_weekly_optional"
down_revision = "079_driver_segment_migrations_weekly_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_segment_migrations_weekly AS
        SELECT * FROM ops.v_driver_segment_migrations_weekly
    """)
    op.execute("CREATE UNIQUE INDEX ux_mv_driver_segment_migrations_weekly_park_week_from_to_type ON ops.mv_driver_segment_migrations_weekly (park_id, week_start, from_segment, to_segment, transition_type)")
    op.execute("CREATE INDEX ix_mv_driver_segment_migrations_weekly_week_start ON ops.mv_driver_segment_migrations_weekly (week_start)")
    op.execute("CREATE INDEX ix_mv_driver_segment_migrations_weekly_from_to ON ops.mv_driver_segment_migrations_weekly (from_segment, to_segment)")
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_driver_segment_migrations_weekly IS 'Materialized copy of v_driver_segment_migrations_weekly for performance when dataset is large. Refresh with REFRESH MATERIALIZED VIEW CONCURRENTLY.'")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_segment_migrations_weekly")
