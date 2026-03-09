"""Verificar disponibilidad de unaccent y probar la normalización propuesta."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
from app.db.connection import _get_connection_params
import psycopg2

conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=10)
conn.autocommit = True
cur = conn.cursor()

# 1. Instalar unaccent
try:
    cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    print("unaccent: extension OK")
except Exception as e:
    print(f"unaccent: FAIL ({e})")
    conn.rollback()

# 2. Test unaccent
tests = ["Económico", "mensajería", "Exprés", "Envíos", "confort+", "tuk-tuk", "Taxi Moto", "tuk tuk"]
for v in tests:
    try:
        cur.execute("SELECT unaccent(%s)", (v,))
        r = cur.fetchone()[0]
        print(f"  unaccent({v!r:30s}) = {r!r}")
    except Exception as e:
        print(f"  unaccent({v!r}) FAIL: {e}")
        conn.rollback()

# 3. Test normalización propuesta completa
# lower(trim(regexp_replace(regexp_replace(unaccent(raw), '[+]', '_plus', 'g'), '[\s-]+', '_', 'g')))
# luego quitar caracteres fuera de [a-z0-9_]
sql = """
    SELECT
        raw_val,
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    LOWER(TRIM(unaccent(raw_val))),
                    '[+]', '_plus', 'g'
                ),
                '[\\s-]+', '_', 'g'
            ),
            '[^a-z0-9_]', '', 'g'
        ) AS normalized
    FROM unnest(ARRAY[
        'Económico', 'mensajería', 'Exprés', 'Envíos',
        'confort+', 'tuk-tuk', 'Taxi Moto', 'tuk tuk',
        'moto', 'Confort', 'cargo', 'express', 'Standard',
        'start', 'premier', 'minivan', 'xl',
        'focos led para auto, moto'
    ]) AS raw_val
"""
cur.execute(sql)
print("\n=== NORMALIZACIÓN PROPUESTA ===")
for r in cur.fetchall():
    print(f"  {r[0]!r:40s} -> {r[1]!r}")

cur.close()
conn.close()
