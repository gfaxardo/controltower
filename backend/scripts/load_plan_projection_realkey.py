"""
Loader: CSV plan por llave real -> staging.plan_projection_realkey_raw.
Header esperado (delimitador coma):
  country,city,park_id,real_tipo_servicio,year,month,trips_plan,active_drivers_plan,avg_ticket_plan,revenue_plan,trips_per_driver_plan
- period_date = make_date(year, month, 1)
- country/city: lower(trim)
- park_id: texto (varchar)
- real_tipo_servicio: lower(trim) + fix_mojibake (latin1->utf8)

Uso: python load_plan_projection_realkey.py <ruta_csv>
"""
import sys
import os
import csv
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

REQUIRED_HEADERS = [
    "country", "city", "park_id", "real_tipo_servicio",
    "year", "month", "trips_plan", "active_drivers_plan", "avg_ticket_plan",
    "revenue_plan", "trips_per_driver_plan",
]


def fix_mojibake(s: str) -> str:
    """Reparar mojibake UTF-8 leído como Latin-1 (econÃ³mico -> económico)."""
    if not s or "\u00c3" not in s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _open_csv(path: str):
    try:
        return open(path, "r", newline="", encoding="utf-8-sig")
    except UnicodeDecodeError:
        return open(path, "r", newline="", encoding="cp1252")


def _norm(s: str) -> str:
    if s is None:
        return ""
    return str(s).strip()


def load(csv_path: str) -> int:
    init_db_pool()
    if not os.path.exists(csv_path):
        print(f"[ERROR] Archivo no encontrado: {csv_path}")
        return 0

    with _open_csv(csv_path) as f:
        reader = csv.DictReader(f, delimiter=",")
        fieldnames = [c.strip().replace("\ufeff", "") for c in (reader.fieldnames or [])]
        for h in REQUIRED_HEADERS:
            if h not in fieldnames:
                print(f"[ERROR] CSV debe tener columna: {h}. Headers: {fieldnames}")
                return 0

        inserted = 0
        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SET statement_timeout = '300s'")
                for row in reader:
                    row = {k.strip().replace("\ufeff", ""): v for k, v in row.items()}
                    country = _norm(row.get("country") or "").lower() or None
                    city = _norm(row.get("city") or "").lower() or None
                    park_id = _norm(row.get("park_id") or "")
                    if not park_id:
                        continue
                    real_ts = _norm(row.get("real_tipo_servicio") or "").lower()
                    real_ts = fix_mojibake(real_ts) or real_ts
                    try:
                        y = int(float(str(row.get("year") or "0").strip()))
                        m = int(float(str(row.get("month") or "0").strip()))
                    except (ValueError, TypeError):
                        continue
                    if y < 2000 or y > 2100 or m < 1 or m > 12:
                        continue
                    period_date = date(y, m, 1)

                    def _num(key, default=None):
                        v = row.get(key)
                        if v is None or _norm(v) == "":
                            return default
                        try:
                            return float(str(v).replace(",", "."))
                        except ValueError:
                            return default

                    trips_plan = _num("trips_plan")
                    active_drivers_plan = _num("active_drivers_plan")
                    avg_ticket_plan = _num("avg_ticket_plan")
                    revenue_plan = _num("revenue_plan")
                    trips_per_driver_plan = _num("trips_per_driver_plan")

                    cur.execute("""
                        INSERT INTO staging.plan_projection_realkey_raw
                        (country, city, park_id, real_tipo_servicio, year, month, period_date,
                         trips_plan, active_drivers_plan, avg_ticket_plan, revenue_plan, trips_per_driver_plan)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        country, city, park_id, real_ts or None, y, m, period_date,
                        trips_plan, active_drivers_plan, avg_ticket_plan, revenue_plan, trips_per_driver_plan
                    ))
                    inserted += cur.rowcount
                conn.commit()
                print(f"[OK] Filas insertadas en staging.plan_projection_realkey_raw: {inserted}")
                return inserted
            finally:
                cur.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python load_plan_projection_realkey.py <ruta_csv>")
        sys.exit(1)
    n = load(sys.argv[1])
    sys.exit(0 if n >= 0 else 1)
