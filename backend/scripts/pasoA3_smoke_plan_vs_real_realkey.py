"""
[YEGO CT] E2E PASO A.3 — Smoke checks Plan vs Real (realkey, sin homologación).
- COUNT plan/real/final por mes
- Top 20 variance_trips desc
- % filas con park_name null (debe ser bajo, ideal < 5%)
statement_timeout = 600s.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool


def run(cur, sql, desc=""):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        return None


def main():
    print("=== PASO A.3 — Smoke Plan vs Real (realkey) ===\n")
    init_db_pool()

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '600s'")

            # COUNT plan by month
            r = run(cur, """
                SELECT period_date, COUNT(*) AS c
                FROM ops.v_plan_universe_by_park_realkey
                GROUP BY period_date ORDER BY period_date
            """, "plan by month")
            print("  Plan rows by month:")
            if r:
                for row in r[:12]:
                    print(f"    {row[0]}: {row[1]}")
                if len(r) > 12:
                    print(f"    ... y {len(r) - 12} meses más")
            else:
                print("    (sin datos o error)")
            print()

            # COUNT real by month
            r = run(cur, """
                SELECT period_date, COUNT(*) AS c
                FROM ops.v_real_universe_by_park_realkey
                GROUP BY period_date ORDER BY period_date
            """, "real by month")
            print("  Real rows by month:")
            if r:
                for row in r[:12]:
                    print(f"    {row[0]}: {row[1]}")
                if len(r) > 12:
                    print(f"    ... y {len(r) - 12} meses más")
            else:
                print("    (sin datos o error)")
            print()

            # COUNT final
            r = run(cur, "SELECT COUNT(*) FROM ops.v_plan_vs_real_realkey_final", "final count")
            final_rows = r[0][0] if r else 0
            print(f"  Final rows (v_plan_vs_real_realkey_final): {final_rows}\n")

            # Top 20 variance_trips desc
            r = run(cur, """
                SELECT country, city, park_id, park_name, real_tipo_servicio, period_date,
                       trips_plan, trips_real, variance_trips, variance_revenue
                FROM ops.v_plan_vs_real_realkey_final
                ORDER BY variance_trips DESC NULLS LAST
                LIMIT 20
            """, "top 20 variance_trips")
            print("  Top 20 variance_trips (desc):")
            if r:
                for row in r:
                    park_name = (row[3] or "")[:30]
                    print(f"    {row[0]} | {row[1]} | {park_name!r} | {row[4][:20] if row[4] else ''} | {row[5]} | plan={row[6]} real={row[7]} var_t={row[8]} var_r={row[9]}")
            else:
                print("    (sin datos o error)")
            print()

            # % park_name null
            r = run(cur, """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN park_name IS NULL OR TRIM(COALESCE(park_name,'')) = '' THEN 1 ELSE 0 END)
                FROM ops.v_plan_vs_real_realkey_final
            """, "park_name null")
            total = 0
            nulls = 0
            if r and r[0][0]:
                total = r[0][0]
                nulls = r[0][1] or 0
            rate = (nulls / total * 100) if total else 0
            print(f"  park_name null: {nulls}/{total} ({rate:.1f}%)")
            if rate > 5:
                print("  [AVISO] park_name null rate > 5%; revisar join con parks.")
            else:
                print("  (objetivo < 5%: OK)")
        finally:
            cur.close()

    print("\n" + "=" * 60)
    if final_rows > 0 and total and rate < 50:
        print("  SMOKE OK")
        print(f"  - final_rows: {final_rows}")
        print(f"  - park_name null rate: {rate:.1f}%")
    else:
        print("  Revisar: final_rows > 0 y park_name null rate razonable.")
    print("=" * 60)


if __name__ == "__main__":
    main()
