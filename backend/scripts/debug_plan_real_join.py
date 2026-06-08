import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Plan LOBs for Lima
        cur.execute("SELECT DISTINCT LOWER(TRIM(lob_base)) AS lob FROM ops.plan_trips_monthly WHERE TRIM(country)='PE' AND TRIM(city)='Lima' ORDER BY 1")
        print("=== Plan LOBs (Lima) ===")
        for r in cur.fetchall():
            print(f"  {r['lob']}")

        # LOB mapping
        cur.execute("SELECT raw_lob_name, canonical_lob_base FROM ops.plan_lob_mapping WHERE status='active' ORDER BY 1")
        print("\n=== LOB Mappings ===")
        for r in cur.fetchall():
            print(f"  {r['raw_lob_name']} -> {r['canonical_lob_base']}")

        # Real table slices for Lima
        cur.execute("SELECT DISTINCT business_slice_name FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))=LOWER(TRIM(%s)) AND LOWER(TRIM(city))=LOWER(TRIM(%s)) ORDER BY 1", ("peru", "lima"))
        real_slices = [r["business_slice_name"] for r in cur.fetchall()]
        print(f"\n=== Real slices (Lima) ===")
        for s in real_slices:
            print(f"  {s}")

        # Test join: plan vs real for January 2026
        print("\n=== Join test (2026-01) ===")
        cur.execute("""
            WITH plan_slice AS (
                SELECT COALESCE(m.canonical_lob_base, LOWER(TRIM(p.lob_base))) AS slice_name,
                       SUM(COALESCE(p.projected_trips,0)) AS plan_val
                FROM ops.plan_trips_monthly p
                LEFT JOIN ops.plan_lob_mapping m ON LOWER(TRIM(p.lob_base)) = LOWER(TRIM(m.raw_lob_name)) AND m.status='active'
                WHERE TRIM(p.country)='PE' AND TRIM(p.city)='Lima'
                  AND p.plan_version='e2e_20260526_165110'
                  AND p.month='2026-01-01'
                GROUP BY 1
            ),
            real_slice AS (
                SELECT business_slice_name AS slice_name,
                       SUM(COALESCE(trips_completed,0)) AS real_val
                FROM ops.real_business_slice_month_fact
                WHERE LOWER(TRIM(country))=LOWER(TRIM(%s)) AND LOWER(TRIM(city))=LOWER(TRIM(%s))
                  AND month='2026-01-01'
                GROUP BY business_slice_name
            )
            SELECT p.slice_name AS plan_slice, p.plan_val,
                   r.slice_name AS real_slice, r.real_val
            FROM plan_slice p
            FULL OUTER JOIN real_slice r ON p.slice_name = r.slice_name
            ORDER BY COALESCE(p.slice_name, r.slice_name)
        """, ("peru", "lima"))
        for d in [dict(r) for r in cur.fetchall()]:
            match = "MATCH" if d["plan_slice"] == d["real_slice"] else "NO MATCH"
            print(f"  plan=[{d['plan_slice']}] {d['plan_val']} | real=[{d['real_slice']}] {d['real_val']} | {match}")
    finally:
        cur.close()
