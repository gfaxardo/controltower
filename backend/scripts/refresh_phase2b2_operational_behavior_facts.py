"""
Refresh Script - Phase 2B.2: Operational Behavioral Intelligence Materialized Facts

Populates 3 optimized daily/hourly facts from public.trips_2026 (indexed, 16.6M rows).
Fast source: does NOT scan the slow 64M+ enriched view.

Usage:
    cd backend
    python scripts/refresh_phase2b2_operational_behavior_facts.py --days 180
"""
from __future__ import annotations

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

SOURCE = "public.trips_2026"
DAILY_DIM = "ops.driver_daily_activity_fact"
STATEMENT_TIMEOUT = "600000"  # 10 min per query

# Column mappings (Spanish source -> English facts)
_SRC_DATE = "t.fecha_inicio_viaje::date"
_SRC_HOUR = "EXTRACT(HOUR FROM t.fecha_inicio_viaje)"
_SRC_DOW = "EXTRACT(DOW FROM t.fecha_inicio_viaje)"
_SRC_COMPLETED = "CASE WHEN t.condicion = 'Completado' THEN 1 ELSE 0 END"
_SRC_CANCELLED = "CASE WHEN t.condicion = 'Cancelado' THEN 1 ELSE 0 END"
_SRC_REVENUE = "COALESCE(t.precio_yango_pro, 0) - COALESCE(t.comision_servicio, 0)"
_SRC_DISTANCE = "COALESCE(t.distancia_km, 0)"
_SRC_DURATION = "EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) / 60.0"
_SRC_PEAK = f"({_SRC_HOUR} BETWEEN 6 AND 9 OR {_SRC_HOUR} BETWEEN 17 AND 20)"
_SRC_WEEKEND = f"{_SRC_DOW} IN (0, 6)"

FACTS = [
    {
        "name": "ops.driver_trip_behavior_daily_fact",
        "label": "Trip Behavior Daily",
    },
    {
        "name": "ops.driver_zone_behavior_daily_fact",
        "label": "Zone Behavior Daily",
    },
    {
        "name": "ops.driver_time_behavior_hourly_fact",
        "label": "Time Behavior Hourly",
    },
]


def _exec(cur, sql, params=None, label=""):
    try:
        cur.execute(sql, params)
    except Exception as e:
        print(f"  ERROR [{label}]: {e}")
        raise


def _verify(cur, table: str) -> dict:
    cur.execute(f"""
        SELECT COUNT(*) AS rows, COUNT(DISTINCT driver_id) AS drivers,
               MIN(activity_date) AS min_date, MAX(activity_date) AS max_date
        FROM {table}
    """)
    r = dict(cur.fetchone())
    cur.execute(f"UPDATE {table} SET last_refreshed_at = NOW()")
    return {"rows": r["rows"], "drivers": r["drivers"],
            "min_date": str(r["min_date"]), "max_date": str(r["max_date"])}


