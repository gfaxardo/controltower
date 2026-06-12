"""
210 — CF-H2G: Omniview Canonical Source Mapper Foundation

Creates:
- ops.omniview_metric_source_registry
- ops.omniview_canonical_day_fact_shadow

Shadow mode only — does NOT modify production Omniview serving facts.
Does NOT change UI data sources. Does NOT promote Yango.

down_revision: 209_yego_lima_v2_pipeline_scheduler_foundation
"""

from alembic import op

revision = "210_cf_h2g_omniview_canonical_source_mapper"
down_revision = "209_yego_lima_v2_pipeline_scheduler_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.omniview_metric_source_registry (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            metric_name         text NOT NULL UNIQUE,
            metric_label        text,
            metric_tier         text NOT NULL DEFAULT 'core',
            canonical_owner     text NOT NULL,
            shadow_validator    text,
            fallback_source     text,
            source_badge        text NOT NULL DEFAULT 'CT_BRIDGE',
            grain               text NOT NULL DEFAULT 'day',
            formula_sql_reference text,
            confidence          text NOT NULL DEFAULT 'MEDIUM',
            promotion_status    text NOT NULL DEFAULT 'NOT_CERTIFIED',
            rollback_source     text,
            is_active           boolean NOT NULL DEFAULT true,
            sort_order          integer DEFAULT 0,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.omniview_canonical_day_fact_shadow (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_date             date NOT NULL,
            park_id                 text NOT NULL,
            city                    text DEFAULT 'lima',
            country                 text DEFAULT 'peru',

            completed_trips_value           numeric(18,2),
            completed_trips_source_badge    text,
            completed_trips_coverage_pct    numeric(5,2),
            completed_trips_freshness_min   numeric(10,2),
            completed_trips_reconciliation  text,

            active_drivers_value            numeric(18,2),
            active_drivers_source_badge     text,
            active_drivers_coverage_pct     numeric(5,2),
            active_drivers_freshness_min    numeric(10,2),
            active_drivers_reconciliation   text,

            revenue_yego_value              numeric(18,4),
            revenue_yego_source_badge       text,
            revenue_yego_coverage_pct       numeric(5,2),
            revenue_yego_freshness_min      numeric(10,2),
            revenue_yego_reconciliation     text,

            gmv_total_value                 numeric(18,4),
            gmv_total_source_badge          text,
            gmv_total_coverage_pct          numeric(5,2),
            gmv_total_freshness_min         numeric(10,2),
            gmv_total_reconciliation        text,

            avg_ticket_value                numeric(18,4),
            avg_ticket_source_badge         text,
            avg_ticket_coverage_pct         numeric(5,2),
            avg_ticket_freshness_min        numeric(10,2),
            avg_ticket_reconciliation       text,

            trips_per_driver_value          numeric(18,4),
            trips_per_driver_source_badge   text,
            trips_per_driver_coverage_pct   numeric(5,2),
            trips_per_driver_freshness_min  numeric(10,2),
            trips_per_driver_reconciliation text,

            revenue_per_order_value         numeric(18,4),
            revenue_per_order_source_badge  text,
            revenue_per_order_coverage_pct  numeric(5,2),
            revenue_per_order_freshness_min numeric(10,2),
            revenue_per_order_reconciliation text,

            commission_rate_value           numeric(18,4),
            commission_rate_source_badge    text,
            commission_rate_coverage_pct    numeric(5,2),
            commission_rate_freshness_min   numeric(10,2),
            commission_rate_reconciliation  text,

            cancelled_trips_value           numeric(18,2),
            cancelled_trips_source_badge    text,
            cancelled_trips_coverage_pct    numeric(5,2),
            cancelled_trips_freshness_min   numeric(10,2),
            cancelled_trips_reconciliation  text,

            cancel_rate_pct_value           numeric(8,4),
            cancel_rate_pct_source_badge    text,
            cancel_rate_pct_coverage_pct    numeric(5,2),
            cancel_rate_pct_freshness_min   numeric(10,2),
            cancel_rate_pct_reconciliation  text,

            generated_at            timestamptz NOT NULL DEFAULT now(),
            mapper_version          text DEFAULT 'CF-H2G-1.0',
            fallback_used           boolean DEFAULT false,
            fallback_details        jsonb,

            UNIQUE (source_date, park_id)
        );
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_canonical_day_shadow_park_date "
        "ON ops.omniview_canonical_day_fact_shadow (park_id, source_date);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_metric_source_registry_active "
        "ON ops.omniview_metric_source_registry (is_active, metric_tier, sort_order);"
    )

    op.execute("""
        INSERT INTO ops.omniview_metric_source_registry
            (metric_name, metric_label, metric_tier, canonical_owner, shadow_validator,
             fallback_source, source_badge, grain, formula_sql_reference, confidence,
             promotion_status, rollback_source, is_active, sort_order)
        VALUES
        ('completed_trips',       'Trips Completados',     'core',   'YANGO', 'CT trips_completed',    'CT_BRIDGE', 'CT_BRIDGE', 'day', 'COUNT(DISTINCT order_id) FROM raw_yango.orders_raw WHERE order_status=''complete''', 'HIGH', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 1),
        ('cancelled_trips',       'Trips Cancelados',      'core',   'CT_BRIDGE', NULL,              NULL,        'CT_BRIDGE', 'day', 'SUM(trips_cancelled) FROM ops.real_business_slice_day_fact', 'MEDIUM', 'NOT_CERTIFIED', NULL, true, 2),
        ('total_orders',          'Total Ordenes',         'core',   'HYBRID', NULL,                 'YANGO',     'HYBRID',    'day', 'K1 + K2', 'MEDIUM', 'READY', NULL, true, 3),
        ('active_drivers',        'Conductores Activos',   'core',   'YANGO', 'CT active_drivers',    'CT_BRIDGE', 'CT_BRIDGE', 'day', 'COUNT(DISTINCT driver_profile_id) FROM raw_yango.orders_raw', 'HIGH', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 4),
        ('revenue_yego',          'Revenue YEGO',          'core',   'YANGO', 'CT revenue_yego_final','CT_BRIDGE', 'CT_BRIDGE', 'day', 'SUM(ABS(amount)) FROM raw_yango.transactions_raw WHERE category_name=''Partner fee for trip''', 'HIGH', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 5),
        ('gmv',                   'GMV',                   'core',   'YANGO', NULL,                   'CT_BRIDGE', 'CT_BRIDGE', 'day', 'SUM(amount) FROM raw_yango.transactions_raw WHERE category_name IN (''Cash'',''Card payment'',''Corporate payment'')', 'HIGH', 'SHADOW_ACCUMULATING', 'MISSING', true, 6),
        ('avg_ticket',            'Ticket Promedio',       'derived','YANGO', 'CT avg_ticket',        'CT_BRIDGE', 'CT_BRIDGE', 'day', 'GMV / completed_trips', 'HIGH', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 7),
        ('trips_per_driver',      'Viajes por Conductor',  'derived','YANGO', 'CT trips_per_driver',  'CT_BRIDGE', 'CT_BRIDGE', 'day', 'completed_trips / active_drivers', 'HIGH', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 8),
        ('revenue_per_order',     'Revenue por Orden',     'derived','YANGO', NULL,                   'CT_BRIDGE', 'CT_BRIDGE', 'day', 'revenue_yego / completed_trips', 'HIGH', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 9),
        ('commission_rate',       'Tasa de Comision',      'derived','YANGO', 'CT commission_pct',    'CT_BRIDGE', 'CT_BRIDGE', 'day', 'Service fee / GMV', 'MEDIUM', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', true, 10),
        ('cancel_rate_pct',       'Tasa de Cancelacion',   'derived','HYBRID', NULL,                  'CT_BRIDGE', 'HYBRID',    'day', 'cancelled / (completed + cancelled)', 'MEDIUM', 'NOT_CERTIFIED', NULL, true, 11),
        ('driver_identity',       'Identidad Conductor',   'identity','SHARED',NULL,                  'CT_BRIDGE', 'SHARED',    'per-driver', 'driver_profile_id = driver_id = conductor_id', 'VERY_HIGH', 'READY', NULL, true, 12),
        ('new_drivers',           'Nuevos Conductores',    'lifecycle','CT_BRIDGE',NULL,              'CT_BRIDGE', 'CT_BRIDGE', 'day', 'COUNT FROM public.drivers WHERE hire_date >= N days', 'HIGH', 'SHADOW_ONLY', NULL, true, 13),
        ('reactivated_drivers',   'Reactivados',           'lifecycle','CT_BRIDGE',NULL,              'CT_BRIDGE', 'CT_BRIDGE', 'day', 'lifecycle_daily logic', 'MEDIUM', 'BLOCKED', NULL, true, 14),
        ('churned_drivers',       'Churn',                 'lifecycle','CT_BRIDGE',NULL,              'CT_BRIDGE', 'CT_BRIDGE', 'day', 'lifecycle_daily logic', 'MEDIUM', 'BLOCKED', NULL, true, 15),
        ('supply_hours',          'Horas Online',          'lifecycle','BLOCKED',NULL,                'CT_BRIDGE', 'BLOCKED',   'day', 'GET /v2/parks/contractors/supply-hours (per-driver)', 'LOW', 'BLOCKED', NULL, false, 16),
        ('business_slice',        'Segmento de Negocio',   'dimensional','REQUIRES_MAPPING',NULL,     'CT_BRIDGE', 'CT_BRIDGE', 'per-fact', 'category -> dim.yango_category_to_slice', 'MEDIUM', 'BLOCKED', NULL, false, 17),
        ('park',                  'Park',                  'dimensional','SHARED',NULL,                'dim_park',  'SHARED',    'per-fact', 'api_park_credentials_registry.park_id = dim_park.park_id', 'HIGH', 'READY', NULL, true, 18),
        ('city',                  'City',                  'dimensional','SHARED',NULL,                'dim_park',  'SHARED',    'per-fact', 'dim_park.city', 'HIGH', 'READY', NULL, true, 19),
        ('country',               'Country',               'dimensional','SHARED',NULL,                'dim_park',  'SHARED',    'per-fact', 'dim_park.country', 'HIGH', 'READY', NULL, true, 20),
        ('scout_cohorts_programs','Scout/Cohortes/Programs','program','CT_BRIDGE',NULL,               'CT_BRIDGE', 'CT_BRIDGE', 'day', 'growth schema program tables', 'MEDIUM', 'SHADOW_ONLY', NULL, true, 21)
        ON CONFLICT (metric_name) DO NOTHING;
    """)

    op.execute("""
        INSERT INTO ops.omniview_canonical_day_fact_shadow
            (source_date, park_id, city, country, mapper_version, fallback_used)
        SELECT
            o.order_date,
            '08e20910d81d42658d4334d3f6d10ac0',
            'lima',
            'peru',
            'CF-H2G-1.0-seed',
            false
        FROM raw_yango.mv_orders_day o
        WHERE o.park_id = '08e20910d81d42658d4334d3f6d10ac0'
          AND o.orders_completed > 0
        ON CONFLICT (source_date, park_id) DO NOTHING;
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.omniview_canonical_day_fact_shadow CASCADE;")
    op.execute("DROP TABLE IF EXISTS ops.omniview_metric_source_registry CASCADE;")
