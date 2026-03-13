"""
Fase 1 — Observabilidad E2E: registro de artefactos y log de refresh.
- ops.observability_artifact_registry: catálogo de artefactos (tablas, MVs, endpoints, scripts) por módulo.
- ops.observability_refresh_log: log de cada ejecución de refresh (artifact_name, started_at, finished_at, status, script_name).
- ops.v_observability_module_status: vista por módulo (latest_refresh_at, freshness_status, observability_coverage).
- ops.v_observability_freshness: vista unificada de señales de frescura (artifact, last_refresh, source).
- ops.v_observability_artifact_lineage: vista de dependencias upstream/downstream (para documentación).
Aditivo: no modifica tablas ni vistas existentes.
"""
from alembic import op

revision = "092_observability_registry"
down_revision = "091_fleet_leakage_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) Registry: catálogo de artefactos ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.observability_artifact_registry (
            id serial PRIMARY KEY,
            artifact_name text NOT NULL,
            artifact_type text NOT NULL,
            module_name text NOT NULL,
            schema_name text,
            refresh_owner text,
            source_kind text,
            active_flag boolean NOT NULL DEFAULT true,
            notes text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE(artifact_name)
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.observability_artifact_registry IS
        'Registro de artefactos críticos para observabilidad: tablas, views, MVs, endpoints, scripts. Fase 1 E2E.'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_observability_artifact_registry_module ON ops.observability_artifact_registry (module_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_observability_artifact_registry_type ON ops.observability_artifact_registry (artifact_type)")

    # --- 2) Refresh log: cada corrida de refresh ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.observability_refresh_log (
            id serial PRIMARY KEY,
            artifact_name text NOT NULL,
            refresh_started_at timestamptz NOT NULL DEFAULT now(),
            refresh_finished_at timestamptz,
            refresh_status text NOT NULL DEFAULT 'running',
            rows_affected_if_known bigint,
            trigger_type text,
            script_name text,
            error_message text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.observability_refresh_log IS
        'Log de ejecuciones de refresh por artefacto. trigger_type: manual, script, system. Fase 1 E2E.'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_observability_refresh_log_artifact ON ops.observability_refresh_log (artifact_name, refresh_started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_observability_refresh_log_started ON ops.observability_refresh_log (refresh_started_at DESC)")

    # --- 3) Vista: estado por módulo (latest_refresh, freshness, coverage) ---
    op.execute("DROP VIEW IF EXISTS ops.v_observability_module_status CASCADE")
    op.execute("""
        CREATE VIEW ops.v_observability_module_status AS
        WITH reg AS (
            SELECT module_name, artifact_name, artifact_type, active_flag
            FROM ops.observability_artifact_registry
            WHERE active_flag
        ),
        last_refresh AS (
            SELECT artifact_name,
                   MAX(refresh_finished_at) FILTER (WHERE refresh_status = 'ok') AS latest_refresh_at
            FROM ops.observability_refresh_log
            GROUP BY artifact_name
        ),
        supply_ts AS (
            SELECT MAX(finished_at) AS ts FROM ops.supply_refresh_log
            WHERE status = 'ok' AND finished_at IS NOT NULL
        ),
        combined AS (
            SELECT r.module_name, r.artifact_name,
                   COALESCE(lr.latest_refresh_at,
                            CASE WHEN r.module_name = 'Supply Dynamics' THEN (SELECT ts FROM supply_ts) END) AS latest_refresh_at,
                   CASE
                       WHEN COALESCE(lr.latest_refresh_at,
                            CASE WHEN r.module_name = 'Supply Dynamics' THEN (SELECT ts FROM supply_ts) END) IS NULL THEN 'unknown'
                       WHEN COALESCE(lr.latest_refresh_at,
                            CASE WHEN r.module_name = 'Supply Dynamics' THEN (SELECT ts FROM supply_ts) END) >= now() - interval '36 hours' THEN 'fresh'
                       ELSE 'stale'
                   END AS freshness_status
            FROM reg r
            LEFT JOIN last_refresh lr ON lr.artifact_name = r.artifact_name
        )
        SELECT
            module_name,
            COUNT(*)::int AS artifact_count,
            COUNT(latest_refresh_at)::int AS with_refresh_count,
            MAX(latest_refresh_at) AS latest_refresh_at,
            (NOT BOOL_OR(freshness_status = 'stale') AND COUNT(latest_refresh_at) > 0) AS all_fresh,
            CASE WHEN COUNT(*) > 0 THEN ROUND(100.0 * COUNT(latest_refresh_at) / COUNT(*), 1) ELSE 0 END AS observability_coverage_pct
        FROM combined
        GROUP BY module_name
    """)
    op.execute("COMMENT ON VIEW ops.v_observability_module_status IS 'Estado por módulo: último refresh, frescura, cobertura de observabilidad. Fase 1.'")

    # --- 4) Vista: frescura unificada (artefacto, último refresh, fuente) ---
    op.execute("DROP VIEW IF EXISTS ops.v_observability_freshness CASCADE")
    op.execute("""
        CREATE VIEW ops.v_observability_freshness AS
        SELECT artifact_name, latest_refresh_at, 'observability_refresh_log'::text AS source
        FROM (
            SELECT artifact_name, MAX(refresh_finished_at) AS latest_refresh_at
            FROM ops.observability_refresh_log
            WHERE refresh_status = 'ok' AND refresh_finished_at IS NOT NULL
            GROUP BY artifact_name
        ) l
        UNION ALL
        SELECT 'ops.supply_alerting_mvs'::text AS artifact_name, MAX(finished_at) AS latest_refresh_at, 'supply_refresh_log'::text
        FROM ops.supply_refresh_log WHERE status = 'ok' AND finished_at IS NOT NULL
    """)
    op.execute("COMMENT ON VIEW ops.v_observability_freshness IS 'Señales de frescura: último refresh por artefacto y fuente. Fase 1.'")

    # --- 5) Vista: lineage simplificado (para UI/documentación; datos se poblan vía seed o API) ---
    op.execute("DROP VIEW IF EXISTS ops.v_observability_artifact_lineage CASCADE")
    op.execute("""
        CREATE VIEW ops.v_observability_artifact_lineage AS
        SELECT artifact_name, artifact_type, module_name, schema_name, refresh_owner, notes
        FROM ops.observability_artifact_registry
        WHERE active_flag
        ORDER BY module_name, artifact_name
    """)
    op.execute("COMMENT ON VIEW ops.v_observability_artifact_lineage IS 'Lineage: artefactos activos por módulo. Upstream/downstream en inventario JSON. Fase 1.'")

    # --- 6) Semilla mínima: artefactos conocidos para que las vistas tengan sentido ---
    op.execute("""
        INSERT INTO ops.observability_artifact_registry (artifact_name, artifact_type, module_name, schema_name, refresh_owner, source_kind, active_flag, notes)
        VALUES
            ('ops.mv_real_lob_month_v2', 'materialized_view', 'Real LOB', 'ops', 'refresh_real_lob_mvs_v2.py', 'script', true, 'Real LOB v2 monthly'),
            ('ops.mv_real_lob_week_v2', 'materialized_view', 'Real LOB', 'ops', 'refresh_real_lob_mvs_v2.py', 'script', true, 'Real LOB v2 weekly'),
            ('ops.real_drill_dim_fact', 'table', 'Real LOB', 'ops', 'refresh_real_lob_drill_pro_mv.py', 'script', true, 'Drill fact'),
            ('ops.mv_driver_lifecycle_base', 'materialized_view', 'Driver Lifecycle', 'ops', 'refresh_driver_lifecycle.py', 'script', true, 'Driver lifecycle base'),
            ('ops.mv_driver_weekly_stats', 'materialized_view', 'Driver Lifecycle', 'ops', 'refresh_driver_lifecycle_mvs', 'function', true, 'Weekly stats'),
            ('ops.mv_driver_segments_weekly', 'materialized_view', 'Supply Dynamics', 'ops', 'refresh_supply_alerting_mvs', 'function', true, 'Driver segments'),
            ('ops.mv_supply_segments_weekly', 'materialized_view', 'Supply Dynamics', 'ops', 'refresh_supply_alerting_mvs', 'function', true, 'Supply segments'),
            ('ops.supply_alerting_mvs', 'function', 'Supply Dynamics', 'ops', 'run_supply_refresh_pipeline.py', 'script', true, 'Supply MVs refresh'),
            ('bi.ingestion_status', 'table', 'Ingestion', 'bi', null, 'etl', true, 'Estado ingesta por dataset'),
            ('ops.data_freshness_audit', 'table', 'System Health', 'ops', 'run_data_freshness_audit.py', 'script', true, 'Auditoría freshness'),
            ('ops.data_integrity_audit', 'table', 'System Health', 'ops', 'audit_control_tower.py', 'script', true, 'Auditoría integridad')
        ON CONFLICT (artifact_name) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_observability_artifact_lineage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_observability_freshness CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_observability_module_status CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.observability_refresh_log CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.observability_artifact_registry CASCADE")
