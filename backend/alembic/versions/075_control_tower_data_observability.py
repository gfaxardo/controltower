"""
Control Tower: capa de observabilidad y auditoría de datos.
- ops.v_trips_canonical: vista canónica de viajes (alias columnas sobre v_trips_real_canon).
- Vistas de auditoría: ingestión, integridad trips/B2B/LOB, joins, duplicados, semanal, MV freshness, consistencia drivers.
- ops.v_control_tower_integrity_report: reporte global de checks (OK/WARNING/CRITICAL).
- ops.data_integrity_audit: tabla para persistir resultados de cada ejecución del script de auditoría.
"""
from alembic import op
from sqlalchemy import text

revision = "075_control_tower_observability"
down_revision = ("074_trips_base_legacy", "073_normalize_expres_to_express")
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1) Vista canónica de viajes (columnas estándar para auditoría y reportes) ---
    op.execute("DROP VIEW IF EXISTS ops.v_trips_canonical CASCADE")
    op.execute("""
        CREATE VIEW ops.v_trips_canonical AS
        SELECT
            t.id AS trip_id,
            t.fecha_finalizacion AS completed_at,
            t.fecha_inicio_viaje AS trip_start_at,
            t.park_id,
            t.conductor_id AS driver_id,
            t.pago_corporativo,
            t.comision_empresa_asociada AS fare_total,
            t.distancia_km AS distance_km,
            t.condicion,
            t.source_table
        FROM ops.v_trips_real_canon t
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_trips_canonical IS
        'Vista canónica de viajes: columnas unificadas (trip_id, completed_at, park_id, driver_id, pago_corporativo, fare_total, distance_km). Fuente: v_trips_real_canon.'
    """)

    # --- 2) Auditoría de ingestión (por fuente y mes) ---
    has_2026_ing = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'trips_2026'
    """)).fetchone()
    op.execute("DROP VIEW IF EXISTS ops.v_ingestion_audit CASCADE")
    if has_2026_ing:
        op.execute("""
            CREATE VIEW ops.v_ingestion_audit AS
            WITH all_months AS (
                SELECT 'trips_all'::text AS fuente, date_trunc('month', fecha_inicio_viaje)::date AS mes,
                       COUNT(*) AS viajes,
                       COUNT(*) FILTER (WHERE (pago_corporativo IS NOT NULL AND (pago_corporativo::text NOT IN ('', '0')))) AS viajes_b2b,
                       COUNT(DISTINCT conductor_id) AS drivers,
                       COUNT(DISTINCT park_id) AS parks
                FROM public.trips_all
                WHERE fecha_inicio_viaje IS NOT NULL
                GROUP BY date_trunc('month', fecha_inicio_viaje)::date
                UNION ALL
                SELECT 'trips_2026', date_trunc('month', fecha_inicio_viaje)::date,
                       COUNT(*),
                       COUNT(*) FILTER (WHERE (pago_corporativo IS NOT NULL AND (pago_corporativo::text NOT IN ('', '0')))),
                       COUNT(DISTINCT conductor_id),
                       COUNT(DISTINCT park_id)
                FROM public.trips_2026
                WHERE fecha_inicio_viaje IS NOT NULL
                GROUP BY date_trunc('month', fecha_inicio_viaje)::date
            )
            SELECT fuente, mes, viajes, viajes_b2b, drivers, parks FROM all_months
            WHERE mes IS NOT NULL
            ORDER BY fuente, mes DESC
        """)
    else:
        op.execute("""
            CREATE VIEW ops.v_ingestion_audit AS
            SELECT 'trips_all'::text AS fuente, date_trunc('month', fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes,
                   COUNT(*) FILTER (WHERE (pago_corporativo IS NOT NULL AND (pago_corporativo::text NOT IN ('', '0')))) AS viajes_b2b,
                   COUNT(DISTINCT conductor_id) AS drivers,
                   COUNT(DISTINCT park_id) AS parks
            FROM public.trips_all
            WHERE fecha_inicio_viaje IS NOT NULL
            GROUP BY date_trunc('month', fecha_inicio_viaje)::date
            ORDER BY mes DESC
        """)
    op.execute("COMMENT ON VIEW ops.v_ingestion_audit IS 'Auditoría de ingestión por fuente (trips_all, trips_2026): viajes, B2B, drivers, parks por mes.'")

    # --- 3) Integridad de viajes: canonical (completados) vs real_lob (rollup) por mes ---
    op.execute("DROP VIEW IF EXISTS ops.v_trip_integrity CASCADE")
    op.execute("""
        CREATE VIEW ops.v_trip_integrity AS
        WITH base AS (
            SELECT date_trunc('month', fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_base
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
            GROUP BY date_trunc('month', fecha_inicio_viaje)::date
        ),
        rl AS (
            SELECT date_trunc('month', trip_day)::date AS mes,
                   SUM(trips)::bigint AS viajes_real_lob
            FROM ops.real_rollup_day_fact
            GROUP BY date_trunc('month', trip_day)::date
        )
        SELECT
            b.mes,
            b.viajes_base,
            COALESCE(r.viajes_real_lob, 0) AS viajes_real_lob,
            CASE WHEN b.viajes_base > 0
                THEN ROUND(100.0 * (b.viajes_base - COALESCE(r.viajes_real_lob, 0)) / b.viajes_base, 4)
                ELSE 0 END AS loss_pct,
            CASE
                WHEN b.viajes_base = 0 THEN 'OK'
                WHEN 100.0 * (b.viajes_base - COALESCE(r.viajes_real_lob, 0)) / b.viajes_base > 1 THEN 'CRITICAL'
                WHEN 100.0 * (b.viajes_base - COALESCE(r.viajes_real_lob, 0)) / b.viajes_base > 0.1 THEN 'WARNING'
                ELSE 'OK'
            END AS status
        FROM base b
        LEFT JOIN rl r ON r.mes = b.mes
        ORDER BY b.mes DESC
    """)
    op.execute("COMMENT ON VIEW ops.v_trip_integrity IS 'Integridad: viajes canonical (Completado) vs real_rollup_day_fact. loss_pct > 1% = CRITICAL.'")

    # --- 4) Auditoría B2B: canonical vs real_lob ---
    op.execute("DROP VIEW IF EXISTS ops.v_b2b_integrity CASCADE")
    op.execute("""
        CREATE VIEW ops.v_b2b_integrity AS
        WITH base AS (
            SELECT date_trunc('month', fecha_inicio_viaje)::date AS mes,
                   COUNT(*) FILTER (WHERE pago_corporativo IS NOT NULL AND (pago_corporativo::text NOT IN ('', '0'))) AS b2b_base
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
            GROUP BY date_trunc('month', fecha_inicio_viaje)::date
        ),
        rl AS (
            SELECT date_trunc('month', trip_day)::date AS mes,
                   SUM(b2b_trips)::bigint AS b2b_real_lob
            FROM ops.real_rollup_day_fact
            GROUP BY date_trunc('month', trip_day)::date
        )
        SELECT
            b.mes,
            b.b2b_base,
            COALESCE(r.b2b_real_lob, 0) AS b2b_real_lob,
            CASE WHEN b.b2b_base > 0
                THEN ROUND(100.0 * (b.b2b_base - COALESCE(r.b2b_real_lob, 0)) / b.b2b_base, 4)
                ELSE 0 END AS diff_pct
        FROM base b
        LEFT JOIN rl r ON r.mes = b.mes
        ORDER BY b.mes DESC
    """)
    op.execute("COMMENT ON VIEW ops.v_b2b_integrity IS 'Integridad B2B: canonical vs real_rollup_day_fact (b2b_trips).'")

    # --- 5) Auditoría mapping LOB (viajes con/sin LOB desde canonical completados) ---
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_audit CASCADE")
    op.execute("""
        CREATE VIEW ops.v_lob_mapping_audit AS
        WITH base AS (
            SELECT date_trunc('month', t.fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_base
            FROM ops.v_trips_real_canon t
            WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje IS NOT NULL
              AND t.tipo_servicio IS NOT NULL AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
            GROUP BY date_trunc('month', t.fecha_inicio_viaje)::date
        ),
        with_lob AS (
            SELECT date_trunc('month', v.fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_con_lob
            FROM ops.v_real_trips_with_lob_v2 v
            WHERE v.lob_group IS NOT NULL AND v.lob_group != 'UNCLASSIFIED'
            GROUP BY date_trunc('month', v.fecha_inicio_viaje)::date
        ),
        unmapped AS (
            SELECT date_trunc('month', v.fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_sin_lob
            FROM ops.v_real_trips_with_lob_v2 v
            WHERE v.lob_group IS NULL OR v.lob_group = 'UNCLASSIFIED'
            GROUP BY date_trunc('month', v.fecha_inicio_viaje)::date
        )
        SELECT
            b.mes,
            b.viajes_base,
            COALESCE(w.viajes_con_lob, 0) AS viajes_con_lob,
            COALESCE(u.viajes_sin_lob, 0) AS viajes_sin_lob,
            CASE WHEN b.viajes_base > 0
                THEN ROUND(100.0 * COALESCE(u.viajes_sin_lob, 0) / b.viajes_base, 4)
                ELSE 0 END AS pct_sin_lob
        FROM base b
        LEFT JOIN with_lob w ON w.mes = b.mes
        LEFT JOIN unmapped u ON u.mes = b.mes
        ORDER BY b.mes DESC
    """)
    op.execute("COMMENT ON VIEW ops.v_lob_mapping_audit IS 'Auditoría LOB: viajes con/sin clasificación LOB por mes (detectar unmapped).'")

    # --- 6) Integridad de joins críticos ---
    op.execute("DROP VIEW IF EXISTS ops.v_join_integrity CASCADE")
    op.execute("""
        CREATE VIEW ops.v_join_integrity AS
        WITH base_trips AS (
            SELECT id, park_id, conductor_id, fecha_inicio_viaje
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado'
        ),
        trips_parks AS (
            SELECT COUNT(*) AS rows_joined
            FROM base_trips t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
        ),
        base_count AS (SELECT COUNT(*) AS rows_base FROM base_trips),
        j_parks AS (
            SELECT 'trips_to_parks'::text AS join_name,
                   (SELECT rows_base FROM base_count) AS rows_base,
                   (SELECT rows_joined FROM trips_parks) AS rows_joined,
                   ROUND(100.0 * (1 - (SELECT rows_joined FROM trips_parks)::numeric / NULLIF((SELECT rows_base FROM base_count), 0)), 4) AS loss_pct
        )
        SELECT * FROM j_parks
    """)
    op.execute("COMMENT ON VIEW ops.v_join_integrity IS 'Pérdida en joins críticos (trips→parks). rows_base vs rows_joined, loss_pct.'")

    # --- 7) Duplicados por trip_id (entre trips_all y trips_2026 si existe) ---
    has_2026 = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'trips_2026'
    """)).fetchone()
    op.execute("DROP VIEW IF EXISTS ops.v_duplicate_trips CASCADE")
    if has_2026:
        op.execute("""
            CREATE VIEW ops.v_duplicate_trips AS
            WITH raw AS (
                SELECT id AS trip_id FROM public.trips_all
                UNION ALL
                SELECT id FROM public.trips_2026
            ),
            dupes AS (
                SELECT trip_id, COUNT(*) AS cnt
                FROM raw
                GROUP BY trip_id
                HAVING COUNT(*) > 1
            )
            SELECT trip_id, cnt AS count FROM dupes
            ORDER BY cnt DESC
        """)
    else:
        op.execute("""
            CREATE VIEW ops.v_duplicate_trips AS
            WITH raw AS (
                SELECT id AS trip_id FROM public.trips_all
            ),
            dupes AS (
                SELECT trip_id, COUNT(*) AS cnt
                FROM raw
                GROUP BY trip_id
                HAVING COUNT(*) > 1
            )
            SELECT trip_id, cnt AS count FROM dupes
            ORDER BY cnt DESC
        """)
    op.execute("COMMENT ON VIEW ops.v_duplicate_trips IS 'trip_id duplicados entre trips_all y trips_2026 (antes de dedup en canonical).'")

    # --- 8) Volumen semanal (WoW) ---
    op.execute("DROP VIEW IF EXISTS ops.v_weekly_trip_volume CASCADE")
    op.execute("""
        CREATE VIEW ops.v_weekly_trip_volume AS
        SELECT
            date_trunc('week', fecha_inicio_viaje)::date AS week_start,
            COUNT(*) AS viajes,
            COUNT(DISTINCT conductor_id) AS drivers,
            COUNT(DISTINCT park_id) AS parks
        FROM ops.v_trips_real_canon
        WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
        GROUP BY date_trunc('week', fecha_inicio_viaje)::date
        ORDER BY week_start DESC
    """)
    op.execute("COMMENT ON VIEW ops.v_weekly_trip_volume IS 'Volumen semanal: viajes, drivers, parks. Detectar semanas incompletas o anomalías WoW.'")

    # --- 9) Freshness de materialized views (lag por max fecha en cada MV) ---
    op.execute("DROP VIEW IF EXISTS ops.v_mv_freshness CASCADE")
    op.execute("""
        CREATE VIEW ops.v_mv_freshness AS
        SELECT 'mv_real_lob_drill'::text AS view_name,
               (SELECT MAX(period_start) FROM ops.real_drill_dim_fact) AS last_period_start,
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(last_trip_ts) FROM ops.real_drill_dim_fact)))/3600.0 AS lag_hours,
               CASE WHEN (SELECT MAX(last_trip_ts) FROM ops.real_drill_dim_fact) >= NOW() - interval '48 hours' THEN 'OK' ELSE 'STALE' END AS status
        UNION ALL
        SELECT 'mv_real_lob',
               (SELECT MAX(trip_day) FROM ops.real_rollup_day_fact),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(last_trip_ts) FROM ops.real_rollup_day_fact)))/3600.0,
               CASE WHEN (SELECT MAX(last_trip_ts) FROM ops.real_rollup_day_fact) >= NOW() - interval '48 hours' THEN 'OK' ELSE 'STALE' END
        UNION ALL
        SELECT 'mv_driver_lifecycle_weekly',
               (SELECT MAX(week_start) FROM ops.mv_driver_weekly_stats),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(week_start) FROM ops.mv_driver_weekly_stats)::timestamptz))/3600.0,
               CASE WHEN (SELECT MAX(week_start) FROM ops.mv_driver_weekly_stats) >= (date_trunc('week', CURRENT_DATE)::date - 7) THEN 'OK' ELSE 'STALE' END
        UNION ALL
        SELECT 'mv_supply_weekly',
               (SELECT MAX(week_start) FROM ops.mv_supply_weekly),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(week_start) FROM ops.mv_supply_weekly)::timestamptz))/3600.0,
               CASE WHEN (SELECT MAX(week_start) FROM ops.mv_supply_weekly) >= (date_trunc('week', CURRENT_DATE)::date - 7) THEN 'OK' ELSE 'STALE' END
        UNION ALL
        SELECT 'mv_driver_segments_weekly',
               (SELECT MAX(week_start) FROM ops.mv_driver_segments_weekly),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(week_start) FROM ops.mv_driver_segments_weekly)::timestamptz))/3600.0,
               CASE WHEN (SELECT MAX(week_start) FROM ops.mv_driver_segments_weekly) >= (date_trunc('week', CURRENT_DATE)::date - 7) THEN 'OK' ELSE 'STALE' END
    """)
    op.execute("COMMENT ON VIEW ops.v_mv_freshness IS 'Freshness de MVs: last_period_start, lag_hours, status OK/STALE.'")

    # --- 10) Consistencia drivers: trips vs lifecycle vs supply ---
    op.execute("DROP VIEW IF EXISTS ops.v_driver_consistency CASCADE")
    op.execute("""
        CREATE VIEW ops.v_driver_consistency AS
        WITH week_trips AS (
            SELECT date_trunc('week', fecha_inicio_viaje)::date AS week_start,
                   COUNT(DISTINCT conductor_id) AS drivers_trips
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL AND conductor_id IS NOT NULL
            GROUP BY date_trunc('week', fecha_inicio_viaje)::date
        ),
        week_lifecycle AS (
            SELECT week_start, COUNT(DISTINCT driver_key) AS drivers_lifecycle
            FROM ops.mv_driver_weekly_stats
            GROUP BY week_start
        ),
        week_supply AS (
            SELECT week_start, SUM(active_drivers) AS drivers_supply
            FROM ops.mv_supply_weekly
            GROUP BY week_start
        )
        SELECT
            COALESCE(t.week_start, l.week_start, s.week_start) AS week,
            COALESCE(t.drivers_trips, 0) AS drivers_trips,
            COALESCE(l.drivers_lifecycle, 0) AS drivers_lifecycle,
            COALESCE(s.drivers_supply, 0) AS drivers_supply,
            GREATEST(
                COALESCE(t.drivers_trips, 0) - COALESCE(l.drivers_lifecycle, 0),
                COALESCE(l.drivers_lifecycle, 0) - COALESCE(t.drivers_trips, 0),
                COALESCE(t.drivers_trips, 0) - COALESCE(s.drivers_supply, 0),
                COALESCE(s.drivers_supply, 0) - COALESCE(t.drivers_trips, 0)
            ) AS diff
        FROM week_trips t
        FULL OUTER JOIN week_lifecycle l ON l.week_start = t.week_start
        FULL OUTER JOIN week_supply s ON s.week_start = COALESCE(t.week_start, l.week_start)
        ORDER BY week DESC
    """)
    op.execute("COMMENT ON VIEW ops.v_driver_consistency IS 'Consistencia: drivers activos por semana según trips, driver_lifecycle y supply.'")

    # --- 11) Reporte global de integridad (agregado de checks) ---
    op.execute("DROP VIEW IF EXISTS ops.v_control_tower_integrity_report CASCADE")
    op.execute("""
        CREATE VIEW ops.v_control_tower_integrity_report AS
        SELECT 'TRIP LOSS'::text AS check_name,
               COALESCE((SELECT status FROM ops.v_trip_integrity ORDER BY mes DESC LIMIT 1), 'OK') AS status,
               CASE COALESCE((SELECT status FROM ops.v_trip_integrity ORDER BY mes DESC LIMIT 1), 'OK')
                   WHEN 'CRITICAL' THEN 'CRITICAL' WHEN 'WARNING' THEN 'WARNING' ELSE 'OK' END AS severity,
               (SELECT json_build_object('mes', mes, 'viajes_base', viajes_base, 'viajes_real_lob', viajes_real_lob, 'loss_pct', loss_pct)
                FROM ops.v_trip_integrity ORDER BY mes DESC LIMIT 1)::text AS details
        UNION ALL
        SELECT 'B2B LOSS',
               'OK',
               'OK',
               (SELECT json_build_object('mes', mes, 'b2b_base', b2b_base, 'b2b_real_lob', b2b_real_lob)
                FROM ops.v_b2b_integrity ORDER BY mes DESC LIMIT 1)::text
        UNION ALL
        SELECT 'LOB MAPPING LOSS',
               CASE WHEN (SELECT pct_sin_lob FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1) > 5 THEN 'WARNING'
                    WHEN (SELECT pct_sin_lob FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1) > 1 THEN 'WARNING' ELSE 'OK' END,
               CASE WHEN (SELECT pct_sin_lob FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1) > 5 THEN 'WARNING' ELSE 'OK' END,
               (SELECT json_build_object('mes', mes, 'viajes_sin_lob', viajes_sin_lob, 'pct_sin_lob', pct_sin_lob)
                FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1)::text
        UNION ALL
        SELECT 'DUPLICATE TRIPS',
               CASE WHEN (SELECT COUNT(*) FROM ops.v_duplicate_trips) > 0 THEN 'WARNING' ELSE 'OK' END,
               CASE WHEN (SELECT COUNT(*) FROM ops.v_duplicate_trips) > 0 THEN 'WARNING' ELSE 'OK' END,
               (SELECT json_build_object('duplicate_count', COUNT(*)) FROM ops.v_duplicate_trips)::text
        UNION ALL
        SELECT 'MV STALE',
               CASE WHEN EXISTS (SELECT 1 FROM ops.v_mv_freshness WHERE status = 'STALE') THEN 'WARNING' ELSE 'OK' END,
               CASE WHEN EXISTS (SELECT 1 FROM ops.v_mv_freshness WHERE status = 'STALE') THEN 'WARNING' ELSE 'OK' END,
               (SELECT json_agg(json_build_object('view_name', view_name, 'status', status))::text FROM ops.v_mv_freshness)
        UNION ALL
        SELECT 'JOIN LOSS',
               CASE WHEN (SELECT loss_pct FROM ops.v_join_integrity LIMIT 1) > 1 THEN 'WARNING' ELSE 'OK' END,
               CASE WHEN (SELECT loss_pct FROM ops.v_join_integrity LIMIT 1) > 5 THEN 'CRITICAL'
                    WHEN (SELECT loss_pct FROM ops.v_join_integrity LIMIT 1) > 1 THEN 'WARNING' ELSE 'OK' END,
               (SELECT json_build_object('join_name', join_name, 'loss_pct', loss_pct) FROM ops.v_join_integrity LIMIT 1)::text
        UNION ALL
        SELECT 'WEEKLY ANOMALY',
               'OK',
               'OK',
               (SELECT json_build_object('latest_week', week_start, 'viajes', viajes)
                FROM ops.v_weekly_trip_volume ORDER BY week_start DESC LIMIT 1)::text
    """)
    op.execute("COMMENT ON VIEW ops.v_control_tower_integrity_report IS 'Reporte global: check_name, status, severity, details. Estados: OK, WARNING, CRITICAL.'")

    # --- 12) Tabla para persistir auditorías por ejecución ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.data_integrity_audit (
            id serial PRIMARY KEY,
            timestamp timestamptz NOT NULL DEFAULT now(),
            check_name text NOT NULL,
            status text NOT NULL,
            metric_value numeric,
            details text
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_data_integrity_audit_timestamp ON ops.data_integrity_audit (timestamp DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_data_integrity_audit_check ON ops.data_integrity_audit (check_name, timestamp DESC)")
    op.execute("COMMENT ON TABLE ops.data_integrity_audit IS 'Resultados de cada ejecución del script audit_control_tower; persistencia de checks de integridad.'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.data_integrity_audit CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_control_tower_integrity_report CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_consistency CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_mv_freshness CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_weekly_trip_volume CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_duplicate_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_join_integrity CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_audit CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_b2b_integrity CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trip_integrity CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_ingestion_audit CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trips_canonical CASCADE")
