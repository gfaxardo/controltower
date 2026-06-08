"""OV2-D.2B.1 Revenue Truth Repair — Full Column & Reconciliation Audit"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from psycopg2 import sql

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "omniview_v2_core")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TABLES = [
    ("day", "ops.real_business_slice_day_fact"),
    ("week", "ops.real_business_slice_week_fact"),
    ("month", "ops.real_business_slice_month_fact"),
]

results = {"column_audit": {}, "reconciliation": {}, "null_analysis": {}}

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # ── 1) COLUMN AUDIT ──
        for grain, table in TABLES:
            print(f"\n{'='*60}")
            print(f"TABLE: {table} ({grain})")
            print(f"{'='*60}")

            schema, tbl = table.split(".")
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                  AND (column_name ILIKE '%%revenue%%'
                       OR column_name ILIKE '%%rev%%'
                       OR column_name ILIKE '%%fee%%'
                       OR column_name ILIKE '%%ingreso%%'
                       OR column_name ILIKE '%%ticket%%')
                ORDER BY column_name
            """, (schema, tbl))
            rev_cols = [dict(r) for r in cur.fetchall()]
            print(f"Revenue-related columns: {len(rev_cols)}")
            for c in rev_cols:
                print(f"  {c['column_name']} ({c['data_type']})")

            for col in rev_cols:
                cn = col["column_name"]
                q = sql.SQL("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT({col}) AS non_null,
                        ROUND(100.0 * COUNT({col}) / NULLIF(COUNT(*), 0), 1) AS fill_pct,
                        COALESCE(SUM(COALESCE({col}, 0)), 0) AS total_sum,
                        COUNT(*) FILTER (WHERE {col} IS NULL) AS null_count
                    FROM {tbl}
                    WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
                """).format(col=sql.Identifier(cn), tbl=sql.Identifier(schema, tbl))
                cur.execute(q, ("peru", "lima"))
                stats = dict(cur.fetchone())
                fill = stats["fill_pct"] or 0
                total = stats["total"] or 0
                nulls = stats["null_count"] or 0
                total_sum_val = stats["total_sum"] or 0
                flag = "OK" if fill > 90 else "CRITICAL" if fill == 0 else "WARN"
                print(f"  {cn:30s} rows={total:5d} non-null={total-nulls:5d} fill={fill:5.1f}% sum={total_sum_val:>15,.0f} [{flag}]")
                results["column_audit"][f"{grain}.{cn}"] = {
                    "total": total, "non_null": total - nulls, "fill_pct": fill,
                    "total_sum": total_sum_val, "flag": flag
                }

        # ── 2) Find best revenue column ──
        rev_col = None
        for k, v in results["column_audit"].items():
            if "day." in k and v["fill_pct"] > 50 and v["total_sum"] > 0:
                rev_col = k.split(".")[1]
                break
        if not rev_col:
            rev_col = "revenue_yego_final"
        print(f"\nBest revenue column for reconciliation: {rev_col}")

        # ── 3) RECONCILIATION ──
        print(f"\n{'='*60}")
        print("RECONCILIATION: SUM(day_fact) vs month_fact")
        print(f"{'='*60}")

        rev = sql.Identifier(rev_col)
        q_rec = sql.SQL("""
            WITH day_sums AS (
                SELECT date_trunc('month', trip_date)::date AS mth, business_slice_name,
                       SUM(COALESCE({rev}, 0)) AS day_rev, COUNT(*) AS d_rows
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s AND trip_date >= '2026-01-01'
                GROUP BY 1, 2
            ),
            month_sums AS (
                SELECT month, business_slice_name,
                       SUM(COALESCE({rev}, 0)) AS month_rev, COUNT(*) AS m_rows
                FROM ops.real_business_slice_month_fact
                WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s AND month >= '2026-01-01'
                GROUP BY 1, 2
            )
            SELECT d.mth, d.business_slice_name AS slice, d.day_rev, m.month_rev, d.d_rows, m.m_rows,
                   ROUND(d.day_rev - COALESCE(m.month_rev, 0), 2) AS delta_abs,
                   CASE WHEN COALESCE(m.month_rev, 0) != 0
                        THEN ROUND((d.day_rev - m.month_rev) / m.month_rev * 100, 1) ELSE NULL END AS delta_pct
            FROM day_sums d LEFT JOIN month_sums m ON d.mth = m.month AND d.business_slice_name = m.business_slice_name
            ORDER BY d.mth, d.business_slice_name
        """).format(rev=rev)
        cur.execute(q_rec, ("peru", "lima", "peru", "lima"))
        rec = [dict(r) for r in cur.fetchall()]
        results["reconciliation"] = rec
        for r in rec:
            flag = "MATCH" if abs(r["delta_pct"] or 0) < 1 else "DELTA" if abs(r["delta_pct"] or 0) < 5 else "MAJOR"
            print(f"  {str(r['mth'])[:10]} {r['slice']:20s} day={r['day_rev']:>12,.0f} month={r['month_rev']:>12,.0f} delta={r['delta_pct']:>6.1f}% [{flag}]")

        # ── 4) NULL by date (Jun 2026) ──
        print(f"\n{'='*60}")
        print(f"DAILY NULL CHECK: {rev_col} (Jun 2026)")
        print(f"{'='*60}")
        q_null = sql.SQL("""
            SELECT trip_date, business_slice_name, COUNT(*) AS rows, SUM(trips_completed) AS trips,
                   SUM(COALESCE({rev}, 0)) AS revenue,
                   COUNT(*) FILTER (WHERE {rev} IS NULL) AS null_rev
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s AND trip_date >= '2026-06-01'
            GROUP BY trip_date, business_slice_name
            ORDER BY trip_date, business_slice_name
        """).format(rev=rev)
        cur.execute(q_null, ("peru", "lima"))
        for d in [dict(r) for r in cur.fetchall()]:
            flag = "NULL" if d["null_rev"] > 0 else "OK"
            print(f"  {str(d['trip_date'])[:10]} {d['business_slice_name']:20s} rows={d['rows']:3d} trips={d['trips']:>5d} rev={d['revenue']:>12,.0f} null={d['null_rev']:3d} [{flag}]")

    finally:
        cur.close()

with open(os.path.join(OUTPUT_DIR, "revenue_column_audit.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str, ensure_ascii=False)
print(f"\nDone. Output: {os.path.join(OUTPUT_DIR, 'revenue_column_audit.json')}")
