#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psycopg2.extras import RealDictCursor

from app.config.kpi_aggregation_rules import OMNIVIEW_MATRIX_VISIBLE_KPIS, get_omniview_kpi_rule
from app.db.connection import get_db_drill
from app.services.business_slice_service import (
    FACT_DAILY,
    FACT_MONTHLY,
    FACT_WEEKLY,
    V_RESOLVED,
    _canonical_metrics_from_components,
)


COMPONENTS_SQL = """
    COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
    COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
    COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
    SUM(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS ticket_sum_completed,
    COUNT(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL)::bigint AS ticket_count_completed,
    SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net,
    SUM(total_fare) FILTER (
        WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
    ) AS total_fare_completed_positive_sum
"""


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def _period_bounds(period_key: str, grain: str) -> tuple[date, date]:
    d = date.fromisoformat(period_key)
    if grain == "weekly":
        return d, d + timedelta(days=6)
    if grain == "monthly":
        next_month = date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)
        return d, next_month - timedelta(days=1)
    return d, d


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, str):
        return v
    x = float(v)
    if math.isfinite(x) and abs(x) >= 100:
        return f"{x:,.2f}"
    if math.isfinite(x):
        return f"{x:.4f}"
    return "n/a"


def _is_close(a: Any, b: Any, tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def _fetch_sample_cities(countries: list[str], lookback_days: int, max_cities: int) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for country in countries:
            cur.execute(
                f"""
                SELECT country, city, COUNT(*)::bigint AS trips
                FROM {V_RESOLVED}
                WHERE resolution_status = 'resolved'
                  AND trip_date >= CURRENT_DATE - (%s * interval '1 day')
                  AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
                  AND city IS NOT NULL
                GROUP BY country, city
                ORDER BY trips DESC, city ASC
                LIMIT %s
                """,
                (lookback_days, country, max_cities),
            )
            rows.extend((r["country"], r["city"]) for r in cur.fetchall())
        cur.close()
    return rows


def _fetch_daily_components(country: str, city: str, lookback_days: int) -> dict[str, dict[str, Any]]:
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                trip_date::date AS period_key,
                {COMPONENTS_SQL}
            FROM {V_RESOLVED}
            WHERE resolution_status = 'resolved'
              AND trip_date >= CURRENT_DATE - (%s * interval '1 day')
              AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))
            GROUP BY 1
            ORDER BY 1 ASC
            """,
            (lookback_days, country, city),
        )
        out = {str(r["period_key"]): dict(r) for r in cur.fetchall()}
        cur.close()
    return out


def _fetch_period_canonical(country: str, city: str, grain: str, lookback_days: int) -> dict[str, dict[str, Any]]:
    period_expr = "date_trunc('week', trip_date)::date" if grain == "weekly" else "date_trunc('month', trip_date)::date"
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                {period_expr} AS period_key,
                {COMPONENTS_SQL}
            FROM {V_RESOLVED}
            WHERE resolution_status = 'resolved'
              AND trip_date >= CURRENT_DATE - (%s * interval '1 day')
              AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))
            GROUP BY 1
            ORDER BY 1 ASC
            """,
            (lookback_days, country, city),
        )
        out = {str(r["period_key"]): _canonical_metrics_from_components(dict(r)) for r in cur.fetchall()}
        cur.close()
    return out


