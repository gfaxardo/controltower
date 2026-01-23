"""create_phase2c_accountability

Revision ID: 018_create_phase2c_accountability
Revises: 017_create_plan_weekly_baselines
Create Date: 2026-01-22 22:04:26.000000

FASE 2C: Accountability - Medir disciplina de ejecución de alertas/acciones 2B, SLA y seguimiento.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '018_phase2c_accountability'
down_revision = '017_create_plan_weekly_baselines'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    
    # Verificar y crear tabla phase2b_actions si no existe (fallback por si migración 015 no se ejecutó)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.phase2b_actions (
            phase2b_action_id SERIAL PRIMARY KEY,
            week_start DATE NOT NULL,
            country TEXT NOT NULL,
            city_norm TEXT,
            lob_base TEXT,
            segment TEXT,
            alert_type TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_description TEXT NOT NULL,
            owner_role TEXT NOT NULL,
            owner_user_id UUID,
            due_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT phase2b_actions_status_check 
                CHECK (status IN ('OPEN', 'IN_PROGRESS', 'DONE', 'MISSED'))
        )
    """)
    
    # Crear índices si no existen
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_week_start
        ON ops.phase2b_actions(week_start)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_owner_role
        ON ops.phase2b_actions(owner_role)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_status
        ON ops.phase2b_actions(status)
    """)

    # 1) Actualizar vista de alertas para agregar campo critical
    op.execute("DROP VIEW IF EXISTS ops.v_alerts_2b_weekly CASCADE")
    op.execute("""
        CREATE VIEW ops.v_alerts_2b_weekly AS
        WITH base AS (
            SELECT *
            FROM ops.v_plan_vs_real_weekly
            WHERE week_start < DATE_TRUNC('week', NOW())::DATE
              AND trips_plan IS NOT NULL
              AND trips_real IS NOT NULL
        ),
        enriched AS (
            SELECT
                *,
                -- dominant_driver mejorado
                CASE
                    WHEN ingreso_por_viaje_plan IS NOT NULL 
                         AND ABS(efecto_unitario) > ABS(efecto_volumen) 
                    THEN 'UNIT'
                    WHEN ingreso_por_viaje_plan IS NOT NULL 
                    THEN 'VOL'
                    ELSE 'VOL'  -- fallback si no hay plan unitario
                END as dominant_driver,
                -- severity_score: priorizar money
                (ABS(gap_revenue) * 1.0) + (ABS(gap_trips) * 0.0) as severity_score,
                -- unit_alert: solo si gap_unitario_pct <= -0.10, trips >= 10k, semana pasada
                CASE
                    WHEN gap_unitario_pct IS NOT NULL 
                         AND gap_unitario_pct <= -0.10
                         AND trips_real >= 10000
                         AND week_start < DATE_TRUNC('week', NOW())::DATE
                    THEN true
                    ELSE false
                END as unit_alert,
                -- alert_key estable
                CONCAT(
                    week_start, '|',
                    COALESCE(country, ''), '|',
                    COALESCE(city_norm, ''), '|',
                    COALESCE(lob_base, ''), '|',
                    COALESCE(segment, '')
                ) as alert_key
            FROM base
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY country
                    ORDER BY severity_score DESC NULLS LAST,
                             ABS(gap_revenue) DESC NULLS LAST,
                             ABS(gap_trips) DESC NULLS LAST
                ) as rank_money_by_country,
                ROW_NUMBER() OVER (
                    ORDER BY severity_score DESC NULLS LAST,
                             ABS(gap_revenue) DESC NULLS LAST,
                             ABS(gap_trips) DESC NULLS LAST
                ) as impacto_rank
            FROM enriched
        )
        SELECT
            week_start,
            country,
            city_norm,
            lob_base,
            segment,
            trips_real,
            trips_plan,
            gap_trips,
            gap_trips_pct,
            drivers_real,
            drivers_plan,
            gap_drivers,
            gap_drivers_pct,
            productividad_real,
            productividad_plan,
            gap_prod,
            revenue_real,
            revenue_plan,
            gap_revenue,
            gap_revenue_pct,
            ingreso_por_viaje_real,
            ingreso_por_viaje_plan,
            gap_unitario,
            gap_unitario_pct,
            efecto_volumen,
            efecto_unitario,
            trips_teoricos_por_drivers,
            trips_teoricos_por_prod,
            -- why mejorado
            CASE
                WHEN dominant_driver = 'UNIT' 
                     AND gap_unitario_pct IS NOT NULL 
                     AND gap_unitario_pct < 0
                    THEN 'Cae ingreso por viaje (unitario) — revisar promos/take/reversos/mix'
                WHEN dominant_driver = 'VOL' 
                     AND gap_trips_pct IS NOT NULL 
                     AND gap_trips_pct < 0
                    THEN 'Cae volumen — revisar supply/productividad'
                WHEN gap_trips IS NOT NULL AND gap_trips < 0
                     AND gap_drivers IS NOT NULL AND gap_drivers < 0
                    THEN 'Falta supply (drivers por debajo del plan)'
                WHEN gap_trips IS NOT NULL AND gap_trips < 0
                     AND (gap_drivers IS NULL OR gap_drivers >= 0)
                     AND gap_prod IS NOT NULL AND gap_prod < 0
                    THEN 'Baja productividad (trips/driver)'
                WHEN gap_trips_pct IS NOT NULL AND ABS(gap_trips_pct) <= 0.05
                     AND gap_revenue IS NOT NULL AND gap_revenue < 0
                    THEN 'Cae ingreso por viaje (take/promos/reversos)'
                WHEN gap_revenue IS NOT NULL AND gap_revenue < 0
                     AND ABS(efecto_unitario) >= ABS(efecto_volumen)
                    THEN 'Principalmente unitario'
                WHEN gap_revenue IS NOT NULL AND gap_revenue < 0
                     AND ABS(efecto_volumen) > ABS(efecto_unitario)
                    THEN 'Principalmente volumen'
                ELSE 'Sin clasificar'
            END as why,
            dominant_driver,
            severity_score,
            unit_alert,
            alert_key,
            rank_money_by_country,
            impacto_rank,
            -- critical: (rank_money <= 20 por país) OR (unit_alert = true) OR (abs(gap_revenue) >= 50000)
            -- Umbral configurable: abs(gap_revenue) >= 50000 (50k PEN/COP según país)
            CASE
                WHEN rank_money_by_country <= 20 THEN true
                WHEN unit_alert = true THEN true
                WHEN ABS(gap_revenue) >= 50000 THEN true
                ELSE false
            END as critical
        FROM ranked
        WHERE gap_trips_pct <= -0.10
           OR gap_revenue_pct <= -0.10
           OR gap_unitario_pct <= -0.10
           OR impacto_rank <= 20
        ORDER BY severity_score DESC NULLS LAST, ABS(gap_revenue) DESC NULLS LAST, ABS(gap_trips) DESC NULLS LAST;
    """)

    # 2) Tabla de audit (snapshot semanal de alertas)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.phase2b_alert_audit (
            audit_id BIGSERIAL PRIMARY KEY,
            week_start DATE NOT NULL,
            alert_key TEXT NOT NULL,
            country TEXT NOT NULL,
            city_norm TEXT,
            lob_base TEXT,
            segment TEXT,
            severity_score NUMERIC,
            critical BOOLEAN NOT NULL,
            gap_revenue NUMERIC,
            gap_trips NUMERIC,
            gap_unitario_pct NUMERIC,
            dominant_driver TEXT,
            why TEXT,
            snapshot_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT phase2b_alert_audit_unique UNIQUE(week_start, alert_key)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_alert_audit_week_start
        ON ops.phase2b_alert_audit(week_start)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_alert_audit_critical
        ON ops.phase2b_alert_audit(critical)
        WHERE critical = true
    """)

    # 3) Tabla de SLA status
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.phase2b_sla_status (
            sla_id BIGSERIAL PRIMARY KEY,
            week_start DATE NOT NULL,
            country TEXT NOT NULL,
            alert_key TEXT NOT NULL,
            is_critical BOOLEAN NOT NULL,
            has_action BOOLEAN NOT NULL DEFAULT false,
            action_created_at TIMESTAMPTZ,
            sla_due_at TIMESTAMPTZ NOT NULL,
            sla_status TEXT NOT NULL,
            evaluated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT phase2b_sla_status_unique UNIQUE(week_start, alert_key)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_sla_status_week_country
        ON ops.phase2b_sla_status(week_start, country)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_sla_status_breach
        ON ops.phase2b_sla_status(sla_status)
        WHERE sla_status = 'BREACH'
    """)

    # 4) Vista scoreboard semanal
    # Nota: Asume que ops.phase2b_actions existe (creada en migración 015)
    # Si no existe, la vista fallará pero se puede recrear después
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_phase2c_weekly_scoreboard AS
        WITH alerts_by_week_country AS (
            SELECT
                week_start,
                country,
                COUNT(*) as alerts_total,
                COUNT(*) FILTER (WHERE critical = true) as alerts_critical
            FROM ops.phase2b_alert_audit
            GROUP BY week_start, country
        ),
        critical_with_action AS (
            SELECT
                a.week_start,
                a.country,
                COUNT(DISTINCT a.alert_key) FILTER (WHERE act.phase2b_action_id IS NOT NULL) as critical_with_action
            FROM ops.phase2b_alert_audit a
            LEFT JOIN ops.phase2b_actions act ON (
                a.week_start = act.week_start
                AND a.country = act.country
                AND COALESCE(a.city_norm, '') = COALESCE(act.city_norm, '')
                AND COALESCE(a.lob_base, '') = COALESCE(act.lob_base, '')
                AND COALESCE(a.segment, '') = COALESCE(act.segment, '')
            )
            WHERE a.critical = true
            GROUP BY a.week_start, a.country
        ),
        actions_by_week_country_fixed AS (
            SELECT
                week_start,
                country,
                COUNT(*) as actions_total,
                COUNT(*) FILTER (WHERE status = 'DONE') as actions_done,
                COUNT(*) FILTER (WHERE status = 'MISSED') as actions_missed,
                COUNT(*) FILTER (WHERE status IN ('OPEN', 'IN_PROGRESS')) as actions_open,
                COUNT(*) FILTER (WHERE status = 'DONE' AND created_at::DATE <= due_date) as actions_done_on_time
            FROM ops.phase2b_actions
            GROUP BY week_start, country
        ),
        sla_breaches AS (
            SELECT
                week_start,
                country,
                COUNT(*) as sla_breaches
            FROM ops.phase2b_sla_status
            WHERE sla_status = 'BREACH'
            GROUP BY week_start, country
        )
        SELECT
            COALESCE(a.week_start, act.week_start) as week_start,
            COALESCE(a.country, act.country) as country,
            COALESCE(a.alerts_total, 0) as alerts_total,
            COALESCE(a.alerts_critical, 0) as alerts_critical,
            COALESCE(act.actions_total, 0) as actions_total,
            COALESCE(cwa.critical_with_action, 0) as critical_with_action,
            CASE
                WHEN COALESCE(a.alerts_critical, 0) > 0
                THEN COALESCE(cwa.critical_with_action, 0)::NUMERIC / a.alerts_critical
                ELSE NULL
            END as pct_critical_with_action,
            COALESCE(act.actions_done, 0) as actions_done,
            COALESCE(act.actions_missed, 0) as actions_missed,
            COALESCE(act.actions_open, 0) as actions_open,
            COALESCE(sb.sla_breaches, 0) as sla_breaches,
            CASE
                WHEN COALESCE(act.actions_total, 0) > 0
                THEN COALESCE(act.actions_done_on_time, 0)::NUMERIC / act.actions_total
                ELSE NULL
            END as pct_done_on_time
        FROM alerts_by_week_country a
        FULL OUTER JOIN actions_by_week_country_fixed act ON (
            a.week_start = act.week_start AND a.country = act.country
        )
        LEFT JOIN critical_with_action cwa ON (
            a.week_start = cwa.week_start AND a.country = cwa.country
        )
        LEFT JOIN sla_breaches sb ON (
            COALESCE(a.week_start, act.week_start) = sb.week_start
            AND COALESCE(a.country, act.country) = sb.country
        )
        ORDER BY week_start DESC, country;
    """)

    # 5) Vista backlog por owner
    # Nota: Asume que ops.phase2b_actions existe (creada en migración 015)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_phase2c_backlog_by_owner AS
        WITH actions_with_age AS (
            SELECT
                owner_role,
                country,
                status,
                due_date,
                CASE
                    WHEN status IN ('OPEN', 'IN_PROGRESS') THEN true
                    ELSE false
                END as is_open,
                CASE
                    WHEN status IN ('OPEN', 'IN_PROGRESS')
                         AND due_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
                    THEN true
                    ELSE false
                END as due_next_7d,
                CASE
                    WHEN status IN ('OPEN', 'IN_PROGRESS')
                         AND due_date < CURRENT_DATE
                    THEN true
                    ELSE false
                END as is_overdue,
                CASE
                    WHEN status IN ('OPEN', 'IN_PROGRESS')
                    THEN CURRENT_DATE - created_at::DATE
                    ELSE NULL
                END as age_days
            FROM ops.phase2b_actions
        )
        SELECT
            owner_role,
            country,
            COUNT(*) FILTER (WHERE is_open = true) as open_count,
            COUNT(*) FILTER (WHERE due_next_7d = true) as due_next_7d,
            COUNT(*) FILTER (WHERE is_overdue = true) as overdue_count,
            MAX(age_days) FILTER (WHERE is_open = true) as oldest_open_age_days
        FROM actions_with_age
        GROUP BY owner_role, country
        ORDER BY owner_role, country;
    """)

    # 6) Vista de breaches
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_phase2c_sla_breaches AS
        SELECT
            s.week_start,
            s.country,
            a.city_norm,
            a.lob_base,
            a.segment,
            a.severity_score,
            a.why,
            s.sla_due_at,
            s.sla_status,
            s.has_action,
            a.alert_key
        FROM ops.phase2b_sla_status s
        INNER JOIN ops.phase2b_alert_audit a ON (
            s.week_start = a.week_start
            AND s.alert_key = a.alert_key
        )
        WHERE s.sla_status = 'BREACH'
        ORDER BY s.week_start DESC, a.severity_score DESC NULLS LAST;
    """)


def downgrade() -> None:
    # Downgrade intencionalmente no destructivo
    op.execute("DROP VIEW IF EXISTS ops.v_phase2c_sla_breaches")
    op.execute("DROP VIEW IF EXISTS ops.v_phase2c_backlog_by_owner")
    op.execute("DROP VIEW IF EXISTS ops.v_phase2c_weekly_scoreboard")
    # No eliminamos tablas para preservar datos
