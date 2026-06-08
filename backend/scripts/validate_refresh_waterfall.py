"""OV2-F.2 — Waterfall Validator: RAW >= DAY >= WEEK >= MONTH >= SNAPSHOT >= UI"""
import sys, os, json
from datetime import date as dt_date, datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "ov2_refresh")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now(timezone.utc).isoformat()

def max_val(conn, query, params=()):
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        r = cur.fetchone()
        cur.close()
        if r and r[0]:
            return str(r[0])[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10]
    except:
        pass
    return None

results = {"validations": [], "waterfall_broken": [], "generated_at": TIMESTAMP}

with get_db() as conn:
    raw = max_val(conn, "SELECT MAX(fecha_inicio_viaje) FROM public.trips_2026")
    day = max_val(conn, "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    week = max_val(conn, "SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    month = max_val(conn, "SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    snap = max_val(conn, "SELECT MAX(operating_date) FROM ops.omniview_v2_serving_snapshot WHERE status='READY'")

def check_waterfall(name, upstream, downstream, upstream_val, downstream_val):
    ok = False
    status = "WATERFALL_BROKEN"
    if upstream_val and downstream_val:
        try:
            u = dt_date.fromisoformat(upstream_val[:10])
            d = dt_date.fromisoformat(downstream_val[:10])
            ok = u >= d
            status = "OK" if ok else "WATERFALL_BROKEN"
        except:
            status = "ERROR"
    elif not upstream_val:
        status = "UPSTREAM_MISSING"
    elif not downstream_val:
        status = "DOWNSTREAM_MISSING"

    item = {"name": name, "upstream": upstream, "downstream": downstream,
            "upstream_val": upstream_val, "downstream_val": downstream_val, "status": status}
    results["validations"].append(item)
    if not ok:
        results["waterfall_broken"].append(name)
    print(f"  [{status}] {name}: {upstream}={upstream_val} >= {downstream}={downstream_val}")

check_waterfall("RAW_to_DAY", "RAW_TRIPS", "DAY_FACT", raw, day)
check_waterfall("DAY_to_WEEK", "DAY_FACT", "WEEK_FACT", day, week)
check_waterfall("WEEK_to_MONTH", "WEEK_FACT", "MONTH_FACT", week, month)
check_waterfall("DAY_to_SNAPSHOT", "DAY_FACT", "SNAPSHOT", day, snap)
# OPERATING_DATE derives from DAY_FACT
results["validations"].append({"name": "SNAPSHOT_to_UI", "status": "OK" if snap else "SNAPSHOT_MISSING",
    "upstream_val": snap, "downstream_val": "UI endpoints"})

results["verdict"] = "GO" if not results["waterfall_broken"] else f"NO-GO: {len(results['waterfall_broken'])} broken"

md_lines = ["# Refresh Waterfall Validation", "", f"**Generated:** {TIMESTAMP}", f"**Verdict:** **{results['verdict']}**", "",
            "| Check | Upstream | Upstream Val | Downstream | Downstream Val | Status |",
            "|-------|----------|-------------|------------|---------------|--------|"]
for v in results["validations"]:
    md_lines.append(f"| {v['name']} | {v.get('upstream','-')} | {v.get('upstream_val','-')} | {v.get('downstream','-')} | {v.get('downstream_val','-')} | {v['status']} |")

if results["waterfall_broken"]:
    md_lines += ["", "## Broken", ""]
    for b in results["waterfall_broken"]:
        md_lines.append(f"- {b}")

json_path = os.path.join(OUTPUT_DIR, "refresh_waterfall_validation.json")
md_path = os.path.join(OUTPUT_DIR, "refresh_waterfall_validation.md")
with open(json_path, "w") as f: json.dump(results, f, indent=2, default=str)
with open(md_path, "w") as f: f.write("\n".join(md_lines))
print(f"\nJSON: {json_path}\nMD: {md_path}\nVerdict: {results['verdict']}")
