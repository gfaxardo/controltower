"""Test validated_service_type() post-migración 072."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
from app.db.connection import _get_connection_params
import psycopg2

conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=10)
conn.autocommit = True
cur = conn.cursor()

tests = [
    ('Económico', 'economico'),
    ('mensajería', 'mensajeria'),
    ('confort+', 'confort_plus'),
    ('tuk-tuk', 'tuk_tuk'),
    ('tuk tuk', 'tuk_tuk'),
    ('Taxi Moto', 'taxi_moto'),
    ('Exprés', 'expres'),
    ('Envíos', 'envios'),
    ('moto', 'moto'),
    ('cargo', 'cargo'),
    ('express', 'express'),
    ('Confort', 'confort'),
    ('Standard', 'standard'),
    ('premier', 'premier'),
    ('xl', 'xl'),
    ('start', 'start'),
    ('minivan', 'minivan'),
    ('focos led para auto, moto', 'UNCLASSIFIED'),  # coma → UNCLASSIFIED
    ('servicio especial para reparto urbano', 'UNCLASSIFIED'),  # >3 palabras
    ('', 'UNCLASSIFIED'),
    (None, 'UNCLASSIFIED'),
]
print(f"{'Input':<45s} {'Expected':<25s} {'Got':<25s} {'OK?'}")
print("-" * 100)
all_ok = True
for raw, expected in tests:
    cur.execute("SELECT ops.validated_service_type(%s)", (raw,))
    got = cur.fetchone()[0]
    ok = got == expected
    if not ok:
        all_ok = False
    print(f"  {str(raw)!r:<43s} {expected:<25s} {got:<25s} {'OK' if ok else 'FAIL !!!'}")

cur.close()
conn.close()
print(f"\n{'ALL TESTS PASSED' if all_ok else 'SOME TESTS FAILED'}")
