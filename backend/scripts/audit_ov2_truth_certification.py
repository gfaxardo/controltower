"""
OV2-T.1 — Omniview V2 Truth Certification: KPIs, Rollups, Revenue, V1 vs V2, Snapshots.
"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "ov2_truth")
os.makedirs(OUTPUT_DIR, exist_ok=True)

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

print("=" * 70)
print("OV2-T.1 TRUTH CERTIFICATION AUDIT")
print("=" * 70)

results = {"rollups": [], "revenue": [], "v1v2": [], "snapshot": []}

with get_db() as c:
    cur = c.cursor(cursor_factory=RealDictCursor)

    # ═══════════════════════════════════════════════════════
    # ROLLUP RECONCILIATION: week vs SUM(day)
    # ═══════════════════════════════════════════════════════
    print("\n--- ROLLUP: week_fact vs SUM(day_fact) ---")
    cur.execute("""
        WITH day_agg AS (
            SELECT
                date_trunc('week', trip_date)::date AS week_start,
                SUM(trips_completed) AS day_trips,
                SUM(revenue_yego_final) AS day_revenue,
                SUM(active_drivers) AS day_drivers,
                AVG(avg_ticket) AS day_ticket,
                AVG(trips_per_driver) AS day_tpd
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
            GROUP BY 1
        ),
        week_agg AS (
            SELECT week_start, SUM(trips_completed) AS week_trips,
                   SUM(revenue_yego_final) AS week_revenue,
                   SUM(active_drivers) AS week_drivers,
                   AVG(avg_ticket) AS week_ticket,
                   AVG(trips_per_driver) AS week_tpd
            FROM ops.real_business_slice_week_fact
            WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
            GROUP BY 1
        )
        SELECT d.week_start,
               d.day_trips, w.week_trips,
               d.day_revenue, w.week_revenue,
               d.day_drivers, w.week_drivers
        FROM day_agg d
        JOIN week_agg w ON d.week_start = w.week_start
        ORDER BY d.week_start DESC
        LIMIT 8
    """)
    for r in cur.fetchall():
        d = dict(r)
        trips_delta = float(d["day_trips"] or 0) - float(d["week_trips"] or 0)
        rev_delta = float(d["day_revenue"] or 0) - float(d["week_revenue"] or 0)
        trips_pct = abs(trips_delta / float(d["week_trips"] or 1) * 100)
        rev_pct = abs(rev_delta / float(d["week_revenue"] or 1) * 100) if d["week_revenue"] else None
        status = "MATCH" if trips_pct <= 0.5 else "MINOR_DELTA" if trips_pct <= 2 else "MAJOR_DELTA"
        results["rollups"].append({
            "week": str(d["week_start"])[:10], "trips_day": d["day_trips"], "trips_week": d["week_trips"],
            "trips_delta_pct": round(trips_pct, 2), "rev_delta_pct": round(rev_pct, 2) if rev_pct else None,
            "status": status,
        })
        print(f"  {str(d['week_start'])[:10]}: trips day={d['day_trips']} week={d['week_trips']} delta={trips_pct:.2f}% [{status}]")

    # ═══════════════════════════════════════════════════════
    # ROLLUP: month vs SUM(day)
    # ═══════════════════════════════════════════════════════
    print("\n--- ROLLUP: month_fact vs SUM(day_fact) ---")
    cur.execute("""
        WITH day_agg AS (
            SELECT date_trunc('month', trip_date)::date AS mth,
                   SUM(trips_completed) AS day_trips, SUM(revenue_yego_final) AS day_revenue
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
            GROUP BY 1
        ),
        month_agg AS (
            SELECT month AS mth, SUM(trips_completed) AS month_trips, SUM(revenue_yego_final) AS month_revenue
            FROM ops.real_business_slice_month_fact
            WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
            GROUP BY 1
        )
        SELECT d.mth, d.day_trips, m.month_trips, d.day_revenue, m.month_revenue
        FROM day_agg d JOIN month_agg m ON d.mth = m.mth
        ORDER BY d.mth DESC LIMIT 6
    """)
    for r in cur.fetchall():
        d = dict(r)
        trips_delta = float(d["day_trips"] or 0) - float(d["month_trips"] or 0)
        trips_pct = abs(trips_delta / float(d["month_trips"] or 1) * 100)
        status = "MATCH" if trips_pct <= 0.5 else "MINOR_DELTA" if trips_pct <= 2 else "MAJOR_DELTA"
        results["rollups"].append({
            "month": str(d["mth"])[:7], "trips_day": d["day_trips"], "trips_month": d["month_trips"],
            "trips_delta_pct": round(trips_pct, 2), "status": status,
        })
        print(f"  {str(d['mth'])[:7]}: trips day={d['day_trips']} month={d['month_trips']} delta={trips_pct:.2f}% [{status}]")

    # ═══════════════════════════════════════════════════════
    # REVENUE TRUTH: revenue_yego_final vs _net, NULLs
    # ═══════════════════════════════════════════════════════
    print("\n--- REVENUE TRUTH ---")
    cur.execute("""
        SELECT
            business_slice_name,
            SUM(trips_completed) AS trips,
            SUM(revenue_yego_final) AS rev_final,
            COUNT(*) FILTER (WHERE revenue_yego_final IS NULL) AS null_final,
            COUNT(*) FILTER (WHERE revenue_yego_final IS NOT NULL AND revenue_yego_final = 0) AS zero_final,
            COUNT(*) FILTER (WHERE revenue_yego_final IS NULL AND trips_completed > 0) AS trips_no_rev
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
        GROUP BY business_slice_name
        ORDER BY trips_no_rev DESC, business_slice_name
    """)
    for r in cur.fetchall():
        d = dict(r)
        null_f = int(d["null_final"] or 0)
        trips_nr = int(d["trips_no_rev"] or 0)
        status = "CERTIFIED" if trips_nr == 0 else f"PARTIAL ({trips_nr} days with trips but no revenue)"
        results["revenue"].append({
            "slice": d["business_slice_name"], "trips": d["trips"], "rev_final": d["rev_final"],
            "null_final": null_f, "zero_final": d["zero_final"], "trips_no_rev": trips_nr, "status": status,
        })
        print(f"  {d['business_slice_name']:20s}: trips_no_rev={trips_nr} null={null_f} zero={d['zero_final']} [{status}]")

    # ═══════════════════════════════════════════════════════
    # V1 vs V2: Same table, same query — just source alignment
    # ═══════════════════════════════════════════════════════
    print("\n--- V1 vs V2 SOURCE ALIGNMENT ---")
    cur.execute("""
        SELECT
            trip_date::text AS period,
            SUM(trips_completed) AS trips,
            SUM(revenue_yego_final) AS revenue,
            SUM(active_drivers) AS drivers,
            AVG(avg_ticket) AS ticket,
            AVG(trips_per_driver) AS tpd,
            COUNT(DISTINCT business_slice_name) AS slices
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND trip_date >= '2026-06-01'
        GROUP BY trip_date ORDER BY trip_date DESC
    """)
    for r in cur.fetchall():
        d = dict(r)
        results["v1v2"].append({"period": d["period"], "trips": d["trips"], "revenue": d["revenue"],
                                 "drivers": d["drivers"], "ticket": round(float(d["ticket"] or 0), 2),
                                 "tpd": round(float(d["tpd"] or 0), 2), "slices": d["slices"]})
        print(f"  {d['period']}: trips={d['trips']} rev={d['revenue']} drivers={d['drivers']} slices={d['slices']}")

    # ═══════════════════════════════════════════════════════
    # SNAPSHOT TRUTH
    # ═══════════════════════════════════════════════════════
    print("\n--- SNAPSHOT TRUTH ---")
    cur.execute("""
        SELECT source_system, grain, operating_date, payload_type, status,
               coverage_pct, freshness_status, build_ms,
               generated_at::text AS generated
        FROM ops.omniview_v2_serving_snapshot
        ORDER BY generated_at DESC
    """)
    for r in cur.fetchall():
        d = dict(r)
        results["snapshot"].append(d)
        print(f"  {d['source_system']}/{d['grain']}/{d['operating_date']}/{d['payload_type']}: {d['status']} build={d['build_ms']}ms cov={d['coverage_pct']}%")

    cur.close()

# ═══════════════════════════════════════════════════════
# Write CSVs
# ═══════════════════════════════════════════════════════
# Write rollup CSV separately for week and month
week_data = [r for r in results["rollups"] if "week" in r]
month_data = [r for r in results["rollups"] if "month" in r]
if week_data:
    with open(os.path.join(OUTPUT_DIR, "rollup_week.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=week_data[0].keys())
        w.writeheader(); w.writerows(week_data)
if month_data:
    with open(os.path.join(OUTPUT_DIR, "rollup_month.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=month_data[0].keys())
        w.writeheader(); w.writerows(month_data)

# Write other CSVs
for name in ["revenue", "v1v2", "snapshot"]:
    data = results.get(name, [])
    if data:
        csv_path = os.path.join(OUTPUT_DIR, f"{name}_truth.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=data[0].keys())
            w.writeheader(); w.writerows(data)

# ═══════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("CERTIFICATION SUMMARY")
print("=" * 70)

# Rollups
deltas = [r["trips_delta_pct"] for r in results["rollups"] if "trips_delta_pct" in r]
if deltas:
    max_d = max(deltas)
    print(f"\nROLLUPS: max delta={max_d:.2f}% — {'CERTIFIED' if max_d <= 0.5 else 'PARTIAL' if max_d <= 2 else 'MAJOR_DELTA'}")

# Revenue
no_rev = [r for r in results["revenue"] if r["trips_no_rev"] > 0]
print(f"REVENUE: {len(no_rev)} slices with trips but no revenue — {'CERTIFIED' if not no_rev else 'PARTIAL'}")

# V1 vs V2
print(f"V1 vs V2: {len(results['v1v2'])} days audited — using same source table (ops.real_business_slice_day_fact)")

# Snapshots
ready = [s for s in results["snapshot"] if s["status"] == "READY"]
print(f"SNAPSHOTS: {len(ready)}/{len(results['snapshot'])} READY")

print(f"\n[output] {OUTPUT_DIR}")
print("Done.")
