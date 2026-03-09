"""Diagnóstico LOB UNCLASSIFIED residual y normalización expres/express."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
from app.db.connection import _get_connection_params
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=15)
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

# 1. Service types que caen en LOB UNCLASSIFIED (desde fact table)
print("=== dimension_key de service_type cuyo LOB es UNCLASSIFIED ===")
cur.execute("""
    SELECT s.dimension_key AS service_type, SUM(s.trips) AS trips
    FROM ops.real_drill_dim_fact s
    WHERE s.breakdown = 'service_type'
      AND NOT EXISTS (
          SELECT 1 FROM canon.map_real_tipo_servicio_to_lob_group m
          WHERE m.real_tipo_servicio = s.dimension_key
      )
    GROUP BY s.dimension_key
    ORDER BY trips DESC
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  {r['service_type']!r:30s} trips={r['trips']}")

# 2. Mapping actual
print("\n=== Mapping LOB actual ===")
cur.execute("SELECT * FROM canon.map_real_tipo_servicio_to_lob_group ORDER BY real_tipo_servicio")
for r in cur.fetchall():
    print(f"  {r['real_tipo_servicio']:20s} -> {r['lob_group']}")

# 3. Test: expres vs express
print("\n=== Test normalización expres/express ===")
for v in ['Exprés', 'expres', 'express', 'Express']:
    cur.execute("SELECT ops.validated_service_type(%s) AS result", (v,))
    print(f"  {v!r:20s} -> {cur.fetchone()['result']}")

# 4. UNCLASSIFIED share actual en LOB
cur.execute("""
    SELECT
        SUM(CASE WHEN dimension_key='UNCLASSIFIED' THEN trips ELSE 0 END) AS uncl,
        SUM(trips) AS total,
        ROUND(100.0*SUM(CASE WHEN dimension_key='UNCLASSIFIED' THEN trips ELSE 0 END)/NULLIF(SUM(trips),0),2) AS pct
    FROM ops.real_drill_dim_fact WHERE breakdown='lob'
""")
r = cur.fetchone()
print(f"\n=== LOB UNCLASSIFIED share === {r['uncl']} / {r['total']} = {r['pct']}%")

cur.close(); conn.close()
