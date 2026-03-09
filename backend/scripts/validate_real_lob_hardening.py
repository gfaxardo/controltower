"""
Validación post-migración 070 y backfill Real LOB.
Ejecuta las comprobaciones SQL definidas en el hardening y escribe resultados a stdout.
Uso: python -m scripts.validate_real_lob_hardening
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def get_cur():
    from app.db.connection import _get_connection_params
    import psycopg2
    from psycopg2.extras import RealDictCursor
    params = dict(_get_connection_params())
    conn = psycopg2.connect(**params, connect_timeout=10)
    conn.autocommit = True
    return conn.cursor(cursor_factory=RealDictCursor), conn


def run(name, sql, cur, max_rows=50):
    print(f"\n=== {name} ===\n")
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        for i, r in enumerate(rows):
            if i >= max_rows:
                print(f"... ({len(rows)} filas total, mostrando {max_rows})")
                break
            print(dict(r))
    except Exception as e:
        print(f"ERROR: {e}")
    print()


def main():
    cur, conn = get_cur()
    try:
        run("1. alembic_version", "SELECT * FROM alembic_version", cur, 5)
        run(
            "2. Funciones ops (normalized_service_type, validated_service_type)",
            """
            SELECT n.nspname, p.proname
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'ops'
              AND p.proname IN ('normalized_service_type', 'validated_service_type')
            """,
            cur,
        )
        run(
            "3. Auditoría service_type (v_audit_service_type) — top 50",
            "SELECT * FROM ops.v_audit_service_type LIMIT 50",
            cur,
        )
        run(
            "4. Auditoría breakdown: filas donde NO breakdown_valid",
            "SELECT * FROM ops.v_audit_breakdown_sum WHERE NOT breakdown_valid LIMIT 50",
            cur,
        )
        run(
            "5. Top service types (dimension_key) en real_drill_dim_fact",
            """
            SELECT dimension_key, COUNT(*) AS n
            FROM ops.real_drill_dim_fact
            WHERE breakdown = 'service_type'
            GROUP BY dimension_key
            ORDER BY n DESC
            LIMIT 30
            """,
            cur,
        )
        run(
            "6. unknown / UNCLASSIFIED / LOW_VOLUME",
            """
            SELECT dimension_key, COUNT(*) AS n
            FROM ops.real_drill_dim_fact
            WHERE breakdown = 'service_type'
              AND dimension_key IN ('unknown', 'UNCLASSIFIED', 'LOW_VOLUME')
            GROUP BY dimension_key
            ORDER BY n DESC
            """,
            cur,
        )
        # Validación matemática: margen_trip vs margen_total/viajes
        run(
            "7. Consistencia margen_trip (muestra: agregado por periodo)",
            """
            SELECT period_start, SUM(trips) AS viajes, SUM(margin_total) AS margen_total,
                   CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip_calc
            FROM ops.real_drill_dim_fact
            WHERE breakdown = 'lob' AND country = 'pe'
            GROUP BY period_start
            ORDER BY period_start DESC
            LIMIT 10
            """,
            cur,
        )
    finally:
        cur.close()
        conn.close()
    print("\n=== Validación finalizada ===\n")


if __name__ == "__main__":
    main()
    sys.exit(0)
