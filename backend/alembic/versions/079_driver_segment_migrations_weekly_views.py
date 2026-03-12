"""
Time-first migration analytics: v_driver_segment_migrations_weekly,
v_driver_segments_weekly_summary, v_driver_segment_critical_movements.
Additive only; no drops. Uses existing ops.mv_driver_segments_weekly and ops.mv_supply_segments_weekly.
"""
from alembic import op

revision = "079_driver_segment_migrations_weekly_views"
down_revision = "078_segment_taxonomy_elite_legend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PHASE 2: Base view — weekly migration aggregates (week_first)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_segment_migrations_weekly AS
        WITH m AS (
            SELECT
                d.week_start,
                d.park_id,
                d.prev_segment_week AS from_segment,
                d.segment_week AS to_segment,
                CASE d.segment_change_type
                    WHEN 'upshift' THEN 'upgrade'
                    WHEN 'downshift' THEN 'downgrade'
                    WHEN 'drop' THEN 'downgrade'
                    WHEN 'stable' THEN 'same'
                    WHEN 'new' THEN 'upgrade'
                    ELSE 'same'
                END AS transition_type,
                COUNT(*)::bigint AS drivers
            FROM ops.mv_driver_segments_weekly d
            WHERE d.park_id IS NOT NULL
              AND (d.prev_segment_week IS NOT NULL OR d.segment_change_type = 'new')
            GROUP BY d.week_start, d.park_id, d.prev_segment_week, d.segment_week, d.segment_change_type
        ),
        prev AS (
            SELECT week_start, park_id, segment_week, drivers_count
            FROM ops.mv_supply_segments_weekly
        )
        SELECT
            m.week_start,
            'S' || EXTRACT(WEEK FROM m.week_start)::integer || '-' || EXTRACT(ISOYEAR FROM m.week_start)::integer AS week_label,
            m.park_id,
            m.from_segment,
            m.to_segment,
            m.transition_type,
            m.drivers,
            CASE
                WHEN prev.drivers_count IS NOT NULL AND prev.drivers_count > 0
                THEN ROUND((m.drivers::numeric / prev.drivers_count), 6)
                ELSE NULL
            END AS rate
        FROM m
        LEFT JOIN prev ON prev.park_id = m.park_id
          AND prev.week_start = (m.week_start - 7)
          AND prev.segment_week = m.from_segment
    """)
    op.execute("COMMENT ON VIEW ops.v_driver_segment_migrations_weekly IS 'Weekly migration aggregates by park, from_segment, to_segment. Time-first analytics base. Additive layer.'")

    # PHASE 3: Weekly segment summary (WoW, upgrades, downgrades)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_segments_weekly_summary AS
        WITH supply AS (
            SELECT
                week_start,
                park_id,
                segment_week AS segment,
                drivers_count AS drivers,
                LAG(drivers_count) OVER (PARTITION BY park_id, segment_week ORDER BY week_start) AS drivers_prev_week
            FROM ops.mv_supply_segments_weekly
        ),
        up_down AS (
            SELECT
                week_start,
                park_id,
                to_segment AS segment,
                SUM(drivers) FILTER (WHERE transition_type = 'upgrade') AS upgrades,
                SUM(drivers) FILTER (WHERE transition_type = 'downgrade') AS downgrades_in
            FROM ops.v_driver_segment_migrations_weekly
            GROUP BY week_start, park_id, to_segment
        ),
        down_out AS (
            SELECT
                week_start,
                park_id,
                from_segment AS segment,
                SUM(drivers) AS downgrades
            FROM ops.v_driver_segment_migrations_weekly
            WHERE transition_type = 'downgrade'
            GROUP BY week_start, park_id, from_segment
        )
        SELECT
            s.week_start,
            'S' || EXTRACT(WEEK FROM s.week_start)::integer || '-' || EXTRACT(ISOYEAR FROM s.week_start)::integer AS week_label,
            s.park_id,
            s.segment,
            s.drivers,
            s.drivers_prev_week,
            (s.drivers - s.drivers_prev_week) AS wow_delta,
            CASE
                WHEN s.drivers_prev_week IS NOT NULL AND s.drivers_prev_week > 0
                THEN ROUND((s.drivers - s.drivers_prev_week)::numeric / s.drivers_prev_week, 6)
                ELSE NULL
            END AS wow_percent,
            COALESCE(u.upgrades, 0)::bigint AS upgrades,
            COALESCE(d.downgrades, 0)::bigint AS downgrades
        FROM supply s
        LEFT JOIN up_down u ON u.week_start = s.week_start AND u.park_id = s.park_id AND u.segment = s.segment
        LEFT JOIN down_out d ON d.week_start = s.week_start AND d.park_id = s.park_id AND d.segment = s.segment
    """)
    op.execute("COMMENT ON VIEW ops.v_driver_segments_weekly_summary IS 'Weekly segment summary with WoW delta/percent and upgrade/downgrade counts. Time-first analytics.'")

    # PHASE 4: Critical movements (drivers > 100 OR rate > 15%)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_segment_critical_movements AS
        SELECT
            week_label,
            week_start,
            park_id,
            from_segment,
            to_segment,
            drivers,
            rate,
            transition_type,
            CASE
                WHEN drivers > 100 OR (rate IS NOT NULL AND rate > 0.15) THEN true
                ELSE false
            END AS critical_flag
        FROM ops.v_driver_segment_migrations_weekly
        WHERE drivers > 100 OR (rate IS NOT NULL AND rate > 0.15)
    """)
    op.execute("COMMENT ON VIEW ops.v_driver_segment_critical_movements IS 'Migration rows flagged critical: drivers > 100 or rate > 15%. Additive layer.'")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_driver_segment_critical_movements")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_segments_weekly_summary")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_segment_migrations_weekly")
