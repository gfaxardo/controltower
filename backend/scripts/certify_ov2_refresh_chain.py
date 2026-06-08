"""OV2-F.1 — Refresh Chain Certification Script"""
import sys, os, json, csv
from datetime import date as dt_date, datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "ov2_refresh")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now(timezone.utc).isoformat()
TODAY = dt_date.today()

certification = {"generated_at": TIMESTAMP, "checks": [], "verdict": "PENDING"}

def check(name, grain, query_or_value, params=(), threshold=None, pass_condition=None):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if callable(query_or_value):
                value = query_or_value(conn)
            elif isinstance(query_or_value, str):
                cur.execute(query_or_value, params)
                value = dict(cur.fetchone()) if cur.rowcount > 0 else {}
            else:
                value = query_or_value

            passed = pass_condition(value, threshold) if pass_condition else True
            status = "PASS" if passed else "FAIL"

            check_result = {"name": name, "grain": grain, "status": status, "data": value}
            if threshold is not None:
                check_result["threshold"] = str(threshold)
            certification["checks"].append(check_result)
            print(f"  [{status}] {name}")
        except Exception as e:
            certification["checks"].append({"name": name, "grain": grain, "status": "ERROR", "data": {"error": str(e)[:200]}})
            print(f"  [ERROR] {name}: {str(e)[:100]}")
        finally:
            cur.close()

# ── 1. RAW TRIPS ──
check("RAW trips freshness", "day",
    "SELECT MAX(fecha_inicio_viaje)::text AS max_date, COUNT(*) AS rows FROM public.trips_2026",
    pass_condition=lambda v, t: v.get("max_date") and dt_date.fromisoformat(v["max_date"][:10]) >= TODAY - timedelta(days=3))

# ── 2. DAY FACT ──
check("day_fact freshness", "day",
    "SELECT MAX(trip_date)::text AS max_date FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
    pass_condition=lambda v, t: v.get("max_date") and dt_date.fromisoformat(v["max_date"][:10]) >= TODAY - timedelta(days=3))

# ── 3. WEEK FACT ──
check("week_fact freshness", "week",
    "SELECT MAX(week_start)::text AS max_date FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
    pass_condition=lambda v, t: v.get("max_date") and dt_date.fromisoformat(v["max_date"][:10]) >= TODAY - timedelta(days=60))

# ── 4. MONTH FACT ──
check("month_fact freshness", "month",
    "SELECT MAX(month)::text AS max_date, COUNT(*) AS rows FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
    pass_condition=lambda v, t: v.get("max_date") is not None)

# ── 5. SNAPSHOT ──
check("snapshot freshness", "day",
    "SELECT MAX(operating_date)::text AS max_date, COUNT(*) FILTER (WHERE status='READY') AS ready, COUNT(*) FILTER (WHERE status='FAILED') AS failed FROM ops.omniview_v2_serving_snapshot",
    pass_condition=lambda v, t: v.get("ready", 0) > 0)

# ── 6. OPERATING DATE ──
check("operating-date consistency", "day",
    "SELECT MAX(trip_date)::text AS max_date FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
    pass_condition=lambda v, t: v.get("max_date") is not None)

# ── 7. REVENUE ──
check("revenue availability", "month",
    "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE revenue_yego_final IS NOT NULL AND revenue_yego_final > 0) AS has_rev, ROUND(100.0*COUNT(*) FILTER (WHERE revenue_yego_final IS NOT NULL AND revenue_yego_final > 0)/NULLIF(COUNT(*),0),1) AS pct FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
    threshold=80,
    pass_condition=lambda v, t: v.get("pct", 0) >= t)

# ── 8. SLICE COVERAGE ──
check("slice coverage (Lima)", "month",
    "SELECT COUNT(DISTINCT business_slice_name) AS slices FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
    threshold=5,
    pass_condition=lambda v, t: v.get("slices", 0) >= t)

# ── 9. PLAN VERSION ──
check("plan version availability", "month",
    "SELECT COUNT(DISTINCT plan_version) AS versions FROM ops.plan_trips_monthly",
    threshold=1,
    pass_condition=lambda v, t: v.get("versions", 0) >= t)

# ── 10. YANGO RAW ──
check("Yango raw availability", "day",
    "SELECT MAX(order_date)::text AS max_date, COUNT(*) AS rows FROM raw_yango.mv_orders_day WHERE park_id='08e20910d81d42658d4334d3f6d10ac0'",
    pass_condition=lambda v, t: v.get("max_date") is not None)

# ── VERDICT ──
failures = [c for c in certification["checks"] if c["status"] in ("FAIL", "ERROR")]
certification["verdict"] = "GO" if not failures else f"NO-GO ({len(failures)} failures)"
certification["failures"] = [c["name"] for c in failures]
certification["total_checks"] = len(certification["checks"])
certification["passed"] = len(certification["checks"]) - len(failures)

# ── WRITE JSON ──
json_path = os.path.join(OUTPUT_DIR, "refresh_certification.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(certification, f, indent=2, default=str, ensure_ascii=False)

# ── WRITE MD ──
md = [
    f"# OV2 Refresh Chain Certification",
    f"",
    f"**Generated:** {TIMESTAMP}",
    f"**Verdict:** **{certification['verdict']}**",
    f"**Passed:** {certification['passed']}/{certification['total_checks']}",
    f"",
    f"| # | Check | Grain | Status | Data |",
    f"|---|-------|-------|--------|------|",
]
for i, c in enumerate(certification["checks"], 1):
    data_str = json.dumps({k: v for k, v in c.get("data", {}).items() if k in ("max_date", "rows", "ready", "failed", "has_rev", "total", "pct", "slices", "versions")}, default=str)[:120]
    md.append(f"| {i} | {c['name']} | {c['grain']} | {c['status']} | {data_str} |")

if failures:
    md += ["", "## Failures", ""]
    for f_name in certification["failures"]:
        md.append(f"- {f_name}")

md_path = os.path.join(OUTPUT_DIR, "refresh_certification.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print(f"\nJSON: {json_path}")
print(f"MD:   {md_path}")
print(f"Verdict: {certification['verdict']}")
