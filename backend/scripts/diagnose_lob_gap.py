"""
Diagnóstico exacto de la brecha service_type -> LOB.
Fuente: ops.real_drill_dim_fact (dimension_key, trips), canon.map_real_tipo_servicio_to_lob_group.
No se usa mv_real_lob_base (no existe en el pipeline del drill actual).
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.db.connection import _get_connection_params
import psycopg2
from psycopg2.extras import RealDictCursor


def run(cur, title, sql, max_rows=200):
    print(f"\n{'='*70}\n{title}\n{'='*70}")
    cur.execute(sql)
    rows = cur.fetchall()
    for i, r in enumerate(rows):
        if i >= max_rows:
            print(f"... ({len(rows)} filas, mostrando {max_rows})")
            break
        print(dict(r))
    if not rows:
        print("(sin resultados)")
    return rows


def main():
    conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SET statement_timeout = '60000'")

    # A. Residual UNCLASSIFIED en service_type y LOB (columnas reales: dimension_key, trips)
    run(cur, "A. UNCLASSIFIED por breakdown (dimension_key = UNCLASSIFIED)", """
        SELECT
            breakdown,
            dimension_key AS breakdown_value,
            SUM(trips) AS trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown IN ('service_type', 'lob')
          AND dimension_key = 'UNCLASSIFIED'
        GROUP BY breakdown, dimension_key
        ORDER BY breakdown
    """)

    # B. Qué validated_service_type (dimension_key en service_type) NO tiene mapping -> generan LOB UNCLASSIFIED
    run(cur, "B. validated_service_type SIN mapping LOB (explican la brecha)", """
        SELECT
            s.dimension_key AS validated_service_type,
            SUM(s.trips) AS trips
        FROM ops.real_drill_dim_fact s
        WHERE s.breakdown = 'service_type'
          AND NOT EXISTS (
              SELECT 1 FROM canon.map_real_tipo_servicio_to_lob_group m
              WHERE m.real_tipo_servicio = s.dimension_key
          )
        GROUP BY s.dimension_key
        ORDER BY trips DESC
    """, max_rows=500)
    run(cur, "B2. Consistencia: suma LOB UNCLASSIFIED vs suma service_type sin mapping", """
        SELECT
            (SELECT SUM(trips) FROM ops.real_drill_dim_fact WHERE breakdown = 'lob' AND dimension_key = 'UNCLASSIFIED') AS lob_unclassified_trips,
            (SELECT SUM(trips) FROM ops.real_drill_dim_fact s WHERE s.breakdown = 'service_type'
             AND NOT EXISTS (SELECT 1 FROM canon.map_real_tipo_servicio_to_lob_group m WHERE m.real_tipo_servicio = s.dimension_key)) AS unmapped_service_type_trips
    """)

    # C. Totales por breakdown para % residual
    run(cur, "C. Totales por breakdown (para % residual)", """
        SELECT
            breakdown,
            SUM(trips) AS total_trips,
            SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) AS unclassified_trips,
            ROUND(100.0 * SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) / NULLIF(SUM(trips), 0), 2) AS pct_unclassified
        FROM ops.real_drill_dim_fact
        WHERE breakdown IN ('service_type', 'lob')
        GROUP BY breakdown
        ORDER BY breakdown
    """)

    # D. LOB UNCLASSIFIED por periodo (detectar si es rango de fechas)
    run(cur, "D. LOB UNCLASSIFIED por año (¿stale por rango?)", """
        SELECT
            DATE_TRUNC('year', period_start)::date AS year_start,
            SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) AS lob_uncl_trips,
            SUM(trips) AS total_lob_trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'lob'
        GROUP BY DATE_TRUNC('year', period_start)::date
        ORDER BY year_start
    """)
    run(cur, "D2. service_type total por año (comparar con LOB)", """
        SELECT
            DATE_TRUNC('year', period_start)::date AS year_start,
            SUM(trips) AS total_st_trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
        GROUP BY DATE_TRUNC('year', period_start)::date
        ORDER BY year_start
    """)

    # E. Mapping LOB actual (referencia)
    run(cur, "E. canon.map_real_tipo_servicio_to_lob_group (referencia)", """
        SELECT real_tipo_servicio, lob_group
        FROM canon.map_real_tipo_servicio_to_lob_group
        ORDER BY real_tipo_servicio
    """, 100)

    cur.close()
    conn.close()
    print("\n" + "="*70 + "\nDiagnóstico brecha service_type -> LOB completado.\n" + "="*70)


if __name__ == "__main__":
    main()
    sys.exit(0)
