"""
Validate migration analytical views (079): consistency with existing lifecycle/segment data,
total drivers consistency, no duplicate transitions.
Run: cd backend && python -m scripts.validate_migration_views
"""
from __future__ import print_function

import os
import sys

# backend/scripts
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

def main():
    try:
        from app.db.connection import get_db
    except Exception as e:
        print("Error importing get_db:", e)
        return 1

    checks = []
    with get_db() as conn:
        cur = conn.cursor()

        # 1) Views exist
        cur.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'ops'
              AND viewname IN ('v_driver_segment_migrations_weekly', 'v_driver_segments_weekly_summary', 'v_driver_segment_critical_movements')
        """)
        views = [r[0] for r in cur.fetchall()]
        checks.append(("Views exist (079)", set(views) == {"v_driver_segment_migrations_weekly", "v_driver_segments_weekly_summary", "v_driver_segment_critical_movements"}, views))

        # 2) Total drivers consistency: sum(drivers) per week in v_driver_segment_migrations_weekly (by park, week) should not exceed supply
        cur.execute("""
            SELECT 1 FROM ops.v_driver_segment_migrations_weekly LIMIT 1
        """)
        if cur.fetchone():
            cur.execute("""
                WITH mig_totals AS (
                    SELECT park_id, week_start, SUM(drivers) AS total_mig
                    FROM ops.v_driver_segment_migrations_weekly
                    GROUP BY park_id, week_start
                ),
                supply_totals AS (
                    SELECT park_id, week_start, SUM(drivers_count) AS total_supply
                    FROM ops.mv_supply_segments_weekly
                    GROUP BY park_id, week_start
                )
                SELECT COUNT(*) FROM mig_totals m
                JOIN supply_totals s ON s.park_id = m.park_id AND s.week_start = m.week_start
                WHERE m.total_mig > s.total_supply * 1.01
            """)
            over = cur.fetchone()[0]
            checks.append(("Migration totals <= supply (no overflow)", over == 0, "overflow count=%s" % over if over else "OK"))
        else:
            checks.append(("Migration totals <= supply", True, "no data"))

        # 3) No duplicate transitions in base view (one row per park, week, from, to, type)
        cur.execute("""
            SELECT park_id, week_start, from_segment, to_segment, transition_type, COUNT(*)
            FROM ops.v_driver_segment_migrations_weekly
            GROUP BY park_id, week_start, from_segment, to_segment, transition_type
            HAVING COUNT(*) > 1
        """)
        dupes = cur.fetchall()
        checks.append(("No duplicate transitions (park,week,from,to,type)", len(dupes) == 0, "dupes=%s" % len(dupes) if dupes else "OK"))

        # 4) Summary view: drivers match supply per (week, park, segment)
        cur.execute("""
            SELECT 1 FROM ops.v_driver_segments_weekly_summary LIMIT 1
        """)
        if cur.fetchone():
            cur.execute("""
                WITH summary_drivers AS (
                    SELECT park_id, week_start, segment, drivers FROM ops.v_driver_segments_weekly_summary
                ),
                supply_drivers AS (
                    SELECT park_id, week_start, segment_week AS segment, drivers_count AS drivers
                    FROM ops.mv_supply_segments_weekly
                )
                SELECT COUNT(*) FROM summary_drivers s
                JOIN supply_drivers u ON u.park_id = s.park_id AND u.week_start = s.week_start AND u.segment = s.segment
                WHERE s.drivers != u.drivers
            """)
            mismatch = cur.fetchone()[0]
            checks.append(("Summary drivers = supply (per week, park, segment)", mismatch == 0, "mismatch count=%s" % mismatch if mismatch else "OK"))
        else:
            checks.append(("Summary drivers = supply", True, "no data"))

    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print("[%s] %s — %s" % (status, name, detail))
    failed = sum(1 for _, ok, _ in checks if not ok)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
