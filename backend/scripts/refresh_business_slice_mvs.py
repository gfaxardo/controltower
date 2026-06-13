#!/usr/bin/env python3
from __future__ import annotations

r"""

    OV2-E: DEPRECATED - DO NOT USE FOR OMNIVIEW V2 FACT TABLES.

    This script uses legacy business_slice_incremental_load.py loader functions
    that have been DEPRECATED. Omniview V2 facts (day_fact, week_fact, month_fact)
    are now refreshed exclusively by the canonical bridge cascade.

    REPLACEMENT:
      python -m scripts.run_ov2_refresh_cascade --confirm

    DOCUMENTATION:
      See docs/architecture/OWNERSHIP_CERTIFICATION.md
      See docs/architecture/OMNIVIEW_V2_CANONICAL.md Section 7

    This script may still be used for non-Omniview V2 backfill scenarios.
    It must NOT be used as the primary refresh mechanism for Omniview V2 facts.

---
"""

# --- Original documentation retained below ---
# Ya no ejecuta REFRESH MATERIALIZED VIEW (la "MV" mensual es vista sobre la tabla fact).
# Requisito: migraciones 116_business_slice_incremental_facts y 117
# Uso: cd backend && python -m scripts.refresh_business_slice_mvs --month YYYY-MM
# --- End original documentation ---


import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2.errors

from app.db.connection import get_db
from app.services.business_slice_incremental_load import (
    backfill_business_slice_months,
    load_business_slice_day_for_month,
    load_business_slice_hour_block,
    load_business_slice_month,
    load_business_slice_week_for_month,
    _drop_enriched_temp,
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
    cur.execute(
        """
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'ops'
          AND p.proname = 'fn_real_trips_business_slice_resolved_subset'
        """
    )
    if cur.fetchone() is None:
        raise RuntimeError(
            "No existe ops.fn_real_trips_business_slice_resolved_subset. "
            "Ejecute alembic upgrade head (migración 117_business_slice_resolved_subset_fn)."
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
    ap = argparse.ArgumentParser(description="Carga incremental business_slice (month_fact / day_fact / week_fact / hour_fact)")
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
    ap.add_argument(
        "--with-daily", action="store_true", default=True,
        help="Cargar también day_fact y week_fact (default: sí). --no-daily para omitir.",
    )
    ap.add_argument("--no-daily", dest="with_daily", action="store_false")
    ap.add_argument(
        "--chunk-grain",
        choices=("country", "city", "city_week", "city_day"),
        default=None,
        help=(
            "Grano de la carga (sobrescribe BUSINESS_SLICE_MONTH_CHUNK_GRAIN). "
            "city_week / city_day se comportan como city (la materialización elimina el cuello)."
        ),
    )
    ap.add_argument(
        "--trigger-source",
        type=str,
        default="manual",
        choices=["manual", "cron", "deploy", "api", "scheduler"],
        help="Origen del trigger para refresh_run_log (default: manual)",
    )
    ap.add_argument(
        "--allow-closed-period",
        action="store_true",
        help="Permite refrescar un periodo closed/locked (requiere CT_ALLOW_CLOSED_PERIOD_REFRESH=1 y --reason).",
    )
    ap.add_argument(
        "--reason",
        type=str,
        default=None,
        help="Razon obligatoria para backfill de periodo cerrado.",
    )
    args = ap.parse_args()

    from app.services.refresh_control_service import refresh_guard

    with refresh_guard(
        refresh_name="refresh_business_slice_mvs",
        pipeline_name="business_slice",
        trigger_source=args.trigger_source,
        grain="daily",
        period_status="mixed",
    ) as guard:
        if guard.skipped:
            print("SKIPPED: otro refresh de business slice ya está en curso (lock held).")
            return 0

        # ── Period Closure Guard (Fase 1D-B) ──
        from app.services.period_closure_service import check_period_refresh_guard

        if args.month:
            target = _parse_month(args.month)
        elif args.backfill_from:
            target = _parse_ym(args.backfill_from)
        else:
            target = date.today().replace(day=1)

        period_check = check_period_refresh_guard(
            grain="monthly",
            period_start=target,
            refresh_name="refresh_business_slice_mvs",
            trigger_source=args.trigger_source,
            reason=args.reason,
            allow_closed_flag=args.allow_closed_period,
        )

        if period_check["blocked"]:
            print(f"[BLOCKED] {period_check['reason']}")
            print("  Use --allow-closed-period --reason '...' with CT_ALLOW_CLOSED_PERIOD_REFRESH=1 for authorized backfill.")
            return 2

        if period_check["would_block"]:
            print(f"[DRY-RUN] {period_check['reason']}")
            print("  Set CT_PERIOD_CLOSURE_DRY_RUN=false to enforce blocking.")

        with get_db() as conn:
            cur = conn.cursor()
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
                total, months = backfill_business_slice_months(
                    cur, start, end, conn,
                    chunk_grain=args.chunk_grain,
                    with_daily=args.with_daily,
                )
                conn.commit()
                cur.close()
                print(f"OK: backfill {len(months)} meses, filas insertadas month_fact (suma)={total}")
                if args.with_daily:
                    print("  (day_fact + week_fact también cargados por mes)")
                return 0

            n = load_business_slice_month(cur, target, conn, chunk_grain=args.chunk_grain)
            conn.commit()

            if args.with_daily:
                print(f"\n--- Cargando day_fact para {target} ---")
                nd = load_business_slice_day_for_month(cur, target, conn, chunk_grain=args.chunk_grain, keep_enriched=True)
                conn.commit()
                print(f"\n--- Cargando week_fact (desde enriched, COUNT DISTINCT canónico) ---")
                nw = load_business_slice_week_for_month(cur, target, conn, chunk_grain=args.chunk_grain)
                conn.commit()
                _drop_enriched_temp(cur)
                conn.commit()
                print(f"OK: month_fact={n}, day_fact={nd}, week_fact={nw} para mes={target}")
            else:
                print(f"OK: month_fact mes={target} filas insertadas={n}")

            cur.close()
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
