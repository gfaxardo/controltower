"""
Auditoría de reconciliación del universo REAL: detección de unmapped.
Cruza trips_2025 + trips_2026 contra dim.dim_park y dimensiones territoriales.

READ-ONLY: No modifica datos. Solo consulta y genera reporte.

Uso:
    cd backend
    python -m scripts.audit_real_universe_unmapped
"""
import sys
import os
import io

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
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
        print("  (sin datos)")
        return
    if columns is None:
        columns = list(rows[0].keys())
    col_widths = {}
    for col in columns:
        col_widths[col] = max(len(str(col)), max(len(str(r.get(col, ""))) for r in rows))
    header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
    sep = "-+-".join("-" * col_widths[col] for col in columns)
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"  {header}")
    print(f"  {sep}")
    for r in rows:
        line = " | ".join(str(r.get(col, "")).ljust(col_widths[col]) for col in columns)
        print(f"  {line}")


def check_dim_park_exists(conn):
    """Verifica que dim.dim_park existe y tiene datos."""
    sql = """
    SELECT
        EXISTS(
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'dim' AND table_name = 'dim_park'
        ) AS table_exists,
        (SELECT COUNT(*) FROM dim.dim_park) AS total_parks
    """
    try:
        return run_query(conn, sql)
    except Exception as e:
        print(f"  [WARN] dim.dim_park no accesible: {e}")
        return [{"table_exists": False, "total_parks": 0}]


