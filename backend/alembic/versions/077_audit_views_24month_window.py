"""
Audit Layer Performance: limitar vistas de auditoría a ventana de 24 meses.
Elimina full scans sobre toda la historia; mantiene exactitud para operación diaria.
- v_trip_integrity, v_b2b_integrity: filtro fecha_inicio_viaje >= current_date - 24 months en CTE base.
- v_lob_mapping_audit: filtro 24 meses en base, with_lob y unmapped.
- v_join_integrity: filtro 24 meses en base_trips.
- v_weekly_trip_volume: filtro 24 meses.
- v_duplicate_trips: solo ids con fecha_inicio_viaje en últimos 24 meses en cada fuente.
"""
from alembic import op
from sqlalchemy import text

revision = "077_audit_views_24month"
down_revision = "076_audit_query_performance"
branch_labels = None
depends_on = None

# Ventana para auditoría operativa (evitar timeouts y full scans).
AUDIT_WINDOW_MONTHS = 24
WINDOW_CONDITION = f"(current_date - interval '{AUDIT_WINDOW_MONTHS} months')::date"


def upgrade() -> None:
    conn = op.get_bind()
    has_2026 = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'trips_2026'
    """)).fetchone()

    # --- 1) v_trip_integrity: ventana 24 meses en base ---
    op.execute("DROP VIEW IF EXISTS ops.v_trip_integrity CASCADE")
    op.execute(f"""
        CREATE VIEW ops.v_trip_integrity AS
        WITH base AS (
            SELECT date_trunc('month', fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_base
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
              AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
            GROUP BY date_trunc('month', fecha_inicio_viaje)::date
        ),
        rl AS (
            SELECT date_trunc('month', trip_day)::date AS mes,
                   SUM(trips)::bigint AS viajes_real_lob
            FROM ops.real_rollup_day_fact
            WHERE trip_day >= {WINDOW_CONDITION}
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
    op.execute("COMMENT ON VIEW ops.v_trip_integrity IS 'Integridad viajes canonical vs real_rollup (últimos 24 meses). loss_pct > 1%% = CRITICAL.'")

    # --- 2) v_b2b_integrity: ventana 24 meses ---
    op.execute("DROP VIEW IF EXISTS ops.v_b2b_integrity CASCADE")
    op.execute(f"""
        CREATE VIEW ops.v_b2b_integrity AS
        WITH base AS (
            SELECT date_trunc('month', fecha_inicio_viaje)::date AS mes,
                   COUNT(*) FILTER (WHERE pago_corporativo IS NOT NULL AND (pago_corporativo::text NOT IN ('', '0'))) AS b2b_base
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
              AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
            GROUP BY date_trunc('month', fecha_inicio_viaje)::date
        ),
        rl AS (
            SELECT date_trunc('month', trip_day)::date AS mes,
                   SUM(b2b_trips)::bigint AS b2b_real_lob
            FROM ops.real_rollup_day_fact
            WHERE trip_day >= {WINDOW_CONDITION}
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
    op.execute("COMMENT ON VIEW ops.v_b2b_integrity IS 'Integridad B2B canonical vs real_rollup (últimos 24 meses).'")

    # --- 3) v_lob_mapping_audit: ventana 24 meses en las tres CTEs ---
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_audit CASCADE")
    op.execute(f"""
        CREATE VIEW ops.v_lob_mapping_audit AS
        WITH base AS (
            SELECT date_trunc('month', t.fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_base
            FROM ops.v_trips_real_canon t
            WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje IS NOT NULL
              AND t.tipo_servicio IS NOT NULL AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.fecha_inicio_viaje::date >= {WINDOW_CONDITION}
            GROUP BY date_trunc('month', t.fecha_inicio_viaje)::date
        ),
        with_lob AS (
            SELECT date_trunc('month', v.fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_con_lob
            FROM ops.v_real_trips_with_lob_v2 v
            WHERE v.lob_group IS NOT NULL AND v.lob_group != 'UNCLASSIFIED'
              AND v.fecha_inicio_viaje::date >= {WINDOW_CONDITION}
            GROUP BY date_trunc('month', v.fecha_inicio_viaje)::date
        ),
        unmapped AS (
            SELECT date_trunc('month', v.fecha_inicio_viaje)::date AS mes,
                   COUNT(*) AS viajes_sin_lob
            FROM ops.v_real_trips_with_lob_v2 v
            WHERE (v.lob_group IS NULL OR v.lob_group = 'UNCLASSIFIED')
              AND v.fecha_inicio_viaje::date >= {WINDOW_CONDITION}
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
    op.execute("COMMENT ON VIEW ops.v_lob_mapping_audit IS 'Auditoría LOB con/sin clasificación por mes (últimos 24 meses).'")

    # --- 4) v_join_integrity: ventana 24 meses en base_trips ---
    op.execute("DROP VIEW IF EXISTS ops.v_join_integrity CASCADE")
    op.execute(f"""
        CREATE VIEW ops.v_join_integrity AS
        WITH base_trips AS (
            SELECT id, park_id, conductor_id, fecha_inicio_viaje
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado'
              AND fecha_inicio_viaje IS NOT NULL
              AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
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
    op.execute("COMMENT ON VIEW ops.v_join_integrity IS 'Pérdida en join trips→parks (últimos 24 meses).'")

    # --- 5) v_weekly_trip_volume: ventana 24 meses ---
    op.execute("DROP VIEW IF EXISTS ops.v_weekly_trip_volume CASCADE")
    op.execute(f"""
        CREATE VIEW ops.v_weekly_trip_volume AS
        SELECT
            date_trunc('week', fecha_inicio_viaje)::date AS week_start,
            COUNT(*) AS viajes,
            COUNT(DISTINCT conductor_id) AS drivers,
            COUNT(DISTINCT park_id) AS parks
        FROM ops.v_trips_real_canon
        WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
          AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
        GROUP BY date_trunc('week', fecha_inicio_viaje)::date
        ORDER BY week_start DESC
    """)
    op.execute("COMMENT ON VIEW ops.v_weekly_trip_volume IS 'Volumen semanal (últimos 24 meses). WoW para anomalías.'")

    # --- 6) v_duplicate_trips: solo ids en ventana 24 meses (reduce full scan) ---
    op.execute("DROP VIEW IF EXISTS ops.v_duplicate_trips CASCADE")
    if has_2026:
        op.execute(f"""
            CREATE VIEW ops.v_duplicate_trips AS
            WITH raw AS (
                SELECT id AS trip_id FROM public.trips_all
                WHERE fecha_inicio_viaje IS NOT NULL AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
                UNION ALL
                SELECT id FROM public.trips_2026
                WHERE fecha_inicio_viaje IS NOT NULL AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
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
        op.execute(f"""
            CREATE VIEW ops.v_duplicate_trips AS
            WITH raw AS (
                SELECT id AS trip_id FROM public.trips_all
                WHERE fecha_inicio_viaje IS NOT NULL AND fecha_inicio_viaje::date >= {WINDOW_CONDITION}
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
    op.execute("COMMENT ON VIEW ops.v_duplicate_trips IS 'trip_id duplicados entre fuentes en últimos 24 meses (solapamiento o carga doble).'")

    # v_control_tower_integrity_report no se redefine; sigue leyendo las vistas ya actualizadas.


def downgrade() -> None:
    # Restaurar vistas sin ventana (definiciones de 075).
    # Por brevedad se deja a 075; en práctica se puede re-ejecutar 075 upgrade o copiar DDL desde 075.
    raise NotImplementedError(
        "Downgrade 077: restaurar vistas sin ventana requiere redefinir cada vista como en 075 (sin filtro de 24 meses)."
    )
