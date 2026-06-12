"""
YEGO Lima Growth - Driver Lifecycle Foundation Service (LG-ACT-1A)
Shadow mode: builds canonical activity + lifecycle from public.trips_* + public.drivers.
Does NOT touch production queue/export/control_loop/taxonomy.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor, execute_values

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_EVENT = "growth.yego_lima_driver_activity_event"
TABLE_DAILY = "growth.yego_lima_driver_activity_daily"
TABLE_WEEKLY = "growth.yego_lima_driver_activity_weekly"
TABLE_MONTHLY = "growth.yego_lima_driver_activity_monthly"
TABLE_LIFECYCLE = "growth.yego_lima_driver_lifecycle_daily"
TABLE_LC_EVENT = "growth.yego_lima_driver_lifecycle_event"

LIMA_PARK = "08e20910d81d42658d4334d3f6d10ac0"
LIFECYCLE_VERSION = "v1"


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return default


def _safe_float(val, default=0.0):
    if val is None: return default
    try: return float(val)
    except: return default


def _dates_between(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# ================================================================
# BACKFILL: Activity Events from trips_2025 + trips_2026
# ================================================================


def backfill_activity_events_from_trips(
    start_date_str: str, end_date_str: str
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    logger.info("Backfilling activity events: %s to %s", start_date, end_date)

    inserted_total = 0
    sources = [
        ("public.trips_2025", "trips_2025"),
        ("public.trips_2026", "trips_2026"),
    ]

    with get_db() as conn:
        cur = conn.cursor()

        for source_table, source_system in sources:
            # Check table exists
            cur.execute(
                "SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)",
                (source_table.split(".")[1],),
            )
            if not cur.fetchone()[0]:
                logger.info("Skipping %s: table not found", source_table)
                continue

            # Check date range in this table
            cur.execute(
                f"SELECT MIN(fecha_finalizacion::date) as mn, MAX(fecha_finalizacion::date) as mx FROM {source_table}"
            )
            r = cur.fetchone()
            if not r or not r[0]:
                continue
            table_min = r[0]
            table_max = r[1]
            eff_start = max(start_date, table_min) if table_min else start_date
            eff_end = min(end_date, table_max) if table_max else end_date
            if eff_start > eff_end:
                continue

            logger.info(
                "Loading %s: %s to %s", source_table, eff_start, eff_end
            )

            # Insert in batches by month to avoid long transactions
            current = date(eff_start.year, eff_start.month, 1)
            while current <= eff_end:
                month_end = min(
                    date(current.year, current.month, 28)
                    + timedelta(days=4),
                    eff_end,
                )
                month_end = month_end.replace(day=1) + timedelta(days=32)
                month_end = month_end.replace(day=1) - timedelta(days=1)
                if month_end > eff_end:
                    month_end = eff_end

                logger.info(
                    "  Batch %s to %s", current, month_end
                )

                cur.execute(
                    f"""
                    INSERT INTO {TABLE_EVENT} (
                        source_system, source_table, source_trip_id,
                        park_id, driver_profile_id, event_type,
                        event_timestamp, event_date,
                        service_type, cancellation_reason,
                        price_yango_pro, distance_km, raw_status
                    )
                    SELECT
                        %(ss)s, %(st)s, t.id,
                        t.park_id, t.conductor_id,
                        CASE
                            WHEN t.condicion = 'Completado' THEN 'COMPLETED_TRIP'
                            WHEN t.condicion = 'Cancelado' THEN 'CANCELLED_TRIP'
                            ELSE 'OTHER'
                        END,
                        t.fecha_finalizacion,
                        t.fecha_finalizacion::date,
                        t.tipo_servicio,
                        t.motivo_cancelacion,
                        t.precio_yango_pro,
                        t.distancia_km,
                        t.condicion
                    FROM {source_table} t
                    WHERE t.park_id = %(p)s
                      AND t.fecha_finalizacion::date BETWEEN %(d1)s AND %(d2)s
                    ON CONFLICT (source_system, source_table, source_trip_id) DO NOTHING
                    """,
                    {
                        "ss": source_system,
                        "st": source_table,
                        "p": LIMA_PARK,
                        "d1": current,
                        "d2": month_end,
                    },
                )
                inserted = cur.rowcount
                inserted_total += inserted
                conn.commit()

                if inserted > 0:
                    logger.info(
                        "    Inserted %d events", inserted
                    )

                current = month_end + timedelta(days=1)

    duration = round((time.perf_counter() - t0) * 1000)
    return {
        "ok": True,
        "source": "trips_2025 + trips_2026",
        "park_id": LIMA_PARK,
        "date_range": f"{start_date} to {end_date}",
        "total_inserted": inserted_total,
        "duration_ms": duration,
    }


# ================================================================
# BUILD: Daily Activity from Events
# ================================================================


def build_activity_daily(start_date_str: str, end_date_str: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    with get_db() as conn:
        cur = conn.cursor()

        for d in _dates_between(start_date, end_date):
            cur.execute(
                f"DELETE FROM {TABLE_DAILY} WHERE activity_date = %(d)s AND park_id = %(p)s",
                {"d": d, "p": LIMA_PARK},
            )

        cur.execute(
            f"""
            INSERT INTO {TABLE_DAILY} (
                activity_date, park_id, driver_profile_id,
                completed_orders, cancelled_orders, total_orders,
                completed_revenue, completed_distance_km,
                has_completed_trip, has_cancelled_trip,
                first_completed_at, last_completed_at,
                first_event_at, last_event_at,
                source_system
            )
            SELECT
                event_date,
                park_id,
                driver_profile_id,
                SUM(CASE WHEN event_type = 'COMPLETED_TRIP' THEN 1 ELSE 0 END),
                SUM(CASE WHEN event_type = 'CANCELLED_TRIP' THEN 1 ELSE 0 END),
                COUNT(*),
                SUM(CASE WHEN event_type = 'COMPLETED_TRIP' THEN price_yango_pro ELSE 0 END),
                SUM(CASE WHEN event_type = 'COMPLETED_TRIP' THEN distance_km ELSE 0 END),
                BOOL_OR(event_type = 'COMPLETED_TRIP'),
                BOOL_OR(event_type = 'CANCELLED_TRIP'),
                MIN(event_timestamp) FILTER (WHERE event_type = 'COMPLETED_TRIP'),
                MAX(event_timestamp) FILTER (WHERE event_type = 'COMPLETED_TRIP'),
                MIN(event_timestamp),
                MAX(event_timestamp),
                'trips_table'
            FROM {TABLE_EVENT}
            WHERE park_id = %(p)s
              AND event_date BETWEEN %(d1)s AND %(d2)s
            GROUP BY event_date, park_id, driver_profile_id
            ON CONFLICT (activity_date, park_id, driver_profile_id) DO UPDATE SET
                completed_orders = EXCLUDED.completed_orders,
                cancelled_orders = EXCLUDED.cancelled_orders,
                total_orders = EXCLUDED.total_orders,
                completed_revenue = EXCLUDED.completed_revenue,
                completed_distance_km = EXCLUDED.completed_distance_km,
                has_completed_trip = EXCLUDED.has_completed_trip,
                has_cancelled_trip = EXCLUDED.has_cancelled_trip,
                first_completed_at = EXCLUDED.first_completed_at,
                last_completed_at = EXCLUDED.last_completed_at,
                first_event_at = EXCLUDED.first_event_at,
                last_event_at = EXCLUDED.last_event_at,
                updated_at = now()
            """,
            {"p": LIMA_PARK, "d1": start_date, "d2": end_date},
        )
        inserted = cur.rowcount
        conn.commit()

    duration = round((time.perf_counter() - t0) * 1000)
    return {
        "ok": True,
        "date_range": f"{start_date} to {end_date}",
        "rows_inserted": inserted,
        "duration_ms": duration,
    }


# ================================================================
# BUILD: Weekly Activity from Daily
# ================================================================


def build_activity_weekly(start_date_str: str, end_date_str: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"""
            DELETE FROM {TABLE_WEEKLY}
            WHERE week_start_date BETWEEN
                DATE_TRUNC('week', %(d1)s::date)::date
                AND DATE_TRUNC('week', %(d2)s::date)::date
              AND park_id = %(p)s
            """,
            {"d1": start_date, "d2": end_date, "p": LIMA_PARK},
        )

        cur.execute(
            f"""
            INSERT INTO {TABLE_WEEKLY} (
                week_start_date, park_id, driver_profile_id,
                completed_orders_week, cancelled_orders_week,
                active_days_week,
                completed_revenue_week, completed_distance_km_week,
                first_completed_at_week, last_completed_at_week
            )
            SELECT
                DATE_TRUNC('week', activity_date)::date,
                park_id,
                driver_profile_id,
                SUM(completed_orders),
                SUM(cancelled_orders),
                COUNT(*) FILTER (WHERE completed_orders > 0),
                SUM(completed_revenue),
                SUM(completed_distance_km),
                MIN(first_completed_at),
                MAX(last_completed_at)
            FROM {TABLE_DAILY}
            WHERE park_id = %(p)s
              AND activity_date BETWEEN %(d1)s AND %(d2)s
            GROUP BY DATE_TRUNC('week', activity_date)::date, park_id, driver_profile_id
            ON CONFLICT (week_start_date, park_id, driver_profile_id) DO UPDATE SET
                completed_orders_week = EXCLUDED.completed_orders_week,
                cancelled_orders_week = EXCLUDED.cancelled_orders_week,
                active_days_week = EXCLUDED.active_days_week,
                completed_revenue_week = EXCLUDED.completed_revenue_week,
                completed_distance_km_week = EXCLUDED.completed_distance_km_week,
                first_completed_at_week = EXCLUDED.first_completed_at_week,
                last_completed_at_week = EXCLUDED.last_completed_at_week
            """,
            {"p": LIMA_PARK, "d1": start_date, "d2": end_date},
        )
        inserted = cur.rowcount
        conn.commit()

    return {
        "ok": True,
        "rows_inserted": inserted,
        "duration_ms": round((time.perf_counter() - t0) * 1000),
    }


# ================================================================
# BUILD: Monthly Activity from Daily
# ================================================================


def build_activity_monthly(start_date_str: str, end_date_str: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"""
            DELETE FROM {TABLE_MONTHLY}
            WHERE month_start_date BETWEEN
                DATE_TRUNC('month', %(d1)s::date)::date
                AND DATE_TRUNC('month', %(d2)s::date)::date
              AND park_id = %(p)s
            """,
            {"d1": start_date, "d2": end_date, "p": LIMA_PARK},
        )

        cur.execute(
            f"""
            INSERT INTO {TABLE_MONTHLY} (
                month_start_date, park_id, driver_profile_id,
                completed_orders_month, cancelled_orders_month,
                active_days_month,
                completed_revenue_month, completed_distance_km_month,
                first_completed_at_month, last_completed_at_month
            )
            SELECT
                DATE_TRUNC('month', activity_date)::date,
                park_id,
                driver_profile_id,
                SUM(completed_orders),
                SUM(cancelled_orders),
                COUNT(*) FILTER (WHERE completed_orders > 0),
                SUM(completed_revenue),
                SUM(completed_distance_km),
                MIN(first_completed_at),
                MAX(last_completed_at)
            FROM {TABLE_DAILY}
            WHERE park_id = %(p)s
              AND activity_date BETWEEN %(d1)s AND %(d2)s
            GROUP BY DATE_TRUNC('month', activity_date)::date, park_id, driver_profile_id
            ON CONFLICT (month_start_date, park_id, driver_profile_id) DO UPDATE SET
                completed_orders_month = EXCLUDED.completed_orders_month,
                cancelled_orders_month = EXCLUDED.cancelled_orders_month,
                active_days_month = EXCLUDED.active_days_month,
                completed_revenue_month = EXCLUDED.completed_revenue_month,
                completed_distance_km_month = EXCLUDED.completed_distance_km_month,
                first_completed_at_month = EXCLUDED.first_completed_at_month,
                last_completed_at_month = EXCLUDED.last_completed_at_month
            """,
            {"p": LIMA_PARK, "d1": start_date, "d2": end_date},
        )
        inserted = cur.rowcount
        conn.commit()

    return {"ok": True, "rows_inserted": inserted, "duration_ms": round((time.perf_counter() - t0) * 1000)}


# ================================================================
# BUILD: Lifecycle Daily State
# ================================================================


def build_lifecycle_daily(snapshot_date_str: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    snapshot_date = date.fromisoformat(snapshot_date_str)

    with get_db() as conn:
        cur = conn.cursor()

        # Clear existing
        cur.execute(
            f"DELETE FROM {TABLE_LIFECYCLE} WHERE snapshot_date = %(d)s AND park_id = %(p)s",
            {"d": snapshot_date, "p": LIMA_PARK},
        )

        # Build lifecycle state: join public.drivers with activity events
        cur.execute(
            f"""
            INSERT INTO {TABLE_LIFECYCLE} (
                snapshot_date, park_id, driver_profile_id,
                hire_date, first_completed_trip_date, last_completed_trip_date,
                days_since_hire, days_since_first_trip, days_since_last_completed_trip,
                completed_trips_7d, completed_trips_14d, completed_trips_30d, completed_trips_90d,
                completed_trips_since_anchor,
                lifecycle_status, current_anchor_date, anchor_type,
                lifecycle_reason, lifecycle_version, evidence_json
            )
            WITH driver_base AS (
                SELECT
                    driver_id,
                    hire_date,
                    COALESCE(hire_date, '2020-01-01'::date) as effective_hire_date
                FROM public.drivers
                WHERE park_id = %(p)s
            ),
            activity_summary AS (
                SELECT
                    driver_profile_id,
                    MIN(event_date) as first_trip_date,
                    MAX(event_date) FILTER (WHERE event_type = 'COMPLETED_TRIP') as last_completed_trip_date,
                    SUM(CASE WHEN event_type = 'COMPLETED_TRIP' AND event_date >= %(sd)s::date - 6 THEN 1 ELSE 0 END) as trips_7d,
                    SUM(CASE WHEN event_type = 'COMPLETED_TRIP' AND event_date >= %(sd)s::date - 13 THEN 1 ELSE 0 END) as trips_14d,
                    SUM(CASE WHEN event_type = 'COMPLETED_TRIP' AND event_date >= %(sd)s::date - 29 THEN 1 ELSE 0 END) as trips_30d,
                    SUM(CASE WHEN event_type = 'COMPLETED_TRIP' AND event_date >= %(sd)s::date - 89 THEN 1 ELSE 0 END) as trips_90d,
                    SUM(CASE WHEN event_type = 'COMPLETED_TRIP' THEN 1 ELSE 0 END) as trips_lifetime
                FROM {TABLE_EVENT}
                WHERE park_id = %(p)s AND event_date <= %(sd)s
                GROUP BY driver_profile_id
            ),
            reactivation_check AS (
                SELECT
                    driver_profile_id,
                    event_date as reactivation_date,
                    LAG(event_date) OVER (PARTITION BY driver_profile_id ORDER BY event_date) as prev_trip_date
                FROM {TABLE_EVENT}
                WHERE park_id = %(p)s
                  AND event_type = 'COMPLETED_TRIP'
                  AND event_date <= %(sd)s
            ),
            reactivated AS (
                SELECT DISTINCT driver_profile_id, reactivation_date
                FROM reactivation_check
                WHERE reactivation_date - prev_trip_date >= 90
                  AND reactivation_date = (
                      SELECT MAX(event_date) FROM {TABLE_EVENT}
                      WHERE park_id = %(p)s AND driver_profile_id = reactivation_check.driver_profile_id
                        AND event_type = 'COMPLETED_TRIP' AND event_date <= %(sd)s
                  )
            )
            SELECT
                %(sd)s::date,
                %(p)s,
                d.driver_id,
                d.hire_date,
                a.first_trip_date,
                a.last_completed_trip_date,
                (%(sd)s::date - d.effective_hire_date) as days_since_hire,
                (%(sd)s::date - a.first_trip_date) as days_since_first_trip,
                (%(sd)s::date - a.last_completed_trip_date) as days_since_last_completed_trip,
                COALESCE(a.trips_7d, 0),
                COALESCE(a.trips_14d, 0),
                COALESCE(a.trips_30d, 0),
                COALESCE(a.trips_90d, 0),
                COALESCE(a.trips_lifetime, 0),
                CASE
                    WHEN r.driver_profile_id IS NOT NULL THEN 'REACTIVATED'
                    WHEN a.last_completed_trip_date IS NULL THEN 'NEVER_ACTIVATED'
                    WHEN (%(sd)s::date - a.last_completed_trip_date) <= 7 THEN 'ACTIVE'
                    WHEN d.hire_date IS NOT NULL AND (%(sd)s::date - d.hire_date) <= 90
                         AND a.last_completed_trip_date IS NOT NULL
                         AND (%(sd)s::date - a.last_completed_trip_date) < 15 THEN 'NEW'
                    WHEN a.last_completed_trip_date IS NOT NULL
                         AND (%(sd)s::date - a.last_completed_trip_date) >= 90 THEN 'ARCHIVED_90D'
                    WHEN a.last_completed_trip_date IS NOT NULL
                         AND (%(sd)s::date - a.last_completed_trip_date) >= 15 THEN 'CHURN_15D'
                    WHEN d.hire_date IS NOT NULL
                         AND (%(sd)s::date - d.hire_date) <= 90 THEN 'NEW'
                    ELSE 'NEVER_ACTIVATED'
                END as lifecycle_status,
                CASE
                    WHEN r.driver_profile_id IS NOT NULL THEN r.reactivation_date
                    WHEN d.hire_date IS NOT NULL THEN d.hire_date
                    WHEN a.first_trip_date IS NOT NULL THEN a.first_trip_date
                    ELSE NULL
                END as current_anchor_date,
                CASE
                    WHEN r.driver_profile_id IS NOT NULL THEN 'REACTIVATION_DATE'
                    WHEN a.first_trip_date IS NOT NULL
                         AND (%(sd)s::date - a.first_trip_date) <= 90 THEN 'FIRST_TRIP_DATE'
                    WHEN d.hire_date IS NOT NULL THEN 'HIRE_DATE'
                    ELSE 'NONE'
                END as anchor_type,
                CASE
                    WHEN r.driver_profile_id IS NOT NULL THEN 'reactivated_after_90d_gap'
                    WHEN a.last_completed_trip_date IS NULL THEN 'no_completed_trips_in_history'
                    WHEN (%(sd)s::date - a.last_completed_trip_date) <= 7 THEN 'active_last_trip_7d'
                    WHEN (d.hire_date IS NOT NULL AND (%(sd)s::date - d.hire_date) <= 90) THEN 'new_driver_window_90d'
                    WHEN (%(sd)s::date - a.last_completed_trip_date) >= 90 THEN 'archived_90d_no_trip'
                    WHEN (%(sd)s::date - a.last_completed_trip_date) >= 15 THEN 'churn_15d_no_trip'
                    ELSE 'fallback'
                END,
                'v1',
                json_build_object(
                    'hire_date', d.hire_date,
                    'first_trip_date', a.first_trip_date,
                    'last_completed_trip_date', a.last_completed_trip_date,
                    'trips_7d', COALESCE(a.trips_7d, 0),
                    'snapshot_date', %(sd)s
                )
            FROM driver_base d
            LEFT JOIN activity_summary a ON d.driver_id = a.driver_profile_id
            LEFT JOIN reactivated r ON d.driver_id = r.driver_profile_id
            ON CONFLICT (snapshot_date, park_id, driver_profile_id) DO UPDATE SET
                hire_date = EXCLUDED.hire_date,
                first_completed_trip_date = EXCLUDED.first_completed_trip_date,
                last_completed_trip_date = EXCLUDED.last_completed_trip_date,
                days_since_hire = EXCLUDED.days_since_hire,
                days_since_first_trip = EXCLUDED.days_since_first_trip,
                days_since_last_completed_trip = EXCLUDED.days_since_last_completed_trip,
                completed_trips_7d = EXCLUDED.completed_trips_7d,
                completed_trips_14d = EXCLUDED.completed_trips_14d,
                completed_trips_30d = EXCLUDED.completed_trips_30d,
                completed_trips_90d = EXCLUDED.completed_trips_90d,
                completed_trips_since_anchor = EXCLUDED.completed_trips_since_anchor,
                lifecycle_status = EXCLUDED.lifecycle_status,
                current_anchor_date = EXCLUDED.current_anchor_date,
                anchor_type = EXCLUDED.anchor_type,
                lifecycle_reason = EXCLUDED.lifecycle_reason,
                lifecycle_version = EXCLUDED.lifecycle_version,
                evidence_json = EXCLUDED.evidence_json
            """,
            {"sd": snapshot_date, "p": LIMA_PARK},
        )
        inserted = cur.rowcount
        conn.commit()

    duration = round((time.perf_counter() - t0) * 1000)
    return {
        "ok": True,
        "snapshot_date": snapshot_date_str,
        "rows_inserted": inserted,
        "duration_ms": duration,
    }


# ================================================================
# BUILD: Lifecycle Events (FIRST_ACTIVITY, REACTIVATION, etc.)
# ================================================================


def build_lifecycle_events(start_date_str: str, end_date_str: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    with get_db() as conn:
        cur = conn.cursor()

        # Clear for date range
        cur.execute(
            f"DELETE FROM {TABLE_LC_EVENT} WHERE event_date BETWEEN %(d1)s AND %(d2)s AND park_id = %(p)s",
            {"d1": start_date, "d2": end_date, "p": LIMA_PARK},
        )

        inserted = 0

        # FIRST_ACTIVITY: first completed trip ever
        cur.execute(
            f"""
            INSERT INTO {TABLE_LC_EVENT} (
                event_date, park_id, driver_profile_id,
                lifecycle_event_type, previous_lifecycle_status, new_lifecycle_status,
                anchor_date, trigger_reason, evidence_json, lifecycle_version
            )
            SELECT
                event_date,
                park_id,
                driver_profile_id,
                'FIRST_ACTIVITY',
                'NEVER_ACTIVATED',
                'ACTIVE',
                event_date,
                'first_completed_trip',
                json_build_object('trip_id', source_trip_id, 'price', price_yango_pro),
                'v1'
            FROM (
                SELECT DISTINCT ON (driver_profile_id)
                    event_date, park_id, driver_profile_id, source_trip_id, price_yango_pro
                FROM {TABLE_EVENT}
                WHERE park_id = %(p)s
                  AND event_type = 'COMPLETED_TRIP'
                  AND event_date BETWEEN %(d1)s AND %(d2)s
                ORDER BY driver_profile_id, event_timestamp
            ) sub
            ON CONFLICT DO NOTHING
            """,
            {"p": LIMA_PARK, "d1": start_date, "d2": end_date},
        )
        inserted += cur.rowcount

        # REACTIVATION: first trip after >= 90d gap
        cur.execute(
            f"""
            INSERT INTO {TABLE_LC_EVENT} (
                event_date, park_id, driver_profile_id,
                lifecycle_event_type, previous_lifecycle_status, new_lifecycle_status,
                anchor_date, trigger_reason, evidence_json, lifecycle_version
            )
            WITH ordered AS (
                SELECT
                    driver_profile_id, event_date,
                    LAG(event_date) OVER (PARTITION BY driver_profile_id ORDER BY event_date) as prev_date,
                    LAG(event_timestamp) OVER (PARTITION BY driver_profile_id ORDER BY event_date) as prev_ts,
                    event_timestamp, source_trip_id
                FROM {TABLE_EVENT}
                WHERE park_id = %(p)s AND event_type = 'COMPLETED_TRIP'
            )
            SELECT
                event_date, %(p)s, driver_profile_id,
                'REACTIVATION', 'ARCHIVED_90D', 'REACTIVATED',
                event_date,
                'first_trip_after_90d_gap',
                json_build_object('gap_days', event_date - prev_date, 'prev_trip_date', prev_date),
                'v1'
            FROM ordered
            WHERE event_date - prev_date >= 90
              AND event_date BETWEEN %(d1)s AND %(d2)s
            ON CONFLICT DO NOTHING
            """,
            {"p": LIMA_PARK, "d1": start_date, "d2": end_date},
        )
        inserted += cur.rowcount

        conn.commit()

    return {
        "ok": True,
        "events_inserted": inserted,
        "duration_ms": round((time.perf_counter() - t0) * 1000),
    }


# ================================================================
# QUERY ENDPOINTS
# ================================================================


def get_lifecycle_summary(snapshot_date_str: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"SELECT lifecycle_status, COUNT(*) as cnt FROM {TABLE_LIFECYCLE} "
            "WHERE snapshot_date = %(d)s AND park_id = %(p)s GROUP BY 1 ORDER BY cnt DESC",
            {"d": snapshot_date_str, "p": LIMA_PARK},
        )
        status = [dict(r) for r in cur.fetchall()]

        cur.execute(
            f"SELECT COUNT(*) as total FROM {TABLE_LIFECYCLE} WHERE snapshot_date = %(d)s AND park_id = %(p)s",
            {"d": snapshot_date_str, "p": LIMA_PARK},
        )
        total = cur.fetchone()["total"]

        cur.execute(
            f"SELECT SUM(completed_orders) as orders, COUNT(DISTINCT driver_profile_id) as drivers "
            f"FROM {TABLE_DAILY} WHERE activity_date = %(d)s AND park_id = %(p)s",
            {"d": snapshot_date_str, "p": LIMA_PARK},
        )
        daily = cur.fetchone()

    return {
        "snapshot_date": snapshot_date_str,
        "total_drivers": total,
        "lifecycle_distribution": status,
        "daily_activity": {
            "completed_orders": daily["orders"] or 0,
            "active_drivers": daily["drivers"] or 0,
        },
    }


def get_driver_lifecycle(driver_id: str, snapshot_date_str: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"SELECT * FROM {TABLE_LIFECYCLE} WHERE snapshot_date = %(d)s AND driver_profile_id = %(did)s AND park_id = %(p)s",
            {"d": snapshot_date_str, "did": driver_id, "p": LIMA_PARK},
        )
        lc = cur.fetchone()

        cur.execute(
            f"SELECT * FROM {TABLE_LC_EVENT} WHERE driver_profile_id = %(did)s AND park_id = %(p)s ORDER BY event_date DESC LIMIT 10",
            {"did": driver_id, "p": LIMA_PARK},
        )
        events = [dict(r) for r in cur.fetchall()]

        cur.execute(
            f"SELECT * FROM {TABLE_DAILY} WHERE driver_profile_id = %(did)s AND park_id = %(p)s ORDER BY activity_date DESC LIMIT 30",
            {"did": driver_id, "p": LIMA_PARK},
        )
        daily = [dict(r) for r in cur.fetchall()]

    if not lc:
        return None

    return {
        "driver_profile_id": driver_id,
        "snapshot_date": snapshot_date_str,
        "lifecycle": dict(lc),
        "recent_events": events,
        "recent_daily_activity": daily,
    }


def get_lifecycle_events(snapshot_date_str: str, limit: int = 100) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT * FROM {TABLE_LC_EVENT} WHERE event_date = %(d)s AND park_id = %(p)s "
            "ORDER BY created_at DESC LIMIT %(lim)s",
            {"d": snapshot_date_str, "p": LIMA_PARK, "lim": min(limit, 500)},
        )
        return [dict(r) for r in cur.fetchall()]
