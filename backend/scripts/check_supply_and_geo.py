#!/usr/bin/env python3
"""
Verificación Supply + Geo: unicidad MVs, coverage, UNKNOWN en dim_geo_park.
Sin full scans. Exit 0 = PASS, 1 = FAIL.
Uso: cd backend && python -m scripts.check_supply_and_geo
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from app.db.connection import init_db_pool, get_db
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    failed = False

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("=== CHECK SUPPLY AND GEO ===\n")

        # Unicidad mv_supply_weekly
        try:
            cur.execute("""
                SELECT week_start, park_id, COUNT(*) AS cnt
                FROM ops.mv_supply_weekly
                GROUP BY week_start, park_id
                HAVING COUNT(*) > 1
            """)
            dupes = cur.fetchall()
            if dupes:
                print("FAIL: mv_supply_weekly duplicados (week_start, park_id):", len(dupes))
                failed = True
            else:
                print("PASS: mv_supply_weekly unicidad (week_start, park_id)")
        except Exception as e:
            print("FAIL: mv_supply_weekly", e)
            failed = True

        # Unicidad mv_supply_monthly
        try:
            cur.execute("""
                SELECT month_start, park_id, COUNT(*) AS cnt
                FROM ops.mv_supply_monthly
                GROUP BY month_start, park_id
                HAVING COUNT(*) > 1
            """)
            dupes = cur.fetchall()
            if dupes:
                print("FAIL: mv_supply_monthly duplicados:", len(dupes))
                failed = True
            else:
                print("PASS: mv_supply_monthly unicidad (month_start, park_id)")
        except Exception as e:
            print("FAIL: mv_supply_monthly", e)
            failed = True

        # Coverage: distinct parks en supply weekly
        try:
            cur.execute("SELECT COUNT(DISTINCT park_id) AS n FROM ops.mv_supply_weekly")
            n = cur.fetchone()["n"]
            print(f"PASS: mv_supply_weekly coverage (distinct park_id): {n}")
        except Exception as e:
            print("FAIL: coverage weekly", e)
            failed = True

        # UNKNOWN geo
        try:
            cur.execute("""
                SELECT COUNT(*) AS n FROM dim.dim_geo_park
                WHERE city = 'UNKNOWN' OR country = 'UNKNOWN'
            """)
            n_unknown = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM dim.dim_geo_park")
            n_total = cur.fetchone()["n"]
            if n_unknown > 0:
                print(f"WARN: dim_geo_park con city/country UNKNOWN: {n_unknown} / {n_total}")
            else:
                print(f"PASS: dim_geo_park sin UNKNOWN: {n_total} parks")
        except Exception as e:
            print("FAIL: dim_geo_park UNKNOWN check", e)
            failed = True

        cur.close()

    print("\n" + ("FAIL" if failed else "PASS") + " (check_supply_and_geo)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
