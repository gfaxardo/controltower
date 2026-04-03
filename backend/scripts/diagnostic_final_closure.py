"""
Diagnóstico final de cierre: ingestión, comisión real, validación operativa y métricas.
READ-ONLY. Ejecuta BLOQUE 1-4 de la minifase de cierre.

Uso: cd backend && python -m scripts.diagnostic_final_closure
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db_audit
from psycopg2.extras import RealDictCursor
from datetime import datetime
from decimal import Decimal


def _f(v):
    if v is None: return None
    if isinstance(v, Decimal): return float(v)
    try:
        f = float(v)
        return None if f != f else f
    except: return None


def q(conn, sql, params=None):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or ())
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def tbl(title, rows, cols=None):
    if not rows:
        print(f"\n{'='*72}\n  {title}\n{'='*72}\n  (sin datos)")
        return
    if cols is None: cols = list(rows[0].keys())
    w = {c: max(len(str(c)), max(len(str(r.get(c,""))) for r in rows)) for c in cols}
    print(f"\n{'='*72}\n  {title}\n{'='*72}")
    print("  " + " | ".join(str(c).ljust(w[c]) for c in cols))
    print("  " + "-+-".join("-"*w[c] for c in cols))
    for r in rows:
        print("  " + " | ".join(str(r.get(c,"")).ljust(w[c]) for c in cols))


def main():
    print("=" * 72)
    print("  DIAGNÓSTICO FINAL DE CIERRE — YEGO CONTROL TOWER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    with get_db_audit(timeout_ms=600000) as conn:

        # ==================================================================
        # BLOQUE 1 — DIAGNÓSTICO DE INGESTIÓN
        # ==================================================================
        print("\n\n" + "#" * 72)
        print("  BLOQUE 1 — DIAGNÓSTICO DE INGESTIÓN comision_empresa_asociada")
        print("#" * 72)

        # 1a. Cobertura por mes en trips_2025
        tbl("1a. COBERTURA comision_empresa_asociada en trips_2025 (por mes)",
            q(conn, """
                SELECT
                    date_trunc('month', fecha_inicio_viaje)::date AS mes,
                    COUNT(*) FILTER (WHERE condicion='Completado') AS completados,
                    COUNT(comision_empresa_asociada)
                        FILTER (WHERE condicion='Completado') AS con_comision,
                    COUNT(*) FILTER (WHERE condicion='Completado'
                        AND comision_empresa_asociada IS NOT NULL
                        AND comision_empresa_asociada != 0) AS con_comision_nz,
                    ROUND(100.0 * COUNT(comision_empresa_asociada)
                        FILTER (WHERE condicion='Completado')
                        / NULLIF(COUNT(*) FILTER (WHERE condicion='Completado'), 0), 2)
                        AS pct_con,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE condicion='Completado'
                        AND comision_empresa_asociada IS NOT NULL
                        AND comision_empresa_asociada != 0)
                        / NULLIF(COUNT(*) FILTER (WHERE condicion='Completado'), 0), 2)
                        AS pct_nz
                FROM public.trips_2025
                WHERE fecha_inicio_viaje IS NOT NULL
                GROUP BY 1 ORDER BY 1
            """),
            ["mes", "completados", "con_comision", "con_comision_nz", "pct_con", "pct_nz"])

        # 1b. Cobertura por mes en trips_2026
        tbl("1b. COBERTURA comision_empresa_asociada en trips_2026 (por mes)",
            q(conn, """
                SELECT
                    date_trunc('month', fecha_inicio_viaje)::date AS mes,
                    COUNT(*) FILTER (WHERE condicion='Completado') AS completados,
                    COUNT(comision_empresa_asociada)
                        FILTER (WHERE condicion='Completado') AS con_comision,
                    COUNT(*) FILTER (WHERE condicion='Completado'
                        AND comision_empresa_asociada IS NOT NULL
                        AND comision_empresa_asociada != 0) AS con_comision_nz,
                    ROUND(100.0 * COUNT(comision_empresa_asociada)
                        FILTER (WHERE condicion='Completado')
                        / NULLIF(COUNT(*) FILTER (WHERE condicion='Completado'), 0), 2)
                        AS pct_con,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE condicion='Completado'
                        AND comision_empresa_asociada IS NOT NULL
                        AND comision_empresa_asociada != 0)
                        / NULLIF(COUNT(*) FILTER (WHERE condicion='Completado'), 0), 2)
                        AS pct_nz
                FROM public.trips_2026
                WHERE fecha_inicio_viaje IS NOT NULL
                GROUP BY 1 ORDER BY 1
            """),
            ["mes", "completados", "con_comision", "con_comision_nz", "pct_con", "pct_nz"])

        # 1c. Patrón por ciudad en trips_2026 enero (donde sí hay comisión)
        tbl("1c. COMISIÓN en enero 2026 por ciudad (trips_2026)",
            q(conn, """
                WITH base AS (
                    SELECT t.*, dp.city, dp.country
                    FROM public.trips_2026 t
                    LEFT JOIN dim.dim_park dp
                        ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
                    WHERE t.condicion = 'Completado'
                      AND t.fecha_inicio_viaje >= '2026-01-01' AND t.fecha_inicio_viaje < '2026-02-01'
                )
                SELECT country, city,
                    COUNT(*) AS completados,
                    COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL
                        AND comision_empresa_asociada != 0) AS con_comision_nz,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL
                        AND comision_empresa_asociada != 0) / NULLIF(COUNT(*), 0), 2) AS pct_nz
                FROM base
                GROUP BY country, city ORDER BY completados DESC
            """),
            ["country", "city", "completados", "con_comision_nz", "pct_nz"])

        # 1d. Columnas disponibles en trips_2025 vs trips_2026
        tbl("1d. COLUMNAS con 'comision' en ambas tablas",
            q(conn, """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('trips_2025', 'trips_2026')
                  AND column_name ILIKE '%%comision%%'
                ORDER BY table_name, column_name
            """))

        # 1e. Signos de comision donde existe
        tbl("1e. SIGNO de comision_empresa_asociada donde existe (trips_2026, ene)",
            q(conn, """
                SELECT
                    CASE WHEN comision_empresa_asociada > 0 THEN 'positivo'
                         WHEN comision_empresa_asociada < 0 THEN 'negativo'
                         WHEN comision_empresa_asociada = 0 THEN 'cero'
                    END AS signo,
                    COUNT(*) AS cnt,
                    ROUND(AVG(comision_empresa_asociada)::numeric, 2) AS avg_val,
                    ROUND(MIN(comision_empresa_asociada)::numeric, 2) AS min_val,
                    ROUND(MAX(comision_empresa_asociada)::numeric, 2) AS max_val
                FROM public.trips_2026
                WHERE condicion = 'Completado'
                  AND fecha_inicio_viaje >= '2026-01-01' AND fecha_inicio_viaje < '2026-02-01'
                  AND comision_empresa_asociada IS NOT NULL AND comision_empresa_asociada != 0
                GROUP BY 1 ORDER BY cnt DESC
            """))

        # ==================================================================
        # BLOQUE 2 — COMISIÓN REAL ESTIMADA
        # ==================================================================
        print("\n\n" + "#" * 72)
        print("  BLOQUE 2 — COMISIÓN REAL ESTIMADA (enero 2026)")
        print("#" * 72)

        # 2a. Ratio global
        tbl("2a. RATIO comision/ticket GLOBAL (ene 2026, donde ambos existen)",
            q(conn, """
                SELECT
                    COUNT(*) AS viajes,
                    ROUND(AVG(ABS(comision_empresa_asociada) / NULLIF(precio_yango_pro, 0))::numeric, 4) AS avg_pct,
                    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY ABS(comision_empresa_asociada) / NULLIF(precio_yango_pro, 0)
                    )::numeric, 4) AS median_pct,
                    ROUND(STDDEV(ABS(comision_empresa_asociada) / NULLIF(precio_yango_pro, 0))::numeric, 4) AS stddev_pct
                FROM public.trips_2026
                WHERE condicion = 'Completado'
                  AND fecha_inicio_viaje >= '2026-01-01' AND fecha_inicio_viaje < '2026-02-01'
                  AND comision_empresa_asociada IS NOT NULL AND comision_empresa_asociada != 0
                  AND precio_yango_pro IS NOT NULL AND precio_yango_pro > 0
                  AND precio_yango_pro != 'NaN'::numeric
            """))

        # 2b. Ratio por país
        tbl("2b. RATIO por PAÍS",
            q(conn, """
                SELECT dp.country,
                    COUNT(*) AS viajes,
                    ROUND(AVG(ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0))::numeric, 4) AS avg_pct,
                    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0)
                    )::numeric, 4) AS median_pct
                FROM public.trips_2026 t
                LEFT JOIN dim.dim_park dp ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
                WHERE t.condicion = 'Completado'
                  AND t.fecha_inicio_viaje >= '2026-01-01' AND t.fecha_inicio_viaje < '2026-02-01'
                  AND t.comision_empresa_asociada IS NOT NULL AND t.comision_empresa_asociada != 0
                  AND t.precio_yango_pro IS NOT NULL AND t.precio_yango_pro > 0
                  AND t.precio_yango_pro != 'NaN'::numeric
                GROUP BY dp.country ORDER BY viajes DESC
            """))

        # 2c. Ratio por ciudad
        tbl("2c. RATIO por CIUDAD",
            q(conn, """
                SELECT dp.country, dp.city,
                    COUNT(*) AS viajes,
                    ROUND(AVG(ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0))::numeric, 4) AS avg_pct,
                    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0)
                    )::numeric, 4) AS median_pct,
                    ROUND(STDDEV(ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0))::numeric, 4) AS stddev
                FROM public.trips_2026 t
                LEFT JOIN dim.dim_park dp ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
                WHERE t.condicion = 'Completado'
                  AND t.fecha_inicio_viaje >= '2026-01-01' AND t.fecha_inicio_viaje < '2026-02-01'
                  AND t.comision_empresa_asociada IS NOT NULL AND t.comision_empresa_asociada != 0
                  AND t.precio_yango_pro IS NOT NULL AND t.precio_yango_pro > 0
                  AND t.precio_yango_pro != 'NaN'::numeric
                GROUP BY dp.country, dp.city ORDER BY viajes DESC
            """))

        # 2d. Ratio por tipo_servicio
        tbl("2d. RATIO por TIPO_SERVICIO (top 10)",
            q(conn, """
                SELECT t.tipo_servicio,
                    COUNT(*) AS viajes,
                    ROUND(AVG(ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0))::numeric, 4) AS avg_pct,
                    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY ABS(t.comision_empresa_asociada) / NULLIF(t.precio_yango_pro, 0)
                    )::numeric, 4) AS median_pct
                FROM public.trips_2026 t
                WHERE t.condicion = 'Completado'
                  AND t.fecha_inicio_viaje >= '2026-01-01' AND t.fecha_inicio_viaje < '2026-02-01'
                  AND t.comision_empresa_asociada IS NOT NULL AND t.comision_empresa_asociada != 0
                  AND t.precio_yango_pro IS NOT NULL AND t.precio_yango_pro > 0
                  AND t.precio_yango_pro != 'NaN'::numeric
                GROUP BY t.tipo_servicio ORDER BY viajes DESC LIMIT 10
            """))

        # ==================================================================
        # BLOQUE 3 — VALIDACIÓN OPERATIVA POR CIUDAD
        # ==================================================================
        print("\n\n" + "#" * 72)
        print("  BLOQUE 3 — VALIDACIÓN OPERATIVA POR CIUDAD")
        print("#" * 72)

        for city_filter in ['lima', 'cali', 'barranquilla']:
            tbl(f"3. PARKS en {city_filter.upper()} — dim.dim_park vs trips reales",
                q(conn, """
                    WITH dim AS (
                        SELECT park_id, park_name, country, city,
                               default_line_of_business, active
                        FROM dim.dim_park
                        WHERE lower(trim(city)) = %s
                    ),
                    trips AS (
                        SELECT park_id, COUNT(*) AS total_trips,
                               COUNT(*) FILTER (WHERE condicion='Completado') AS completed
                        FROM public.trips_2026
                        WHERE fecha_inicio_viaje >= '2026-01-01'
                          AND park_id IS NOT NULL
                        GROUP BY park_id
                    )
                    SELECT
                        COALESCE(d.park_id, t.park_id) AS park_id,
                        d.park_name,
                        d.default_line_of_business AS lob,
                        d.active,
                        COALESCE(t.total_trips, 0) AS total_trips_2026,
                        COALESCE(t.completed, 0) AS completed_2026,
                        CASE
                            WHEN d.park_id IS NULL THEN 'FANTASMA (trips sin dim)'
                            WHEN t.park_id IS NULL THEN 'INACTIVO (dim sin trips)'
                            ELSE 'OK'
                        END AS status
                    FROM dim d
                    FULL OUTER JOIN trips t
                        ON lower(trim(d.park_id::text)) = lower(trim(t.park_id::text))
                    WHERE d.park_id IS NOT NULL OR t.park_id IS NOT NULL
                    ORDER BY completed_2026 DESC
                """, (city_filter,)),
                ["park_id", "park_name", "lob", "active", "total_trips_2026",
                 "completed_2026", "status"])

        # ==================================================================
        # BLOQUE 4 — VALIDACIÓN DE MÉTRICAS CLAVE
        # ==================================================================
        print("\n\n" + "#" * 72)
        print("  BLOQUE 4 — MÉTRICAS CLAVE POR CIUDAD")
        print("#" * 72)

        tbl("4a. MÉTRICAS CLAVE por ciudad (último mes cerrado, desde day_v2)",
            q(conn, """
                SELECT country, city,
                    SUM(completed_trips)::bigint AS trips,
                    SUM(cancelled_trips)::bigint AS cancelled,
                    SUM(requested_trips)::bigint AS requested,
                    CASE WHEN SUM(requested_trips) > 0
                        THEN ROUND(100.0 * SUM(cancelled_trips) / SUM(requested_trips), 2)
                        ELSE NULL
                    END AS cancel_rate_pct,
                    ROUND(SUM(gross_revenue)::numeric, 0) AS revenue,
                    CASE WHEN SUM(completed_trips) > 0
                        THEN ROUND(SUM(gross_revenue)::numeric / SUM(completed_trips), 2)
                        ELSE NULL
                    END AS avg_ticket
                FROM ops.mv_real_lob_day_v2
                WHERE trip_date >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
                  AND trip_date < date_trunc('month', CURRENT_DATE)::date
                GROUP BY country, city
                ORDER BY trips DESC
            """),
            ["country", "city", "trips", "cancelled", "cancel_rate_pct",
             "revenue", "avg_ticket"])

        # 4b. Active drivers (desde fact_v2, más pesado, sample reciente)
        tbl("4b. ACTIVE DRIVERS por ciudad (últimos 7 días, fact_v2)",
            q(conn, """
                SELECT country, city,
                    COUNT(DISTINCT conductor_id) FILTER (WHERE is_completed) AS active_drivers,
                    COUNT(*) FILTER (WHERE is_completed) AS completed_trips,
                    CASE WHEN COUNT(DISTINCT conductor_id) FILTER (WHERE is_completed) > 0
                        THEN ROUND(
                            COUNT(*) FILTER (WHERE is_completed)::numeric
                            / COUNT(DISTINCT conductor_id) FILTER (WHERE is_completed), 2
                        )
                        ELSE NULL
                    END AS trips_per_driver
                FROM ops.v_real_trip_fact_v2
                WHERE trip_date >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY country, city
                HAVING COUNT(*) FILTER (WHERE is_completed) > 50
                ORDER BY completed_trips DESC
            """),
            ["country", "city", "active_drivers", "completed_trips", "trips_per_driver"])

        # 4c. Sanity check: valores absurdos
        tbl("4c. SANITY CHECK — outliers de ticket (avg_ticket > 500 o < 0.01)",
            q(conn, """
                SELECT country, city, trip_date,
                    SUM(completed_trips) AS trips,
                    CASE WHEN SUM(completed_trips) > 0
                        THEN ROUND(SUM(gross_revenue)::numeric / SUM(completed_trips), 2)
                        ELSE NULL
                    END AS avg_ticket
                FROM ops.mv_real_lob_day_v2
                WHERE trip_date >= CURRENT_DATE - INTERVAL '14 days'
                GROUP BY country, city, trip_date
                HAVING SUM(completed_trips) > 20
                   AND (SUM(gross_revenue)::numeric / NULLIF(SUM(completed_trips), 0) > 500
                        OR SUM(gross_revenue)::numeric / NULLIF(SUM(completed_trips), 0) < 0.01)
                ORDER BY trip_date DESC
                LIMIT 20
            """))

    print(f"\n\n  Diagnóstico completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
