"""Validación rápida (sin vistas pesadas sobre trips)."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.db.connection import _get_connection_params
import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=10)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SET statement_timeout = '30000'")
    print("=== 1. alembic_version ===")
    cur.execute("SELECT * FROM alembic_version")
    for r in cur.fetchall(): print(dict(r))
    print("\n=== 2. Funciones ops ===")
    cur.execute("""
        SELECT n.nspname, p.proname FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'ops' AND p.proname IN ('normalized_service_type', 'validated_service_type')
    """)
    for r in cur.fetchall(): print(dict(r))
    print("\n=== 3. Vistas auditoría existen ===")
    cur.execute("""
        SELECT table_schema, table_name FROM information_schema.views
        WHERE table_schema = 'ops' AND table_name IN ('v_audit_service_type', 'v_audit_breakdown_sum')
    """)
    for r in cur.fetchall(): print(dict(r))
    print("\n=== 4. Top dimension_key service_type (real_drill_dim_fact) ===")
    cur.execute("""
        SELECT dimension_key, COUNT(*) AS n FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type' GROUP BY dimension_key ORDER BY n DESC LIMIT 20
    """)
    for r in cur.fetchall(): print(dict(r))
    print("\n=== 5. v_audit_breakdown_sum (solo inválidos) ===")
    try:
        cur.execute("SELECT * FROM ops.v_audit_breakdown_sum WHERE NOT breakdown_valid LIMIT 20")
        rows = cur.fetchall()
        for r in rows: print(dict(r))
        if not rows: print("(ninguna fila con breakdown_valid = false)")
    except Exception as e: print("ERROR:", e)
    print("\n=== 6. Muestra consistencia margen (lob pe) ===")
    cur.execute("""
        SELECT period_start, SUM(trips) AS viajes, SUM(margin_total) AS margen_total,
               CASE WHEN SUM(trips)>0 THEN SUM(margin_total)/SUM(trips) ELSE NULL END AS margen_trip_calc
        FROM ops.real_drill_dim_fact WHERE breakdown='lob' AND country='pe'
        GROUP BY period_start ORDER BY period_start DESC LIMIT 5
    """)
    for r in cur.fetchall(): print(dict(r))
    cur.close()
    conn.close()
    print("\n=== Listo ===")

if __name__ == "__main__":
    main()
