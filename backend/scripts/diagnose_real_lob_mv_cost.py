#!/usr/bin/env python3
"""
FASE B — Diagnóstico de costo del bootstrap Real LOB.

Ejecuta EXPLAIN (sin ANALYZE, no destructivo) sobre:
- La vista base filtrada por 120 días
- La agregación mensual/semanal equivalente a un bloque

Ayuda a identificar: full scans, nested loops pesados, sorts/hashes costosos.
Requiere que las MVs existan (pueden estar vacías).

Uso: cd backend && python scripts/diagnose_real_lob_mv_cost.py
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


def main():
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()

        # 0) Si existe vista _120d (post-098), explicar esa (index-friendly)
        cur.execute("SELECT 1 FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_real_trips_with_lob_v2_120d'")
        has_120d = cur.fetchone()
        if has_120d:
            print("\n=== EXPLAIN: SELECT desde v_real_trips_with_lob_v2_120d (ventana en vista) ===")
            cur.execute("""
                EXPLAIN (FORMAT TEXT)
                SELECT * FROM ops.v_real_trips_with_lob_v2_120d LIMIT 1
            """)
            for row in cur.fetchall():
                print(row[0])

        # 1) EXPLAIN de la vista base con ventana 120 días (solo lectura)
        print("\n=== EXPLAIN: SELECT desde v_real_trips_with_lob_v2 (120 días) ===")
        cur.execute("""
            EXPLAIN (FORMAT TEXT)
            SELECT * FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
            LIMIT 1
        """)
        for row in cur.fetchall():
            print(row[0])

        # 2) EXPLAIN de un bloque mensual (un mes)
        print("\n=== EXPLAIN: agregación mensual (un mes) ===")
        cur.execute("""
            EXPLAIN (FORMAT TEXT)
            WITH base AS (
                SELECT * FROM ops.v_real_trips_with_lob_v2
                WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '31 days'
                  AND fecha_inicio_viaje <  CURRENT_DATE - INTERVAL '30 days'
            )
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                     (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        """)
        for row in cur.fetchall():
            print(row[0])

        # 3) Índices en tablas fuente (v_trips_real_canon suele depender de una tabla de viajes)
        print("\n=== Índices en ops (tablas/vistas relacionadas) ===")
        cur.execute("""
            SELECT c.relname, i.relname AS index_name, a.attname
            FROM pg_index x
            JOIN pg_class c ON c.oid = x.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'ops'
            JOIN pg_class i ON i.oid = x.indexrelid
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(x.indkey) AND a.attnum > 0 AND NOT a.attisdropped
            WHERE c.relkind IN ('r','v','m')
            ORDER BY c.relname, i.relname
            LIMIT 50
        """)
        for row in cur.fetchall():
            print("  %s | %s | %s" % (row[0], row[1], row[2]))

        cur.close()

    print("\n--- Fin diagnóstico (solo EXPLAIN, sin ANALYZE) ---\n")


if __name__ == "__main__":
    main()
