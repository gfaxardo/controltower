"""
Carga homologación LOB desde CSV (llave: country, city, park_id, real_tipo_servicio).
Upsert idempotente. Filas sin plan_lob_name o confidence → confidence='unmapped', notes '[UNMAPPED]'.
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

CSV_CANDIDATES = [
    os.path.join(EXPORTS_DIR, "lob_homologation_filled.csv"),
    os.path.join(EXPORTS_DIR, "lob_homologation_template_filled.csv"),
    os.path.join(EXPORTS_DIR, "lob_homologation_template.csv"),
]


def detect_csv_path():
    for path in CSV_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _norm_park_id(s: str) -> str:
    v = (s or "").strip()
    if len(v) > 32:
        return v[:32]
    return v


def load_lob_homologation_csv(csv_path: str, dry_run: bool = False):
    init_db_pool()
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    required_key = ["country", "city", "park_id", "real_tipo_servicio"]
    filas_leidas = 0
    filas_validas = 0
    filas_invalidas = 0
    inserts = 0
    updates = 0
    unmapped_count = 0

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '300s'")
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                first_line = f.readline()
                f.seek(0)
                delimiter = ";" if ";" in first_line and first_line.count(";") >= first_line.count(",") else ","
                reader = csv.DictReader(f, delimiter=delimiter)
                if not reader.fieldnames:
                    raise ValueError("CSV sin columnas")
                fieldnames_norm = [c.strip().replace("\ufeff", "") for c in reader.fieldnames]
                missing = [c for c in required_key if c not in fieldnames_norm]
                if missing:
                    raise ValueError(f"CSV faltan columnas de llave: {missing}")

                for row_num, row in enumerate(reader, start=2):
                    filas_leidas += 1
                    row_norm = {k.strip().replace("\ufeff", ""): v for k, v in row.items()}
                    country = _norm(row_norm.get("country") or "")
                    city = _norm(row_norm.get("city") or "")
                    park_id = _norm_park_id(row_norm.get("park_id") or "")
                    real_tipo_servicio = _norm(row_norm.get("real_tipo_servicio") or "")
                    plan_lob_name_raw = (row_norm.get("plan_lob_name") or "").strip().lower()
                    plan_lob_name = plan_lob_name_raw if plan_lob_name_raw else None
                    confidence_raw = _norm(row_norm.get("confidence") or "")
                    notes_raw = (row_norm.get("notes") or "").strip()

                    if not park_id or not real_tipo_servicio:
                        filas_invalidas += 1
                        continue
                    # country/city pueden ser '' (heredan de contexto)

                    filas_validas += 1

                    if not plan_lob_name or not confidence_raw or confidence_raw == "unmapped":
                        confidence = "unmapped"
                        notes = (notes_raw + " [UNMAPPED]" if notes_raw else "[UNMAPPED]")
                        unmapped_count += 1
                    else:
                        confidence = confidence_raw if confidence_raw in ("high", "medium", "low") else "medium"
                        notes = notes_raw or None

                    if dry_run:
                        continue

                    cur.execute(
                        """
                        INSERT INTO ops.lob_homologation (
                            country, city, park_id, real_tipo_servicio, plan_lob_name, confidence, notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (country, city, park_id, real_tipo_servicio)
                        DO UPDATE SET
                            plan_lob_name = EXCLUDED.plan_lob_name,
                            confidence = EXCLUDED.confidence,
                            notes = EXCLUDED.notes,
                            updated_at = now()
                        """,
                        (country, city, park_id, real_tipo_servicio, plan_lob_name, confidence, notes),
                    )
                    if cur.rowcount == 1:
                        inserts += 1
                    else:
                        updates += 1

            if not dry_run:
                conn.commit()
        finally:
            cur.close()

    print(f"filas_leidas={filas_leidas} filas_validas={filas_validas} filas_invalidas={filas_invalidas} inserts={inserts} updates={updates} unmapped_count={unmapped_count}")
    return {
        "filas_leidas": filas_leidas,
        "filas_validas": filas_validas,
        "filas_invalidas": filas_invalidas,
        "inserts": inserts,
        "updates": updates,
        "unmapped_count": unmapped_count,
    }


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
    if not csv_path:
        csv_path = detect_csv_path()
        if not csv_path:
            print("ERROR: No se encontró CSV. Rutas esperadas:")
            for p in CSV_CANDIDATES:
                print(f"  - {p}")
            sys.exit(1)
    dry_run = "--dry-run" in sys.argv
    print(f"CSV: {csv_path}" + (" (dry-run)" if dry_run else ""))
    load_lob_homologation_csv(csv_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
