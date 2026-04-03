"""
Validación de consolidación de revenue: compara business slice vs hourly-first.
Verifica coherencia de revenue tras migración 121.

READ-ONLY. No modifica datos.

Uso: cd backend && python -m scripts.validate_revenue_consolidation
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db_audit
from psycopg2.extras import RealDictCursor
from datetime import datetime


def run_query(conn, sql, params=None):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or ())
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def print_table(title, rows, columns=None):
    if not rows:
        print(f"\n{'='*70}\n  {title}\n{'='*70}\n  (sin datos)")
        return
    if columns is None:
        columns = list(rows[0].keys())
    widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    hdr = " | ".join(str(c).ljust(widths[c]) for c in columns)
    sep = "-+-".join("-" * widths[c] for c in columns)
    print(f"\n{'='*70}\n  {title}\n{'='*70}\n  {hdr}\n  {sep}")
    for r in rows:
        print("  " + " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def main():
    print("=" * 70)
    print("  VALIDACIÓN DE CONSOLIDACIÓN DE REVENUE")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    with get_db_audit(timeout_ms=600000) as conn:

        # 1. Verificar que canon_120d ya no usa trips_all
        print("\n[1/6] Verificando fuentes de v_trips_real_canon_120d...")
        rows = run_query(conn, """
            SELECT pg_get_viewdef('ops.v_trips_real_canon_120d'::regclass, true) AS viewdef
        """)
        if rows:
            viewdef = rows[0].get('viewdef', '')
            has_trips_all = 'trips_all' in viewdef
            has_trips_2025 = 'trips_2025' in viewdef
            has_trips_2026 = 'trips_2026' in viewdef
            print(f"  trips_all: {'SÍ (PROBLEMA)' if has_trips_all else 'NO (OK)'}")
            print(f"  trips_2025: {'SÍ (OK)' if has_trips_2025 else 'NO'}")
            print(f"  trips_2026: {'SÍ (OK)' if has_trips_2026 else 'NO'}")

        # 2. Verificar columnas de v_real_trip_fact_v2
        print("\n[2/6] Verificando columnas de v_real_trip_fact_v2...")
        rows = run_query(conn, """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'v_real_trip_fact_v2'
            AND column_name IN ('gross_revenue', 'margin_total', 'revenue_source',
                                'comision_empresa_asociada_raw')
            ORDER BY column_name
        """)
        print_table("COLUMNAS FACT_V2", rows, ["column_name"])

        # 3. Revenue source distribution en fact_v2 (sample reciente)
        print("\n[3/6] Distribución de revenue_source en fact_v2 (mes más reciente)...")
        rows = run_query(conn, """
            SELECT revenue_source, count(*) AS cnt,
                   ROUND(AVG(gross_revenue)::numeric, 2) AS avg_gross_revenue,
                   ROUND(SUM(margin_total)::numeric, 2) AS sum_margin
            FROM ops.v_real_trip_fact_v2
            WHERE is_completed AND trip_month_start >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY revenue_source
            ORDER BY cnt DESC
        """)
        print_table("REVENUE SOURCE (último mes cerrado, completados)", rows)

        # 4. Comparar hourly-first day_v2 vs business slice por ciudad
        print("\n[4/6] Comparativa hourly-first day_v2 vs business_slice month_fact...")
        rows = run_query(conn, """
            WITH hf AS (
                SELECT
                    date_trunc('month', trip_date)::date AS month,
                    country, city,
                    SUM(completed_trips) AS hf_completed,
                    ROUND(SUM(gross_revenue)::numeric, 2) AS hf_gross_revenue,
                    ROUND(SUM(margin_total)::numeric, 2) AS hf_margin
                FROM ops.mv_real_lob_day_v2
                WHERE trip_date >= '2026-01-01'::date
                GROUP BY 1, 2, 3
            ),
            bs AS (
                SELECT
                    month,
                    LOWER(TRIM(country)) AS country,
                    LOWER(TRIM(city)) AS city,
                    SUM(trips_completed) AS bs_completed,
                    ROUND(SUM(COALESCE(revenue_yego_final, revenue_yego_net))::numeric, 2) AS bs_revenue,
                    ROUND(SUM(revenue_yego_net)::numeric, 2) AS bs_revenue_net
                FROM ops.real_business_slice_month_fact
                WHERE month >= '2026-01-01'::date
                GROUP BY 1, 2, 3
            )
            SELECT
                COALESCE(hf.month, bs.month) AS month,
                COALESCE(hf.country, bs.country) AS country,
                COALESCE(hf.city, bs.city) AS city,
                hf.hf_completed, bs.bs_completed,
                hf.hf_gross_revenue, hf.hf_margin,
                bs.bs_revenue, bs.bs_revenue_net
            FROM hf
            FULL OUTER JOIN bs ON hf.month = bs.month
                AND hf.country = bs.country AND hf.city = bs.city
            ORDER BY month DESC, country, city
        """)
        print_table("HOURLY-FIRST vs BUSINESS SLICE (2026+)", rows,
                     ["month", "country", "city", "hf_completed", "bs_completed",
                      "hf_gross_revenue", "bs_revenue"])

        # 5. Revenue por ciudad clave
        print("\n[5/6] Revenue consolidado por ciudad clave (fact_v2, mes reciente)...")
        rows = run_query(conn, """
            SELECT city,
                   count(*) FILTER (WHERE is_completed) AS completed,
                   count(*) FILTER (WHERE is_completed AND revenue_source = 'real') AS real_trips,
                   count(*) FILTER (WHERE is_completed AND revenue_source = 'proxy') AS proxy_trips,
                   count(*) FILTER (WHERE is_completed AND revenue_source = 'missing') AS missing_trips,
                   ROUND(SUM(gross_revenue) FILTER (WHERE is_completed)::numeric, 2) AS total_revenue,
                   ROUND(AVG(gross_revenue) FILTER (WHERE is_completed)::numeric, 2) AS avg_revenue
            FROM ops.v_real_trip_fact_v2
            WHERE trip_month_start >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
              AND city IN ('lima', 'cali', 'barranquilla', 'medellin', 'trujillo')
            GROUP BY city
            ORDER BY completed DESC
        """)
        print_table("REVENUE POR CIUDAD CLAVE", rows)

        # 6. Verificar consistencia fact_v2 → day_v2
        print("\n[6/6] Consistencia fact_v2 vs day_v2 (último mes)...")
        rows = run_query(conn, """
            WITH fact AS (
                SELECT
                    SUM(gross_revenue) FILTER (WHERE is_completed) AS fact_revenue,
                    COUNT(*) FILTER (WHERE is_completed) AS fact_completed
                FROM ops.v_real_trip_fact_v2
                WHERE trip_month_start >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            ),
            day AS (
                SELECT
                    SUM(gross_revenue) AS day_revenue,
                    SUM(completed_trips) AS day_completed
                FROM ops.mv_real_lob_day_v2
                WHERE trip_date >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            )
            SELECT
                fact.fact_completed, day.day_completed,
                ROUND(fact.fact_revenue::numeric, 2) AS fact_revenue,
                ROUND(day.day_revenue::numeric, 2) AS day_revenue,
                CASE WHEN fact.fact_revenue > 0
                    THEN ROUND(((day.day_revenue - fact.fact_revenue) / fact.fact_revenue * 100)::numeric, 2)
                    ELSE NULL
                END AS diff_pct
            FROM fact, day
        """)
        print_table("CONSISTENCIA FACT_V2 vs DAY_V2", rows)

    print(f"\n  Validación completada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
