#!/usr/bin/env python3
"""Solo consulta B: top validated_service_type en LOB UNCLASSIFIED (ventana 90 días). Timeout 60s."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()
OUTPUT_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docs", "real_lob_gap_query_b.json")
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SET statement_timeout = '60000'")
    try:
        cur.execute("""
            SELECT real_tipo_servicio_norm AS validated_service_type, COUNT(*)::bigint AS trips
            FROM ops.v_real_trips_with_lob_v2
            WHERE lob_group = 'UNCLASSIFIED' AND fecha_inicio_viaje::date >= (current_date - 90)
            GROUP BY real_tipo_servicio_norm
            ORDER BY trips DESC
            LIMIT 200
        """)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        rows = []
        print("Error:", e)
    cur.close()

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump({"query": "B", "rows": rows}, f, indent=2, ensure_ascii=False)
print("Rows:", len(rows))
for r in rows[:20]:
    print(r)