def refresh_fact_a(conn, days: int) -> dict:
    """A. driver_trip_behavior_daily_fact - from trips_2026 JOIN daily_activity_fact"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
    table = "ops.driver_trip_behavior_daily_fact"

    print("  Truncating...")
    _exec(cur, f"TRUNCATE TABLE {table}", label="truncate A")

    print("  Populating from trips_2026 via daily_activity_fact...")
    sql = f"""
        INSERT INTO {table} (
            driver_id, activity_date, country, city, park_id,
            trips, cancelled_trips, revenue, distance_km, duration_min,
            peak_hour_trips, weekend_trips, weekday_trips,
            avg_ticket, revenue_per_trip, revenue_per_hour_proxy,
            revenue_per_km, trips_per_hour_proxy
        )
        SELECT
            d.driver_id,
            d.activity_date,
            d.country,
            d.city,
            d.park_id,
            SUM({_SRC_COMPLETED})::INTEGER AS trips,
            SUM({_SRC_CANCELLED})::INTEGER AS cancelled_trips,
            COALESCE(SUM({_SRC_REVENUE}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(14,2) AS revenue,
            COALESCE(SUM({_SRC_DISTANCE}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(10,2) AS distance_km,
            COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(10,1) AS duration_min,
            SUM(CASE WHEN t.condicion = 'Completado' AND ({_SRC_PEAK}) THEN 1 ELSE 0 END)::INTEGER AS peak_hour_trips,
            SUM(CASE WHEN t.condicion = 'Completado' AND ({_SRC_WEEKEND}) THEN 1 ELSE 0 END)::INTEGER AS weekend_trips,
            SUM(CASE WHEN t.condicion = 'Completado' AND NOT ({_SRC_WEEKEND}) THEN 1 ELSE 0 END)::INTEGER AS weekday_trips,
            AVG(t.precio_yango_pro) FILTER (WHERE t.condicion = 'Completado' AND t.precio_yango_pro IS NOT NULL)::NUMERIC(10,2) AS avg_ticket,
            CASE WHEN SUM({_SRC_COMPLETED}) > 0
                 THEN (COALESCE(SUM({_SRC_REVENUE}) FILTER (WHERE t.condicion = 'Completado'), 0) / SUM({_SRC_COMPLETED}))::NUMERIC(10,2)
            END AS revenue_per_trip,
            CASE WHEN COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0) > 0
                 THEN (COALESCE(SUM({_SRC_REVENUE}) FILTER (WHERE t.condicion = 'Completado'), 0) /
                       (COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0) / 60.0))::NUMERIC(10,2)
            END AS revenue_per_hour_proxy,
            CASE WHEN COALESCE(SUM({_SRC_DISTANCE}) FILTER (WHERE t.condicion = 'Completado'), 0) > 0
                 THEN (COALESCE(SUM({_SRC_REVENUE}) FILTER (WHERE t.condicion = 'Completado'), 0) /
                       COALESCE(SUM({_SRC_DISTANCE}) FILTER (WHERE t.condicion = 'Completado'), 0))::NUMERIC(10,2)
            END AS revenue_per_km,
            CASE WHEN COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0) > 0
                 THEN (SUM({_SRC_COMPLETED})::NUMERIC /
                       (COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0) / 60.0))::NUMERIC(10,4)
            END AS trips_per_hour_proxy
        FROM {DAILY_DIM} d
        JOIN {SOURCE} t ON d.driver_id = t.conductor_id
            AND d.activity_date = t.fecha_inicio_viaje::date
        WHERE d.activity_date >= CURRENT_DATE - %(days)s
        GROUP BY d.driver_id, d.activity_date, d.country, d.city, d.park_id
    """
    _exec(cur, sql, {"days": days}, label="insert A")
    print(f"  Inserted: {cur.rowcount:,} rows")

    r = _verify(cur, table)
    cur.close()
    return r


def refresh_fact_b(conn, days: int) -> dict:
    """B. driver_zone_behavior_daily_fact"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
    table = "ops.driver_zone_behavior_daily_fact"

    print("  Truncating...")
    _exec(cur, f"TRUNCATE TABLE {table}", label="truncate B")

    print("  Populating from trips_2026...")
    sql = f"""
        INSERT INTO {table} (
            driver_id, activity_date, country, city, zone_key, zone_type,
            trips, cancelled_trips, revenue, distance_km, duration_min,
            peak_hour_trips, weekend_trips, weekday_trips
        )
        SELECT
            d.driver_id, d.activity_date, d.country, d.city,
            d.park_id AS zone_key, 'park_id' AS zone_type,
            SUM({_SRC_COMPLETED})::INTEGER AS trips,
            SUM({_SRC_CANCELLED})::INTEGER AS cancelled_trips,
            COALESCE(SUM({_SRC_REVENUE}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(14,2) AS revenue,
            COALESCE(SUM({_SRC_DISTANCE}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(10,2) AS distance_km,
            COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(10,1) AS duration_min,
            SUM(CASE WHEN t.condicion = 'Completado' AND ({_SRC_PEAK}) THEN 1 ELSE 0 END)::INTEGER AS peak_hour_trips,
            SUM(CASE WHEN t.condicion = 'Completado' AND ({_SRC_WEEKEND}) THEN 1 ELSE 0 END)::INTEGER AS weekend_trips,
            SUM(CASE WHEN t.condicion = 'Completado' AND NOT ({_SRC_WEEKEND}) THEN 1 ELSE 0 END)::INTEGER AS weekday_trips
        FROM {DAILY_DIM} d
        JOIN {SOURCE} t ON d.driver_id = t.conductor_id
            AND d.activity_date = t.fecha_inicio_viaje::date
        WHERE d.activity_date >= CURRENT_DATE - %(days)s
          AND d.park_id IS NOT NULL
        GROUP BY d.driver_id, d.activity_date, d.country, d.city, d.park_id
    """
    _exec(cur, sql, {"days": days}, label="insert B")
    print(f"  Inserted: {cur.rowcount:,} rows")

    r = _verify(cur, table)
    cur.close()
    return r


