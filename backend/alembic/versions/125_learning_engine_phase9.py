"""
Learning Engine — fase 9: extensión del log, reglas de evaluación, vista de
efectividad y columnas de feedback en el engine output.

Revision ID: 125_learning_engine_phase9
Revises: 124_action_orchestrator_phase8
"""
from alembic import op

revision = "125_learning_engine_phase9"
down_revision = "124_action_orchestrator_phase8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── L1: Extender action_execution_log con columnas de resultado ──────
    op.execute("""
        ALTER TABLE ops.action_execution_log
        ADD COLUMN IF NOT EXISTS result_metric TEXT,
        ADD COLUMN IF NOT EXISTS result_value_before NUMERIC,
        ADD COLUMN IF NOT EXISTS result_value_after NUMERIC,
        ADD COLUMN IF NOT EXISTS result_delta NUMERIC,
        ADD COLUMN IF NOT EXISTS success_flag BOOLEAN,
        ADD COLUMN IF NOT EXISTS evaluation_window_days INTEGER,
        ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.result_metric IS
        'Métrica usada para medir resultado (active_drivers, trips, cancel_rate, revenue, proxy_pct, etc.)'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.result_value_before IS
        'Valor de result_metric en la ventana ANTES de la ejecución'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.result_value_after IS
        'Valor de result_metric en la ventana DESPUÉS de la ejecución'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.result_delta IS
        'result_value_after - result_value_before (o inverso si expected_direction = down)'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.success_flag IS
        'true si el delta cumplió el criterio definido en action_evaluation_rules'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.evaluation_window_days IS
        'Días transcurridos entre ejecución y medición posterior'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_execution_log.evaluated_at IS
        'Timestamp de cuando se corrió la evaluación'
    """)

    # ── L2: Tabla de reglas de evaluación por acción ─────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.action_evaluation_rules (
            id SERIAL PRIMARY KEY,
            action_id TEXT NOT NULL REFERENCES ops.action_catalog(action_id),
            action_name TEXT NOT NULL,
            result_metric TEXT NOT NULL,
            expected_direction TEXT NOT NULL CHECK (expected_direction IN ('up','down')),
            evaluation_window_days INTEGER NOT NULL DEFAULT 7,
            success_threshold_pct NUMERIC NOT NULL DEFAULT 5,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (action_id, result_metric)
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.action_evaluation_rules IS
        'Reglas explícitas para evaluar si una acción fue exitosa: métrica, dirección esperada, ventana y umbral mínimo (%). Una fila por (action_id, result_metric).'
    """)

    op.execute("""
        INSERT INTO ops.action_evaluation_rules
            (action_id, action_name, result_metric, expected_direction,
             evaluation_window_days, success_threshold_pct, is_active)
        VALUES
        ('DRIVER_REACTIVATION', 'Reactivar conductores inactivos',
         'active_drivers', 'up', 7, 5.0, TRUE),

        ('ACQUISITION_NEEDED', 'Activar captación de conductores',
         'active_drivers', 'up', 14, 3.0, TRUE),

        ('LOW_PRODUCTIVITY', 'Revisar productividad de conductores',
         'trips_per_driver', 'up', 7, 5.0, TRUE),

        ('CANCEL_RATE_SPIKE', 'Auditar cancelaciones elevadas',
         'cancel_rate', 'down', 7, 2.0, TRUE),

        ('TICKET_DROP', 'Revisar pricing por caída de ticket promedio',
         'revenue', 'up', 7, 3.0, TRUE),

        ('TRIPS_DROP_CITY', 'Investigar caída de viajes en ciudad',
         'trips', 'up', 7, 5.0, TRUE),

        ('REVENUE_DROP_CITY', 'Investigar caída de revenue en ciudad',
         'revenue', 'up', 7, 5.0, TRUE),

        ('ZERO_REVENUE_CITY', 'Revenue cero en ciudad activa',
         'revenue', 'up', 7, 1.0, TRUE),

        ('INGEST_ESCALATE', 'Escalar problema de ingestión de comisión',
         'proxy_pct', 'down', 7, 5.0, TRUE),

        ('NAN_RAW_DATA', 'Limpiar NaN en datos fuente',
         'data_quality_issue_count', 'down', 7, 10.0, TRUE),

        ('DRIFT_CROSS_CHAIN', 'Auditoría de drift entre cadenas',
         'data_quality_issue_count', 'down', 7, 10.0, TRUE),

        ('DATA_FRESHNESS', 'Datos desactualizados en cadena crítica',
         'data_quality_issue_count', 'down', 3, 50.0, TRUE),

        ('MISSING_REVENUE', 'Viajes sin revenue (ni real ni proxy)',
         'data_quality_issue_count', 'down', 7, 10.0, TRUE),

        ('PARK_ANOMALY', 'Auditar parque con métricas anómalas',
         'data_quality_issue_count', 'down', 7, 10.0, TRUE)

        ON CONFLICT (action_id, result_metric) DO NOTHING
    """)

    # ── L4: Vista materializable de efectividad histórica ────────────────
    op.execute("DROP VIEW IF EXISTS ops.action_effectiveness CASCADE")
    op.execute("""
        CREATE VIEW ops.action_effectiveness AS
        SELECT
            l.action_id,
            MAX(l.action_id) AS _action_id_agg,
            COALESCE(
                p.city,
                (SELECT eo.city FROM ops.action_engine_output eo
                 WHERE eo.id = l.action_output_id LIMIT 1)
            ) AS city,
            COALESCE(
                p.country,
                (SELECT eo.country FROM ops.action_engine_output eo
                 WHERE eo.id = l.action_output_id LIMIT 1)
            ) AS country,
            COUNT(*)::bigint AS executions_count,
            COUNT(*) FILTER (WHERE l.success_flag IS TRUE)::bigint AS success_count,
            CASE WHEN COUNT(*) > 0
                THEN ROUND(
                    COUNT(*) FILTER (WHERE l.success_flag IS TRUE)::numeric
                    / COUNT(*)::numeric * 100, 2)
                ELSE NULL
            END AS success_rate,
            ROUND(AVG(l.result_delta)::numeric, 4) AS avg_result_delta,
            MAX(l.execution_date) AS last_execution_at,
            MAX(l.evaluated_at) AS last_evaluated_at
        FROM ops.action_execution_log l
        LEFT JOIN ops.action_plan_daily p ON p.id = l.action_plan_id
        WHERE l.evaluated_at IS NOT NULL
        GROUP BY
            l.action_id,
            COALESCE(
                p.city,
                (SELECT eo.city FROM ops.action_engine_output eo
                 WHERE eo.id = l.action_output_id LIMIT 1)
            ),
            COALESCE(
                p.country,
                (SELECT eo.country FROM ops.action_engine_output eo
                 WHERE eo.id = l.action_output_id LIMIT 1)
            )
    """)
    op.execute("""
        COMMENT ON VIEW ops.action_effectiveness IS
        'Efectividad histórica por (action_id, city, country). Alimenta effectiveness_multiplier del engine y orchestrator.'
    """)

    # ── L5: Columnas de feedback en action_engine_output ─────────────────
    op.execute("""
        ALTER TABLE ops.action_engine_output
        ADD COLUMN IF NOT EXISTS effectiveness_score NUMERIC,
        ADD COLUMN IF NOT EXISTS effectiveness_scope TEXT,
        ADD COLUMN IF NOT EXISTS priority_score_base NUMERIC,
        ADD COLUMN IF NOT EXISTS priority_score_final NUMERIC
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_engine_output.effectiveness_score IS
        'Multiplicador [0.7..1.3] derivado de action_effectiveness; NULL = sin historial'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.action_engine_output.effectiveness_scope IS
        'Scope del lookup: city, country, global, o none si no hay historial'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ops.action_engine_output
        DROP COLUMN IF EXISTS effectiveness_score,
        DROP COLUMN IF EXISTS effectiveness_scope,
        DROP COLUMN IF EXISTS priority_score_base,
        DROP COLUMN IF EXISTS priority_score_final
    """)

    op.execute("DROP VIEW IF EXISTS ops.action_effectiveness CASCADE")

    op.execute("DROP TABLE IF EXISTS ops.action_evaluation_rules CASCADE")

    op.execute("""
        ALTER TABLE ops.action_execution_log
        DROP COLUMN IF EXISTS result_metric,
        DROP COLUMN IF EXISTS result_value_before,
        DROP COLUMN IF EXISTS result_value_after,
        DROP COLUMN IF EXISTS result_delta,
        DROP COLUMN IF EXISTS success_flag,
        DROP COLUMN IF EXISTS evaluation_window_days,
        DROP COLUMN IF EXISTS evaluated_at
    """)
