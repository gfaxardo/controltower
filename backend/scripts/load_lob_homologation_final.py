"""
PASO 4 E2E — Carga CSV mapeado en ops.lob_homologation_final.
TRUNCATE + insert. Claves normalizadas (lower/trim). plan_lob_name vacío → UNMAPPED. confidence vacío → low.
Encoding: utf-8-sig con fallback cp1252.
"""
import sys
import os
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
CSV_PATH = os.path.join(EXPORTS_DIR, "lob_homologation_template.csv")


def _open_csv(path: str):
    try:
        return open(path, "r", newline="", encoding="utf-8-sig")
    except UnicodeDecodeError:
        return open(path, "r", newline="", encoding="cp1252")


def load():
    init_db_pool()
    if not os.path.isfile(CSV_PATH):
        print(f"ERROR: CSV no encontrado: {CSV_PATH}")
        return 0

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '120s'")
            cur.execute("TRUNCATE ops.lob_homologation_final")

            with _open_csv(CSV_PATH) as f:
                first = f.readline()
                f.seek(0)
                delim = ";" if ";" in first and first.count(";") >= first.count(",") else ","
                reader = csv.DictReader(f, delimiter=delim)
                fieldnames = [c.strip().replace("\ufeff", "") for c in (reader.fieldnames or [])]
                if "country" not in fieldnames or "city" not in fieldnames or "park_id" not in fieldnames or "real_tipo_servicio" not in fieldnames:
                    print("ERROR: CSV debe tener columnas country, city, park_id, real_tipo_servicio")
                    return 0

                count = 0
                for row in reader:
                    row_norm = {k.strip().replace("\ufeff", ""): v for k, v in row.items()}
                    # Claves normalizadas para join con vista real (city_key, country_key)
                    country = (row_norm.get("country") or "").strip().lower() or ""
                    city = (row_norm.get("city") or "").strip().lower() or ""
                    park_id = (row_norm.get("park_id") or "").strip()
                    park_name = (row_norm.get("park_name") or "").strip() or None
                    real_tipo_servicio = (row_norm.get("real_tipo_servicio") or "").strip().lower()
                    plan_lob_raw = (row_norm.get("plan_lob_name") or "").strip()
                    plan_lob_name = (plan_lob_raw.strip().lower() if plan_lob_raw else "UNMAPPED")
                    confidence = (row_norm.get("confidence") or "").strip() or "low"
                    notes = (row_norm.get("notes") or "").strip() or None

                    if not park_id or not real_tipo_servicio:
                        continue

                    cur.execute(
                        """
                        INSERT INTO ops.lob_homologation_final
                        (country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (country, city, park_id, real_tipo_servicio) DO UPDATE SET
                            park_name = EXCLUDED.park_name,
                            plan_lob_name = EXCLUDED.plan_lob_name,
                            confidence = EXCLUDED.confidence,
                            notes = EXCLUDED.notes
                        """,
                        (country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes),
                    )
                    count += 1

            conn.commit()
            print(f"Total filas insertadas en ops.lob_homologation_final: {count}")
            return count
        finally:
            cur.close()


if __name__ == "__main__":
    load()
