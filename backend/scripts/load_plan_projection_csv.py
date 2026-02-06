"""
Loader: CSV de proyección -> staging.plan_projection_raw.
- Detecta headers del CSV.
- Mapea a country, city, lob_name, period_date, trips_plan, revenue_plan.
- Guarda fila completa en raw_row (JSONB).
- Log: filas cargadas, fechas min/max, nulos por columna.

Uso: python load_plan_projection_csv.py <ruta_csv>
"""
import sys
import os
import csv
import json
import re
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

# Mapeo flexible: nombre header (lower, sin espacios) -> columna interna
HEADER_ALIASES = {
    "country": ["country", "pais", "país"],
    "city": ["city", "ciudad", "city_name"],
    "lob_name": ["lob_name", "lob", "line_of_business", "lineofbusiness", "lob_base", "tipo", "servicio"],
    "period_date": ["period_date", "period", "date", "fecha", "periodo", "year_month", "year-month"],
    "year": ["year", "ano", "año"],
    "month": ["month", "mes", "month_num"],
    "trips_plan": ["trips_plan", "trips", "viajes", "trips_plan"],
    "revenue_plan": ["revenue_plan", "revenue", "revenue_plan", "ingresos", "revenue_plan"],
}

def normalize_header(h):
    return re.sub(r"\s+", "_", h.strip().lower())

def detect_column_mapping(headers):
    """Devuelve dict: columna_interna -> índice en headers."""
    normalized = [normalize_header(h) for h in headers]
    mapping = {}
    for internal, aliases in HEADER_ALIASES.items():
        for i, n in enumerate(normalized):
            if n in aliases or n in [normalize_header(a) for a in aliases]:
                mapping[internal] = i
                break
    return mapping

def parse_period_date(val):
    """Convierte YYYY-MM o DD/MM/YYYY etc a date."""
    if not val:
        return None
    val = str(val).strip()
    # YYYY-MM
    m = re.match(r"(\d{4})-(\d{1,2})", val)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).date()
        except ValueError:
            return None
    # DD/MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", val)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
        except ValueError:
            return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return None

def load_csv_to_staging(csv_path: str):
    init_db_pool()
    if not os.path.exists(csv_path):
        print(f"[ERROR] Archivo no encontrado: {csv_path}")
        return

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            print("[ERROR] CSV sin cabecera")
            return
        mapping = detect_column_mapping(headers)
        missing = set(HEADER_ALIASES.keys()) - set(mapping.keys())
        if missing:
            print(f"[WARN] Columnas no detectadas (se rellenarán NULL): {missing}")
            print(f"  Headers leídos: {headers}")

        rows = list(reader)
        null_counts = defaultdict(int)
        period_dates = []
        inserted = 0

        with get_db() as conn:
            cur = conn.cursor()
            max_idx = max(mapping.values(), default=-1) if mapping else -1
            for row in rows:
                if mapping and len(row) <= max_idx:
                    continue
                country = row[mapping["country"]] if "country" in mapping else None
                city = row[mapping["city"]] if "city" in mapping else None
                lob_name = row[mapping["lob_name"]] if "lob_name" in mapping else None
                period_date = None
                if "period_date" in mapping:
                    period_date = parse_period_date(row[mapping["period_date"]])
                elif "year" in mapping and "month" in mapping:
                    try:
                        y = int(float(str(row[mapping["year"]]).strip()))
                        m = int(float(str(row[mapping["month"]]).strip()))
                        period_date = datetime(y, m, 1).date()
                    except (ValueError, TypeError):
                        period_date = None
                trips_plan = None
                if "trips_plan" in mapping and row[mapping["trips_plan"]]:
                    try:
                        trips_plan = float(str(row[mapping["trips_plan"]]).replace(",", "."))
                    except ValueError:
                        pass
                revenue_plan = None
                if "revenue_plan" in mapping and row[mapping["revenue_plan"]]:
                    try:
                        revenue_plan = float(str(row[mapping["revenue_plan"]]).replace(",", "."))
                    except ValueError:
                        pass

                for k, v in [("country", country), ("city", city), ("lob_name", lob_name),
                              ("period_date", period_date), ("trips_plan", trips_plan), ("revenue_plan", revenue_plan)]:
                    if v is None or (isinstance(v, str) and not v.strip()):
                        null_counts[k] += 1

                if period_date:
                    period_dates.append(period_date)

                raw_row = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
                raw_row_json = json.dumps(raw_row, default=str)

                try:
                    cur.execute("""
                        INSERT INTO staging.plan_projection_raw
                        (country, city, lob_name, period_date, trips_plan, revenue_plan, raw_row)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """, (country or None, city or None, lob_name or None, period_date, trips_plan, revenue_plan, raw_row_json))
                    inserted += cur.rowcount
                except Exception as e:
                    print(f"[ERROR] Fila: {e}")
            conn.commit()
            cur.close()

        print(f"[OK] Filas cargadas: {inserted}")
        print(f"  Fechas period_date: min={min(period_dates) if period_dates else 'N/A'}, max={max(period_dates) if period_dates else 'N/A'}")
        print("  Nulos por columna:", dict(null_counts))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python load_plan_projection_csv.py <ruta_csv>")
        sys.exit(1)
    load_csv_to_staging(sys.argv[1])
