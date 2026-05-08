"""
P2B — Descubrir periodos y dimensiones con datos en ops.real_business_slice_*_fact.

Sin hardcodear periodos: lee MIN/MAX y rankings desde la BD.
Salida JSON en scripts/outputs/kpi_fact_discovery_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db.connection import get_db, init_db_pool  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out",
        type=str,
        default=None,
        help="Ruta JSON (default: scripts/outputs/kpi_fact_discovery_<ts>.json)",
    )
    args = p.parse_args()

    init_db_pool()
    out: dict = {}
    facts = [
        ("day", "ops.real_business_slice_day_fact", "trip_date"),
        ("week", "ops.real_business_slice_week_fact", "week_start"),
        ("month", "ops.real_business_slice_month_fact", "month"),
    ]

    with get_db() as conn:
        cur = conn.cursor()
        for label, table, col in facts:
            cur.execute(
                f"SELECT MIN({col})::text AS mn, MAX({col})::text AS mx, COUNT(*)::bigint AS n FROM {table}"
            )
            row = cur.fetchone()
            out[label] = {
                "table": table,
                "time_col": col,
                "min": row[0],
                "max": row[1],
                "row_count": row[2],
            }
            cur.execute(
                f"""
                SELECT country, COALESCE(SUM(trips_completed),0)::bigint AS trips
                FROM {table} GROUP BY 1 ORDER BY trips DESC NULLS LAST LIMIT 20
                """
            )
            out[label]["top_countries"] = [
                {"country": r[0], "trips": r[1]} for r in cur.fetchall()
            ]
            cur.execute(
                f"""
                SELECT city, COALESCE(SUM(trips_completed),0)::bigint AS trips
                FROM {table} GROUP BY 1 ORDER BY trips DESC NULLS LAST LIMIT 20
                """
            )
            out[label]["top_cities"] = [{"city": r[0], "trips": r[1]} for r in cur.fetchall()]
            cur.execute(
                f"""
                SELECT business_slice_name, COALESCE(SUM(trips_completed),0)::bigint AS trips
                FROM {table} GROUP BY 1 ORDER BY trips DESC NULLS LAST LIMIT 20
                """
            )
            out[label]["top_business_slices"] = [
                {"business_slice": r[0], "trips": r[1]} for r in cur.fetchall()
            ]

        cur.execute(
            """
            SELECT date_trunc('month', month)::date AS m,
                   COALESCE(SUM(trips_completed),0)::bigint AS trips
            FROM ops.real_business_slice_month_fact
            GROUP BY 1 ORDER BY m DESC LIMIT 6
            """
        )
        out["last_6_calendar_months"] = [
            {"month_start": str(r[0]), "trips": r[1]} for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT week_start::text, COALESCE(SUM(trips_completed),0)::bigint AS trips
            FROM ops.real_business_slice_week_fact
            GROUP BY 1 ORDER BY 1 DESC LIMIT 8
            """
        )
        out["last_8_week_starts"] = [
            {"week_start": r[0], "trips": r[1]} for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT date_trunc('month', month)::date AS m
            FROM ops.real_business_slice_month_fact
            GROUP BY 1
            HAVING COALESCE(SUM(trips_completed),0) > 0
            ORDER BY 1 DESC LIMIT 3
            """
        )
        out["last_months_with_trips_positive"] = [str(r[0]) for r in cur.fetchall()]

        cur.close()

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = Path(args.out) if args.out else _HERE / "outputs" / f"kpi_fact_discovery_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[discover] JSON: {out_path}", flush=True)
    # Resumen consola
    for label, table, _ in facts:
        b = out.get(label, {})
        print(
            f"[{label}] {b.get('table')} rows={b.get('row_count')} min={b.get('min')} max={b.get('max')}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
