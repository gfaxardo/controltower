"""152 — Yango Loyalty Reachability Engine — Fase 3A.

Crea:
  - ops.yango_loyalty_kpi_registry: catálogo de KPIs Yango Oro/Plata/Bronce
  - ops.yango_loyalty_monthly_goals: metas mensuales por ciudad y KPI
  - ops.yango_loyalty_manual_results: resultados manuales (KPIs sin fuente automatizada)
"""
from alembic import op

revision = "152_yango_loyalty_reachability_engine"
down_revision = "151_autocobro_eligibility_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")

    # ── KPI Registry ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_kpi_registry (
            id              BIGSERIAL PRIMARY KEY,
            kpi_code        TEXT NOT NULL UNIQUE,
            kpi_name        TEXT NOT NULL,
            category        TEXT NOT NULL CHECK (category IN ('AD', 'SH', 'N_R', 'CALLS', 'CONVERSION', 'UFC', 'COMMS', 'SUPPORT', 'SOCIAL')),
            source_type     TEXT NOT NULL DEFAULT 'future_integration'
                            CHECK (source_type IN ('available_now', 'manual_input', 'future_integration')),
            source_table    TEXT,
            source_query    TEXT,
            unit            TEXT NOT NULL DEFAULT 'count',
            gold_threshold  NUMERIC(5,2),
            silver_threshold NUMERIC(5,2),
            bronze_threshold NUMERIC(5,2),
            higher_is_better BOOLEAN NOT NULL DEFAULT true,
            owner           TEXT,
            notes           TEXT,
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now()
        )
    """)

    # ── Monthly Goals ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_monthly_goals (
            id              BIGSERIAL PRIMARY KEY,
            month           TEXT NOT NULL,
            country         TEXT NOT NULL DEFAULT 'PE',
            city            TEXT NOT NULL,
            kpi_code        TEXT NOT NULL REFERENCES ops.yango_loyalty_kpi_registry(kpi_code),
            target_value    NUMERIC NOT NULL,
            gold_min        NUMERIC,
            silver_min      NUMERIC,
            bronze_min      NUMERIC,
            source_type     TEXT NOT NULL DEFAULT 'manual_input',
            owner           TEXT,
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now(),
            UNIQUE (month, country, city, kpi_code)
        )
    """)

    # ── Manual Results ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_loyalty_manual_results (
            id              BIGSERIAL PRIMARY KEY,
            month           TEXT NOT NULL,
            country         TEXT NOT NULL DEFAULT 'PE',
            city            TEXT NOT NULL,
            kpi_code        TEXT NOT NULL REFERENCES ops.yango_loyalty_kpi_registry(kpi_code),
            real_value      NUMERIC,
            source_note     TEXT,
            owner           TEXT,
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now(),
            UNIQUE (month, country, city, kpi_code)
        )
    """)

    # ── Seed KPI Registry ──
    op.execute("""
        INSERT INTO ops.yango_loyalty_kpi_registry
            (kpi_code, kpi_name, category, source_type, source_table, unit, gold_threshold, silver_threshold, bronze_threshold, higher_is_better, owner, notes)
        VALUES
            ('AD',      'Active Drivers',           'AD',        'available_now',
             'ops.real_business_slice_month_fact',
             'count',   95, 85, 70, true,  'ops', 'Drivers activos con completed_flag en el mes'),
            ('SH',      'Supply Hours',             'SH',        'manual_input',
             NULL,
             'hours',   95, 85, 70, true,  'ops', 'Horas de supply agregadas. Fuente pendiente de integración.'),
            ('N_R',     'Nuevos + Reactivados',     'N_R',       'available_now',
             'ops.mv_driver_lifecycle_weekly_kpis',
             'count',   90, 80, 65, true,  'ops', 'Suma de activaciones + reactivaciones en el mes'),
            ('CALLS',   'Calls efectivas',          'CALLS',     'manual_input',
             NULL,
             'count',   90, 80, 65, true,  'ops', 'Llamadas efectivas a drivers. Fuente pendiente de integración.'),
            ('CONV_NEW','Conversión nuevos',        'CONVERSION','manual_input',
             NULL,
             'pct',     25, 15, 10, true, 'ops', 'Tasa de conversión de nuevos registrados a primer viaje.'),
            ('CONV_REA','Conversión reactivados',   'CONVERSION','manual_input',
             NULL,
             'pct',     15, 10, 5,  true, 'ops', 'Tasa de conversión de reactivados contactados a primer viaje.'),
            ('UFC',     '% AD en UFC',              'UFC',       'manual_input',
             NULL,
             'pct',     70, 50, 30, true, 'ops', '% de AD que pertenecen a UFC. Fuente pendiente de integración.'),
            ('COMMS',   'Fleetroom communications', 'COMMS',     'manual_input',
             NULL,
             'score',   90, 75, 60, true, 'comms', 'Score de comunicaciones en Fleetroom. Fuente pendiente.'),
            ('SUPPORT', 'Support MS score',         'SUPPORT',   'manual_input',
             NULL,
             'score',   90, 75, 60, true, 'support', 'Mystery Shopper score de soporte. Fuente pendiente.'),
            ('SOCIAL',  'Social Media score',       'SOCIAL',    'manual_input',
             NULL,
             'score',   90, 75, 60, true, 'marketing', 'Score de presencia en redes sociales. Fuente pendiente.')
        ON CONFLICT (kpi_code) DO UPDATE SET
            kpi_name   = EXCLUDED.kpi_name,
            category   = EXCLUDED.category,
            source_type= EXCLUDED.source_type,
            unit       = EXCLUDED.unit,
            gold_threshold   = EXCLUDED.gold_threshold,
            silver_threshold = EXCLUDED.silver_threshold,
            bronze_threshold = EXCLUDED.bronze_threshold,
            higher_is_better = EXCLUDED.higher_is_better,
            owner      = EXCLUDED.owner,
            notes      = EXCLUDED.notes,
            updated_at = now()
    """)

    # Indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_loyalty_goals_month_city
            ON ops.yango_loyalty_monthly_goals (month, country, city)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_loyalty_manual_month_city
            ON ops.yango_loyalty_manual_results (month, country, city)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_manual_results CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_monthly_goals CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.yango_loyalty_kpi_registry CASCADE")
