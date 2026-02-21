#!/usr/bin/env python3
"""
Comprueba calidad de Real LOB (tipo_servicio -> LOB normalizado).
- Top tipo_servicio raw con count (detectar basura).
- pct_unclassified por country/city (warning si > 5%).
- Último mes y última semana detectados.
Uso: desde backend/ ejecutar python -m scripts.check_real_lob_quality
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

from app.db.connection import get_db, init_db_pool

TOP_N = 50
WARN_PCT_UNCLASSIFIED = 5.0


TIMEOUT_MS = 300000  # 5 min para consultas sobre trips_all


def main():
    init_db_pool()
    print("=" * 60)
    print("Real LOB — Calidad (tipo_servicio -> LOB)")
    print("=" * 60)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))

        # 1) Top tipo_servicio raw
        cur.execute("""
            SELECT LOWER(TRIM(tipo_servicio::text)) AS ts, COUNT(*) AS cnt
            FROM public.trips_all
            WHERE condicion = 'Completado'
              AND tipo_servicio IS NOT NULL
            GROUP BY LOWER(TRIM(tipo_servicio::text))
            ORDER BY cnt DESC
            LIMIT %s
        """, (TOP_N,))
        rows = cur.fetchall()
        print(f"\n1) Top {TOP_N} tipo_servicio (raw) en trips_all:")
        print("-" * 40)
        for ts, cnt in rows:
            print(f"  {cnt:>10}  {ts or '(null)'}")

        # 2) pct_unclassified por country/city (usando misma lógica que la vista)
        cur.execute("""
            WITH base AS (
                SELECT
                    t.tipo_servicio,
                    p.name AS park_name_raw,
                    p.city AS park_city_raw
                FROM public.trips_all t
                JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
                WHERE t.condicion = 'Completado' AND t.tipo_servicio IS NOT NULL
                  AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
            ),
            with_city AS (
                SELECT
                    tipo_servicio,
                    CASE
                        WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                        WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                        WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                        WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                        WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                        WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                        WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                        WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                        WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                        ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                    END AS city_norm
                FROM base
            ),
            with_key AS (
                SELECT
                    tipo_servicio,
                    LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
                FROM with_city
            ),
            with_country AS (
                SELECT
                    tipo_servicio,
                    COALESCE(NULLIF(city_key, ''), '') AS city,
                    CASE
                        WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                        WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                        ELSE ''
                    END AS country
                FROM with_key
            ),
            with_lob AS (
                SELECT
                    country,
                    city,
                    CASE
                        WHEN LOWER(TRIM(tipo_servicio::text)) IS NULL OR LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                        WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                        WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                        WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                        WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','tuk-tuk','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                        WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                        ELSE 'UNCLASSIFIED'
                    END AS lob
                FROM with_country
            )
            SELECT
                country,
                city,
                COUNT(*) AS total,
                SUM(CASE WHEN lob = 'UNCLASSIFIED' THEN 1 ELSE 0 END) AS unclassified
            FROM with_lob
            WHERE country IN ('co', 'pe')
            GROUP BY country, city
            ORDER BY country, city
        """)
        rows_cc = cur.fetchall()
        print(f"\n2) pct_unclassified por country/city (warning si > {WARN_PCT_UNCLASSIFIED}%):")
        print("-" * 50)
        warn_any = False
        for country, city, total, uncl in rows_cc:
            pct = (100.0 * uncl / total) if total else 0
            flag = " [WARNING]" if pct > WARN_PCT_UNCLASSIFIED else ""
            if pct > WARN_PCT_UNCLASSIFIED:
                warn_any = True
            print(f"  {country} / {city or '(vacío)'}: {pct:.1f}% UNCLASSIFIED ({uncl}/{total}){flag}")
        if not rows_cc:
            print("  (sin datos country/city)")
        elif not warn_any:
            print("  OK: pct_unclassified <= 5% en todos.")

        # 3) Último mes y última semana
        try:
            cur.execute("SELECT MAX(month_start) FROM ops.mv_real_trips_by_lob_month")
            r = cur.fetchone()
            last_month = r[0].strftime("%Y-%m") if r and r[0] else "—"
            cur.execute("SELECT MAX(week_start) FROM ops.mv_real_trips_by_lob_week")
            r = cur.fetchone()
            last_week = r[0].strftime("%Y-%m-%d") if r and r[0] else "—"
        except Exception:
            last_month = "—"
            last_week = "—"
        print(f"\n3) Último mes detectado (MV): {last_month}")
        print(f"   Última semana detectada (MV): {last_week}")

        cur.close()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
