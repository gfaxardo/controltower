"""
158 — Yango Loyalty Metric Definition Registry
Control Foundation / Data Source Governance

Creates configurable, versioned metric definition layer:
- ops.yango_loyalty_source_registry: Available data sources
- ops.yango_loyalty_metric_definition_sets: Versioned definition sets
- ops.yango_loyalty_metric_rules: Per-metric calculation rules
- ops.yango_loyalty_official_reconciliation_reference: Official Yango reference values

Additive only. No DROP. No modification to raw tables.

down_revision: 157_yango_loyalty_performance_foundation
"""

from alembic import op

revision = "158_yango_loyalty_metric_definition_registry"
down_revision = "157_yango_loyalty_performance_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")

    # 1. Source Registry
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_source_registry (
            source_key TEXT PRIMARY KEY,
            source_table TEXT NOT NULL,
            source_schema TEXT NOT NULL DEFAULT 'public',
            grain TEXT NOT NULL,
            supports_driver_id BOOLEAN NOT NULL DEFAULT false,
            supports_city BOOLEAN NOT NULL DEFAULT false,
            supports_connection_time BOOLEAN NOT NULL DEFAULT false,
            supports_supply_hours BOOLEAN NOT NULL DEFAULT false,
            supports_completed_trips BOOLEAN NOT NULL DEFAULT false,
            supports_lifecycle BOOLEAN NOT NULL DEFAULT false,
            freshness_column TEXT,
            source_confidence TEXT NOT NULL DEFAULT 'medium',
            source_scope TEXT NOT NULL DEFAULT 'lima_only',
            is_active BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    # 2. Metric Definition Sets
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_metric_definition_sets (
            definition_set_id TEXT PRIMARY KEY,
            program_key TEXT NOT NULL DEFAULT 'yango_loyalty_performance',
            country TEXT NOT NULL DEFAULT 'PE',
            city_norm TEXT NOT NULL DEFAULT 'lima',
            effective_from TEXT,
            effective_to TEXT,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'active', 'locked', 'deprecated')),
            validation_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (validation_status IN ('pending', 'warning', 'blocked', 'passed')),
            created_by TEXT DEFAULT 'system',
            approved_by TEXT,
            approved_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    # 3. Metric Rules
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_metric_rules (
            rule_id SERIAL PRIMARY KEY,
            definition_set_id TEXT NOT NULL REFERENCES ops.yango_loyalty_metric_definition_sets(definition_set_id),
            metric_key TEXT NOT NULL
                CHECK (metric_key IN ('active_drivers', 'supply_hours',
                                       'new_drivers', 'reactivated_drivers', 'new_plus_reactivated')),
            source_key TEXT REFERENCES ops.yango_loyalty_source_registry(source_key),
            calculation_strategy TEXT NOT NULL,
            activity_signal TEXT,
            threshold_value NUMERIC,
            threshold_unit TEXT,
            lookback_days INTEGER,
            inactive_days INTEGER,
            aggregation_method TEXT,
            fallback_source_key TEXT,
            definition_status TEXT NOT NULL DEFAULT 'provisional'
                CHECK (definition_status IN ('final', 'provisional_pending_validation', 'blocked')),
            source_confidence TEXT NOT NULL DEFAULT 'medium',
            is_active BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    # 4. Reconciliation Reference
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_official_reconciliation_reference (
            reference_id SERIAL PRIMARY KEY,
            month_start TEXT NOT NULL,
            country TEXT NOT NULL DEFAULT 'PE',
            city_norm TEXT NOT NULL DEFAULT 'lima',
            metric_key TEXT NOT NULL
                CHECK (metric_key IN ('active_drivers', 'supply_hours', 'new_plus_reactivated')),
            official_value NUMERIC NOT NULL,
            official_target_value NUMERIC,
            official_source TEXT,
            received_at TIMESTAMPTZ DEFAULT now(),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (month_start, country, city_norm, metric_key)
        );
    """)

    # Indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_loyalty_def_sets_status
        ON ops.yango_loyalty_metric_definition_sets (status, country, city_norm);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_loyalty_metric_rules_def_set
        ON ops.yango_loyalty_metric_rules (definition_set_id, metric_key);
    """)

    # --- Seed Data ---

    # Sources
    op.execute("""
        INSERT INTO ops.yango_loyalty_source_registry
            (source_key, source_table, source_schema, grain, supports_driver_id, supports_city,
             supports_supply_hours, supports_completed_trips, supports_lifecycle,
             source_confidence, notes)
        VALUES
            ('fleet_summary_daily', 'module_ct_fleet_summary_daily', 'public', 'daily',
             true, false, true, true, false, 'high', 'Source confirmed Lima-only. 30/30 days April 2026.'),
            ('real_business_slice_month', 'real_business_slice_month_fact', 'ops', 'monthly_city_slice',
             false, true, false, true, false, 'high', 'Official CT source. city-resolved. Auto regular slice filters for Yango matching.'),
            ('trips_2026', 'trips_2026', 'public', 'trip_event',
             true, false, false, true, false, 'medium', 'conductor_id. Needs park join for city. condicion=Completado for completed trips.'),
            ('trips_2025', 'trips_2025', 'public', 'trip_event',
             true, false, false, true, false, 'medium', 'Historical trip data for first-trip detection.'),
            ('dim_park', 'dim_park', 'dim', 'park',
             false, true, false, false, false, 'high', 'Park-to-city mapping. Used to filter trips by Lima parks.'),
            ('fleet_summary_daily_active', 'module_ct_fleet_summary_daily', 'public', 'daily',
             true, false, false, true, false, 'high', 'Same as fleet_summary but filtered WHERE count_orders_completed > 0.')
        ON CONFLICT (source_key) DO NOTHING;
    """)

    # Official reconciliation reference — April 2026 Lima
    op.execute("""
        INSERT INTO ops.yango_loyalty_official_reconciliation_reference
            (month_start, country, city_norm, metric_key, official_value, official_target_value,
             official_source, notes)
        VALUES
            ('2026-04', 'PE', 'lima', 'active_drivers',          5601,  5295,
             'Yango Official Report April 2026', 'Meta AD=5295, Result=5601'),
            ('2026-04', 'PE', 'lima', 'supply_hours',            357000, 356000,
             'Yango Official Report April 2026', 'Meta SH=356000, Result=357000'),
            ('2026-04', 'PE', 'lima', 'new_plus_reactivated',    1064,  1261,
             'Yango Official Report April 2026', 'Meta N+R=1261, Result=1064')
        ON CONFLICT (month_start, country, city_norm, metric_key) DO NOTHING;
    """)

    # Definition sets: 5 candidate strategies
    sets_to_create = [
        ("trips_based_fallback", "AD/SH from trips; N+R from first-trip & reactivation via trips history"),
        ("connection_based", "AD from connection via fleet_summary; SH from fleet_summary; N+R from first connection"),
        ("supply_based", "AD from count where supply_hours>0; SH = SUM(work_time_hours); N+R from first supply day"),
        ("lifecycle_candidate", "AD/SH/N+R from ops.v_driver_weekly_churn_reactivation if populated"),
        ("hybrid_ct_default", "AD from real_business_slice Auto regular; SH from fleet_summary; N+R from fleet-scoped trips"),
    ]
    for ds_id, notes in sets_to_create:
        op.execute(f"""
            INSERT INTO ops.yango_loyalty_metric_definition_sets
                (definition_set_id, status, validation_status, notes)
            VALUES ('{ds_id}', 'draft', 'pending', '{notes}')
            ON CONFLICT (definition_set_id) DO NOTHING;
        """)

    # Metric rules for each set
    _seed_rules(op)


