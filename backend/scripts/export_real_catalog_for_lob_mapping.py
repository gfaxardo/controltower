#!/usr/bin/env python3
"""
Exporta combinaciones (country, city, park_id, real_tipo_servicio) que aún NO tienen
mapeo en canon.map_real_to_lob. Sirve para mantener el mapping de REAL LOB Observability.
Salida: backend/exports/real_catalog_for_lob_mapping.csv
Columnas: country, city, park_id, park_name, real_tipo_servicio, lob_id, notes
(lob_id y notes se dejan vacíos para rellenar; lob_id debe ser PK de canon.dim_lob).
"""
import os
import sys
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

from app.db.connection import get_db, init_db_pool

OUTPUT_FILE = "real_catalog_for_lob_mapping.csv"
HEADERS = ["country", "city", "park_id", "park_name", "real_tipo_servicio", "lob_id", "notes"]


def main():
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    out_path = os.path.join(EXPORTS_DIR, OUTPUT_FILE)
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '300000'")  # 5 min para vistas pesadas
        # Vistas requeridas (migración 041)
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'canon' AND table_name = 'map_real_to_lob'
        """)
        if cur.fetchone() is None:
            print("ERROR: canon.map_real_to_lob no existe. Ejecutar migración 041_real_lob_observability.")
            sys.exit(1)
        cur.execute("""
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'ops' AND table_name = 'v_real_universe_by_park_realkey'
        """)
        if cur.fetchone() is None:
            print("ERROR: ops.v_real_universe_by_park_realkey no existe. Ejecutar migraciones previas.")
            sys.exit(1)
        # Distinct real keys sin mapeo vigente
        cur.execute("""
            WITH real_keys AS (
                SELECT DISTINCT country, city, park_id, park_name, real_tipo_servicio
                FROM ops.v_real_universe_by_park_realkey
            ),
            mapped AS (
                SELECT country, city, park_id, real_tipo_servicio
                FROM canon.map_real_to_lob
                WHERE valid_to IS NULL
            )
            SELECT r.country, r.city, r.park_id, r.park_name, r.real_tipo_servicio
            FROM real_keys r
            LEFT JOIN mapped m
                ON LOWER(TRIM(r.country)) = LOWER(TRIM(m.country))
               AND LOWER(TRIM(r.city)) = LOWER(TRIM(m.city))
               AND TRIM(r.park_id) = TRIM(m.park_id)
               AND LOWER(TRIM(r.real_tipo_servicio)) = LOWER(TRIM(m.real_tipo_servicio))
            WHERE m.park_id IS NULL
            ORDER BY r.country, r.city, r.park_id, r.real_tipo_servicio
        """)
        rows = cur.fetchall()
        cur.close()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], "", ""])
    print(f"Exportados {len(rows)} combos sin mapeo a {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
