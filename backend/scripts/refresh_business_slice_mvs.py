#!/usr/bin/env python3
"""
Carga incremental BUSINESS_SLICE (ops.real_business_slice_month_fact y opcional hour_fact).

Ya no ejecuta REFRESH MATERIALIZED VIEW (la “MV” mensual es vista sobre la tabla fact).

Requisito: migración 116_business_slice_incremental_facts aplicada:
  cd backend && alembic upgrade head

En PowerShell, escriba el comando en **una sola línea**; si aparece el prompt ``>>``, está en continuación
de línea (Ctrl+C y reintente).

Si aparece "No space left on device" en base/pgsql_tmp: liberar disco en el **host donde corre PostgreSQL**
(no en la carpeta del proyecto). Opcional: más RAM para sorts en sesión, p. ej.
  $env:BUSINESS_SLICE_LOAD_WORK_MEM='512MB'   # PowerShell
  export BUSINESS_SLICE_LOAD_WORK_MEM=512MB  # bash
(0 u off desactiva el ajuste.)

Uso:
  cd backend && python -m scripts.refresh_business_slice_mvs
  python -m scripts.refresh_business_slice_mvs --month 2025-03
  python -m scripts.refresh_business_slice_mvs --month 2025-03-15
  python -m scripts.refresh_business_slice_mvs --backfill-from 2023-01 --backfill-to 2025-12
  python -m scripts.refresh_business_slice_mvs --hour-from "2025-03-01 00:00:00" --hour-to "2025-03-08 00:00:00"
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2.errors

from app.db.connection import get_db_audit
from app.services.business_slice_incremental_load import (
    backfill_business_slice_months,
    load_business_slice_hour_block,
    load_business_slice_month,
    month_first_day,
)

_LOAD_TIMEOUT_MS = 7_200_000


def _require_business_slice_facts(cur) -> None:
    cur.execute("SELECT to_regclass(%s)", ("ops.real_business_slice_month_fact",))
    if cur.fetchone()[0] is None:
        raise RuntimeError(
            "No existe ops.real_business_slice_month_fact. Aplique migraciones desde backend: "
            "alembic upgrade head  (revisión 116_business_slice_incremental_facts)."
        )


def _parse_month(s: str) -> date:
    """Acepta YYYY-MM o YYYY-MM-DD (se usa el mes civil de esa fecha)."""
    s = s.strip()
    if len(s) == 7 and s[4] == "-":
        y, m = int(s[:4]), int(s[5:7])
        return month_first_day(y, m)
    try:
        d = date.fromisoformat(s[:10])
        return month_first_day(d.year, d.month)
    except ValueError:
        pass
    raise ValueError("Use YYYY-MM or YYYY-MM-DD")


def _parse_ym(s: str) -> date:
    s = s.strip()
    if len(s) == 7 and s[4] == "-":
        return _parse_month(s)
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return date.fromisoformat(s[:10])
    raise ValueError("Use YYYY-MM or YYYY-MM-DD")


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga incremental business_slice (month_fact / hour_fact)")
    ap.add_argument(
        "--month",
        help="Mes objetivo: YYYY-MM o YYYY-MM-DD (se recalcula todo el mes civil)",
    )
    ap.add_argument("--backfill-from", help="Inicio rango mensual YYYY-MM")
    ap.add_argument("--backfill-to", help="Fin rango mensual YYYY-MM")
    ap.add_argument(
        "--hour-from",
        help="Inicio bloque horario (timestamp, ej. 2025-03-01 00:00:00)",
    )
    ap.add_argument(
        "--hour-to",
        help="Fin exclusivo bloque horario",
    )
    args = ap.parse_args()

    with get_db_audit(timeout_ms=_LOAD_TIMEOUT_MS) as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = %s", (_LOAD_TIMEOUT_MS,))
        _require_business_slice_facts(cur)

        if args.hour_from and args.hour_to:
            hf = datetime.fromisoformat(args.hour_from.replace("Z", "+00:00"))
            ht = datetime.fromisoformat(args.hour_to.replace("Z", "+00:00"))
            n = load_business_slice_hour_block(cur, hf, ht)
            conn.commit()
            cur.close()
            print(f"OK: hour_fact bloque [{hf}, {ht}) filas insertadas={n}")
            return 0

        if args.backfill_from and args.backfill_to:
            start = _parse_ym(args.backfill_from)
            end = _parse_ym(args.backfill_to)
            start = month_first_day(start.year, start.month)
            end = month_first_day(end.year, end.month)
            total, months = backfill_business_slice_months(cur, start, end, conn)
            conn.commit()
            cur.close()
            print(f"OK: backfill {len(months)} meses, filas insertadas (suma)={total}")
            return 0

        if args.month:
            target = _parse_month(args.month)
        else:
            today = date.today()
            target = month_first_day(today.year, today.month)

        n = load_business_slice_month(cur, target, conn)
        conn.commit()
        cur.close()
        print(f"OK: month_fact mes={target} filas insertadas={n}")
        print("Opcional: python -m scripts.validate_business_slice_refresh")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        print("ERROR:", e)
        raise SystemExit(2)
    except psycopg2.errors.DiskFull as e:
        print("ERROR: PostgreSQL sin espacio en disco (suele ser pgsql_tmp bajo el data_directory del servidor).")
        print("  Libere espacio o amplíe el volumen donde está Postgres; el cliente Windows no es ese disco.")
        print("  Tras liberar espacio, reintente. Opcional: BUSINESS_SLICE_LOAD_WORK_MEM=512MB reduce ficheros temporales.")
        print(str(e))
        raise SystemExit(3)
    except Exception as e:
        msg = str(e)
        print("ERROR:", e)
        if "already closed" in msg.lower():
            print(
                "Sugerencia: conexión cortada (red, reinicio de Postgres, Ctrl+C o timeout). "
                "La carga por país hace COMMIT por chunk: puede reejecutar el mismo --month para rellenar lo que falte "
                "tras borrar el mes (o dejar que DELETE + chunks lo repueblen entero)."
            )
        if "No space left on device" in msg or "could not write to file" in msg.lower():
            print(
                "Sugerencia: espacio en disco del servidor PostgreSQL (pgsql_tmp). "
                "Libere disco en ese host; opcional BUSINESS_SLICE_LOAD_WORK_MEM=512MB."
            )
        if "real_business_slice_month_fact" in msg and "does not exist" in msg:
            print("Sugerencia: desde backend ejecute: alembic upgrade head")
        raise SystemExit(1)
