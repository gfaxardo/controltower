"""create_plan_weekly_baselines

Revision ID: 017_create_plan_weekly_baselines
Revises: 016_enhance_weekly_margin
Create Date: 2026-01-22 21:56:36.000000

FASE 2B: Parametrizar baseline (período representativo) por país para weights de Plan Semanal.
PE usa baseline desde 2025-04-01 (excluir operación pequeña). CO mantiene continuidad.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '017_create_plan_weekly_baselines'
down_revision = '016_enhance_weekly_margin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    # 1) Crear tabla de baselines
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.plan_weekly_baselines (
            baseline_id SERIAL PRIMARY KEY,
            baseline_tag TEXT UNIQUE NOT NULL,
            country TEXT NULL,  -- 'PE','CO' ; null = global fallback
            baseline_start_date DATE NOT NULL,
            baseline_end_date DATE NOT NULL,
            reason TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Índices
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_weekly_baselines_country_active
        ON ops.plan_weekly_baselines(country, is_active)
        WHERE is_active = true
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_weekly_baselines_active
        ON ops.plan_weekly_baselines(is_active)
        WHERE is_active = true
    """)

    # Constraint: solo 1 baseline activo por country (y opcional 1 global activo)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_plan_weekly_baselines_unique_active_country
        ON ops.plan_weekly_baselines(country, is_active)
        WHERE is_active = true AND country IS NOT NULL
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_plan_weekly_baselines_unique_active_global
        ON ops.plan_weekly_baselines(is_active)
        WHERE is_active = true AND country IS NULL
    """)

    # 2) Vista de baseline efectivo por país
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_weekly_baseline_effective AS
        WITH countries_present AS (
            SELECT DISTINCT country
            FROM (
                SELECT DISTINCT country FROM ops.mv_real_trips_weekly WHERE country IS NOT NULL AND country != ''
                UNION
                SELECT DISTINCT country FROM ops.v_plan_trips_weekly_from_monthly WHERE country IS NOT NULL AND country != ''
            ) c
            WHERE country IS NOT NULL AND country != ''
        ),
        country_baselines AS (
            SELECT DISTINCT ON (c.country)
                c.country,
                b.baseline_tag,
                b.baseline_start_date,
                b.baseline_end_date
            FROM countries_present c
            LEFT JOIN ops.plan_weekly_baselines b ON (
                b.country = c.country
                AND b.is_active = true
            )
            ORDER BY c.country, b.baseline_id DESC NULLS LAST
        ),
        global_baseline AS (
            SELECT
                baseline_tag,
                baseline_start_date,
                baseline_end_date
            FROM ops.plan_weekly_baselines
            WHERE country IS NULL
              AND is_active = true
            LIMIT 1
        )
        SELECT
            cb.country,
            COALESCE(cb.baseline_tag, gb.baseline_tag) as baseline_tag,
            COALESCE(cb.baseline_start_date, gb.baseline_start_date) as baseline_start_date,
            COALESCE(cb.baseline_end_date, gb.baseline_end_date) as baseline_end_date
        FROM country_baselines cb
        CROSS JOIN global_baseline gb
        WHERE COALESCE(cb.baseline_tag, gb.baseline_tag) IS NOT NULL;
    """)

    # 3) Vista de cobertura real sobre baseline efectivo
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_coverage_baseline_by_key AS
        WITH baseline_effective AS (
            SELECT * FROM ops.v_plan_weekly_baseline_effective
        ),
        real_daily_keys AS (
            SELECT DISTINCT
                COALESCE(dp.country, '') as country,
                LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
                COALESCE(dp.default_line_of_business, t.tipo_servicio) as lob_base,
                CASE
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END as segment
            FROM public.trips_all t
            LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje IS NOT NULL
        ),
        real_by_key_date AS (
            SELECT
                COALESCE(dp.country, '') as country,
                LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
                COALESCE(dp.default_line_of_business, t.tipo_servicio) as lob_base,
                CASE
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END as segment,
                t.fecha_inicio_viaje::DATE as date_base,
                COUNT(*) as trips_present
            FROM public.trips_all t
            LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje IS NOT NULL
            GROUP BY
                COALESCE(dp.country, ''),
                LOWER(TRIM(COALESCE(dp.city, ''))),
                COALESCE(dp.default_line_of_business, t.tipo_servicio),
                CASE
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END,
                t.fecha_inicio_viaje::DATE
        ),
        coverage_by_key AS (
            SELECT
                rk.country,
                rk.city_norm,
                rk.lob_base,
                rk.segment,
                be.baseline_tag,
                be.baseline_start_date,
                be.baseline_end_date,
                COUNT(DISTINCT rk.date_base) as days_present,
                (be.baseline_end_date - be.baseline_start_date + 1) as days_expected,
                CASE
                    WHEN (be.baseline_end_date - be.baseline_start_date + 1) > 0
                    THEN COUNT(DISTINCT rk.date_base)::NUMERIC / (be.baseline_end_date - be.baseline_start_date + 1)
                    ELSE 0
                END as coverage_pct,
                SUM(rk.trips_present) as trips_present
            FROM real_by_key_date rk
            INNER JOIN baseline_effective be ON rk.country = be.country
            WHERE rk.date_base BETWEEN be.baseline_start_date AND be.baseline_end_date
            GROUP BY
                rk.country,
                rk.city_norm,
                rk.lob_base,
                rk.segment,
                be.baseline_tag,
                be.baseline_start_date,
                be.baseline_end_date
        )
        SELECT
            country,
            city_norm,
            lob_base,
            segment,
            baseline_tag,
            baseline_start_date,
            baseline_end_date,
            days_present,
            days_expected,
            coverage_pct,
            trips_present,
            -- ready: coverage_pct >= 0.80 AND trips_present >= 1000
            -- Parámetros: min_coverage = 0.80 (80%), min_trips = 1000
            -- Estos valores pueden ajustarse según necesidades operativas
            CASE
                WHEN coverage_pct >= 0.80 AND trips_present >= 1000 THEN true
                ELSE false
            END as ready
        FROM coverage_by_key;
    """)

    # 4) Verificar si existe tabla de weights y renombrar o extender
    op.execute("""
        DO $$
        BEGIN
            -- Verificar si existe ops.plan_weekly_weights_2025
            IF EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_weekly_weights_2025'
            ) THEN
                -- Renombrar a ops.plan_weekly_weights_baseline
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'ops' 
                    AND table_name = 'plan_weekly_weights_baseline'
                ) THEN
                    ALTER TABLE ops.plan_weekly_weights_2025 
                    RENAME TO plan_weekly_weights_baseline;
                END IF;
            END IF;

            -- Si no existe ninguna, crear estructura base (solo metadata, no poblar)
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_weekly_weights_baseline'
            ) THEN
                CREATE TABLE ops.plan_weekly_weights_baseline (
                    weight_id SERIAL PRIMARY KEY,
                    baseline_tag TEXT NOT NULL,
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    country TEXT,
                    city_norm TEXT,
                    lob_base TEXT,
                    segment TEXT,
                    weight_value NUMERIC,
                    is_ready BOOLEAN DEFAULT false,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            END IF;

            -- Agregar columnas si no existen (para compatibilidad con tabla existente)
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_weekly_weights_baseline' 
                AND column_name = 'baseline_tag'
            ) THEN
                ALTER TABLE ops.plan_weekly_weights_baseline 
                ADD COLUMN baseline_tag TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_weekly_weights_baseline' 
                AND column_name = 'period_start'
            ) THEN
                ALTER TABLE ops.plan_weekly_weights_baseline 
                ADD COLUMN period_start DATE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_weekly_weights_baseline' 
                AND column_name = 'period_end'
            ) THEN
                ALTER TABLE ops.plan_weekly_weights_baseline 
                ADD COLUMN period_end DATE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_weekly_weights_baseline' 
                AND column_name = 'is_ready'
            ) THEN
                ALTER TABLE ops.plan_weekly_weights_baseline 
                ADD COLUMN is_ready BOOLEAN DEFAULT false;
            END IF;
        END $$;
    """)

    # 5) Insertar baselines iniciales (PE y CO)
    # Primero desactivar cualquier baseline global previo
    op.execute("""
        UPDATE ops.plan_weekly_baselines
        SET is_active = false
        WHERE country IS NULL AND is_active = true
    """)

    # Insertar baseline para PE (post-relaunch desde 2025-04-01)
    op.execute("""
        INSERT INTO ops.plan_weekly_baselines (
            baseline_tag, country, baseline_start_date, baseline_end_date, reason, is_active
        )
        SELECT
            'PE_post_relaunch_2025_04',
            'PE',
            '2025-04-01'::DATE,
            COALESCE(
                (SELECT MAX(t.fecha_inicio_viaje::DATE)
                 FROM public.trips_all t
                 INNER JOIN dim.dim_park dp ON t.park_id = dp.park_id
                 WHERE t.condicion = 'Completado'
                   AND t.fecha_inicio_viaje IS NOT NULL
                   AND dp.country = 'PE'),
                CURRENT_DATE
            ),
            'PE: operación seria con Yango desde abril 2025; excluir etapa autos propios',
            true
        ON CONFLICT (baseline_tag) DO UPDATE SET
            baseline_start_date = EXCLUDED.baseline_start_date,
            baseline_end_date = EXCLUDED.baseline_end_date,
            reason = EXCLUDED.reason,
            is_active = EXCLUDED.is_active;
    """)

    # Insertar baseline para CO (continuidad desde 2025-01-01 o primer día disponible)
    op.execute("""
        INSERT INTO ops.plan_weekly_baselines (
            baseline_tag, country, baseline_start_date, baseline_end_date, reason, is_active
        )
        SELECT
            'CO_continuity_2025',
            'CO',
            COALESCE(
                (SELECT MIN(t.fecha_inicio_viaje::DATE)
                 FROM public.trips_all t
                 INNER JOIN dim.dim_park dp ON t.park_id = dp.park_id
                 WHERE t.condicion = 'Completado'
                   AND t.fecha_inicio_viaje IS NOT NULL
                   AND dp.country = 'CO'
                   AND t.fecha_inicio_viaje::DATE >= '2025-01-01'::DATE),
                '2025-01-01'::DATE
            ),
            COALESCE(
                (SELECT MAX(t.fecha_inicio_viaje::DATE)
                 FROM public.trips_all t
                 INNER JOIN dim.dim_park dp ON t.park_id = dp.park_id
                 WHERE t.condicion = 'Completado'
                   AND t.fecha_inicio_viaje IS NOT NULL
                   AND dp.country = 'CO'),
                CURRENT_DATE
            ),
            'CO: continuidad operativa; usar baseline completo',
            true
        ON CONFLICT (baseline_tag) DO UPDATE SET
            baseline_start_date = EXCLUDED.baseline_start_date,
            baseline_end_date = EXCLUDED.baseline_end_date,
            reason = EXCLUDED.reason,
            is_active = EXCLUDED.is_active;
    """)


def downgrade() -> None:
    # Downgrade intencionalmente no destructivo
    op.execute("DROP VIEW IF EXISTS ops.v_real_coverage_baseline_by_key")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_weekly_baseline_effective")
    # No eliminamos la tabla de baselines ni weights para preservar datos
