"""
FASE 1G.3 — Refresh Omniview Projection Facts
Pre-computa proyección daily/weekly para plan_version dado y la almacena
en serving.omniview_projection_daily_fact.

Uso:
  python refresh_omniview_projection_facts.py --plan-version ruta27_2026_04_21 [--grain daily] [--country peru] [--year 2026]

Reglas:
- Idempotente: borra datos previos para (plan_version, grain) y re-inserta.
- Solo daily y weekly. Monthly no necesita serving (es rápido).
- Imprime resumen: rows inserted, min/max date, duration, unmatched.
"""
from __future__ import annotations

import argparse, sys, time, uuid, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, ".")

from app.services.projection_expected_progress_service import get_omniview_projection
from app.db.connection import get_db
from psycopg2.extras import execute_values


INSERT_COLS = [
    "plan_version", "grain", "country", "city", "business_slice_name",
    "period_key", "year", "month", "trip_date", "week_start", "week_end",
    "iso_year", "iso_week", "month_source",
    "real_trips", "real_revenue", "real_active_drivers", "real_trips_cancelled",
    "real_avg_ticket", "real_commission_pct", "real_trips_per_driver", "real_cancel_rate_pct",
    "trips_completed_projected_total", "trips_completed_projected_expected",
    "revenue_yego_net_projected_total", "revenue_yego_net_projected_expected",
    "active_drivers_projected_total", "active_drivers_projected_expected",
    "trips_completed", "revenue_yego_net", "active_drivers",
    "trips_completed_attainment_pct", "revenue_yego_net_attainment_pct", "active_drivers_attainment_pct",
    "trips_completed_gap_to_expected", "revenue_yego_net_gap_to_expected", "active_drivers_gap_to_expected",
    "trips_completed_gap_to_full", "revenue_yego_net_gap_to_full", "active_drivers_gap_to_full",
    "trips_completed_completion_pct", "revenue_yego_net_completion_pct", "active_drivers_completion_pct",
    "trips_completed_signal", "revenue_yego_net_signal", "active_drivers_signal",
    "comparison_status", "comparison_basis", "curve_method", "curve_confidence",
    "fallback_level", "expected_ratio", "projection_confidence", "projection_anomaly",
    "avg_ticket", "commission_pct", "trips_per_driver", "cancel_rate_pct", "trips_cancelled",
    "week_label", "week_range_label", "week_full_label", "distribution_model", "gap_pct",
    "batch_id",
]

TABLE = "serving.omniview_projection_daily_fact"