def dim_park_sample(conn):
    """Muestra estructura y sample de dim.dim_park."""
    sql = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'dim' AND table_name = 'dim_park'
    ORDER BY ordinal_position
    """
    return run_query(conn, sql)


def mapping_classification_global(conn):
    """Clasifica el universo en mapped/unmapped globalmente."""
    sql = """
    WITH raw_trips AS (
        SELECT park_id, fecha_inicio_viaje, condicion
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
        UNION ALL
        SELECT park_id, fecha_inicio_viaje, condicion
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
    ),
    classified AS (
        SELECT
            t.park_id,
            dp.park_id AS dim_park_id,
            dp.country AS dim_country,
            dp.city AS dim_city,
            CASE
                WHEN t.park_id IS NULL OR trim(t.park_id) = '' THEN 'park_null'
                WHEN dp.park_id IS NULL THEN 'park_unmapped'
                WHEN NULLIF(TRIM(COALESCE(dp.country::text, '')), '') IS NULL THEN 'country_unmapped'
                WHEN NULLIF(TRIM(COALESCE(dp.city::text, '')), '') IS NULL THEN 'city_unmapped'
                ELSE 'fully_mapped'
            END AS mapping_status
        FROM raw_trips t
        LEFT JOIN dim.dim_park dp
            ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
    )
    SELECT
        mapping_status,
        COUNT(*) AS trips,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM classified
    GROUP BY mapping_status
    ORDER BY trips DESC
    """
    return run_query(conn, sql)


def mapping_classification_by_year_month(conn):
    """Clasificación de mapping por año-mes."""
    sql = """
    WITH raw_trips AS (
        SELECT park_id, fecha_inicio_viaje, condicion,
               date_trunc('month', fecha_inicio_viaje)::date AS mes
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
        UNION ALL
        SELECT park_id, fecha_inicio_viaje, condicion,
               date_trunc('month', fecha_inicio_viaje)::date AS mes
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
    ),
    classified AS (
        SELECT
            t.mes,
            CASE
                WHEN t.park_id IS NULL OR trim(t.park_id) = '' THEN 'park_null'
                WHEN dp.park_id IS NULL THEN 'park_unmapped'
                WHEN NULLIF(TRIM(COALESCE(dp.country::text, '')), '') IS NULL THEN 'country_unmapped'
                WHEN NULLIF(TRIM(COALESCE(dp.city::text, '')), '') IS NULL THEN 'city_unmapped'
                ELSE 'fully_mapped'
            END AS mapping_status
        FROM raw_trips t
        LEFT JOIN dim.dim_park dp
            ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
    )
    SELECT
        mes,
        COUNT(*) AS total_trips,
        COUNT(*) FILTER (WHERE mapping_status = 'fully_mapped') AS fully_mapped,
        COUNT(*) FILTER (WHERE mapping_status = 'park_unmapped') AS park_unmapped,
        COUNT(*) FILTER (WHERE mapping_status = 'park_null') AS park_null,
        COUNT(*) FILTER (WHERE mapping_status = 'country_unmapped') AS country_unmapped,
        COUNT(*) FILTER (WHERE mapping_status = 'city_unmapped') AS city_unmapped,
        ROUND(100.0 * COUNT(*) FILTER (WHERE mapping_status = 'fully_mapped') / NULLIF(COUNT(*), 0), 2) AS pct_mapped
    FROM classified
    GROUP BY mes
    ORDER BY mes
    """
    return run_query(conn, sql)


def top_unmapped_parks(conn, limit=20):
    """Top parks no mapeados por volumen de viajes."""
    sql = """
    WITH raw_trips AS (
        SELECT park_id, fecha_inicio_viaje
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
          AND park_id IS NOT NULL AND trim(park_id) != ''
        UNION ALL
        SELECT park_id, fecha_inicio_viaje
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
          AND park_id IS NOT NULL AND trim(park_id) != ''
    )
    SELECT
        t.park_id,
        COUNT(*) AS trips_count,
        MIN(t.fecha_inicio_viaje)::date AS first_trip,
        MAX(t.fecha_inicio_viaje)::date AS last_trip
    FROM raw_trips t
    WHERE NOT EXISTS (
        SELECT 1 FROM dim.dim_park dp
        WHERE lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
    )
    GROUP BY t.park_id
    ORDER BY trips_count DESC
    LIMIT %s
    """
    return run_query(conn, sql, (limit,))


def mapping_by_city(conn):
    """Mapeo por ciudad (solo las resueltas) para detectar ciudades críticas."""
    sql = """
    WITH raw_trips AS (
        SELECT park_id, fecha_inicio_viaje
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
        UNION ALL
        SELECT park_id, fecha_inicio_viaje
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
    ),
    classified AS (
        SELECT
            COALESCE(NULLIF(TRIM(dp.city::text), ''), '(unmapped)') AS city,
            COALESCE(NULLIF(TRIM(dp.country::text), ''), '(unmapped)') AS country,
            CASE
                WHEN t.park_id IS NULL OR trim(t.park_id) = '' THEN 'park_null'
                WHEN dp.park_id IS NULL THEN 'park_unmapped'
                WHEN NULLIF(TRIM(COALESCE(dp.country::text, '')), '') IS NULL THEN 'country_unmapped'
                WHEN NULLIF(TRIM(COALESCE(dp.city::text, '')), '') IS NULL THEN 'city_unmapped'
                ELSE 'fully_mapped'
            END AS mapping_status
        FROM raw_trips t
        LEFT JOIN dim.dim_park dp
            ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
    )
    SELECT
        country,
        city,
        COUNT(*) AS total_trips,
        COUNT(*) FILTER (WHERE mapping_status = 'fully_mapped') AS mapped,
        COUNT(*) FILTER (WHERE mapping_status != 'fully_mapped') AS unmapped,
        ROUND(100.0 * COUNT(*) FILTER (WHERE mapping_status = 'fully_mapped') / NULLIF(COUNT(*), 0), 2) AS pct_mapped
    FROM classified
    GROUP BY country, city
    ORDER BY total_trips DESC
    LIMIT 30
    """
    return run_query(conn, sql)


def lob_mapping_diagnostic(conn):
    """Diagnóstico de tipo_servicio -> LOB mapping coverage."""
    sql = """
    WITH raw_trips AS (
        SELECT tipo_servicio
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
          AND condicion = 'Completado'
        UNION ALL
        SELECT tipo_servicio
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
          AND condicion = 'Completado'
    )
    SELECT
        COALESCE(NULLIF(TRIM(tipo_servicio), ''), '(null/vacío)') AS tipo_servicio,
        COUNT(*) AS trips,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM raw_trips
    GROUP BY 1
    ORDER BY trips DESC
    LIMIT 30
    """
    return run_query(conn, sql)


def enriched_base_coverage(conn):
    """Cobertura del enriched base (vista 118) si existe."""
    sql = """
    SELECT EXISTS(
        SELECT 1 FROM information_schema.views
        WHERE table_schema = 'ops' AND table_name = 'v_real_trips_enriched_base'
    ) AS view_exists
    """
    result = run_query(conn, sql)
    if not result or not result[0].get("view_exists"):
        return None

    sql2 = """
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE country IS NOT NULL) AS con_country,
        ROUND(100.0 * COUNT(*) FILTER (WHERE country IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS pct_country,
        COUNT(*) FILTER (WHERE city IS NOT NULL) AS con_city,
        ROUND(100.0 * COUNT(*) FILTER (WHERE city IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS pct_city,
        COUNT(*) FILTER (WHERE park_name IS NOT NULL) AS con_park_name,
        ROUND(100.0 * COUNT(*) FILTER (WHERE park_name IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS pct_park_name,
        COUNT(*) FILTER (WHERE completed_flag) AS completed,
        COUNT(*) FILTER (WHERE cancelled_flag) AS cancelled
    FROM ops.v_real_trips_enriched_base
    WHERE trip_month >= '2025-01-01'::date
    """
    return run_query(conn, sql2)


def main():
    print("=" * 70)
    print("  AUDITORÍA DE RECONCILIACIÓN: UNIVERSO REAL UNMAPPED")
    print(f"  Fuentes: public.trips_2025 + public.trips_2026 vs dim.dim_park")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Modo: READ-ONLY")
    print("=" * 70)

    with get_db_audit(timeout_ms=900000) as conn:
        print("\n[1/7] Verificando dim.dim_park...")
        dp_check = check_dim_park_exists(conn)
        print_table("dim.dim_park STATUS", dp_check, ["table_exists", "total_parks"])

        if dp_check and dp_check[0].get("table_exists"):
            print("\n[1b] Schema de dim.dim_park...")
            dp_schema = dim_park_sample(conn)
            print_table("dim.dim_park COLUMNAS", dp_schema, ["column_name", "data_type"])

        print("\n[2/7] Clasificación global de mapping...")
        global_class = mapping_classification_global(conn)
        print_table("MAPPING GLOBAL", global_class,
                     ["mapping_status", "trips", "pct"])

        print("\n[3/7] Clasificación por año-mes...")
        monthly_class = mapping_classification_by_year_month(conn)
        print_table("MAPPING POR MES", monthly_class,
                     ["mes", "total_trips", "fully_mapped", "park_unmapped",
                      "park_null", "country_unmapped", "city_unmapped", "pct_mapped"])

        print("\n[4/7] Top 20 parks no mapeados...")
        top_unmapped = top_unmapped_parks(conn)
        print_table("TOP PARKS UNMAPPED", top_unmapped,
                     ["park_id", "trips_count", "first_trip", "last_trip"])

        print("\n[5/7] Mapping por ciudad (top 30)...")
        by_city = mapping_by_city(conn)
        print_table("MAPPING POR CIUDAD", by_city,
                     ["country", "city", "total_trips", "mapped", "unmapped", "pct_mapped"])

        print("\n[6/7] Diagnóstico tipo_servicio (completados, top 30)...")
        lob_diag = lob_mapping_diagnostic(conn)
        print_table("TIPO_SERVICIO EN COMPLETADOS", lob_diag,
                     ["tipo_servicio", "trips", "pct"])

        print("\n[7/7] Cobertura vista enriched_base (ops.v_real_trips_enriched_base)...")
        enriched = enriched_base_coverage(conn)
        if enriched:
            print_table("ENRICHED BASE COVERAGE", enriched,
                         ["total", "pct_country", "pct_city", "pct_park_name",
                          "completed", "cancelled"])
        else:
            print("  [SKIP] Vista ops.v_real_trips_enriched_base no existe o no accesible")

        # Resumen
        print("\n" + "=" * 70)
        print("  RESUMEN DE RECONCILIACIÓN")
        print("=" * 70)

        if global_class:
            total = sum(int(r.get("trips", 0)) for r in global_class)
            mapped = sum(int(r.get("trips", 0)) for r in global_class
                         if r.get("mapping_status") == "fully_mapped")
            unmapped = total - mapped
            pct_mapped = round(100.0 * mapped / total, 2) if total else 0
            pct_unmapped = round(100.0 * unmapped / total, 2) if total else 0

            print(f"  Total viajes (trips_2025 + trips_2026): {total:,}")
            print(f"  Fully mapped: {mapped:,} ({pct_mapped}%)")
            print(f"  Unmapped (cualquier categoría): {unmapped:,} ({pct_unmapped}%)")
            print()

            for r in global_class:
                status = r.get("mapping_status", "")
                trips = int(r.get("trips", 0))
                pct = r.get("pct", 0)
                if status != "fully_mapped":
                    print(f"  - {status}: {trips:,} viajes ({pct}%)")

            if pct_unmapped > 5:
                print(f"\n  → ALERTA: {pct_unmapped}% del universo no está mapeado.")
                print(f"    Se requiere atención en dim.dim_park o en los park_id de las fuentes.")
            elif pct_unmapped > 1:
                print(f"\n  → ATENCIÓN: {pct_unmapped}% del universo no mapeado (nivel moderado).")
            else:
                print(f"\n  → OK: Solo {pct_unmapped}% del universo no mapeado.")

        print("\n  RECOMENDACIÓN PARA FASE POSTERIOR:")
        print("  1. Agregar park_ids faltantes a dim.dim_park (priorizar top 20 por volumen)")
        print("  2. Crear categoría 'UNMAPPED' explícita en staging/resolved para visibilidad")
        print("  3. No excluir viajes unmapped de facts; exponerlos con fallback territorial")
        print("  4. Implementar en capa staging (ej. ops.v_real_trips_enriched_base ya hace LEFT JOIN)")
        print("  5. Considerar alertas automáticas cuando pct_unmapped > 2%")

    print(f"\n  Auditoría completada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
