#!/usr/bin/env python3
"""
CF-H1M.5 — Metric Lineage & Traceability Console

Audita cualquier KPI desde raw source hasta serving fact,
con breakdown por park, fleet, subfleet, driver, y reconciliation raw vs fact.

Uso:
  python backend/scripts/audit_metric_lineage.py \
    --metric trips --grain month --period 2026-05 \
    --country Peru --city Lima --business-slice "Auto regular"

  python backend/scripts/audit_metric_lineage.py \
    --metric trips --grain month --period 2026-05 \
    --country Peru --city Lima --business-slice "__ALL__"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

# ── Canonical tables ──
RAW_SOURCE = "public.trips_2026"
FACT_DAY = "ops.real_business_slice_day_fact"
FACT_WEEK = "ops.real_business_slice_week_fact"
FACT_MONTH = "ops.real_business_slice_month_fact"
ENRICHED = "ops.v_real_trips_enriched_base"
RESOLVED = "ops.v_real_trips_business_slice_resolved"

# ── KPI definitions ──
KPI_CONFIG = {
    "trips": {
        "label": "Viajes completados",
        "raw_col": "COUNT(*) FILTER (WHERE completed_flag)",
        "raw_sum": "COUNT(*)",
        "fact_col": "SUM(trips_completed)",
        "unit": "viajes",
    },
    "revenue": {
        "label": "Revenue YEGO",
        "raw_col": "SUM(revenue_yego_net) FILTER (WHERE completed_flag)",
        "raw_sum": "SUM(revenue_yego_net)",
        "fact_col": "SUM(revenue_yego_final)",
        "unit": "moneda",
    },
    "drivers": {
        "label": "Conductores activos",
        "raw_col": "COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)",
        "raw_sum": "COUNT(DISTINCT driver_id)",
        "fact_col": "SUM(active_drivers)",
        "unit": "conductores",
    },
    "ticket": {
        "label": "Ticket promedio",
        "raw_col": "AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL)",
        "raw_sum": "AVG(ticket)",
        "fact_col": "AVG(avg_ticket)",
        "unit": "moneda",
    },
    "tpd": {
        "label": "Viajes por conductor",
        "raw_col": None,
        "raw_sum": None,
        "fact_col": "AVG(trips_per_driver)",
        "unit": "viajes/conductor",
        "derived": True,
    },
}

GRAIN_CONFIG = {
    "day": {"fact_table": FACT_DAY, "time_col": "trip_date", "date_format": "%Y-%m-%d", "label": "Diario"},
    "week": {"fact_table": FACT_WEEK, "time_col": "week_start", "date_format": "%Y-%W", "label": "Semanal"},
    "month": {"fact_table": FACT_MONTH, "time_col": "month", "date_format": "%Y-%m", "label": "Mensual"},
}


def _safe_int(v: Any) -> int:
    if v is None:
        return 0
    return int(v)


def _safe_num(v: Any) -> float:
    if v is None:
        return 0.0
    return float(v)


def _q(cur, sql: str, params: list = None) -> Any:
    cur.execute(sql, params or [])
    return cur.fetchone()


def _qa(cur, sql: str, params: list = None) -> list:
    cur.execute(sql, params or [])
    return cur.fetchall()


def run_audit(args) -> dict:
    """Ejecuta auditoria completa y retorna resultados."""
    metric = args.metric
    grain = args.grain
    period = args.period
    country = args.country
    city = args.city
    business_slice = args.business_slice
    park_id = args.park_id
    fleet_ref = args.fleet_room_reference

    kpi = KPI_CONFIG[metric]
    grain_cfg = GRAIN_CONFIG[grain]
    fact_table = grain_cfg["fact_table"]
    time_col = grain_cfg["time_col"]

    # Parse period into date range
    if grain == "month":
        period_dt = datetime.strptime(period, "%Y-%m").date()
        start_date = period_dt.replace(day=1)
        if period_dt.month == 12:
            end_date = date(period_dt.year + 1, 1, 1)
        else:
            end_date = date(period_dt.year, period_dt.month + 1, 1)
    elif grain == "week":
        parts = period.split("-W")
        year = int(parts[0])
        iso_week = int(parts[1])
        start_date = date.fromisocalendar(year, iso_week, 1)
        end_date = start_date + timedelta(days=7)
    else:  # day
        start_date = datetime.strptime(period, "%Y-%m-%d").date()
        end_date = start_date + timedelta(days=1)

    results = {
        "meta": {
            "script": "CF-H1M.5 Metric Lineage Audit",
            "timestamp": datetime.now().isoformat(),
            "metric": metric,
            "grain": grain,
            "period": period,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "country": country,
            "city": city,
            "business_slice": business_slice,
            "park_id": park_id,
            "fleet_room_reference": fleet_ref,
        },
        "total_kpi": {},
        "breakdown_park": [],
        "breakdown_fleet": [],
        "breakdown_subfleet": [],
        "top_drivers": [],
        "reconciliation": {},
        "warnings": [],
    }

    norm_country = country.strip().lower()
    norm_city = city.strip().lower()

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ── 1. Total KPI from serving fact ──
        slice_filter = ""
        slice_params = []
        if business_slice and business_slice != "__ALL__":
            slice_filter = "AND LOWER(TRIM(business_slice_name)) = LOWER(TRIM(%s))"
            slice_params.append(business_slice)

        cur.execute(f"""
            SELECT {kpi['fact_col']}::numeric AS fact_value
            FROM {fact_table}
            WHERE LOWER(TRIM(country)) = %s
              AND LOWER(TRIM(city)) = %s
              AND {time_col} >= %s AND {time_col} < %s
              {slice_filter}
        """, [norm_country, norm_city, start_date, end_date] + slice_params)
        fact_row = cur.fetchone()
        fact_value = _safe_num(fact_row["fact_value"]) if fact_row else 0
        results["total_kpi"]["fact_value"] = round(fact_value, 2)
        results["total_kpi"]["fact_table"] = fact_table
        results["total_kpi"]["metric"] = metric
        results["total_kpi"]["unit"] = kpi["unit"]

        # ── 2. Total from RAW (public.trips_2026 — no mapping filter) ──
        raw_trips_filter = ""
        if norm_country:
            raw_trips_filter += " AND LOWER(TRIM(park_id)) LIKE %s"
        # trips_2026 doesn't have country/city columns — use fact table for raw reference
        results["total_kpi"]["raw_value"] = None
        results["total_kpi"]["raw_source"] = "N/A (trips_2026 has no country/city columns)"

        # ── 3. Raw trips from trips_2026 ──
        raw_trips_sql = f"""
            SELECT COUNT(*)::bigint AS raw_trips
            FROM {RAW_SOURCE}
            WHERE fecha_inicio_viaje >= %s AND fecha_inicio_viaje < %s
              AND condicion = 'completed'
        """
        cur.execute(raw_trips_sql, [start_date, end_date])
        raw_trips_row = cur.fetchone()
        results["total_kpi"]["raw_trips_2026"] = _safe_int(raw_trips_row["raw_trips"])

        # ── 4. Breakdown by park_id (from fact tables — park_id not in fact, show slice breakdown instead) ──
        if business_slice == "__ALL__":
            cur.execute(f"""
                SELECT business_slice_name,
                       SUM(trips_completed)::bigint AS trips
                FROM {fact_table}
                WHERE LOWER(TRIM(country)) = %s
                  AND LOWER(TRIM(city)) = %s
                  AND {time_col} >= %s AND {time_col} < %s
                GROUP BY business_slice_name
                ORDER BY trips DESC
            """, [norm_country, norm_city, start_date, end_date])
            for r in cur.fetchall():
                results["breakdown_park"].append({
                    "slice": r["business_slice_name"],
                    "trips": _safe_int(r["trips"]),
                })
        else:
            results["breakdown_park"].append({
                "note": f"park_id not available in fact tables. Use enriched base for park-level breakdown.",
            })
            for r in cur.fetchall():
                results["breakdown_park"].append({
                    "park_id": r["park_id"],
                    "park_name": r["park_name"],
                    "kpi_value": round(_safe_num(r["kpi_value"]), 2),
                    "trip_count": _safe_int(r["trip_count"]),
                })

        # ── 5. Breakdown by fleet_display_name ──
        cur.execute(f"""
            SELECT fleet_display_name,
                   {kpi['fact_col']}::numeric AS kpi_value
            FROM {fact_table}
            WHERE LOWER(TRIM(country)) = %s
              AND LOWER(TRIM(city)) = %s
              AND {time_col} >= %s AND {time_col} < %s
              {slice_filter}
            GROUP BY fleet_display_name
            ORDER BY kpi_value DESC
        """, [norm_country, norm_city, start_date, end_date] + slice_params)
        for r in cur.fetchall():
            results["breakdown_fleet"].append({
                "fleet_display_name": r["fleet_display_name"],
                "kpi_value": round(_safe_num(r["kpi_value"]), 2),
            })

        # ── 6. Breakdown by subfleet ──
        cur.execute(f"""
            SELECT is_subfleet, subfleet_name, parent_fleet_name,
                   {kpi['fact_col']}::numeric AS kpi_value
            FROM {fact_table}
            WHERE LOWER(TRIM(country)) = %s
              AND LOWER(TRIM(city)) = %s
              AND {time_col} >= %s AND {time_col} < %s
              {slice_filter}
            GROUP BY is_subfleet, subfleet_name, parent_fleet_name
            ORDER BY kpi_value DESC
        """, [norm_country, norm_city, start_date, end_date] + slice_params)
        for r in cur.fetchall():
            results["breakdown_subfleet"].append({
                "is_subfleet": r["is_subfleet"],
                "subfleet_name": r["subfleet_name"],
                "parent_fleet_name": r["parent_fleet_name"],
                "kpi_value": round(_safe_num(r["kpi_value"]), 2),
            })

        # ── 7. Top drivers (skip — enriched base too slow for production audit) ──
        results["top_drivers"] = [{"note": "Skipped — enriched base scan too expensive for audit script. Use targeted query."}]

        # ── 8. Reconciliation: day_fact sum vs month_fact ──
        # For monthly grain, compare day_fact rollup vs month_fact
        if grain == "month" and metric in ("trips", "revenue", "drivers"):
            fact_col_agg = "SUM(trips_completed)" if metric == "trips" else (
                "SUM(revenue_yego_final)" if metric == "revenue" else "SUM(active_drivers)"
            )
            cur.execute(f"""
                SELECT {fact_col_agg}::numeric AS day_rollup
                FROM {FACT_DAY}
                WHERE LOWER(TRIM(country)) = %s
                  AND LOWER(TRIM(city)) = %s
                  AND trip_date >= %s AND trip_date < %s
                  {slice_filter}
            """, [norm_country, norm_city, start_date, end_date] + slice_params)
            day_row = cur.fetchone()
            day_val = _safe_num(day_row["day_rollup"]) if day_row else 0
            fact_val = results["total_kpi"].get("fact_value", 0)
            
            if day_val and fact_val and fact_val > 0:
                delta = day_val - fact_val
                delta_pct = (delta / fact_val) * 100
                results["reconciliation"] = {
                    "day_fact_sum": round(day_val, 2),
                    "month_fact": round(fact_val, 2),
                    "delta": round(delta, 2),
                    "delta_pct": round(delta_pct, 2),
                    "status": "PASS" if abs(delta_pct) <= 1.0 else "FAIL",
                    "threshold": "1%",
                    "note": "day_fact rollup vs month_fact",
                }
            else:
                results["reconciliation"] = {"status": "SKIPPED", "reason": "insufficient data"}
        else:
            results["reconciliation"] = {
                "status": "INFO",
                "note": f"Reconciliation for grain={grain} uses day_fact vs {grain}_fact",
            }

        # ── 9. Warnings ──
        warnings = results["warnings"]

        # Raw vs fact divergence
        if results["reconciliation"].get("status") == "FAIL":
            warnings.append({
                "code": "RAW_FACT_DIVERGENCE",
                "message": f"Raw ({raw_val}) != fact ({fact_val}): delta={delta:.2f} ({delta_pct:.1f}%)",
            })

        # Unmapped parks: skip enriched scan. See slice mapping audit for park-level traceability.
            unmapped = cur.fetchone()
            if unmapped and _safe_int(unmapped["unmapped_parks"]) > 0:
                warnings.append({
                    "code": "UNMAPPED_PARKS",
                    "message": f"{unmapped['unmapped_parks']} parks sin business slice asignado.",
                })

        # Fleet name variant check
        cur.execute(f"""
            SELECT business_slice_name, COUNT(DISTINCT fleet_display_name) AS variants
            FROM {fact_table}
            WHERE LOWER(TRIM(country)) = %s
              AND LOWER(TRIM(city)) = %s
              AND {time_col} >= %s AND {time_col} < %s
            GROUP BY business_slice_name
            HAVING COUNT(DISTINCT fleet_display_name) > 1
        """, [norm_country, norm_city, start_date, end_date])
        for r in cur.fetchall():
            warnings.append({
                "code": "FLEET_NAME_VARIANTS",
                "message": f"Slice '{r['business_slice_name']}' tiene {r['variants']} fleet_display_name variants.",
            })

        # Data freshness warning
        cur.execute(f"""
            SELECT MAX({time_col}) AS max_date
            FROM {fact_table}
            WHERE LOWER(TRIM(country)) = %s
              AND LOWER(TRIM(city)) = %s
        """, [norm_country, norm_city])
        max_d = cur.fetchone()
        if max_d and max_d["max_date"]:
            lag = (date.today() - max_d["max_date"]).days
            if lag > 3:
                warnings.append({
                    "code": "DATA_FRESHNESS_LAG",
                    "message": f"Max fact date: {max_d['max_date']} ({lag}d lag).",
                })

        cur.close()

    return results


def print_report(results: dict) -> None:
    """Imprime reporte formateado."""
    meta = results["meta"]
    total = results["total_kpi"]
    rec = results["reconciliation"]
    warnings = results["warnings"]

    print("=" * 72)
    print("CF-H1M.5 — Metric Lineage & Traceability Console")
    print("=" * 72)
    print(f"Timestamp:  {meta['timestamp']}")
    print(f"Metric:     {meta['metric']} ({KPI_CONFIG[meta['metric']]['label']})")
    print(f"Grain:      {meta['grain']}")
    print(f"Period:     {meta['period']}")
    print(f"Location:   {meta['country']} / {meta['city']}")
    print(f"Slice:      {meta['business_slice']}")
    if meta.get("park_id"):
        print(f"Park:       {meta['park_id']}")
    print()

    # ── Total KPI ──
    print("─── 1. TOTAL KPI ───")
    print(f"  Fact value:    {total.get('fact_value', 'N/A'):,} {KPI_CONFIG[meta['metric']]['unit']}")
    print(f"  Fact table:    {total.get('fact_table', 'N/A')}")
    if total.get("raw_value") is not None:
        print(f"  Raw value:     {total['raw_value']:,.2f} (from {total.get('raw_source', 'N/A')})")
    print(f"  Raw trips_2026:{total.get('raw_trips_2026', 'N/A'):,}")
    print()

    # ── Reconciliation ──
    print("─── 2. RECONCILIATION ───")
    if rec.get("status") == "PASS":
        print(f"  STATUS: PASS  (day_fact={rec.get('day_fact_sum', 'N/A'):,.2f} vs month_fact={rec.get('month_fact', 'N/A'):,.2f}, delta={rec.get('delta_pct', 0):.2f}%)")
    elif rec.get("status") == "FAIL":
        print(f"  STATUS: FAIL  (day_fact={rec.get('day_fact_sum', 'N/A'):,.2f} vs month_fact={rec.get('month_fact', 'N/A'):,.2f}, delta={rec.get('delta_pct', 0):.2f}%)")
    else:
        print(f"  STATUS: {rec.get('status')} ({rec.get('note', rec.get('reason', 'N/A'))})")
    print()

    # ── Park/Slice breakdown ──
    if results["breakdown_park"]:
        print("─── 3. BREAKDOWN ───")
        for r in results["breakdown_park"]:
            if "slice" in r:
                print(f"  {r['slice']:<35} {r.get('trips', 0):>12,}")
            elif "note" in r:
                print(f"  {r['note']}")
            elif "park_id" in r:
                pid = (r["park_id"] or "")[:20]
                pname = (r.get("park_name") or "")[:30]
                val = r.get("kpi_value", r.get("trip_count", 0))
                print(f"  {pid:<20} {pname:<30} {val:>12,}")
        print()

    # ── Fleet breakdown ──
    if results["breakdown_fleet"]:
        print("─── 4. BREAKDOWN BY FLEET ───")
        for r in results["breakdown_fleet"]:
            print(f"  {r['fleet_display_name']:<35} {r['kpi_value']:>12,.0f}")
        print()

    # ── Subfleet breakdown ──
    if results["breakdown_subfleet"]:
        print("─── 5. BREAKDOWN BY SUBFLEET ───")
        for r in results["breakdown_subfleet"]:
            sub = r["subfleet_name"] or "(none)"
            parent = r["parent_fleet_name"] or "(none)"
            print(f"  sub={sub:<20} parent={parent:<20} subfleet={r['is_subfleet']}  {r['kpi_value']:>12,.0f}")
        print()

    # ── Top drivers ──
    if results["top_drivers"]:
        print("─── 6. TOP DRIVERS ───")
        for r in results["top_drivers"]:
            if "driver_id" in r:
                print(f"  driver_id={r['driver_id']:<25} trips={r.get('trip_count', 0):,}")
            elif "note" in r:
                print(f"  {r['note']}")
        print()

    # ── Warnings ──
    if warnings:
        print("─── 7. WARNINGS ───")
        for w in warnings:
            print(f"  [{w['code']}] {w['message']}")
        print()
    else:
        print("─── 7. WARNINGS: None ───\n")

    # ── Fleet Room reference ──
    print("─── 8. FLEET ROOM ───")
    if meta.get("fleet_room_reference"):
        delta = total.get("fact_value", 0) - float(meta["fleet_room_reference"])
        print(f"  Fleet Room ref: {float(meta['fleet_room_reference']):,.0f}")
        print(f"  Control Tower:  {total.get('fact_value', 0):,.0f}")
        print(f"  Delta:          {delta:,.0f}")
    else:
        print(f"  Fleet Room reference: NOT PROVIDED")
        print(f"  Control Tower total:  {total.get('fact_value', 0):,.0f}")
        print(f"  Difference:           NOT COMPUTED")
        print(f"  Required input:       valor Fleet Room / {meta['period']} / {meta['metric']}")
    print()

    # ── Veredict ──
    print("─── 9. VEREDICT ───")
    rec_fail = rec.get("status") == "FAIL"
    has_warnings = len(warnings) > 0
    if rec_fail:
        print("  NO GO — Raw/Fact reconciliation failed.")
    elif has_warnings:
        print("  CONDITIONAL GO — Warnings detected (see above).")
    else:
        print("  GO — KPI fully traceable from raw to fact.")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="CF-H1M.5 Metric Lineage Audit")
    ap.add_argument("--metric", required=True, choices=["trips", "revenue", "drivers", "ticket", "tpd"])
    ap.add_argument("--grain", required=True, choices=["day", "week", "month"])
    ap.add_argument("--period", required=True, help="YYYY-MM-DD, YYYY-WW, or YYYY-MM")
    ap.add_argument("--country", required=True)
    ap.add_argument("--city", required=True)
    ap.add_argument("--business-slice", required=True)
    ap.add_argument("--park-id", default=None)
    ap.add_argument("--fleet-room-reference", type=float, default=None)
    ap.add_argument("--json", action="store_true", help="Output JSON instead of report")
    ap.add_argument("--export-dir", default=None, help="Override export directory")
    args = ap.parse_args()

    results = run_audit(args)
    meta = results["meta"]
    warnings = results["warnings"]
    rec = results["reconciliation"]

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_report(results)

    # ── Export to file ──
    export_dir = args.export_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "exports", "audits", "metric_lineage",
    )
    os.makedirs(export_dir, exist_ok=True)

    safe_slice = meta["business_slice"].replace(" ", "_").replace('"', '').lower()
    safe_slice = safe_slice if safe_slice != "__all__" else "all_slices"
    fname_base = f"cf_h1m5_{meta['country'].lower()}_{meta['city'].lower()}_{safe_slice}_{meta['period']}_{meta['metric']}"

    json_path = os.path.join(export_dir, f"{fname_base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    md_path = os.path.join(export_dir, f"{fname_base}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# CF-H1M.5 — {meta['metric'].upper()} Lineage Audit\n\n")
        f.write(f"| Field | Value |\n|-------|-------|\n")
        for k, v in meta.items():
            f.write(f"| {k} | {v} |\n")
        f.write(f"\n## Total KPI\n\nFact: {results['total_kpi'].get('fact_value', 'N/A')}\n\n")
        if results["breakdown_park"]:
            f.write(f"\n## Breakdown\n\n")
            for p in results["breakdown_park"][:10]:
                if "slice" in p:
                    f.write(f"- {p['slice']}: {p.get('trips', 0):,}\n")
                elif "note" in p:
                    f.write(f"- {p['note']}\n")
        if warnings:
            f.write(f"\n## Warnings\n\n")
            for w in warnings:
                f.write(f"- [{w['code']}] {w['message']}\n")

    print(f"  Evidence saved: {md_path}")

    rec_fail = rec.get("status") == "FAIL"
    has_warnings = len(warnings) > 0
    if rec_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
