"""
Genera backend/exports/lob_homologation_template.csv con columnas:
  country, city, real_tipo_servicio, plan_lob_name, confidence, notes
Precarga country/city/real_tipo_servicio desde real_tiposerv_export.csv
(top 200 por ciudad por real_trips), dejando plan_lob_name/confidence/notes vacíos.
"""

import os
import csv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
REAL_FILE = os.path.join(EXPORTS_DIR, "real_tiposerv_export.csv")
OUT_FILE = os.path.join(EXPORTS_DIR, "lob_homologation_template.csv")
TOP_PER_CITY = 200
OUT_HEADERS = ["country", "city", "real_tipo_servicio", "plan_lob_name", "confidence", "notes"]


def main():
    if not os.path.isfile(REAL_FILE):
        print(f"AVISO: No existe {REAL_FILE}. Ejecuta antes: python scripts/export_lob_hunt_lists.py")
        with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=",")
            w.writerow(OUT_HEADERS)
        print(f"Creado {OUT_FILE} vacío (solo cabecera).")
        return

    rows_by_city = {}
    with open(REAL_FILE, "r", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter=",")
        for row in r:
            country = (row.get("country") or "").strip()
            city = (row.get("city") or "").strip()
            real_tipo = (row.get("real_tipo_servicio") or "").strip()
            try:
                trips = int(float(row.get("real_trips") or 0))
            except (ValueError, TypeError):
                trips = 0
            key = (country, city)
            if key not in rows_by_city:
                rows_by_city[key] = []
            rows_by_city[key].append((trips, real_tipo))

    # Top TOP_PER_CITY por ciudad (ordenado por real_trips desc)
    out_rows = []
    for (country, city), list_rows in sorted(rows_by_city.items()):
        list_rows.sort(key=lambda x: -x[0])
        for trips, real_tipo in list_rows[:TOP_PER_CITY]:
            out_rows.append((country, city, real_tipo, "", "", ""))

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(OUT_HEADERS)
        w.writerows(out_rows)

    print(f"Generado {OUT_FILE}: {len(out_rows)} filas (top {TOP_PER_CITY} por ciudad).")


if __name__ == "__main__":
    main()
