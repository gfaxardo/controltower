"""OV2-D.1 — Slice Inventory & Governance Audit"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "omniview_v2_slice_governance")
os.makedirs(OUTPUT_DIR, exist_ok=True)

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

TABLES = {
    "day": ("ops.real_business_slice_day_fact", "trip_date"),
    "week": ("ops.real_business_slice_week_fact", "week_start"),
    "month": ("ops.real_business_slice_month_fact", "month"),
}

def _fmt(v):
    if v is None: return "NULL"
    if hasattr(v, 'isoformat'): return v.isoformat()
    return str(v)

print("=" * 60)
print("OV2-D.1 Slice Governance Audit")
print("=" * 60)

all_slices = {}
anomalies = []

with get_db() as c:
    cur = c.cursor(cursor_factory=RealDictCursor)

    for grain, (table, date_field) in TABLES.items():
        print(f"\n--- {grain.upper()} ({table}) ---")

        # Get slices with stats
        cur.execute(f"""
            SELECT
                business_slice_name,
                COUNT(*) AS row_count,
                MIN({date_field}) AS first_seen,
                MAX({date_field}) AS last_seen,
                COUNT(DISTINCT {date_field}) AS days_active,
                SUM(trips_completed) AS total_trips,
                SUM(revenue_yego_final) AS total_revenue,
                SUM(active_drivers) AS total_drivers,
                COUNT(DISTINCT country) AS countries,
                COUNT(DISTINCT city) AS cities
            FROM {table}
            WHERE business_slice_name IS NOT NULL
            GROUP BY business_slice_name
            ORDER BY business_slice_name
        """)

        for r in cur.fetchall():
            d = dict(r)
            name = d["business_slice_name"]
            if name not in all_slices:
                all_slices[name] = {
                    "name": name,
                    "grains": {},
                    "first_seen_global": d["first_seen"],
                    "last_seen_global": d["last_seen"],
                }
            all_slices[name]["grains"][grain] = {
                "row_count": d["row_count"],
                "first_seen": _fmt(d["first_seen"]),
                "last_seen": _fmt(d["last_seen"]),
                "days_active": d["days_active"],
                "total_trips": int(d["total_trips"] or 0),
                "total_revenue": float(d["total_revenue"] or 0),
                "total_drivers": int(d["total_drivers"] or 0),
            }

            trips = int(d["total_trips"] or 0)
            rev = float(d["total_revenue"] or 0)
            drivers = int(d["total_drivers"] or 0)

            print(f"  {name:30s} rows={d['row_count']:4d} trips={trips:>8,} rev={rev:>10,.1f} drivers={drivers:>5,} dates={d['days_active']}")

            # Anomaly detection
            if trips > 0 and rev == 0:
                anomalies.append({"slice": name, "grain": grain, "type": "TRIPS_NO_REVENUE", "trips": trips})
            if rev > 0 and trips == 0:
                anomalies.append({"slice": name, "grain": grain, "type": "REVENUE_NO_TRIPS", "revenue": rev})
            if drivers == 0 and trips > 0:
                anomalies.append({"slice": name, "grain": grain, "type": "NO_DRIVERS_BUT_TRIPS", "trips": trips})

    # Cross-grain consistency
    print("\n--- CROSS-GRAIN CONSISTENCY ---")
    slice_names = sorted(all_slices.keys())
    for name in slice_names:
        grains_present = list(all_slices[name]["grains"].keys())
        missing = [g for g in TABLES if g not in grains_present]
        if missing:
            print(f"  {name}: present in {grains_present}, MISSING in {missing}")
            anomalies.append({"slice": name, "grain": ",".join(missing), "type": "MISSING_GRAIN"})

        # Check name consistency across grains
        for g in grains_present:
            if all_slices[name]["grains"][g]["total_trips"] == 0:
                anomalies.append({"slice": name, "grain": g, "type": "ZERO_TRIPS"})

    cur.close()

# Inventory CSV
csv_path = os.path.join(OUTPUT_DIR, "slice_inventory.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["slice_name", "grain", "row_count", "first_seen", "last_seen", "days_active", "total_trips", "total_revenue", "total_drivers"])
    for name, info in sorted(all_slices.items()):
        for grain, ginfo in info["grains"].items():
            w.writerow([name, grain, ginfo["row_count"], ginfo["first_seen"], ginfo["last_seen"],
                        ginfo["days_active"], ginfo["total_trips"], ginfo["total_revenue"], ginfo["total_drivers"]])

# Anomalies CSV
anom_path = os.path.join(OUTPUT_DIR, "slice_anomalies.csv")
with open(anom_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["slice", "grain", "type", "details"])
    for a in anomalies:
        w.writerow([a["slice"], a["grain"], a["type"], str(a.get("trips", a.get("revenue", "")))])

# Summary MD
md = [
    "# OV2-D.1 Slice Governance Summary",
    "",
    f"**Slices found:** {len(all_slices)}",
    f"**Anomalies:** {len(anomalies)}",
    "",
    "## Slice Inventory",
    "",
    "| Slice | Day | Week | Month | Trips (day) | Revenue (day) |",
    "|-------|-----|------|-------|-------------|---------------|",
]
for name, info in sorted(all_slices.items()):
    day_t = info["grains"].get("day", {}).get("total_trips", 0)
    day_r = info["grains"].get("day", {}).get("total_revenue", 0)
    has_d = "X" if "day" in info["grains"] else "-"
    has_w = "X" if "week" in info["grains"] else "-"
    has_m = "X" if "month" in info["grains"] else "-"
    md.append(f"| {name} | {has_d} | {has_w} | {has_m} | {day_t:,} | {day_r:,.1f} |")

if anomalies:
    md += ["", "## Anomalies", "", "| Slice | Grain | Type |", "|-------|-------|------|"]
    for a in anomalies[:20]:
        md.append(f"| {a['slice']} | {a['grain']} | {a['type']} |")

summary_path = os.path.join(OUTPUT_DIR, "slice_governance_summary.md")
with open(summary_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

# Matrix inventory
print("\n--- MATRIX SLICE INTEGRATION ---")
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
for grain in ["day", "week", "month"]:
    resp = build_matrix_response("CT_TRIPS_2026", grain, "2026-06-01", "2026-06-01" if grain == "day" else "2026-03-01")
    d = resp.to_dict()
    rows = [r["label"] for r in d.get("rows", [])]
    print(f"  Matrix {grain}: {len(rows)} rows: {rows}")

# CT vs Matrix consistency
day_slices = set(all_slices.keys())
matrix_day = set()
resp = build_matrix_response("CT_TRIPS_2026", "day", "2026-06-04", "2026-06-04")
for r in resp.to_dict().get("rows", []):
    matrix_day.add(r["label"])
only_ct = day_slices - matrix_day
only_matrix = matrix_day - day_slices
print(f"\n  CT slices: {sorted(day_slices)}")
print(f"  Matrix rows: {sorted(matrix_day)}")
if only_ct: print(f"  Only in CT: {only_ct}")
if only_matrix: print(f"  Only in Matrix: {only_matrix}")

print(f"\n[output] {OUTPUT_DIR}")
print("Done.")
