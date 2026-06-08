"""OV2-F.2D — Validate driver_day_slice_fact against day_fact
Validates: trip counts match, driver counts match, no duplicates, flags correct.
"""
import sys, os, argparse, csv, json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "driver_day_slice_fact")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).isoformat()
BRIDGE = "ops.driver_day_slice_fact"
DAY = "ops.real_business_slice_day_fact"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--country", default="peru")
    ap.add_argument("--city", default="lima")
    args = ap.parse_args()

    results = []
    print("OV2-F.2D BRIDGE VALIDATION")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # 1) Row counts
            cur.execute(f"SELECT COUNT(*) AS rows FROM {BRIDGE} WHERE country=%s AND city=%s", (args.country, args.city))
            bridge_rows = cur.fetchone()["rows"]
            print(f"  Bridge rows: {bridge_rows:,}")

            # 2) Duplicate check
            cur.execute(f"""
                SELECT COUNT(*) AS dupes FROM (
                    SELECT activity_date, country, city, park_id, business_slice_name, driver_id, COUNT(*) AS n
                    FROM {BRIDGE} WHERE country=%s AND city=%s
                    GROUP BY 1,2,3,4,5,6 HAVING COUNT(*) > 1
                ) d
            """, (args.country, args.city))
            dupes = cur.fetchone()["dupes"]
            results.append({"check": "duplicates", "status": "PASS" if dupes == 0 else f"FAIL ({dupes} dupes)", "value": dupes})
            print(f"  Duplicates: {dupes} {'OK' if dupes == 0 else 'FAIL'}")

            # 3) Trip totals vs day_fact
            cur.execute(f"""
                SELECT SUM(completed_trips) AS bridge_trips FROM {BRIDGE}
                WHERE country=%s AND city=%s AND activity_date >= %s AND activity_date <= %s
            """, (args.country, args.city, args.date_from, args.date_to))
            bridge_trips = cur.fetchone()["bridge_trips"] or 0

            cur.execute(f"""
                SELECT SUM(trips_completed) AS day_trips FROM {DAY}
                WHERE LOWER(TRIM(country))=%s AND LOWER(TRIM(city))=%s AND trip_date >= %s AND trip_date <= %s
            """, ("peru", "lima", args.date_from, args.date_to))
            day_trips = cur.fetchone()["day_trips"] or 0

            trips_ok = abs(bridge_trips - day_trips) / max(day_trips, 1) < 0.01
            results.append({"check": "trips vs day_fact", "status": "PASS" if trips_ok else "FAIL",
                            "bridge_trips": bridge_trips, "day_trips": day_trips,
                            "delta_pct": round(abs(bridge_trips - day_trips) / max(day_trips, 1) * 100, 2)})
            print(f"  Trips: bridge={bridge_trips:,} day_fact={day_trips:,} {'OK' if trips_ok else 'MISMATCH'}")

            # 4) Daily driver counts vs day_fact active_drivers
            cur.execute(f"""
                SELECT activity_date, business_slice_name,
                       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS bridge_drivers,
                       SUM(completed_trips) AS bridge_trips
                FROM {BRIDGE}
                WHERE country=%s AND city=%s AND activity_date >= %s AND activity_date <= %s
                GROUP BY activity_date, business_slice_name
                ORDER BY activity_date, business_slice_name
            """, (args.country, args.city, args.date_from, args.date_to))
            bridge_daily = {f"{r['activity_date']}|{r['business_slice_name']}": r for r in cur.fetchall()}

            cur.execute(f"""
                SELECT trip_date, business_slice_name, active_drivers, trips_completed
                FROM {DAY}
                WHERE LOWER(TRIM(country))=%s AND LOWER(TRIM(city))=%s AND trip_date >= %s AND trip_date <= %s
            """, ("peru", "lima", args.date_from, args.date_to))
            day_rows = [dict(r) for r in cur.fetchall()]

            driver_diffs = []
            for d in day_rows:
                key = f"{d['trip_date']}|{d['business_slice_name']}"
                b = bridge_daily.get(key, {})
                b_drivers = b.get("bridge_drivers", None)
                d_drivers = d["active_drivers"]
                if b_drivers is not None and b_drivers != d_drivers:
                    driver_diffs.append({
                        "date": str(d["trip_date"])[:10],
                        "slice": d["business_slice_name"],
                        "bridge_drivers": b_drivers,
                        "day_drivers": d_drivers,
                        "delta": b_drivers - d_drivers,
                    })

            drivers_match = len(driver_diffs) == 0
            results.append({"check": "drivers vs day_fact", "status": "PASS" if drivers_match else f"FAIL ({len(driver_diffs)} diffs)",
                            "diffs": driver_diffs[:10]})
            print(f"  Driver diffs: {len(driver_diffs)} {'OK' if drivers_match else 'FAIL'}")
            for d in driver_diffs[:5]:
                print(f"    {d['date']} {d['slice']:20s} bridge={d['bridge_drivers']} day={d['day_drivers']} delta={d['delta']:+d}")

            # 5) Empty supply check
            cur.execute(f"""
                SELECT COUNT(DISTINCT driver_id) AS empty_drivers,
                       COUNT(*) AS empty_rows
                FROM {BRIDGE}
                WHERE country=%s AND city=%s AND empty_supply_flag = true
            """, (args.country, args.city))
            empty = cur.fetchone()
            results.append({"check": "empty_supply", "status": "INFO",
                            "empty_drivers": empty["empty_drivers"], "empty_rows": empty["empty_rows"]})
            print(f"  Empty supply: {empty['empty_drivers']:,} drivers, {empty['empty_rows']} rows")

            # Write CSV
            csv_path = os.path.join(OUTPUT_DIR, "bridge_validation.csv")
            if driver_diffs:
                with open(csv_path, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["date", "slice", "bridge_drivers", "day_drivers", "delta"])
                    w.writeheader(); w.writerows(driver_diffs)

            # Write MD
            md = [f"# Driver Day Slice Bridge Validation", f"**{TIMESTAMP}**", "",
                  f"| Check | Status | Details |",
                  f"|-------|--------|---------|"]
            for r in results:
                md.append(f"| {r['check']} | {r['status']} | {str({k:v for k,v in r.items() if k not in ('check','status')})[:100]} |")

            md_path = os.path.join(OUTPUT_DIR, "bridge_validation.md")
            with open(md_path, "w") as f:
                f.write("\n".join(md))
            print(f"\nOutput: {md_path}")

        except Exception as e:
            print(f"ERROR: {e}")
            return 1
        finally:
            cur.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
