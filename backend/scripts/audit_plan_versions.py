"""
OV2_D2B Plan Version Audit — quick script to audit plan source.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date as dt_date
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "omniview_v2_core",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

results = {}
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT DISTINCT plan_version, MIN(month) as first_month, MAX(month) as last_month, "
            "COUNT(*) as rows FROM ops.plan_trips_monthly GROUP BY plan_version ORDER BY MAX(month) DESC"
        )
        results["versions"] = [dict(r) for r in cur.fetchall()]
        for v in results["versions"]:
            fm = str(v["first_month"])[:10] if v["first_month"] else "?"
            lm = str(v["last_month"])[:10] if v["last_month"] else "?"
            print(f"Version: {v['plan_version']} | {v['rows']} rows | {fm} -> {lm}")

        cur.execute(
            "SELECT country, COUNT(*) as rows, COUNT(DISTINCT city) as cities, "
            "COUNT(DISTINCT month) as months FROM ops.plan_trips_monthly GROUP BY country ORDER BY rows DESC"
        )
        results["by_country"] = [dict(r) for r in cur.fetchall()]
        print("\nBy country:")
        for c in results["by_country"]:
            print(f"  {c['country']}: {c['rows']} rows, {c['cities']} cities, {c['months']} months")

        cur.execute(
            "SELECT city, COUNT(*) as rows, COUNT(DISTINCT month) as months "
            "FROM ops.plan_trips_monthly WHERE LOWER(TRIM(country))='peru' GROUP BY city ORDER BY rows DESC"
        )
        results["peru_cities"] = [dict(r) for r in cur.fetchall()]
        print("\nPeru cities:")
        for c in results["peru_cities"]:
            print(f"  {c['city']}: {c['rows']} rows, {c['months']} months")

        cur.execute(
            "SELECT LOWER(TRIM(lob_base)) as lob, COUNT(*) as rows, COUNT(DISTINCT month) as months "
            "FROM ops.plan_trips_monthly WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' "
            "GROUP BY LOWER(TRIM(lob_base)) ORDER BY rows DESC"
        )
        results["lima_lobs"] = [dict(r) for r in cur.fetchall()]
        print("\nLima LOBs:")
        for l in results["lima_lobs"]:
            print(f"  {l['lob']}: {l['rows']} rows, {l['months']} months")

        cur.execute(
            "SELECT raw_lob_name, canonical_lob_base FROM ops.plan_lob_mapping WHERE status='active' LIMIT 30"
        )
        results["lob_mappings"] = [dict(r) for r in cur.fetchall()]
        print(f"\nLOB mappings: {len(results['lob_mappings'])} active")

        # Sample
        cur.execute(
            "SELECT * FROM ops.plan_trips_monthly WHERE LOWER(TRIM(country))='peru' "
            "AND LOWER(TRIM(city))='lima' LIMIT 2"
        )
        sample = [dict(r) for r in cur.fetchall()]
        for s in sample:
            d = {k: (str(v)[:30] if hasattr(v, 'isoformat') else v) for k, v in s.items()}
            print(f"\nSample: {json.dumps(d, default=str, indent=2)}")

    finally:
        cur.close()

with open(os.path.join(OUTPUT_DIR, "plan_version_audit.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str, ensure_ascii=False)
print(f"\nDone. Output: {os.path.join(OUTPUT_DIR, 'plan_version_audit.json')}")
