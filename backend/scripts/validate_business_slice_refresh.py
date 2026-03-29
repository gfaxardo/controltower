#!/usr/bin/env python3
"""
Validación operativa BUSINESS_SLICE (sin API/UI):

- Tamaño y filas de ops.real_business_slice_month_fact (fuente mensual canónica).
- La relación ops.mv_real_business_slice_monthly es vista de compatibilidad (no REFRESH).
- Comprueba desambiguación works_terms vs park_only en v_real_trips_business_slice_resolved_mv12.

Uso: cd backend && python -m scripts.validate_business_slice_refresh [--run-month-load] [--light]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

from app.db.connection import get_db, init_db_pool
from app.services.business_slice_incremental_load import load_business_slice_month, month_first_day


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-month-load",
        action="store_true",
        help="Ejecuta carga del mes calendario actual en month_fact antes de medir.",
    )
    ap.add_argument(
        "--light",
        action="store_true",
        help="Sin consultas pesadas sobre resolved_mv12.",
    )
    args = ap.parse_args()

    init_db_pool()
    fact = "ops.real_business_slice_month_fact"
    elapsed = 0.0
    if args.run_month_load:
        from datetime import date

        today = date.today()
        target = month_first_day(today.year, today.month)
        t0 = time.perf_counter()
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET statement_timeout = '7200000'")
            load_business_slice_month(cur, target, conn)
            conn.commit()
            cur.close()
        elapsed = time.perf_counter() - t0

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = 0")
        cur.execute(
            """
            SELECT
                pg_total_relation_size(%s::regclass) AS bytes_total,
                pg_relation_size(%s::regclass) AS bytes_heap,
                (SELECT count(*)::bigint FROM ops.real_business_slice_month_fact) AS row_count
            """,
            (fact, fact),
        )
        sz = dict(cur.fetchone())
        mix_parks = []
        ymm_samples = []
        if args.light:
            print("[INFO] Modo --light: omitidas consultas de auditoría resolved_mv12.")
        else:
            try:
                cur.execute(
                    """
                    SELECT park_id,
                           count(*) FILTER (WHERE matched_rule_type = 'park_plus_works_terms')::bigint AS trips_works_rule,
                           count(*) FILTER (WHERE matched_rule_type = 'park_only')::bigint AS trips_park_only,
                           count(DISTINCT business_slice_name) AS distinct_slices
                    FROM ops.v_real_trips_business_slice_resolved_mv12
                    WHERE resolution_status = 'resolved'
                    GROUP BY park_id
                    HAVING count(*) FILTER (WHERE matched_rule_type = 'park_plus_works_terms') > 0
                       AND count(*) FILTER (WHERE matched_rule_type = 'park_only') > 0
                    ORDER BY trips_works_rule DESC
                    LIMIT 10
                    """
                )
                mix_parks = cur.fetchall()
                cur.execute(
                    """
                    SELECT park_id, business_slice_name, matched_rule_type, count(*)::bigint AS trips
                    FROM ops.v_real_trips_business_slice_resolved_mv12
                    WHERE resolution_status = 'resolved'
                      AND matched_rule_type = 'park_plus_works_terms'
                    GROUP BY park_id, business_slice_name, matched_rule_type
                    HAVING count(*) > 0
                    ORDER BY trips DESC
                    LIMIT 5
                    """
                )
                ymm_samples = cur.fetchall()
            except psycopg2.Error as ex:
                print(f"[WARN] Consultas de auditoría omitidas ({type(ex).__name__}): {ex.pgerror or ex}")
        cur.close()

    if args.run_month_load:
        print(f"Carga month_fact (mes actual): {elapsed:.2f} s")
    else:
        print("Carga month_fact: omitida (usar --run-month-load o scripts.refresh_business_slice_mvs)")
    print(
        f"Tamaño total {fact}: {sz['bytes_total']} bytes (heap {sz['bytes_heap']}), filas: {sz['row_count']}"
    )
    print("Parques con convivencia works_terms + park_only (muestra):")
    for r in mix_parks:
        print(dict(r))
    if not mix_parks and not args.light:
        print("  (ninguno — puede ser normal si no hay park mixto con reglas activas)")
    print("Top filas con regla park_plus_works_terms (muestra):")
    for r in ymm_samples:
        print(dict(r))
    if not ymm_samples and not args.light:
        print(
            "(Sin filas: no hay viajes clasificados por works_terms en ventana, "
            "o mapping no activo — revisar import y reglas.)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
