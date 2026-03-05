#!/usr/bin/env python3
"""
Verificación Supply Alerting & Segments: existencia de objetos, unicidad, última semana,
conteo de alertas últimas 4 semanas, sanity segment totals <= total drivers.
Sin full scans (no COUNT(*) sobre trips).
Uso: cd backend && python -m scripts.check_supply_alerting_and_segments
Exit 0 = PASS, 1 = FAIL.
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

        print("=== CHECK SUPPLY ALERTING AND SEGMENTS ===\n")

        # 1) Existencia de objetos
        objects = [
            ("ops.mv_driver_segments_weekly", "matview"),
            ("ops.mv_supply_segments_weekly", "matview"),
            ("ops.mv_supply_segment_anomalies_weekly", "matview"),
            ("ops.mv_supply_alerts_weekly", "matview"),
            ("ops.v_supply_alert_drilldown", "view"),
            ("ops.refresh_supply_alerting_mvs", "function"),
        ]
        for name, kind in objects:
            try:
                if kind == "matview":
                    cur.execute(
                        "SELECT 1 FROM pg_matviews WHERE schemaname = %s AND matviewname = %s",
                        (name.split(".")[0], name.split(".")[1]),
                    )
                elif kind == "view":
                    cur.execute(
                        "SELECT 1 FROM pg_views WHERE schemaname = %s AND viewname = %s",
                        (name.split(".")[0], name.split(".")[1]),
                    )
                else:
                    cur.execute(
                        "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = %s AND p.proname = %s",
                        (name.split(".")[0], name.split(".")[1]),
                    )
                if cur.fetchone():
                    print(f"PASS: exists {name}")
                else:
                    print(f"FAIL: missing {name}")
                    failed = True
            except Exception as e:
                print(f"FAIL: existence {name} — {e}")
                failed = True

        # 2) Unicidad mv_driver_segments_weekly (driver_key, week_start)
        try:
            cur.execute("""
                SELECT driver_key, week_start, COUNT(*) AS cnt
                FROM ops.mv_driver_segments_weekly
                GROUP BY driver_key, week_start
                HAVING COUNT(*) > 1
            """)
            dupes = cur.fetchall()
            if dupes:
                print(f"FAIL: mv_driver_segments_weekly duplicados (driver_key, week_start): {len(dupes)}")
                failed = True
            else:
                print("PASS: mv_driver_segments_weekly unicidad (driver_key, week_start)")
        except Exception as e:
            print("FAIL: unicidad mv_driver_segments_weekly", e)
            failed = True

        # 3) Unicidad mv_supply_segments_weekly (week_start, park_id, segment_week)
        try:
            cur.execute("""
                SELECT week_start, park_id, segment_week, COUNT(*) AS cnt
                FROM ops.mv_supply_segments_weekly
                GROUP BY week_start, park_id, segment_week
                HAVING COUNT(*) > 1
            """)
            dupes = cur.fetchall()
            if dupes:
                print(f"FAIL: mv_supply_segments_weekly duplicados: {len(dupes)}")
                failed = True
            else:
                print("PASS: mv_supply_segments_weekly unicidad (week_start, park_id, segment_week)")
        except Exception as e:
            print("FAIL: unicidad mv_supply_segments_weekly", e)
            failed = True

        # 4) Latest week exists (en mv_driver_segments_weekly)
        try:
            cur.execute("""
                SELECT MAX(week_start) AS latest FROM ops.mv_driver_segments_weekly
            """)
            row = cur.fetchone()
            latest = row["latest"] if row else None
            if latest:
                print(f"PASS: latest week_start en mv_driver_segments_weekly: {latest}")
            else:
                print("WARN: no hay datos en mv_driver_segments_weekly (latest week null)")
        except Exception as e:
            print("FAIL: latest week", e)
            failed = True

        # 5) Count alerts last 4 weeks
        try:
            cur.execute("""
                SELECT COUNT(*) AS n
                FROM ops.mv_supply_alerts_weekly a
                WHERE a.week_start >= (SELECT COALESCE(MAX(week_start), '1970-01-01'::date) - INTERVAL '28 days' FROM ops.mv_supply_segments_weekly)
            """)
            n = cur.fetchone()["n"]
            print(f"PASS: alertas últimas 4 semanas: {n}")
        except Exception as e:
            print("FAIL: count alerts", e)
            failed = True

        # 6) Sanity: por (week_start, park_id) suma de drivers_count por segment <= total drivers en supply weekly (si existe)
        try:
            cur.execute("""
                WITH segment_totals AS (
                    SELECT week_start, park_id, SUM(drivers_count) AS seg_total
                    FROM ops.mv_supply_segments_weekly
                    GROUP BY week_start, park_id
                ),
                supply_weekly AS (
                    SELECT week_start, park_id, active_drivers
                    FROM ops.mv_supply_weekly
                )
                SELECT s.week_start, s.park_id, s.seg_total, w.active_drivers
                FROM segment_totals s
                JOIN supply_weekly w ON w.week_start = s.week_start AND w.park_id = s.park_id
                WHERE s.seg_total > w.active_drivers
                LIMIT 5
            """)
            bad = cur.fetchall()
            if bad:
                print(f"WARN: segment totals > active_drivers en supply_weekly: {len(bad)} filas (muestra)")
            else:
                print("PASS: sanity segment totals <= active_drivers (donde existe mv_supply_weekly)")
        except Exception as e:
            # mv_supply_weekly puede no existir en algunos entornos
            if "mv_supply_weekly" in str(e) or "does not exist" in str(e).lower():
                print("SKIP: sanity vs mv_supply_weekly (tabla no presente)")
            else:
                print("FAIL: sanity check", e)
                failed = True

        cur.close()

    print("\n" + ("FAIL" if failed else "PASS") + " (check_supply_alerting_and_segments)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
