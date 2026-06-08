import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.repositories.omniview_v2_plan_real_repository import get_monthly_plan_real, _plan_country, _plan_city
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

print("=== Direct SQL: Plan Revenue Query ===")
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            WITH plan AS (
                SELECT month, LOWER(TRIM(lob_base)) AS lob_raw,
                       SUM(COALESCE(projected_revenue, 0)) AS plan_value
                FROM ops.plan_trips_monthly
                WHERE TRIM(country) = %s AND TRIM(city) = %s
                  AND plan_version = %s
                  AND (%s::date IS NULL OR month >= %s::date)
                  AND (%s::date IS NULL OR month <= %s::date)
                GROUP BY month, LOWER(TRIM(lob_base))
            ),
            lob_map AS (
                SELECT DISTINCT LOWER(TRIM(raw_lob_name)) AS raw_lob, canonical_lob_base
                FROM ops.plan_lob_mapping WHERE status = 'active'
            )
            SELECT p.month, COALESCE(m.canonical_lob_base, p.lob_raw) AS slice_name, p.plan_value
            FROM plan p LEFT JOIN lob_map m ON p.lob_raw = m.raw_lob
            ORDER BY p.month, slice_name
        """, ("PE", "Lima", "e2e_20260526_165110", None, None, None, None))
        plan_rows = [dict(r) for r in cur.fetchall()]
        print(f"Plan rows: {len(plan_rows)}")
        for r in plan_rows[:8]:
            m = str(r["month"])[:10] if r["month"] else "?"
            print(f"  {m} | {r['slice_name']:20s} | rev={r['plan_value']:>12,.0f}")
        if len(plan_rows) > 8:
            print(f"  ... ({len(plan_rows) - 8} more)")
    finally:
        cur.close()

print("\n=== Repository call ===")
raw = get_monthly_plan_real("peru", "lima", "2026-01-01", None, "revenue")
print(f"Combined rows: {len(raw)}")
for r in raw[:8]:
    print(f"  {r['period']} | {r['business_slice_name']:20s} | plan={r['plan_value']:>12,.0f} real={r['real_value']} status={r['status']}")
if len(raw) > 8:
    print(f"  ... ({len(raw) - 8} more)")

# Check plan rows that have revenue > 0
has_rev = [r for r in raw if r["plan_value"] > 0]
print(f"\nRows with plan_value > 0: {len(has_rev)}")
for r in has_rev[:5]:
    print(f"  {r['period']} | {r['business_slice_name']} | plan={r['plan_value']:>12,.0f} status={r['status']}")
