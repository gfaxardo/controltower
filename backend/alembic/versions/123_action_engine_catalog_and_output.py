"""
Action Engine: catálogo de acciones, tabla de output, log de ejecución.

Revision ID: 123_action_engine_catalog_and_output
Revises: 122_revenue_hardening_nan_guard_and_alerts
"""
from alembic import op

revision = "123_action_engine_catalog_and_output"
down_revision = "122_revenue_hardening_nan_guard_and_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Catálogo de acciones ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.action_catalog (
            action_id TEXT PRIMARY KEY,
            action_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            description TEXT,
            trigger_metric TEXT NOT NULL,
            trigger_condition TEXT NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
            suggested_owner TEXT,
            suggested_channel TEXT,
            expected_impact TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── Seed: acciones operativas reales ──
    op.execute("""
        INSERT INTO ops.action_catalog
            (action_id, action_name, action_type, description,
             trigger_metric, trigger_condition, severity,
             suggested_owner, suggested_channel, expected_impact, is_active)
        VALUES
        ('INGEST_ESCALATE', 'Escalar problema de ingestión de comisión',
         'finance', 'comision_empresa_asociada no se está ingiriendo; revenue opera 100%% proxy',
         'pct_proxy', '>= 95', 'critical',
         'data_engineering', 'ticket_jira', 'Restaurar revenue real para reducir dependencia de proxy', TRUE),

        ('TRIPS_DROP_CITY', 'Investigar caída de viajes en ciudad',
         'ops', 'Viajes completados cayeron >20%% WoW en una ciudad activa',
         'trips_wow_change_pct', '<= -20', 'high',
         'ops_city_manager', 'dashboard_alert', 'Identificar causa raíz y recuperar volumen', TRUE),

        ('DRIVER_REACTIVATION', 'Reactivar conductores inactivos',
         'supply', 'Active drivers cayó >15%% WoW en una ciudad',
         'active_drivers_wow_change_pct', '<= -15', 'high',
         'supply_team', 'whatsapp_campaign', 'Recuperar base activa de conductores', TRUE),

        ('TICKET_DROP', 'Revisar pricing por caída de ticket promedio',
         'pricing', 'Ticket promedio cayó >15%% WoW',
         'avg_ticket_wow_change_pct', '<= -15', 'medium',
         'pricing_team', 'pricing_review', 'Ajustar pricing o investigar cambio de mix', TRUE),

        ('CANCEL_RATE_SPIKE', 'Auditar cancelaciones elevadas',
         'ops', 'Tasa de cancelación subió >5pp WoW',
         'cancel_rate_change_pp', '>= 5', 'high',
         'ops_team', 'investigation', 'Reducir cancelaciones y mejorar completion rate', TRUE),

        ('ZERO_REVENUE_CITY', 'Revenue cero en ciudad activa',
         'finance', 'Ciudad con viajes pero revenue = 0',
         'city_revenue', '= 0', 'critical',
         'data_engineering', 'ticket_jira', 'Restaurar revenue (revisar proxy y NaN)', TRUE),

        ('REVENUE_DROP_CITY', 'Investigar caída de revenue en ciudad',
         'finance', 'Revenue total cayó >30%% WoW en una ciudad',
         'revenue_wow_change_pct', '<= -30', 'high',
         'ops_city_manager', 'dashboard_alert', 'Identificar causa de caída de revenue', TRUE),

        ('NAN_RAW_DATA', 'Limpiar NaN en datos fuente',
         'data_quality', 'Existen registros con precio_yango_pro = NaN en tablas raw',
         'nan_count_raw', '> 0', 'high',
         'data_engineering', 'ticket_jira', 'Limpiar NaN para evitar contaminación de revenue', TRUE),

        ('DRIFT_CROSS_CHAIN', 'Auditoría de drift entre cadenas',
         'data_quality', 'Diferencia >15%% entre hourly-first y business slice',
         'cross_chain_drift_pct', '>= 15', 'medium',
         'data_engineering', 'investigation', 'Reconciliar cadenas para evitar doble verdad', TRUE),

        ('PARK_ANOMALY', 'Auditar parque con métricas anómalas',
         'ops', 'Un parque muestra revenue o trips fuera de rango esperado',
         'park_anomaly_score', '>= 3', 'medium',
         'ops_team', 'investigation', 'Investigar parque para descartar fraude o error', TRUE),

        ('LOW_PRODUCTIVITY', 'Revisar productividad de conductores',
         'supply', 'Trips per driver cayó >20%% WoW en una ciudad',
         'trips_per_driver_wow_change_pct', '<= -20', 'medium',
         'supply_team', 'ops_review', 'Investigar baja productividad y optimizar asignación', TRUE),

        ('MISSING_REVENUE', 'Viajes sin revenue (ni real ni proxy)',
         'data_quality', 'Porcentaje de viajes completados sin revenue supera umbral',
         'pct_missing_revenue', '>= 5', 'high',
         'data_engineering', 'ticket_jira', 'Verificar precio_yango_pro y comisión para viajes afectados', TRUE),

        ('ACQUISITION_NEEDED', 'Activar captación de conductores',
         'acquisition', 'Ciudad con demanda sostenida pero supply insuficiente',
         'demand_supply_ratio', '>= 3', 'high',
         'marketing', 'campaign', 'Campaña de captación para cubrir demanda', TRUE),

        ('DATA_FRESHNESS', 'Datos desactualizados en cadena crítica',
         'data_quality', 'Último dato en MV tiene más de 48h de antigüedad',
         'hours_since_last_trip', '>= 48', 'high',
         'data_engineering', 'ticket_jira', 'Verificar pipeline de ingestión y refresh', TRUE)

        ON CONFLICT (action_id) DO NOTHING
    """)

    # ── 2. Tabla de output del engine ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.action_engine_output (
            id SERIAL PRIMARY KEY,
            run_date DATE NOT NULL DEFAULT CURRENT_DATE,
            country TEXT,
            city TEXT,
            park_id TEXT,
            action_id TEXT NOT NULL REFERENCES ops.action_catalog(action_id),
            action_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            priority_score NUMERIC NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            metric_name TEXT,
            metric_value NUMERIC,
            threshold NUMERIC,
            suggested_owner TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_aeo_date ON ops.action_engine_output (run_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_aeo_severity ON ops.action_engine_output (severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_aeo_priority ON ops.action_engine_output (priority_score DESC)")

    # ── 3. Log de ejecución de acciones ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.action_execution_log (
            id SERIAL PRIMARY KEY,
            action_output_id INT REFERENCES ops.action_engine_output(id),
            action_id TEXT NOT NULL,
            execution_date DATE NOT NULL DEFAULT CURRENT_DATE,
            owner TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','in_progress','done','ignored')),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.action_execution_log CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.action_engine_output CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.action_catalog CASCADE")
