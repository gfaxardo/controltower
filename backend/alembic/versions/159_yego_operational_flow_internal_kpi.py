"""
159 — YEGO Operational Flow Internal KPI

Extends metric definition registry with metric_universe support.
Adds yego_operational definition sets, rules, and internal KPI infrastructure.

Additive only. No DROP. No modification to raw tables.

down_revision: 158_yango_loyalty_metric_definition_registry
"""

from alembic import op

revision = "159_yego_operational_flow_internal_kpi"
down_revision = "158_yango_loyalty_metric_definition_registry"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Extend metric_definition_sets with universe columns
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_definition_sets
        ADD COLUMN IF NOT EXISTS metric_universe TEXT NOT NULL DEFAULT 'yango_official'
            CHECK (metric_universe IN ('yango_official', 'yego_operational'));
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_definition_sets
        ADD COLUMN IF NOT EXISTS metric_scope TEXT NOT NULL DEFAULT 'pilot_lima';
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_definition_sets
        ADD COLUMN IF NOT EXISTS official_comparable BOOLEAN NOT NULL DEFAULT true;
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_definition_sets
        ADD COLUMN IF NOT EXISTS scoring_eligible BOOLEAN NOT NULL DEFAULT true;
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_definition_sets
        ADD COLUMN IF NOT EXISTS usage_type TEXT NOT NULL DEFAULT 'official_scoring'
            CHECK (usage_type IN ('official_scoring', 'internal_management', 'reconciliation_only'));
    """)

    # 2. Extend metric_rules with universe columns
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_rules
        ADD COLUMN IF NOT EXISTS metric_universe TEXT NOT NULL DEFAULT 'yango_official';
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_metric_rules
        ADD COLUMN IF NOT EXISTS scoring_eligible BOOLEAN NOT NULL DEFAULT true;
    """)

    # 3. Mark existing sets as yango_official
    op.execute("""
        UPDATE ops.yango_loyalty_metric_definition_sets
        SET metric_universe = 'yango_official', usage_type = 'official_scoring',
            official_comparable = true, scoring_eligible = true
        WHERE metric_universe = 'yango_official';
    """)

    # 4. Create yego_operational definition sets (5 variants)
    op_sets = [
        ("yego_operational_supply_30d", "New = first supply_hours>0. Reactivated = no SH 30d then active. Source: fleet_summary."),
        ("yego_operational_supply_60d", "Same as supply_30d but 60-day inactivity window."),
        ("yego_operational_supply_90d", "Same as supply_30d but 90-day inactivity window."),
        ("yego_operational_trips_30d", "New = first completed trip. Reactivated = no trips 30d then active. Source: trips."),
        ("yego_operational_connection_30d", "New = first connection. Reactivated = no connection 30d then active. Source: fleet_summary any driver."),
    ]
    for ds_id, notes in op_sets:
        op.execute(f"""
            INSERT INTO ops.yango_loyalty_metric_definition_sets
                (definition_set_id, status, validation_status, metric_universe, metric_scope,
                 official_comparable, scoring_eligible, usage_type, notes)
            VALUES ('{ds_id}', 'draft', 'pending', 'yego_operational', 'pilot_lima',
                    false, false, 'internal_management', '{notes}')
            ON CONFLICT (definition_set_id) DO UPDATE SET
                metric_universe = 'yego_operational',
                official_comparable = false,
                scoring_eligible = false,
                usage_type = 'internal_management';
        """)

    # 5. Seed rules for each yego_operational set
    _seed_yego_operational_rules(op)


