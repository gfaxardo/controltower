"""
OV2-F.1 — Refresh Freshness Audit
Measures max dates across the full data pipeline: raw → enriched → facts → snapshots → UI.
"""
import sys, os, csv, json
from datetime import date as dt_date, datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "ov2_refresh")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now(timezone.utc).isoformat()

results = []
today = dt_date.today().isoformat()

def log(grain, layer, source, max_date, expected_today=None, status="OK"):
    gap = None
    if max_date and expected_today:
        try:
            gap = (dt_date.fromisoformat(str(max_date)[:10]) - dt_date.fromisoformat(expected_today)).days
        except:
            pass
    results.append({
        "grain": grain, "layer": layer, "source": source,
        "max_date": str(max_date)[:10] if max_date else None,
        "expected": expected_today,
        "gap_days": gap,
        "status": status,
    })

def fetch_max(conn, query, params=()):
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        r = cur.fetchone()
        if r and r[0]:
            return str(r[0])[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10]
    except:
        pass
    finally:
        cur.close()
    return None

with get_db() as conn:
    # ── LAYER 0: RAW ──
    log("day", "RAW_TRIPS", "public.trips_2026",
        fetch_max(conn, "SELECT MAX(fecha_inicio_viaje) FROM public.trips_2026"), today, "OK")
    log("day", "RAW_YANGO", "raw_yango.mv_orders_day",
        fetch_max(conn, "SELECT MAX(order_date) FROM raw_yango.mv_orders_day WHERE park_id='08e20910d81d42658d4334d3f6d10ac0'"), today)

    # ── LAYER 1: SOURCE COVERAGE ──
    log("day", "SOURCE_COVERAGE", "raw_yango.mv_source_coverage_day",
        fetch_max(conn, "SELECT MAX(coverage_date) FROM raw_yango.mv_source_coverage_day"), today)

    # ── LAYER 2: DAY FACT ──
    max_day = fetch_max(conn,
        "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    log("day", "DAY_FACT", "ops.real_business_slice_day_fact", max_day, today, "FRESH" if max_day else "STALE")

    # ── LAYER 3: WEEK FACT ──
    max_week = fetch_max(conn,
        "SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    log("week", "WEEK_FACT", "ops.real_business_slice_week_fact", max_week, today)

    # ── LAYER 4: MONTH FACT ──
    max_month = fetch_max(conn,
        "SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    log("month", "MONTH_FACT", "ops.real_business_slice_month_fact", max_month, today)

    # ── LAYER 5: SNAPSHOTS ──
    max_snapshot = fetch_max(conn,
        "SELECT MAX(operating_date) FROM ops.omniview_v2_serving_snapshot WHERE status='READY'")
    log("day", "SNAPSHOT", "ops.omniview_v2_serving_snapshot", max_snapshot, today,
        "FRESH" if max_snapshot and max_snapshot >= today else "STALE")

    # ── LAYER 6: OPERATING DATE ──
    op_date = fetch_max(conn,
        "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    log("day", "OPERATING_DATE", "from day_fact MAX(trip_date)", op_date, today,
        "OK" if op_date else "MISSING")

    # ── REVENUE AVAILABILITY ──
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE revenue_yego_final IS NOT NULL AND revenue_yego_final > 0) AS has_rev,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE revenue_yego_final IS NOT NULL AND revenue_yego_final > 0) / NULLIF(COUNT(*), 0), 1) AS rev_pct
            FROM ops.real_business_slice_month_fact
            WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
        """)
        rev = dict(cur.fetchone())
        results.append({
            "grain": "month", "layer": "REVENUE", "source": "month_fact.revenue_yego_final",
            "max_date": None, "expected": None, "gap_days": None,
            "status": f"{rev['has_rev']}/{rev['total']} ({rev['rev_pct']}%)"
        })
    finally:
        cur.close()

    # ── SLICE COVERAGE ──
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT business_slice_name) AS slices
            FROM ops.real_business_slice_month_fact
            WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
        """)
        slices = dict(cur.fetchone())
        results.append({
            "grain": "month", "layer": "SLICE_COVERAGE", "source": "month_fact slices (Lima)",
            "max_date": None, "expected": "6", "gap_days": None,
            "status": f"{slices['slices']} slices"
        })
    finally:
        cur.close()

    # ── PLAN VERSION ──
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT plan_version FROM ops.plan_trips_monthly ORDER BY created_at DESC LIMIT 1")
        pv = dict(cur.fetchone())
        results.append({
            "grain": "month", "layer": "PLAN_VERSION", "source": "ops.plan_trips_monthly",
            "max_date": None, "expected": None, "gap_days": None,
            "status": pv["plan_version"] if pv else "MISSING"
        })
    finally:
        cur.close()

# ── WRITE CSV ──
csv_path = os.path.join(OUTPUT_DIR, "freshness_audit.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["grain", "layer", "source", "max_date", "expected", "gap_days", "status"])
    w.writeheader()
    w.writerows(results)

# ── WRITE MD ──
md_lines = ["# OV2 Refresh Freshness Audit", "", f"**Generated:** {TIMESTAMP}", "",
            "| Layer | Grain | Source | Max Date | Gap (days) | Status |",
            "|-------|-------|--------|----------|------------|--------|"]
for r in results:
    gap = r["gap_days"] if r["gap_days"] is not None else "-"
    md_lines.append(f"| {r['layer']} | {r['grain']} | {r['source']} | {r['max_date'] or '-'} | {gap} | {r['status']} |")

# Summary
critical = [r for r in results if r.get("gap_days") is not None and r["gap_days"] < -2]
stale = [r for r in results if r.get("gap_days") is not None and r["gap_days"] <= -1]
md_lines += ["", "## Summary", "",
             f"- Critical gaps (>2 days): {len(critical)}",
             f"- Stale facts (>=1 day): {len(stale)}",
             f"- Layers with data: {sum(1 for r in results if r['max_date'])}",
             ""]

md_path = os.path.join(OUTPUT_DIR, "freshness_summary.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"CSV: {csv_path}")
print(f"MD:  {md_path}")
for r in results:
    gap = r["gap_days"] if r["gap_days"] is not None else "-"
    print(f"  {r['layer']:20s} {r['grain']:5s} max={str(r['max_date']):12s} gap={str(gap):4s} [{r['status']}]")
