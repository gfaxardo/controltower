"""
Carga homologación LOB desde CSV (template con park_id/park_name).

USO:
    python load_lob_homologation_csv.py [csv_path]

CSV: country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes
- park_id: si viene vacío se inserta NULL.
- park_name: solo informativo, no se guarda en ops.lob_homologation.

Por defecto usa: backend/exports/lob_homologation_template.csv
"""

import sys
import os
import io
import csv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
DEFAULT_CSV = os.path.join(EXPORTS_DIR, "lob_homologation_template.csv")


def load_lob_homologation_csv(csv_path: str, dry_run: bool = False):
    init_db_pool()

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    required = ["country", "city", "real_tipo_servicio", "plan_lob_name"]
    optional = ["park_id", "park_name", "confidence", "notes"]

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            loaded = 0
            skipped = 0
            errors = []

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError("CSV sin columnas")
                missing = [c for c in required if c not in reader.fieldnames]
                if missing:
                    raise ValueError(f"CSV faltan columnas obligatorias: {missing}")

                for row_num, row in enumerate(reader, start=2):
                    try:
                        country = (row.get("country") or "").strip() or None
                        city = (row.get("city") or "").strip() or None
                        park_id_raw = (row.get("park_id") or "").strip()
                        park_id = park_id_raw if park_id_raw else None
                        # park_name no se guarda
                        real_tipo_servicio = (row.get("real_tipo_servicio") or "").strip()
                        plan_lob_name = (row.get("plan_lob_name") or "").strip()
                        confidence_raw = (row.get("confidence") or "").strip()
                        confidence = confidence_raw if confidence_raw in ("high", "medium", "low") else "medium"
                        notes = (row.get("notes") or "").strip() or None

                        if not real_tipo_servicio or not plan_lob_name:
                            skipped += 1
                            continue

                        if dry_run:
                            loaded += 1
                            continue

                        cursor.execute(
                            """
                            INSERT INTO ops.lob_homologation (
                                country, city, park_id, real_tipo_servicio, plan_lob_name, confidence, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (country, city, park_id, real_tipo_servicio, plan_lob_name)
                            DO UPDATE SET
                                confidence = EXCLUDED.confidence,
                                notes = EXCLUDED.notes
                            """,
                            (country, city, park_id, real_tipo_servicio, plan_lob_name, confidence, notes),
                        )
                        loaded += 1
                    except Exception as e:
                        errors.append(f"Fila {row_num}: {e}")

            if not dry_run:
                conn.commit()
            print(f"Filas procesadas: {loaded}, omitidas (sin real/plan_lob): {skipped}")
            if errors:
                for e in errors[:20]:
                    print(f"  [ERROR] {e}")
                if len(errors) > 20:
                    print(f"  ... y {len(errors) - 20} más")
        finally:
            cursor.close()


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    dry_run = "--dry-run" in sys.argv
    if dry_run and csv_path == "--dry-run":
        csv_path = DEFAULT_CSV
    print(f"CSV: {csv_path}" + (" (dry-run)" if dry_run else ""))
    load_lob_homologation_csv(csv_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
