"""
[YEGO CT] E2E PASO A.1 — Exportar catálogo real para armar plan en Excel.
Genera backend/exports/real_catalog_for_plan.csv con filas únicas por
(country, city, park_id, park_name, real_tipo_servicio) + total_trips, last_seen_date.
"""
import sys
import os
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
OUTPUT_FILE = "real_catalog_for_plan.csv"


def main():
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    path = os.path.join(EXPORTS_DIR, OUTPUT_FILE)

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '600s'")
            cur.execute("""
                SELECT
                    country,
                    city,
                    park_id,
                    park_name,
                    real_tipo_servicio,
                    SUM(real_trips) AS total_trips,
                    MAX(last_seen_date) AS last_seen_date
                FROM ops.v_real_universe_by_park_for_hunt
                GROUP BY country, city, park_id, park_name, real_tipo_servicio
                ORDER BY total_trips DESC NULLS LAST
            """)
            rows = cur.fetchall()
        finally:
            cur.close()

    headers = ["country", "city", "park_id", "park_name", "real_tipo_servicio", "total_trips", "last_seen_date"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        w.writerow(headers)
        w.writerows(rows)

    print("=== PASO A.1 — Export catálogo real para plan ===\n")
    print(f"  Exportado: {path}")
    print(f"  Filas:     {len(rows)}")
    if rows:
        print(f"  Top 5 por total_trips:")
        for r in rows[:5]:
            print(f"    {r[0]} | {r[1]} | {r[2][:20] if r[2] else ''}... | {r[4][:25] if r[4] else ''} | {r[5]} | {r[6]}")
    print("\n  Comando siguiente (tras armar CSV de plan con esa llave):")
    print('  python scripts/pasoA2_load_plan_realkey.py --csv "C:\\ruta\\plan_realkey.csv"')
    print("=" * 60)


if __name__ == "__main__":
    main()
