"""
Backfill de campos comerciales en public.trips_2026 desde un CSV.
Para usar cuando el equipo externo proporcione un export corregido con
comision_empresa_asociada y pago_corporativo desde 2026-02-16.

El CSV debe tener al menos: id, comision_empresa_asociada, pago_corporativo
(opcional: fecha_inicio_viaje para filtrar solo ventana rota).

Uso:
  cd backend && python -m scripts.backfill_trips_2026_commercial_from_csv --csv /ruta/al/export.csv --dry-run
  cd backend && python -m scripts.backfill_trips_2026_commercial_from_csv --csv /ruta/al/export.csv

Opciones:
  --csv       Ruta al CSV (separador coma, cabecera con id, comision_empresa_asociada, pago_corporativo)
  --dry-run   Solo contar cuántas filas matchearían; no escribir en DB
  --min-date  Fecha mínima de viaje a considerar (default 2026-02-16)
  --delimiter Separador (default ,)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

DEFAULT_MIN_DATE = date(2026, 2, 16)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill trips_2026 comision/pago_corporativo desde CSV")
    parser.add_argument("--csv", required=True, help="Ruta al archivo CSV")
    parser.add_argument("--dry-run", action="store_true", help="No escribir en DB")
    parser.add_argument("--min-date", type=str, default="2026-02-16", help="Fecha mínima viaje (YYYY-MM-DD)")
    parser.add_argument("--delimiter", type=str, default=",", help="Separador CSV")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        print(f"ERROR: Archivo no encontrado: {csv_path}", file=sys.stderr)
        return 1
    min_date = args.min_date

    rows_to_apply = []
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        if not reader.fieldnames:
            print("ERROR: CSV sin cabecera", file=sys.stderr)
            return 1
        fieldnames = [x.strip().lower() for x in reader.fieldnames]
        if "id" not in fieldnames:
            print("ERROR: CSV debe tener columna 'id'", file=sys.stderr)
            return 1
        if "comision_empresa_asociada" not in fieldnames and "comision_empresa_asociada" not in reader.fieldnames:
            # allow original case
            if not any("comision" in fn.lower() for fn in reader.fieldnames):
                print("ERROR: CSV debe tener columna comision_empresa_asociada (o similar)", file=sys.stderr)
                return 1
        for row in reader:
            raw = dict(row)
            id_val = raw.get("id") or raw.get("ID")
            if not id_val:
                continue
            comision = raw.get("comision_empresa_asociada") or raw.get("Comision_empresa_asociada") or raw.get("comision")
            pago = raw.get("pago_corporativo") or raw.get("Pago_corporativo") or raw.get("pago_corp")
            fecha = raw.get("fecha_inicio_viaje") or raw.get("fecha_inicio")
            if fecha and str(fecha)[:10] < min_date:
                continue
            rows_to_apply.append((id_val.strip(), comision, pago))

    if not rows_to_apply:
        print("No hay filas para aplicar (revisar CSV y --min-date).")
        return 0

    print(f"Filas a aplicar: {len(rows_to_apply)} (min_date={min_date})")
    if args.dry_run:
        print("DRY-RUN: no se escribe en DB.")
        return 0

    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    updated = 0
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '300000'")
        for id_val, comision, pago in rows_to_apply:
            try:
                if comision is not None and str(comision).strip() != "":
                    try:
                        comision_num = float(str(comision).replace(",", "."))
                    except ValueError:
                        comision_num = None
                else:
                    comision_num = None
                if pago is not None and str(pago).strip() != "":
                    try:
                        pago_num = float(str(pago).replace(",", "."))
                    except ValueError:
                        pago_num = None
                else:
                    pago_num = None
                cur.execute(
                    """
                    UPDATE public.trips_2026
                    SET comision_empresa_asociada = COALESCE(%s, comision_empresa_asociada),
                        pago_corporativo = COALESCE(%s, pago_corporativo)
                    WHERE id::text = %s
                      AND fecha_inicio_viaje >= %s::date
                    """,
                    (comision_num, pago_num, str(id_val), min_date),
                )
                updated += cur.rowcount
            except Exception as e:
                print(f"Warning: id={id_val} error: {e}", file=sys.stderr)
        conn.commit()
        cur.close()
    print(f"Filas actualizadas en trips_2026: {updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
