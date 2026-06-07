"""
OV2-R.2A — V1 vs V2 Render Reconciliation
Captures served values from both V1 and V2 endpoints, compares them.
"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "ov2_render_reconciliation")
os.makedirs(OUTPUT_DIR, exist_ok=True)

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response

print("=" * 70)
print("OV2-R.2A V1 vs V2 Render Reconciliation")
print("=" * 70)

# ═══════════════════════════════════════════════════════
# V1: Direct query from fact tables (same tables V1 endpoints use)
# ═══════════════════════════════════════════════════════
v1_rows = []
v2_rows = []
comparisons = []

with get_db() as c:
    cur = c.cursor(cursor_factory=RealDictCursor)

    # V1 Daily
    print("\n--- V1 DAILY ---")
    cur.execute("""
        SELECT trip_date AS period, business_slice_name,
               SUM(trips_completed) AS trips, SUM(revenue_yego_final) AS revenue,
               SUM(active_drivers) AS drivers, AVG(avg_ticket) AS ticket,
               AVG(trips_per_driver) AS tpd
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND trip_date BETWEEN '2026-06-01' AND '2026-06-05'
        GROUP BY trip_date, business_slice_name ORDER BY trip_date, business_slice_name
    """)
    for r in cur.fetchall():
        d = dict(r)
        d["grain"] = "day"; d["source"] = "V1"
        v1_rows.append(d)
        if d["trips"]:
            print(f"  V1 day {str(d['period'])[:10]} {d['business_slice_name']:20s}: trips={d['trips']} rev={float(d['revenue'] or 0):.1f}")

    # V1 Weekly
    print("\n--- V1 WEEKLY ---")
    cur.execute("""
        SELECT week_start AS period, business_slice_name,
               SUM(trips_completed) AS trips, SUM(revenue_yego_final) AS revenue,
               SUM(active_drivers) AS drivers, AVG(avg_ticket) AS ticket, AVG(trips_per_driver) AS tpd
        FROM ops.real_business_slice_week_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND week_start BETWEEN '2026-03-23' AND '2026-04-25'
        GROUP BY week_start, business_slice_name ORDER BY week_start, business_slice_name
    """)
    for r in cur.fetchall():
        d = dict(r); d["grain"] = "week"; d["source"] = "V1"
        v1_rows.append(d)

    # V1 Monthly
    print("\n--- V1 MONTHLY ---")
    cur.execute("""
        SELECT month AS period, business_slice_name,
               SUM(trips_completed) AS trips, SUM(revenue_yego_final) AS revenue,
               SUM(active_drivers) AS drivers, AVG(avg_ticket) AS ticket, AVG(trips_per_driver) AS tpd
        FROM ops.real_business_slice_month_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND month BETWEEN '2026-01-01' AND '2026-06-01'
        GROUP BY month, business_slice_name ORDER BY month, business_slice_name
    """)
    for r in cur.fetchall():
        d = dict(r); d["grain"] = "month"; d["source"] = "V1"
        v1_rows.append(d)
    cur.close()

# ═══════════════════════════════════════════════════════
# V2: Matrix endpoint with all metrics
# ═══════════════════════════════════════════════════════
v2_queries = [
    ("day", "orders", "2026-06-01", "2026-06-05"),
    ("day", "revenue", "2026-06-01", "2026-06-05"),
    ("day", "active_drivers", "2026-06-01", "2026-06-05"),
    ("day", "avg_ticket", "2026-06-01", "2026-06-05"),
    ("day", "trips_per_driver", "2026-06-01", "2026-06-05"),
    ("week", "orders", "2026-03-23", "2026-04-25"),
    ("week", "revenue", "2026-03-23", "2026-04-25"),
    ("week", "active_drivers", "2026-03-23", "2026-04-25"),
    ("month", "orders", "2026-01-01", "2026-06-01"),
    ("month", "revenue", "2026-01-01", "2026-06-01"),
    ("month", "active_drivers", "2026-01-01", "2026-06-01"),
]

print("\n--- V2 MATRIX ---")
for grain, metric, d1, d2 in v2_queries:
    r = build_matrix_response("CT_TRIPS_2026", grain, d1, d2, metric_id=metric)
    d = r.to_dict()
    cells = d.get("cells", [])
    for cell in cells:
        if cell.get("value") is not None:
            v2_rows.append({
                "grain": grain, "metric_id": metric, "period": cell["period"],
                "business_slice_name": cell.get("row_id", "").replace("row_", "").replace("_", " ").title(),
                "value": cell["value"], "source": "V2",
            })

print(f"\n  V1 rows captured: {len(v1_rows)}")
print(f"  V2 cells captured: {len(v2_rows)}")

# ═══════════════════════════════════════════════════════
# COMPARISON: Match V1 rows to V2 cells by grain+period+slice+metric
# ═══════════════════════════════════════════════════════
metric_map = {"orders": "trips", "revenue": "revenue", "active_drivers": "drivers",
              "avg_ticket": "ticket", "trips_per_driver": "tpd"}

print("\n--- COMPARISON ---")
match_count = 0; minor = 0; major = 0; v1only = 0; v2only = 0; total = 0

for v1 in v1_rows:
    grain = v1["grain"]
    period = str(v1["period"])[:10]
    slice_name = v1["business_slice_name"]
    for v2 in v2_rows:
        if v2["grain"] != grain or v2["period"] != period:
            continue
        v2_slice = v2["business_slice_name"]
        if v2_slice.lower().replace(" ", "_") != slice_name.lower().replace(" ", "_"):
            continue
        mkey = metric_map.get(v2["metric_id"])
        if not mkey:
            continue
        v1_val = float(v1.get(mkey, 0) or 0)
        v2_val = float(v2.get("value", 0) or 0)
        if v1_val == 0 and v2_val == 0: continue
        delta_pct = abs((v1_val - v2_val) / v1_val * 100) if v1_val != 0 else (0 if v2_val == 0 else 100)
        status = "MATCH" if delta_pct <= 0.5 else "MINOR_DELTA" if delta_pct <= 2 else "MAJOR_DELTA"
        comparisons.append({"grain": grain, "period": period, "slice": slice_name,
                            "metric": mkey, "v1": v1_val, "v2": v2_val,
                            "delta_pct": round(delta_pct, 3), "status": status})
        if status == "MATCH": match_count += 1
        elif status == "MINOR_DELTA": minor += 1
        else: major += 1
        total += 1

print(f"  MATCH: {match_count}")
print(f"  MINOR_DELTA: {minor}")
print(f"  MAJOR_DELTA: {major}")
print(f"  Total comparisons: {total}")

if major > 0:
    print(f"\n  MAJOR_DELTA details:")
    for c in comparisons:
        if c["status"] == "MAJOR_DELTA":
            print(f"    {c['grain']} {c['period']} {c['slice']} {c['metric']}: V1={c['v1']} V2={c['v2']} delta={c['delta_pct']:.1f}%")

# ═══════════════════════════════════════════════════════
# Write output
# ═══════════════════════════════════════════════════════
if v1_rows:
    with open(os.path.join(OUTPUT_DIR, "ov1_render_values.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=v1_rows[0].keys())
        w.writeheader(); w.writerows(v1_rows)
if v2_rows:
    with open(os.path.join(OUTPUT_DIR, "ov2_render_values.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(v2_rows[0].keys()))
        w.writeheader(); w.writerows(v2_rows)
if comparisons:
    with open(os.path.join(OUTPUT_DIR, "v1_vs_v2_render_reconciliation.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=comparisons[0].keys())
        w.writeheader(); w.writerows(comparisons)

summary = [
    "# V1 vs V2 Render Reconciliation Summary",
    "",
    f"**Comparisons:** {total}",
    f"**MATCH:** {match_count}",
    f"**MINOR_DELTA:** {minor}",
    f"**MAJOR_DELTA:** {major}",
    "",
    "## Verdict",
    "",
    f"Feature parity: {'PASS' if major == 0 and match_count > 0 else 'PARTIAL' if match_count > minor else 'BLOCKED'}",
]
with open(os.path.join(OUTPUT_DIR, "v1_vs_v2_render_reconciliation_summary.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(summary))

print(f"\n[output] {OUTPUT_DIR}")
print("Done.")
