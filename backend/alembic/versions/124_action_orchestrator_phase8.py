"""
Fase 8 — Orquestación operativa: planes diarios, playbooks, segmentos, tracking.

Revision ID: 124_action_orchestrator_phase8
Revises: 123_action_engine_catalog_and_output
"""
from alembic import op

revision = "124_action_orchestrator_phase8"
down_revision = "123_action_engine_catalog_and_output"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Playbooks (cerebro operativo; consume catálogo de acciones) ───────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.action_playbooks (
            playbook_id TEXT NOT NULL,
            action_id TEXT NOT NULL REFERENCES ops.action_catalog(action_id),
            action_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            description TEXT,
            default_volume_formula TEXT NOT NULL,
            target_segment TEXT NOT NULL,
            execution_steps TEXT NOT NULL,
            expected_impact TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (playbook_id, action_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_playbooks_action ON ops.action_playbooks (action_id) WHERE is_active"
    )

    op.execute("""
        INSERT INTO ops.action_playbooks
            (playbook_id, action_id, action_name, action_type, description,
             default_volume_formula, target_segment, execution_steps, expected_impact, is_active)
        VALUES
        ('PB_DRIVER_REACTIVATION', 'DRIVER_REACTIVATION',
         'Reactivar conductores inactivos', 'supply',
         'Campaña focalizada en conductores con actividad reciente pero sin viajes en ventana corta.',
         'GREATEST(100, FLOOR(inactive_7d * 0.30))', 'inactive_7d',
         'Extraer lista drivers inactive_7d por ciudad/park → llamada o WhatsApp 1:1 con incentivo acotado → registro en CRM → seguimiento a las 48h → medir reactivaciones 7d.',
         'Subir base activa y completados en la ciudad.', TRUE),

        ('PB_DRIVER_RECRUITMENT', 'ACQUISITION_NEEDED',
         'Activar captación de conductores', 'acquisition',
         'Cubrir brecha demanda/supply con captación medible.',
         'GREATEST(50, FLOOR(active * 0.20))', 'active',
         'Validar funnel de captación por ciudad → brief creativo + landing/WhatsApp → meta diaria de leads calificados → onboarding mismo día → revisión de conversión a primer viaje a 72h.',
         'Incrementar conductores activos y reducir ratio demanda/supply.', TRUE),

        ('PB_PRODUCTIVITY', 'LOW_PRODUCTIVITY',
         'Revisar productividad de conductores', 'supply',
         'Corregir baja trips-per-driver vs histórico.',
         'GREATEST(40, FLOOR(low_productivity * 0.35))', 'low_productivity',
         'Segmentar low_productivity por park → taller express 30m (asignación, horarios pico) → checklist vehículo/app → seguimiento individual top 20%% más bajo a 7d.',
         'Recuperar TPD hacia niveles WoW previos.', TRUE),

        ('PB_CANCEL_REDUCTION', 'CANCEL_RATE_SPIKE',
         'Auditar cancelaciones elevadas', 'ops',
         'Reducir cancel rate con foco operativo por ciudad.',
         'GREATEST(30, FLOOR(active * 0.10))', 'active',
         'Revisar motivos cancelación top 3 → coordinar con dispatch/ops park → ajuste de SLA espera → comunicación a conductores activos → monitor diario cancel rate 5 días.',
         'Bajar cancelaciones y mejorar completion rate.', TRUE),

        ('PB_PRICING_REVIEW', 'TICKET_DROP',
         'Revisar pricing por caída de ticket promedio', 'pricing',
         'Proteger revenue ante caída de ticket.',
         'GREATEST(25, FLOOR(high_performer * 0.12))', 'high_performer',
         'Congelar snapshot tarifas y mix servicio → comparar vs ciudades par → simular escenarios ±X%% → decisión acotada por LOB → comunicar a ops → vigilar ticket y volumen 7d.',
         'Estabilizar ticket medio sin destruir volumen.', TRUE),

        ('PB_DATA_QUALITY', 'NAN_RAW_DATA',
         'Escalamiento de data quality', 'data_quality',
         'Playbook para incidentes de calidad de datos (NaN, drift, ingestión, freshness).',
         '500', 'active',
         'Abrir ticket con dueño data → identificar tabla/fuente → cuarentena o marca de calidad → reproceso o fix upstream → validar muestra 1k filas → cerrar con métrica de alerta en verde.',
         'Restaurar confiabilidad de métricas y revenue.', TRUE),

        ('PB_DATA_QUALITY', 'DRIFT_CROSS_CHAIN',
         'Escalamiento de data quality', 'data_quality',
         'Reconciliación entre cadenas de revenue/trips.',
         '500', 'active',
         'Congelar ventana temporal del drift → extraer diff por ciudad/LOB → revisar reglas hourly-first vs slice → alinear definición única → documentar excepción o corregir pipeline → re-ejecutar validación.',
         'Eliminar doble verdad entre cadenas.', TRUE),

        ('PB_DATA_QUALITY', 'INGEST_ESCALATE',
         'Escalamiento de data quality', 'data_quality',
         'Ingestión de comisión / proxy elevado.',
         '500', 'active',
         'Escalar a proveedor de datos → verificar job ingestión → validar volumen filas vs esperado → backfill si aplica → confirmar pct_proxy bajo umbral.',
         'Recuperar revenue real y bajar dependencia de proxy.', TRUE),

        ('PB_DATA_QUALITY', 'DATA_FRESHNESS',
         'Escalamiento de data quality', 'data_quality',
         'Cadena crítica desactualizada.',
         '300', 'active',
         'Revisar última fecha en MV fuente → trazar pipeline hasta raw → ejecutar refresh manual si procede → fijar SLA de cron → alerta si >24h.',
         'Volver a decisiones con datos del día.', TRUE),

        ('PB_DATA_QUALITY', 'MISSING_REVENUE',
         'Escalamiento de data quality', 'data_quality',
         'Viajes completados sin revenue atribuible.',
         '400', 'active',
         'Muestreo de viajes afectados → revisar precio_yango_pro y comisión → corregir mapping LOB/park → recompute revenue proxy → validar pct_missing_revenue.',
         'Cerrar brecha de revenue faltante.', TRUE)
        ON CONFLICT (playbook_id, action_id) DO NOTHING
    """)

    # ── Plan operativo diario (consume Action Engine + playbooks + segmentos) ─
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.action_plan_daily (
            id SERIAL PRIMARY KEY,
            plan_date DATE NOT NULL,
            country TEXT,
            city TEXT,
            park_id TEXT,
            action_id TEXT NOT NULL REFERENCES ops.action_catalog(action_id),
            action_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            priority_score NUMERIC NOT NULL DEFAULT 0,
            suggested_volume INTEGER NOT NULL DEFAULT 0,
            target_segment TEXT,
            suggested_playbook_id TEXT,
            suggested_playbook_text TEXT,
            expected_impact TEXT,
            status TEXT NOT NULL DEFAULT 'ready'
                CHECK (status IN ('pending','ready','in_progress','done','ignored')),
            source TEXT NOT NULL DEFAULT 'action_engine',
            engine_reason TEXT,
            engine_output_id INTEGER REFERENCES ops.action_engine_output(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_plan_daily_date ON ops.action_plan_daily (plan_date DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_action_plan_daily_dedup ON ops.action_plan_daily ("
        "plan_date, action_id, COALESCE(country,''), COALESCE(city,''), COALESCE(park_id,''))"
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION ops.touch_action_plan_daily()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_action_plan_daily_touch ON ops.action_plan_daily;
        CREATE TRIGGER trg_action_plan_daily_touch
        BEFORE UPDATE ON ops.action_plan_daily
        FOR EACH ROW EXECUTE FUNCTION ops.touch_action_plan_daily()
    """)

    # ── Segmentación de drivers (vista; cruza ciudad y park) ───────────────
    op.execute("DROP VIEW IF EXISTS ops.driver_segments CASCADE")
    op.execute("""
        CREATE VIEW ops.driver_segments AS
        WITH completed AS (
            SELECT
                driver_key AS driver_id,
                country,
                city,
                NULLIF(TRIM(park_id::text), '') AS park_id,
                trip_date
            FROM ops.v_real_driver_segment_trips
            WHERE condicion = 'Completado'
              AND trip_date >= CURRENT_DATE - INTERVAL '120 days'
        ),
        park_rank AS (
            SELECT
                driver_id,
                country,
                city,
                park_id,
                COUNT(*)::bigint AS trips_in_window
            FROM completed
            GROUP BY driver_id, country, city, park_id
        ),
        dominant_park AS (
            SELECT DISTINCT ON (driver_id, country, city)
                driver_id,
                country,
                city,
                park_id AS park_id_dom
            FROM park_rank
            ORDER BY driver_id, country, city, trips_in_window DESC NULLS LAST, park_id
        ),
        per_driver AS (
            SELECT
                c.driver_id,
                c.country,
                c.city,
                dp.park_id_dom AS park_id,
                COUNT(*) FILTER (WHERE c.trip_date >= CURRENT_DATE - INTERVAL '7 days')::bigint AS trips_7d,
                COUNT(*) FILTER (WHERE c.trip_date >= CURRENT_DATE - INTERVAL '30 days')::bigint AS trips_30d,
                COUNT(*) FILTER (WHERE c.trip_date >= CURRENT_DATE - INTERVAL '90 days')::bigint AS trips_90d,
                MAX(c.trip_date) AS last_completed
            FROM completed c
            INNER JOIN dominant_park dp
                ON dp.driver_id = c.driver_id
                AND dp.country = c.country
                AND dp.city = c.city
            GROUP BY c.driver_id, c.country, c.city, dp.park_id_dom
        ),
        city_pct AS (
            SELECT
                country,
                city,
                percentile_cont(0.25) WITHIN GROUP (ORDER BY trips_7d) AS p25_7d,
                percentile_cont(0.80) WITHIN GROUP (ORDER BY trips_7d) AS p80_7d
            FROM per_driver
            WHERE trips_7d > 0
            GROUP BY country, city
        )
        SELECT
            p.driver_id,
            p.country,
            p.city,
            COALESCE(p.park_id::text, 'UNKNOWN') AS park_id,
            p.trips_7d,
            p.trips_30d,
            p.trips_90d,
            p.last_completed,
            CASE
                WHEN p.trips_7d > 0 AND cp.p80_7d IS NOT NULL
                     AND p.trips_7d::numeric >= cp.p80_7d THEN 'high_performer'
                WHEN p.trips_7d > 0 AND cp.p25_7d IS NOT NULL
                     AND p.trips_7d::numeric <= cp.p25_7d THEN 'low_productivity'
                WHEN p.trips_7d > 0 THEN 'active'
                WHEN p.trips_30d > 0 AND p.trips_7d = 0 THEN 'inactive_7d'
                WHEN p.trips_30d = 0 AND p.trips_90d > 0 THEN 'inactive_30d'
                ELSE 'dormant'
            END AS segment,
            CURRENT_DATE::date AS as_of_date
        FROM per_driver p
        LEFT JOIN city_pct cp ON cp.country = p.country AND cp.city = p.city
    """)
    op.execute("""
        COMMENT ON VIEW ops.driver_segments IS
        'Segmento operativo por conductor (active, inactive_7d, inactive_30d, low_productivity, high_performer, dormant) con park dominante 30d. Cruce por country, city, park_id.'
    """)

    # ── Tracking: ampliar action_execution_log al plan diario ───────────────
    op.execute("ALTER TABLE ops.action_execution_log ALTER COLUMN action_output_id DROP NOT NULL")
    op.execute("""
        ALTER TABLE ops.action_execution_log
        ADD COLUMN IF NOT EXISTS action_plan_id INTEGER
            REFERENCES ops.action_plan_daily(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE ops.action_execution_log DROP CONSTRAINT IF EXISTS chk_action_exec_one_target
    """)
    op.execute("""
        ALTER TABLE ops.action_execution_log ADD CONSTRAINT chk_action_exec_one_target CHECK (
            (action_output_id IS NOT NULL AND action_plan_id IS NULL)
            OR (action_output_id IS NULL AND action_plan_id IS NOT NULL)
        )
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.touch_action_execution_log()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_action_execution_log_touch ON ops.action_execution_log;
        CREATE TRIGGER trg_action_execution_log_touch
        BEFORE UPDATE ON ops.action_execution_log
        FOR EACH ROW EXECUTE FUNCTION ops.touch_action_execution_log()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_action_execution_log_touch ON ops.action_execution_log")
    op.execute("DROP FUNCTION IF EXISTS ops.touch_action_execution_log()")
    op.execute(
        "ALTER TABLE ops.action_execution_log DROP CONSTRAINT IF EXISTS chk_action_exec_one_target"
    )
    op.execute("DELETE FROM ops.action_execution_log WHERE action_plan_id IS NOT NULL")
    op.execute("ALTER TABLE ops.action_execution_log DROP COLUMN IF EXISTS action_plan_id")
    op.execute(
        "ALTER TABLE ops.action_execution_log ALTER COLUMN action_output_id SET NOT NULL"
    )

    op.execute("DROP TRIGGER IF EXISTS trg_action_plan_daily_touch ON ops.action_plan_daily")
    op.execute("DROP FUNCTION IF EXISTS ops.touch_action_plan_daily()")
    op.execute("DROP TABLE IF EXISTS ops.action_plan_daily CASCADE")

    op.execute("DROP VIEW IF EXISTS ops.driver_segments CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.action_playbooks CASCADE")
