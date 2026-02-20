"""
Genera un CSV de plan realkey mínimo desde real_catalog_for_plan.csv
para poder ejecutar pasoA2/pasoA3 sin plan manual.
Uso: python scripts/build_plan_realkey_from_catalog.py [year] [month]
"""
import os
import sys
import csv
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
CATALOG = os.path.join(EXPORTS_DIR, "real_catalog_for_plan.csv")
OUTPUT = os.path.join(EXPORTS_DIR, "plan_realkey_from_catalog.csv")

HEADER = ["country", "city", "park_id", "real_tipo_servicio", "year", "month",
          "trips_plan", "active_drivers_plan", "avg_ticket_plan", "revenue_plan", "trips_per_driver_plan"]


def main():
    today = date.today()
    year = int(sys.argv[1]) if len(sys.argv) > 1 else today.year
    month = int(sys.argv[2]) if len(sys.argv) > 2 else today.month

    if not os.path.isfile(CATALOG):
        print(f"ERROR: No existe {CATALOG}. Ejecuta antes pasoA1_export_real_catalog_for_plan.py")
        sys.exit(1)

    rows = []
    with open(CATALOG, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            total = int(float(row.get("total_trips") or 0))
            # Plan mínimo: 10% del total o 100, para que haya datos
            trips_plan = max(100, total // 10) if total else 100
            rows.append({
                "country": row.get("country", ""),
                "city": row.get("city", ""),
                "park_id": row.get("park_id", ""),
                "real_tipo_servicio": row.get("real_tipo_servicio", ""),
                "year": year,
                "month": month,
                "trips_plan": trips_plan,
                "active_drivers_plan": 50,
                "avg_ticket_plan": 5.5,
                "revenue_plan": round(trips_plan * 5.5, 2),
                "trips_per_driver_plan": round(trips_plan / 50, 2),
            })

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)

    print(f"Generado: {OUTPUT} ({len(rows)} filas, year={year}, month={month})")
    return OUTPUT


if __name__ == "__main__":
    main()