def _safe_num(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _extract_row(r: dict, plan_version: str, grain: str, batch_id: str) -> tuple:
    return (
        plan_version,
        grain,
        r.get("country", ""),
        r.get("city", ""),
        r.get("business_slice_name", ""),
        r.get("trip_date") or r.get("week_start") or r.get("month", ""),
        r.get("year"),
        r.get("month_number") or (int(str(r.get("month", "1970-01"))[5:7]) if r.get("month") else None),
        r.get("trip_date"),
        r.get("week_start"),
        r.get("week_end"),
        r.get("iso_year"),
        r.get("iso_week"),
        r.get("month_source"),
        _safe_num(r.get("real_trips")), _safe_num(r.get("real_revenue")),
        _safe_num(r.get("real_active_drivers")), _safe_num(r.get("real_trips_cancelled")),
        _safe_num(r.get("real_avg_ticket")), _safe_num(r.get("real_commission_pct")),
        _safe_num(r.get("real_trips_per_driver")), _safe_num(r.get("real_cancel_rate_pct")),
        _safe_num(r.get("trips_completed_projected_total")),
        _safe_num(r.get("trips_completed_projected_expected")),
        _safe_num(r.get("revenue_yego_net_projected_total")),
        _safe_num(r.get("revenue_yego_net_projected_expected")),
        _safe_num(r.get("active_drivers_projected_total")),
        _safe_num(r.get("active_drivers_projected_expected")),
        _safe_num(r.get("trips_completed")), _safe_num(r.get("revenue_yego_net")),
        _safe_num(r.get("active_drivers")),
        _safe_num(r.get("trips_completed_attainment_pct")),
        _safe_num(r.get("revenue_yego_net_attainment_pct")),
        _safe_num(r.get("active_drivers_attainment_pct")),
        _safe_num(r.get("trips_completed_gap_to_expected")),
        _safe_num(r.get("revenue_yego_net_gap_to_expected")),
        _safe_num(r.get("active_drivers_gap_to_expected")),
        _safe_num(r.get("trips_completed_gap_to_full")),
        _safe_num(r.get("revenue_yego_net_gap_to_full")),
        _safe_num(r.get("active_drivers_gap_to_full")),
        _safe_num(r.get("trips_completed_completion_pct")),
        _safe_num(r.get("revenue_yego_net_completion_pct")),
        _safe_num(r.get("active_drivers_completion_pct")),
        r.get("trips_completed_signal"), r.get("revenue_yego_net_signal"),
        r.get("active_drivers_signal"),
        r.get("comparison_status"), r.get("comparison_basis"),
        r.get("curve_method", r.get("trips_completed_curve_method")),
        r.get("curve_confidence", r.get("trips_completed_curve_confidence")),
        r.get("fallback_level", r.get("trips_completed_fallback_level")),
        _safe_num(r.get("expected_ratio", r.get("trips_completed_expected_ratio"))),
        r.get("projection_confidence"), r.get("projection_anomaly", False),
        _safe_num(r.get("avg_ticket")), _safe_num(r.get("commission_pct")),
        _safe_num(r.get("trips_per_driver")), _safe_num(r.get("cancel_rate_pct")),
        _safe_num(r.get("trips_cancelled")),
        r.get("week_label"), r.get("week_range_label"), r.get("week_full_label"),
        r.get("distribution_model"), _safe_num(r.get("gap_pct")),
        batch_id,
    )


def main():
    parser = argparse.ArgumentParser(description="Refresh Omniview Projection Serving Facts")
    parser.add_argument("--plan-version", required=True, help="Plan version (ej: ruta27_2026_04_21)")
    parser.add_argument("--grain", default="daily", choices=["daily", "weekly"],
                        help="Granularidad a pre-computar (default: daily)")
    parser.add_argument("--country", default=None, help="Filtro país opcional")
    parser.add_argument("--city", default=None, help="Filtro ciudad opcional")
    parser.add_argument("--year", type=int, default=None, help="Filtro año opcional")
    parser.add_argument("--month", type=int, default=None, help="Filtro mes opcional")
    parser.add_argument("--business-slice", default=None, help="Filtro business slice opcional")
    parser.add_argument("--refresh-filters-catalog", action="store_true",
                        help="Tambien refrescar serving.business_slice_filters_catalog desde la MV mensual")

    args = parser.parse_args()

    batch_id = uuid.uuid4().hex[:12]
    print(f"BATCH {batch_id} — plan_version={args.plan_version} grain={args.grain}")

    t0 = time.perf_counter()

    # 1. Computar proyección completa (runtime)
    print("Computing projection...")
    response = get_omniview_projection(
        plan_version=args.plan_version,
        grain=args.grain,
        country=args.country,
        city=args.city,
        business_slice=args.business_slice,
        year=args.year,
        month=args.month,
        debug_distribution=False,
    )
    compute_s = round(time.perf_counter() - t0, 2)
    print(f"Computed in {compute_s}s")

    data_rows = response.get("data", [])
    if not data_rows:
        print("No data rows in projection response. Nothing to refresh.")
        print(f"  meta.message: {response.get('meta', {}).get('message', 'N/A')}")
        return 0

    # 2. Extract rows
    rows = []
    unmatched_plan = 0
    unmatched_real = 0
    for r in data_rows:
        status = r.get("comparison_status", "")
        if status == "plan_without_real":
            unmatched_plan += 1
        elif status == "missing_plan":
            unmatched_real += 1
        rows.append(_extract_row(r, args.plan_version, args.grain, batch_id))

    # 3. Delete old data for this plan_version + grain (+ optional filters)
    print(f"Deleting existing facts for plan_version={args.plan_version} grain={args.grain}...")
    with get_db() as conn:
        cur = conn.cursor()
        del_clauses = ["plan_version = %s", "grain = %s"]
        del_params = [args.plan_version, args.grain]
        if args.country:
            del_clauses.append("country = %s")
            del_params.append(args.country)
        if args.city:
            del_clauses.append("city = %s")
            del_params.append(args.city)
        if args.year:
            del_clauses.append("year = %s")
            del_params.append(args.year)
        if args.month:
            del_clauses.append("month = %s")
            del_params.append(args.month)
        where = " AND ".join(del_clauses)
        cur.execute(f"DELETE FROM {TABLE} WHERE {where}", del_params)
        deleted = cur.rowcount
        conn.commit()
        cur.close()

    print(f"Deleted {deleted} existing rows.")

    # 4. Insert new rows
    t1 = time.perf_counter()
    with get_db() as conn:
        cur = conn.cursor()
        col_names = ", ".join(INSERT_COLS)
        placeholders = ", ".join(["%s"] * len(INSERT_COLS))
        sql = f"INSERT INTO {TABLE} ({col_names}) VALUES %s"
        execute_values(cur, sql, rows, template=f"({placeholders})", page_size=500)
        conn.commit()
        inserted = cur.rowcount
        cur.close()

    insert_s = round(time.perf_counter() - t1, 2)

    # 5. Filters catalog refresh (opcional)
    filters_catalog_count = 0
    if args.refresh_filters_catalog:
        t2 = time.perf_counter()
        print("Refreshing business_slice_filters_catalog...")
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM serving.business_slice_filters_catalog")
            cur.execute("""
                INSERT INTO serving.business_slice_filters_catalog
                    (country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name)
                SELECT country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
                FROM ops.v_real_business_slice_month_serving
                WHERE country IS NOT NULL AND city IS NOT NULL
                GROUP BY country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
            """)
            filters_catalog_count = cur.rowcount
            conn.commit()
            cur.close()
        filters_catalog_s = round(time.perf_counter() - t2, 2)
        print(f"Filters catalog refreshed: {filters_catalog_count} rows in {filters_catalog_s}s")
    else:
        filters_catalog_s = 0

    total_s = round(time.perf_counter() - t0, 2)

    # 5. Summary
    dates = [r.get("trip_date") or r.get("week_start") for r in data_rows if r.get("trip_date") or r.get("week_start")]
    min_date = min(dates) if dates else "N/A"
    max_date = max(dates) if dates else "N/A"

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Plan version:      {args.plan_version}")
    print(f"  Grain:             {args.grain}")
    print(f"  Rows inserted:     {inserted}")
    print(f"  Rows deleted:      {deleted}")
    print(f"  Rows in response:  {len(data_rows)}")
    print(f"  Min date:          {min_date}")
    print(f"  Max date:          {max_date}")
    print(f"  Unmatched plan:    {unmatched_plan}")
    print(f"  Unmatched real:    {unmatched_real}")
    print(f"  Compute time:      {compute_s}s")
    print(f"  Insert time:       {insert_s}s")
    if args.refresh_filters_catalog:
        print(f"  Filters catalog:   {filters_catalog_count} rows in {filters_catalog_s}s")
    print(f"  Total time:        {total_s}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