def _seed_rules(op):
    rules = [
        # trips_based_fallback
        ("trips_based_fallback", "active_drivers", "trips_2026",
         "count_distinct_drivers_with_completed_trips", "count_orders_completed > 0", None, None,
         "provisional_pending_validation", "medium", "Uses trips_2026 + dim_park for Lima filter. May overcount."),
        ("trips_based_fallback", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None,
         "final", "high", "SUM(work_time_hours) from fleet_summary_daily, all rows."),
        ("trips_based_fallback", "new_drivers", "trips_2025",
         "first_completed_trip_in_month", "first_trip_date", 365, None,
         "provisional_pending_validation", "medium", "First trip from trips_2025+2026, Lima parks only."),
        ("trips_based_fallback", "reactivated_drivers", "trips_2025",
         "inactive_30d_then_active_current_month", "completed_trip", 30, 30,
         "provisional_pending_validation", "medium", "30-day inactivity window before month start."),

        # connection_based
        ("connection_based", "active_drivers", "fleet_summary_daily",
         "count_distinct_drivers_with_any_connection", "driver_id", None, None,
         "final", "high", "All drivers appearing in fleet_summary (even 0 completed trips)."),
        ("connection_based", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None,
         "final", "high", "SUM(work_time_hours), all rows."),
        ("connection_based", "new_drivers", "fleet_summary_daily",
         "first_appearance_in_fleet_summary", "MIN(fecha)", None, None,
         "provisional_pending_validation", "medium", "First fecha in fleet_summary. Fleet_summary starts 2026-02, may miss older drivers."),
        ("connection_based", "reactivated_drivers", "fleet_summary_daily",
         "inactive_in_fleet_summary_30d", "fecha", 30, 30,
         "provisional_pending_validation", "low", "fleet_summary only goes back to Feb 2026. Reactivation detection unreliable."),

        # supply_based
        ("supply_based", "active_drivers", "fleet_summary_daily",
         "count_distinct_drivers_with_work_time_hours_gt_0", "work_time_hours > 0", None, None,
         "final", "high", "Drivers with any work_time_hours in the month."),
        ("supply_based", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None,
         "final", "high", "Standard SH sum."),
        ("supply_based", "new_drivers", "fleet_summary_daily",
         "first_day_with_work_time_hours_gt_0", "MIN(fecha WHERE work_time_hours > 0)", None, None,
         "provisional_pending_validation", "medium", "First day with hours. Same vintage limitation as connection_based."),
        ("supply_based", "reactivated_drivers", "fleet_summary_daily",
         "no_hours_30d_then_hours_current", "work_time_hours", 30, 30,
         "provisional_pending_validation", "low", "Vintage limitation."),

        # lifecycle_candidate
        ("lifecycle_candidate", "active_drivers", "real_business_slice_month",
         "sum_active_drivers_auto_regular", "active_drivers", None, None,
         "final", "high", "From real_business_slice, Auto regular only."),
        ("lifecycle_candidate", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None,
         "final", "high", "Standard SH from fleet_summary."),
        ("lifecycle_candidate", "new_drivers", "fleet_summary_daily_active",
         "first_completed_trip_in_month_fleet_scope", "first_activity", 365, None,
         "provisional_pending_validation", "medium", "New from fleet_summary active drivers. Cross-referenced with trips history."),
        ("lifecycle_candidate", "reactivated_drivers", "fleet_summary_daily_active",
         "reactivated_30d_from_fleet_and_trips", "completed_trip", 30, 30,
         "provisional_pending_validation", "medium", "Uses fleet_summary universe + trips for history."),

        # hybrid_ct_default
        ("hybrid_ct_default", "active_drivers", "real_business_slice_month",
         "sum_active_drivers_auto_regular_only", "active_drivers", None, None,
         "final", "high", "SUM active_drivers from real_business_slice, Auto regular slice only."),
        ("hybrid_ct_default", "supply_hours", "fleet_summary_daily",
         "sum_work_time_hours_all_rows", "work_time_hours", None, None,
         "final", "high", "Standard SH from fleet_summary."),
        ("hybrid_ct_default", "new_drivers", "fleet_summary_daily_active",
         "first_completed_trip_in_fleet_universe", "first_trip_date", 365, None,
         "provisional_pending_validation", "medium", "First completed trip only for drivers in fleet_summary. Uses trips_2025+2026 for history."),
        ("hybrid_ct_default", "reactivated_drivers", "fleet_summary_daily_active",
         "reactivated_fleet_scope_30d_inactive", "completed_trip", 30, 30,
         "provisional_pending_validation", "medium", "Fleet-summary universe, trips-based history, 30d inactivity."),
    ]
    for r in rules:
        op.execute(f"""
            INSERT INTO ops.yango_loyalty_metric_rules
                (definition_set_id, metric_key, source_key, calculation_strategy, activity_signal,
                 lookback_days, inactive_days, definition_status, source_confidence, notes)
            VALUES ('{r[0]}', '{r[1]}', '{r[2]}', '{r[3]}', '{r[4]}', {r[5] or 'NULL'}, {r[6] or 'NULL'},
                    '{r[7]}', '{r[8]}', '{r[9]}')
            ON CONFLICT DO NOTHING;
        """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_metric_rules;")
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_metric_definition_sets;")
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_official_reconciliation_reference;")
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_source_registry;")