def _seed_yego_operational_rules(op):
    rules = [
        # supply_30d
        ("yego_operational_supply_30d", "active_drivers", "fleet_summary_daily",
         "count_distinct_with_supply_hours_gt_0", "work_time_hours > 0", None, None, "final", "high",
         "AD = COUNT(DISTINCT driver_id) WHERE work_time_hours > 0 in month"),

        ("yego_operational_supply_30d", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None, "final", "high",
         "Standard SH from fleet_summary"),

        ("yego_operational_supply_30d", "new_drivers", "fleet_summary_daily",
         "first_day_with_supply_hours_gt_0", "MIN(fecha WHERE work_time_hours > 0)", 365, None, "provisional_pending_validation", "medium",
         "New = first day with SH>0 in fleet_summary history. Limited to fleet_summary vintage (2026-02+)."),

        ("yego_operational_supply_30d", "reactivated_drivers", "fleet_summary_daily",
         "inactive_in_sh_30d_then_active_current_month", "work_time_hours > 0", 30, 30, "provisional_pending_validation", "medium",
         "Reactivated = had SH>0 before, none in 30d before month, has SH>0 in month."),

        # supply_60d
        ("yego_operational_supply_60d", "active_drivers", "fleet_summary_daily",
         "count_distinct_with_supply_hours_gt_0", "work_time_hours > 0", None, None, "final", "high",
         "Same AD definition."),
        ("yego_operational_supply_60d", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None, "final", "high", "Standard SH."),
        ("yego_operational_supply_60d", "new_drivers", "fleet_summary_daily",
         "first_day_with_supply_hours_gt_0", "MIN(fecha WHERE work_time_hours > 0)", 365, None, "provisional_pending_validation", "medium",
         "New same definition."),
        ("yego_operational_supply_60d", "reactivated_drivers", "fleet_summary_daily",
         "inactive_in_sh_60d_then_active", "work_time_hours > 0", 60, 60, "provisional_pending_validation", "medium",
         "Reactivated with 60-day window."),

        # supply_90d
        ("yego_operational_supply_90d", "active_drivers", "fleet_summary_daily",
         "count_distinct_with_supply_hours_gt_0", "work_time_hours > 0", None, None, "final", "high", "Same AD."),
        ("yego_operational_supply_90d", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None, "final", "high", "Standard SH."),
        ("yego_operational_supply_90d", "new_drivers", "fleet_summary_daily",
         "first_day_with_supply_hours_gt_0", "MIN(fecha WHERE work_time_hours > 0)", 365, None, "provisional_pending_validation", "medium", "New same."),
        ("yego_operational_supply_90d", "reactivated_drivers", "fleet_summary_daily",
         "inactive_in_sh_90d_then_active", "work_time_hours > 0", 90, 90, "provisional_pending_validation", "medium",
         "Reactivated with 90-day window."),

        # trips_30d
        ("yego_operational_trips_30d", "active_drivers", "fleet_summary_daily_active",
         "count_distinct_with_completed_trips", "count_orders_completed > 0", None, None, "final", "high",
         "AD from fleet_summary active (completed>0)."),
        ("yego_operational_trips_30d", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None, "final", "high", "Standard SH."),
        ("yego_operational_trips_30d", "new_drivers", "trips_2026",
         "first_completed_trip_fleet_universe", "first_trip_date", 365, None, "provisional_pending_validation", "medium",
         "New = first completed trip in fleet_summary universe, cross-ref trips_2025+2026."),
        ("yego_operational_trips_30d", "reactivated_drivers", "trips_2026",
         "reactivated_fleet_scope_30d_inactive", "completed_trip", 30, 30, "provisional_pending_validation", "medium",
         "Reactivated = fleet universe, 30d inactivity via trips history."),

        # connection_30d
        ("yego_operational_connection_30d", "active_drivers", "fleet_summary_daily",
         "count_distinct_all_drivers", "driver_id", None, None, "final", "high",
         "AD = all drivers appearing in fleet_summary (even 0 SH)."),
        ("yego_operational_connection_30d", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None, "final", "high", "Standard SH."),
        ("yego_operational_connection_30d", "new_drivers", "fleet_summary_daily",
         "first_appearance_in_fleet_summary", "MIN(fecha)", None, None, "provisional_pending_validation", "low",
         "First fecha in fleet_summary. Vintage limited (2026-02+)."),
        ("yego_operational_connection_30d", "reactivated_drivers", "fleet_summary_daily",
         "inactive_in_fleet_30d_then_active", "fecha", 30, 30, "provisional_pending_validation", "low",
         "Reactivation via fleet_summary alone. Vintage limited."),
    ]

    for r in rules:
        op.execute(f"""
            INSERT INTO ops.yango_loyalty_metric_rules
                (definition_set_id, metric_key, source_key, calculation_strategy, activity_signal,
                 lookback_days, inactive_days, definition_status, source_confidence,
                 metric_universe, scoring_eligible, notes)
            VALUES ('{r[0]}', '{r[1]}', '{r[2]}', '{r[3]}', '{r[4]}',
                    {r[5] or 'NULL'}, {r[6] or 'NULL'}, '{r[7]}', '{r[8]}',
                    'yego_operational', false, '{r[9]}')
            ON CONFLICT DO NOTHING;
        """)


def downgrade():
    # Remove yego_operational def sets and rules
    op.execute("DELETE FROM ops.yango_loyalty_metric_rules WHERE metric_universe = 'yego_operational';")
    op.execute("DELETE FROM ops.yango_loyalty_metric_definition_sets WHERE metric_universe = 'yego_operational';")
    # Drop new columns (optional, additive so we can leave them)
