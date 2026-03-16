"""
Auditoría de cobertura comercial en public.trips_2026.
Detecta si comision_empresa_asociada y pago_corporativo caen por debajo de umbral
(ruptura como la de 2026-02-16). Sale con código 1 si la última semana completa
tiene cobertura de comisión por debajo del umbral (guardrail para no volver a pasar).

Uso:
  cd backend && python -m scripts.audit_trips_2026_commercial_coverage
  cd backend && python -m scripts.audit_trips_2026_commercial_coverage --weeks 4  (revisar últimas 4 semanas)
  cd backend && python -m scripts.audit_trips_2026_commercial_coverage --min-comision-pct 10

Integración: ejecutar tras carga de viajes o en cron diario/semanal.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría cobertura comercial trips_2026")
    parser.add_argument("--weeks", type=int, default=4, help="Semanas recientes a evaluar (default 4)")
    parser.add_argument(
        "--min-comision-pct",
        type=float,
        default=15.0,
        help="Umbral mínimo %% de filas con comision no NULL en semana (default 15)",
    )
    parser.add_argument(
        "--min-pago-corp-count",
        type=int,
        default=1,
        help="Mínimo conteo de filas con pago_corporativo no NULL en semana (default 1)",
    )
    parser.add_argument("--verbose", action="store_true", help="Imprimir detalle por semana")
    args = parser.parse_args()

    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    today = date.today()
    # Última semana "completa" = la que terminó el domingo pasado
    last_complete_week = week_start(today) - timedelta(days=7)
    start_week = last_complete_week - timedelta(weeks=args.weeks - 1)
    end_exclusive = last_complete_week + timedelta(days=7)

    failed_weeks = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '60000'")
        cur.execute(
            """
            SELECT
                date_trunc('week', fecha_inicio_viaje)::date AS week_start,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed,
                COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL) AS con_comision,
                COUNT(*) FILTER (WHERE pago_corporativo IS NOT NULL) AS con_pago_corp
            FROM public.trips_2026
            WHERE fecha_inicio_viaje >= %s
              AND fecha_inicio_viaje < %s
            GROUP BY date_trunc('week', fecha_inicio_viaje)::date
            ORDER BY week_start
            """,
            (start_week, end_exclusive),
        )
        rows = cur.fetchall()
        cur.close()

    for r in rows:
        ws = r["week_start"]
        total = r["total"] or 0
        con_comision = r["con_comision"] or 0
        con_pago_corp = r["con_pago_corp"] or 0
        pct_comision = (100.0 * con_comision / total) if total else 0
        if args.verbose:
            print(f"  {ws}  total={total}  con_comision={con_comision} ({pct_comision:.1f}%%)  con_pago_corp={con_pago_corp}")
        if total > 0:
            if pct_comision < args.min_comision_pct:
                failed_weeks.append((str(ws), f"comision_pct={pct_comision:.1f}% < {args.min_comision_pct}%"))
            if con_pago_corp < args.min_pago_corp_count:
                failed_weeks.append((str(ws), f"pago_corp_count={con_pago_corp} < {args.min_pago_corp_count}"))

    if failed_weeks:
        print("AUDIT TRIPS_2026 COMMERCIAL COVERAGE: FAIL")
        for ws, reason in failed_weeks:
            print(f"  Semana {ws}: {reason}")
        print("Posible ruptura de fuente (comision_empresa_asociada/pago_corporativo). Revisar proceso que alimenta trips_2026.")
        return 1
    print("AUDIT TRIPS_2026 COMMERCIAL COVERAGE: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