def refresh_fact_c(conn, days: int) -> dict:
    """C. driver_time_behavior_hourly_fact"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
    table = "ops.driver_time_behavior_hourly_fact"

    print("  Truncating...")
    _exec(cur, f"TRUNCATE TABLE {table}", label="truncate C")

    print("  Populating from trips_2026...")
    sql = f"""
        INSERT INTO {table} (
            driver_id, activity_date, trip_hour, day_of_week, country, city,
            trips, cancelled_trips, revenue, distance_km, duration_min,
            is_peak_hour, is_weekend
        )
        SELECT
            d.driver_id, d.activity_date,
            EXTRACT(HOUR FROM t.fecha_inicio_viaje)::INTEGER AS trip_hour,
            EXTRACT(DOW FROM t.fecha_inicio_viaje)::INTEGER AS day_of_week,
            d.country, d.city,
            SUM({_SRC_COMPLETED})::INTEGER AS trips,
            SUM({_SRC_CANCELLED})::INTEGER AS cancelled_trips,
            COALESCE(SUM({_SRC_REVENUE}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(14,2) AS revenue,
            COALESCE(SUM({_SRC_DISTANCE}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(10,2) AS distance_km,
            COALESCE(SUM({_SRC_DURATION}) FILTER (WHERE t.condicion = 'Completado'), 0)::NUMERIC(10,1) AS duration_min,
            BOOL_OR({_SRC_PEAK}) AS is_peak_hour,
            BOOL_OR({_SRC_WEEKEND}) AS is_weekend
        FROM {DAILY_DIM} d
        JOIN {SOURCE} t ON d.driver_id = t.conductor_id
            AND d.activity_date = t.fecha_inicio_viaje::date
        WHERE d.activity_date >= CURRENT_DATE - %(days)s
        GROUP BY d.driver_id, d.activity_date,
                 EXTRACT(HOUR FROM t.fecha_inicio_viaje),
                 EXTRACT(DOW FROM t.fecha_inicio_viaje),
                 d.country, d.city
    """
    _exec(cur, sql, {"days": days}, label="insert C")
    print(f"  Inserted: {cur.rowcount:,} rows")

    r = _verify(cur, table)
    cur.close()
    return r


def main():
    parser = argparse.ArgumentParser(description="Refresh Phase 2B.2 materialized facts")
    parser.add_argument("--days", type=int, default=180, help="Days window (default: 180, max: 365)")
    args = parser.parse_args()
    days = max(7, min(args.days, 365))

    print("=" * 70)
    print("PHASE 2B.2: Materialized Facts Refresh")
    print(f"  Window: {days} days")
    print(f"  Source: {SOURCE} (via {DAILY_DIM})")
    print("=" * 70)

    total_start = time.time()
    results = {}

    with get_db() as conn:
        conn.autocommit = True

        for fact in FACTS:
            name = fact["name"]
            label = fact["label"]
            print(f"\n--- {name} ---")
            print(f"  {label}")
            start = time.time()

            try:
                if "trip_behavior_daily" in name:
                    r = refresh_fact_a(conn, days)
                elif "zone_behavior_daily" in name:
                    r = refresh_fact_b(conn, days)
                else:
                    r = refresh_fact_c(conn, days)

                elapsed = time.time() - start
                r["elapsed_s"] = round(elapsed, 1)
                r["status"] = "OK" if r["rows"] > 0 else "EMPTY"
                results[name] = r

                print(f"  Result: {r['rows']:,} rows | {r['drivers']:,} drivers")
                print(f"  Range:  {r['min_date']} to {r['max_date']}")
                print(f"  Time:   {elapsed:.1f}s")
                print(f"  Status: {r['status']}")

                if r["rows"] == 0:
                    print(f"  WARNING: Fact is EMPTY!")
            except Exception as e:
                elapsed = time.time() - start
                results[name] = {"rows": 0, "drivers": 0, "elapsed_s": elapsed, "status": "ERROR"}
                print(f"  ERROR: {e}")

    total_time = time.time() - total_start
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, r in results.items():
        tag = "[OK]" if r["status"] == "OK" else "[FAIL]"
        print(f"  {tag} {name:55s} {r['rows']:>10,} rows  {r['elapsed_s']:6.1f}s")
    print(f"\nTotal time: {total_time:.1f}s")
    print("=" * 70)

    empty = [n for n, r in results.items() if r["rows"] == 0]
    if empty:
        print(f"\nFAIL: {len(empty)} fact(s) empty: {', '.join(empty)}")
        sys.exit(1)
    else:
        print("\nOK: All facts populated.")
        sys.exit(0)


if __name__ == "__main__":
    main()
