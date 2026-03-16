"""
Investigación ruptura común REAL (margen, B2B, LOB) desde feb 2026.
Ejecuta cobertura por semana por capa. NO implementa fixes.
Uso: cd backend && python -m scripts.investigate_real_rupture_2026
"""
from __future__ import annotations

import sys
import os
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


def week_starts(from_d: date, to_d: date):
    """Genera lunes de cada semana en [from_d, to_d]."""
    d = from_d - timedelta(days=from_d.weekday())
    while d <= to_d:
        yield d
        d += timedelta(days=7)


def main():
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    from_d = date(2026, 1, 1)
    to_d = date.today()
    weeks = list(week_starts(from_d, to_d))

    print("=" * 70)
    print("FASE 0 — MAPA DE CAMPOS (resumen)")
    print("=" * 70)
    print("""
metrica          | campo origen              | vista 1ra aparicion   | hasta day_v2/week_v3
margen_total     | comision_empresa_asociada | v_trips_real_canon_120d -> v_real_trip_fact_v2.margin_total -> hourly -> day_v2
margen_trip      | derivado margen/viajes    | hourly/day agregado  | idem
viajes B2B       | pago_corporativo IS NOT NULL | v_real_trip_fact_v2 segment_tag B2B -> hourly -> day_v2 (b2b_trips)
LOB resuelto     | tipo_servicio + dim_service_type + dim_lob_group | v_real_trip_fact_v2 lob_group
tipo_servicio    | tipo_servicio + normalize_real_tipo_servicio | v_real_trip_fact_v2 real_tipo_servicio_norm
Joins: canon -> parks (LEFT) -> with_geo; with_service (tipo_servicio IS NOT NULL); with_lob (dim_service_type, dim_lob_group).
FILTRO CRITICO: with_service WHERE tipo_servicio IS NOT NULL; si tipo_servicio null la fila se PIERDE en trip_fact.
""")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '120000'")

        # Columnas en fuente
        print("\n--- Columnas comision/pago/tipo en trips_all y trips_2026 ---")
        for tbl in ("trips_all", "trips_2026"):
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                  AND (column_name ILIKE '%%comision%%' OR column_name ILIKE '%%pago%%' OR column_name ILIKE '%%tipo_servicio%%' OR column_name = 'condicion')
                ORDER BY ordinal_position
            """, (tbl,))
            rows = cur.fetchall()
            print(f"  {tbl}: {[r['column_name'] for r in rows]}")

        # FASE 1 y 2 — Cobertura por semana por capa
        print("\n" + "=" * 70)
        print("FASE 1–2 — CORTE TEMPORAL Y COBERTURA POR SEMANA (desde 2026-01-01)")
        print("=" * 70)

        # 1) trips_2026 por semana (solo datos >= 2026-01-01)
        print("\n--- 1. FUENTE RAÍZ trips_2026 (por week_start) ---")
        cur.execute("""
            SELECT
                date_trunc('week', fecha_inicio_viaje)::date AS week_start,
                COUNT(*) AS total_trips,
                COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed,
                COUNT(*) FILTER (WHERE condicion = 'Cancelado' OR condicion ILIKE '%%cancel%%') AS cancelled,
                COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL) AS con_comision,
                COUNT(*) FILTER (WHERE pago_corporativo IS NOT NULL) AS con_pago_corp,
                COUNT(*) FILTER (WHERE tipo_servicio IS NOT NULL AND TRIM(tipo_servicio::text) <> '') AS con_tipo_servicio
            FROM public.trips_2026
            WHERE fecha_inicio_viaje >= '2026-01-01'
            GROUP BY date_trunc('week', fecha_inicio_viaje)::date
            ORDER BY week_start
        """)
        src_rows = cur.fetchall()
        for r in src_rows:
            ws = str(r["week_start"])[:10]
            ct = r["con_comision"] or 0
            tot = r["total_trips"] or 0
            pct = (100.0 * ct / tot) if tot else 0
            print(f"  {ws}  total={tot} completed={r['completed']} con_comision={ct} ({pct:.1f}%%) con_pago_corp={r['con_pago_corp']} con_tipo_servicio={r['con_tipo_servicio']}")

        # 2) v_real_trip_fact_v2 por semana (solo viajes con fecha en ventana; vista 120d)
        print("\n--- 2. v_real_trip_fact_v2 (por week_start, margin_total y segment_tag) ---")
        try:
            cur.execute("SET statement_timeout = '300000'")
            cur.execute("""
                SELECT
                    trip_week_start AS week_start,
                    COUNT(*) AS total_rows,
                    COUNT(*) FILTER (WHERE margin_total IS NOT NULL) AS con_margin,
                    COUNT(*) FILTER (WHERE segment_tag = 'B2B') AS b2b_rows,
                    COUNT(*) FILTER (WHERE lob_group IS NOT NULL AND lob_group <> 'UNCLASSIFIED') AS con_lob
                FROM ops.v_real_trip_fact_v2
                WHERE trip_date >= '2026-01-01'
                GROUP BY trip_week_start
                ORDER BY trip_week_start
            """)
            fact_rows = cur.fetchall()
            cur.execute("SET statement_timeout = '120000'")
            for r in fact_rows:
                ws = str(r["week_start"])[:10]
                tot = r["total_rows"] or 0
                cm = r["con_margin"] or 0
                pct = (100.0 * cm / tot) if tot else 0
                print(f"  {ws}  total={tot} con_margin={cm} ({pct:.1f}%%) b2b={r['b2b_rows']} con_lob={r['con_lob']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            conn.rollback()
            cur.execute("SET statement_timeout = '120000'")

        # 3) day_v2 por semana (columnas: requested_trips, completed_trips, cancelled_trips, margin_total, segment_tag)
        print("\n--- 3. mv_real_lob_day_v2 (por week = date_trunc week de trip_date) ---")
        try:
            cur.execute("""
                SELECT
                    date_trunc('week', trip_date)::date AS week_start,
                    SUM(requested_trips) AS total_trips,
                    SUM(completed_trips) AS completed,
                    SUM(cancelled_trips) AS cancelled,
                    COUNT(*) FILTER (WHERE margin_total IS NOT NULL AND margin_total <> 0) AS filas_con_margin,
                    SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END) AS b2b_trips
                FROM ops.mv_real_lob_day_v2
                WHERE trip_date >= '2026-01-01'
                GROUP BY date_trunc('week', trip_date)::date
                ORDER BY week_start
            """)
            day_rows = cur.fetchall()
            for r in day_rows:
                ws = str(r["week_start"])[:10]
                tot = float(r["total_trips"] or 0)
                mm = r["filas_con_margin"] or 0
                print(f"  {ws}  total_trips={tot} completed={r['completed']} filas_con_margin={mm} b2b_trips={r['b2b_trips']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            conn.rollback()

        # 4) week_v3
        print("\n--- 4. mv_real_lob_week_v3 ---")
        try:
            cur.execute("""
                SELECT week_start::text,
                       SUM(trips) AS total_trips,
                       SUM(completed_trips) AS completed,
                       SUM(cancelled_trips) AS cancelled,
                       SUM(margin_total) AS sum_margin,
                       SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END) AS b2b_trips
                FROM ops.mv_real_lob_week_v3
                WHERE week_start >= '2026-01-01'
                GROUP BY week_start
                ORDER BY week_start
            """)
            for r in cur.fetchall():
                print(f"  {r['week_start']}  total={r['total_trips']} sum_margin={r['sum_margin']} b2b_trips={r['b2b_trips']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            conn.rollback()

        # 5) month_v3
        print("\n--- 5. mv_real_lob_month_v3 ---")
        try:
            cur.execute("""
                SELECT month_start::text,
                       SUM(trips) AS total_trips,
                       SUM(completed_trips) AS completed,
                       SUM(margin_total) AS sum_margin,
                       SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END) AS b2b_trips
                FROM ops.mv_real_lob_month_v3
                WHERE month_start >= '2026-01-01'
                GROUP BY month_start
                ORDER BY month_start
            """)
            for r in cur.fetchall():
                print(f"  {r['month_start']}  total={r['total_trips']} sum_margin={r['sum_margin']} b2b_trips={r['b2b_trips']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            conn.rollback()

        # FASE 3 — Cuadro null-rate por semana (trips_2026)
        print("\n" + "=" * 70)
        print("FASE 3 — NULL-RATE POR SEMANA (trips_2026)")
        print("=" * 70)
        try:
            cur.execute("""
            SELECT
                date_trunc('week', fecha_inicio_viaje)::date AS week_start,
                COUNT(*) AS n,
                ROUND(100.0 * COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_comision,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pago_corporativo IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_pago_corp,
                ROUND(100.0 * COUNT(*) FILTER (WHERE tipo_servicio IS NOT NULL AND TRIM(COALESCE(tipo_servicio::text,'')) <> '') / NULLIF(COUNT(*), 0), 1) AS pct_tipo_servicio
            FROM public.trips_2026
            WHERE fecha_inicio_viaje >= '2026-01-01'
            GROUP BY date_trunc('week', fecha_inicio_viaje)::date
            ORDER BY week_start
        """)
            for r in cur.fetchall():
                print(f"  {r['week_start']}  n={r['n']}  pct_comision={r['pct_comision']}%%  pct_pago_corp={r['pct_pago_corp']}%%  pct_tipo_servicio={r['pct_tipo_servicio']}%%")
        except Exception as e:
            print(f"  ERROR: {e}")
            conn.rollback()

        # FASE 5 — Por país (trips_2026: necesitamos país; no hay country en trips_2026, usar park o inferir)
        print("\n" + "=" * 70)
        print("FASE 5 — COBERTURA POR PAÍS (v_real_trip_fact_v2 tiene country)")
        print("=" * 70)
        try:
            cur.execute("""
                SELECT
                    trip_week_start::text,
                    country,
                    COUNT(*) AS n,
                    COUNT(*) FILTER (WHERE margin_total IS NOT NULL) AS con_margin,
                    COUNT(*) FILTER (WHERE segment_tag = 'B2B') AS b2b
                FROM ops.v_real_trip_fact_v2
                WHERE trip_date >= '2026-01-01'
                GROUP BY trip_week_start, country
                ORDER BY trip_week_start, country
            """)
            for r in cur.fetchall():
                tot = r["n"] or 0
                pct = (100.0 * (r["con_margin"] or 0) / tot) if tot else 0
                print(f"  {r['trip_week_start']}  {r['country'] or '?'}  n={tot}  con_margin={r['con_margin']} ({pct:.1f}%%)  b2b={r['b2b']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            conn.rollback()

        cur.close()

    print("\n" + "=" * 70)
    print("Fin diagnóstico. Revisar: semana donde pct_comision/con_margin cae = quiebre.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