def _fetch_fact_rollup(country: str, city: str, grain: str, lookback_days: int) -> dict[str, dict[str, Any]]:
    table = FACT_WEEKLY if grain == "weekly" else FACT_MONTHLY
    period_col = "week_start" if grain == "weekly" else "month"
    period_filter = (
        "week_start >= date_trunc('week', CURRENT_DATE)::date - (%s * interval '1 day')"
        if grain == "weekly"
        else "month >= date_trunc('month', CURRENT_DATE)::date - (%s * interval '1 day')"
    )
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                {period_col} AS period_key,
                SUM(trips_completed)::bigint AS trips_completed,
                SUM(trips_cancelled)::bigint AS trips_cancelled,
                SUM(active_drivers)::bigint AS active_drivers,
                AVG(avg_ticket) AS avg_ticket,
                SUM(revenue_yego_net) AS revenue_yego_net,
                AVG(commission_pct) AS commission_pct,
                AVG(trips_per_driver) AS trips_per_driver,
                AVG(cancel_rate_pct) AS cancel_rate_pct
            FROM {table}
            WHERE {period_filter}
              AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))
            GROUP BY 1
            ORDER BY 1 ASC
            """,
            (lookback_days, country, city),
        )
        out = {str(r["period_key"]): dict(r) for r in cur.fetchall()}
        cur.close()
    return out


def _aggregate_daily_reference(
    daily_components: dict[str, dict[str, Any]],
    grain: str,
    period_key: str,
    kpi_key: str,
) -> str:
    start_date, end_date = _period_bounds(period_key, grain)
    selected = [
        row
        for key, row in daily_components.items()
        if start_date <= date.fromisoformat(key) <= end_date
    ]
    if not selected:
        return "n/a"
    if kpi_key == "active_drivers":
        total = sum(int(_num(r.get("active_drivers"))) for r in selected)
        max_daily = max(int(_num(r.get("active_drivers"))) for r in selected)
        return f"max={max_daily} / sum={total}"
    if kpi_key == "trips_per_driver":
        return "no permitido desde daily"
    agg = defaultdict(float)
    for row in selected:
        agg["trips_completed"] += _num(row.get("trips_completed"))
        agg["trips_cancelled"] += _num(row.get("trips_cancelled"))
        agg["ticket_sum_completed"] += _num(row.get("ticket_sum_completed"))
        agg["ticket_count_completed"] += _num(row.get("ticket_count_completed"))
        agg["revenue_yego_net"] += _num(row.get("revenue_yego_net"))
        agg["total_fare_completed_positive_sum"] += _num(row.get("total_fare_completed_positive_sum"))
    rebuilt = _canonical_metrics_from_components(dict(agg))
    return _fmt(rebuilt.get(kpi_key))


def _evaluate_status(
    kpi_key: str,
    canonical_value: Any,
    fact_value: Any,
    daily_reference: str,
) -> tuple[str, str]:
    if kpi_key == "active_drivers":
        if isinstance(daily_reference, str) and daily_reference.startswith("max="):
            pieces = daily_reference.replace("max=", "").replace("sum=", "").split(" / ")
            max_daily = float(pieces[0])
            sum_daily = float(pieces[1])
            within_bounds = max_daily <= float(canonical_value or 0) <= sum_daily
            if not within_bounds:
                return "failed", "Distinct weekly/monthly drivers fuera de cota diaria."
        if not _is_close(canonical_value, fact_value):
            return "failed", "La capa fact agregada no conserva unicidad de drivers."
        return "ok", "Distinct drivers consistente."
    if kpi_key == "trips_per_driver":
        if not _is_close(canonical_value, fact_value):
            return "failed", "TPD no coincide con trips / active_drivers canónicos."
        return "warning", "No debe reconstruirse desde daily agregado; comparar contra canónico del periodo."
    if daily_reference == "n/a":
        return "warning", "Sin referencia diaria suficiente en la ventana."
    if not _is_close(canonical_value, fact_value):
        return "failed", "El rollup observado en facts difiere del valor canónico del periodo."
    return "ok", "El valor del periodo coincide con la reconstrucción canónica."


def build_report(countries: list[str], lookback_days: int, max_cities: int) -> tuple[str, dict[str, int]]:
    cities = _fetch_sample_cities(countries, lookback_days, max_cities)
    status_totals = {"ok": 0, "warning": 0, "failed": 0}
    lines: list[str] = []
    lines.append("# OMNIVIEW KPI Consistency Report")
    lines.append("")
    lines.append(f"- Countries objetivo: {', '.join(countries)}")
    lines.append(f"- Lookback usado: {lookback_days} dias")
    lines.append(f"- Max cities por pais: {max_cities}")
    lines.append(f"- Muestras evaluadas: {', '.join([f'{c}/{ct}' for c, ct in cities]) if cities else 'ninguna'}")
    lines.append("- Fuente canónica: `ops.v_real_trips_business_slice_resolved`")
    lines.append("- Fuente fact auditada: `ops.real_business_slice_week_fact` y `ops.real_business_slice_month_fact` agregadas a nivel ciudad.")
    lines.append("")
    lines.append("## Resultados")
    lines.append("")
    lines.append("| Grain | Period | Country | City | KPI | Daily reference | Canonical period | Fact rollup | Expected rule | Status | Explanation |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for country, city in cities:
        daily_components = _fetch_daily_components(country, city, lookback_days)
        for grain in ("weekly", "monthly"):
            canonical = _fetch_period_canonical(country, city, grain, lookback_days)
            fact_rollup = _fetch_fact_rollup(country, city, grain, lookback_days)
            for period_key, canonical_metrics in canonical.items():
                fact_metrics = fact_rollup.get(period_key, {})
                for kpi_key in OMNIVIEW_MATRIX_VISIBLE_KPIS:
                    daily_reference = _aggregate_daily_reference(daily_components, grain, period_key, kpi_key)
                    canonical_value = canonical_metrics.get(kpi_key)
                    fact_value = fact_metrics.get(kpi_key)
                    rule = get_omniview_kpi_rule(kpi_key)
                    status, explanation = _evaluate_status(
                        kpi_key,
                        canonical_value,
                        fact_value,
                        daily_reference,
                    )
                    status_totals[status] += 1
                    lines.append(
                        "| {grain} | {period} | {country} | {city} | {kpi} | {daily} | {canonical} | {fact} | {rule} | {status} | {explanation} |".format(
                            grain=grain,
                            period=period_key,
                            country=country,
                            city=city,
                            kpi=kpi_key,
                            daily=daily_reference,
                            canonical=_fmt(canonical_value),
                            fact=_fmt(fact_value),
                            rule=rule["aggregation_type"],
                            status=status,
                            explanation=explanation,
                        )
                    )
    lines.insert(
        10,
        f"- Totales: ok={status_totals['ok']}, warning={status_totals['warning']}, failed={status_totals['failed']}",
    )
    return "\n".join(lines) + "\n", status_totals


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita consistencia KPI de Omniview Matrix.")
    parser.add_argument("--countries", nargs="+", default=["Peru", "Colombia"])
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--max-cities", type=int, default=2)
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[2] / "docs" / "OMNIVIEW_KPI_CONSISTENCY_REPORT.md"),
    )
    args = parser.parse_args()
    report, totals = build_report(args.countries, args.lookback_days, args.max_cities)
    out_path = Path(args.output)
    out_path.write_text(report, encoding="utf-8")
    print(report)
    return 0 if totals["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
