"""Agregar mapping mensajeria -> delivery (sin tilde) en LOB."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
from app.db.connection import _get_connection_params
import psycopg2

conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=10)
conn.autocommit = True
cur = conn.cursor()
cur.execute("""
    INSERT INTO canon.map_real_tipo_servicio_to_lob_group (real_tipo_servicio, lob_group)
    VALUES ('mensajeria', 'delivery')
    ON CONFLICT (real_tipo_servicio) DO UPDATE SET lob_group = EXCLUDED.lob_group
""")
print(f"Inserted/updated mensajeria -> delivery: {cur.rowcount}")
# Verify
cur.execute("SELECT * FROM canon.map_real_tipo_servicio_to_lob_group ORDER BY real_tipo_servicio")
for r in cur.fetchall():
    print(f"  {r[0]:20s} -> {r[1]}")
cur.close()
conn.close()
