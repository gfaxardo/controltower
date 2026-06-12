"""
LG-SCH-2A — Lima Growth V2 Daily Pipeline Runner Shadow

SHADOW MODE ONLY. Reads from existing production tables, writes to new
growth.yego_lima_v2_* shadow tables. Does NOT touch:
  - queue productiva
  - control_loop productivo
  - export productivo
  - legacy assignment_queue
  - legacy program_eligibility
  - legacy prioritized_opportunity

DAG (9 steps):
  1. build_activity_daily
  2. build_activity_weekly
  3. build_activity_monthly
  4. build_lifecycle_daily
  5. build_taxonomy_v2_daily
  6. build_program_v2_daily
  7. build_movement_fact
  8. build_observability_facts
  9. build_effectiveness_facts
"""

from __future__ import annotations

import json
import logging
import time as time_mod
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_RUN = "growth.yego_lima_v2_pipeline_run_log"
TABLE_STEP = "growth.yego_lima_v2_pipeline_step_log"
TABLE_FRESHNESS = "growth.yego_lima_v2_freshness_registry"

STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED_NO_NEW_DATA = "SKIPPED_NO_NEW_DATA"
STATUS_SKIPPED_ALREADY_FRESH = "SKIPPED_ALREADY_FRESH"

FRESHNESS_STATUSES = ["FRESH", "WARNING", "STALE", "BROKEN"]

OPERABILITY_OPERABLE = "OPERABLE"
OPERABILITY_DEGRADED = "DEGRADED"
OPERABILITY_NOT_OPERABLE = "NOT_OPERABLE"

PIPELINE_STEPS = [
    ("build_activity_daily", 1),
    ("build_activity_weekly", 2),
    ("build_activity_monthly", 3),
    ("build_lifecycle_daily", 4),
    ("build_taxonomy_v2_daily", 5),
    ("build_program_v2_daily", 6),
    ("build_movement_fact", 7),
    ("build_observability_facts", 8),
    ("build_effectiveness_facts", 9),
]

SCHEMA_CREATED = False


def _ensure_shadow_tables():
    global SCHEMA_CREATED
    if SCHEMA_CREATED:
        return
    ddl = [
        "CREATE SCHEMA IF NOT EXISTS growth;",
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_activity_daily (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            trips           integer DEFAULT 0,
            orders          integer DEFAULT 0,
            gross_revenue   numeric(18,4) DEFAULT 0,
            active_hours    numeric(10,2) DEFAULT 0,
            activity_trend  text DEFAULT 'unknown',
            PRIMARY KEY (target_date, driver_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_activity_weekly (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            trips           integer DEFAULT 0,
            orders          integer DEFAULT 0,
            gross_revenue   numeric(18,4) DEFAULT 0,
            active_days     integer DEFAULT 0,
            activity_trend  text DEFAULT 'unknown',
            PRIMARY KEY (target_date, driver_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_activity_monthly (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            trips           integer DEFAULT 0,
            orders          integer DEFAULT 0,
            gross_revenue   numeric(18,4) DEFAULT 0,
            active_days     integer DEFAULT 0,
            activity_trend  text DEFAULT 'unknown',
            PRIMARY KEY (target_date, driver_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_lifecycle_daily (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            lifecycle_stage text,
            days_in_stage   integer,
            first_trip_at   timestamptz,
            last_trip_at    timestamptz,
            total_trips     integer DEFAULT 0,
            churn_risk      text DEFAULT 'unknown',
            PRIMARY KEY (target_date, driver_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_taxonomy_daily (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            segment         text,
            sub_segment     text,
            elite_tier      text,
            loyalty_tier    text,
            park_id         text,
            park_name       text,
            city            text,
            country         text,
            PRIMARY KEY (target_date, driver_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_program_daily (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            program_code    text NOT NULL,
            program_name    text,
            eligibility_reason text,
            priority_score  numeric(10,2) DEFAULT 0,
            is_new_entry    boolean DEFAULT false,
            PRIMARY KEY (target_date, driver_id, program_code)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_movement_fact (
            target_date     date NOT NULL,
            driver_id       text NOT NULL,
            movement_type   text NOT NULL,
            from_state      text,
            to_state        text,
            from_program    text,
            to_program      text,
            trigger_reason  text,
            PRIMARY KEY (target_date, driver_id, movement_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_observability_fact (
            target_date         date NOT NULL,
            module_name         text NOT NULL,
            artifact_count      integer DEFAULT 0,
            with_refresh_count  integer DEFAULT 0,
            all_fresh           boolean DEFAULT false,
            coverage_pct        numeric(5,2) DEFAULT 0,
            latest_refresh_at   timestamptz,
            PRIMARY KEY (target_date, module_name)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_effectiveness_fact (
            target_date         date NOT NULL,
            campaign_id         text NOT NULL,
            campaign_name       text,
            total_members       integer DEFAULT 0,
            reactivated_count   integer DEFAULT 0,
            reactivation_rate   numeric(5,4) DEFAULT 0,
            avg_days_to_react   numeric(8,2),
            PRIMARY KEY (target_date, campaign_id)
        );
        """,
    ]
    try:
        with get_db() as conn:
            cur = conn.cursor()
            for sql in ddl:
                cur.execute(sql)
            conn.commit()
        SCHEMA_CREATED = True
        logger.info("V2 shadow tables ensured")
    except Exception as e:
        logger.warning("V2 shadow table creation deferred: %s", e)


def _now_utc():
    return datetime.now(timezone.utc)


def _today_str():
    return date.today().isoformat()


def run_lima_growth_v2_daily_pipeline(
    target_date: str,
    triggered_by: str = "manual",
) -> Dict[str, Any]:
    _ensure_shadow_tables()

    run_id = str(uuid4())
    started_at = _now_utc()
    t0 = time_mod.perf_counter()

    _create_run_log(run_id, target_date, STATUS_PARTIAL, triggered_by)

    steps_result: List[Dict[str, Any]] = []
    overall_status = STATUS_SUCCESS
    error_messages: List[str] = []

    for step_name, step_order in PIPELINE_STEPS:
        step_start = time_mod.perf_counter()
        step_status = STATUS_SUCCESS
        rows_before = 0
        rows_after = 0
        error_msg = None

        try:
            rows_before = _count_step_output(step_name, target_date)

            if _is_step_already_fresh(step_name, target_date, rows_before):
                step_status = STATUS_SKIPPED_ALREADY_FRESH
                rows_after = rows_before
            else:
                rows_after = _execute_step(step_name, target_date)
                if rows_after == 0 and rows_before == 0:
                    step_status = STATUS_SKIPPED_NO_NEW_DATA

        except Exception as e:
            step_status = STATUS_FAILED
            error_msg = str(e)[:500]
            error_messages.append(f"{step_name}: {error_msg}")
            logger.exception("V2 pipeline step %s failed for %s", step_name, target_date)

        duration_ms = int((time_mod.perf_counter() - step_start) * 1000)

        _log_step(run_id, target_date, step_name, step_order, step_status,
                  rows_before, rows_after, duration_ms, error_msg)

        steps_result.append({
            "step": step_name,
            "order": step_order,
            "status": step_status,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "duration_ms": duration_ms,
            "error": error_msg,
        })

        if step_status == STATUS_FAILED:
            overall_status = STATUS_FAILED
        elif step_status == STATUS_PARTIAL and overall_status == STATUS_SUCCESS:
            overall_status = STATUS_PARTIAL

    total_duration_ms = int((time_mod.perf_counter() - t0) * 1000)

    _update_run_log(run_id, overall_status, total_duration_ms,
                    steps_result, error_messages)
    _update_freshness_registry(target_date, run_id, steps_result)

    return {
        "run_id": run_id,
        "target_date": target_date,
        "overall_status": overall_status,
        "duration_ms": total_duration_ms,
        "triggered_by": triggered_by,
        "steps": steps_result,
        "errors": error_messages,
    }


def _is_step_already_fresh(step_name: str, target_date: str, current_rows: int) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT freshness_status FROM {TABLE_FRESHNESS} WHERE component = %(c)s",
            {"c": step_name}
        )
        row = cur.fetchone()
        if row and row[0] == "FRESH" and current_rows > 0:
            cur.execute(
                f"SELECT status FROM {TABLE_STEP} "
                f"WHERE step_name = %(s)s AND target_date = %(d)s AND status = 'SUCCESS' "
                f"ORDER BY created_at DESC LIMIT 1",
                {"s": step_name, "d": target_date}
            )
            prev = cur.fetchone()
            if prev:
                return True
    return False


def _count_step_output(step_name: str, target_date: str) -> int:
    table_map = {
        "build_activity_daily": "growth.yego_lima_v2_activity_daily",
        "build_activity_weekly": "growth.yego_lima_v2_activity_weekly",
        "build_activity_monthly": "growth.yego_lima_v2_activity_monthly",
        "build_lifecycle_daily": "growth.yego_lima_v2_lifecycle_daily",
        "build_taxonomy_v2_daily": "growth.yego_lima_v2_taxonomy_daily",
        "build_program_v2_daily": "growth.yego_lima_v2_program_daily",
        "build_movement_fact": "growth.yego_lima_v2_movement_fact",
        "build_observability_facts": "growth.yego_lima_v2_observability_fact",
        "build_effectiveness_facts": "growth.yego_lima_v2_effectiveness_fact",
    }
    table = table_map.get(step_name)
    if not table:
        return 0
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE target_date = %(d)s",
                {"d": target_date}
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def _execute_step(step_name: str, target_date: str) -> int:
    if step_name == "build_activity_daily":
        return _build_activity_daily(target_date)
    elif step_name == "build_activity_weekly":
        return _build_activity_weekly(target_date)
    elif step_name == "build_activity_monthly":
        return _build_activity_monthly(target_date)
    elif step_name == "build_lifecycle_daily":
        return _build_lifecycle_daily(target_date)
    elif step_name == "build_taxonomy_v2_daily":
        return _build_taxonomy_v2_daily(target_date)
    elif step_name == "build_program_v2_daily":
        return _build_program_v2_daily(target_date)
    elif step_name == "build_movement_fact":
        return _build_movement_fact(target_date)
    elif step_name == "build_observability_facts":
        return _build_observability_facts(target_date)
    elif step_name == "build_effectiveness_facts":
        return _build_effectiveness_facts(target_date)
    return 0


def _run_statement_timeout(cur, timeout_ms: int = 180000):
    cur.execute("SET LOCAL statement_timeout = %s", (str(timeout_ms),))


# ─── STEP 1: Activity Daily ──────────────────────────────────────────────────

def _build_activity_daily(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_activity_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )

        cur.execute("""
            INSERT INTO growth.yego_lima_v2_activity_daily
                (target_date, driver_id, trips, activity_trend)
            SELECT
                %(d)s::date,
                a.driver_id::text,
                COALESCE(a.completed_trips, 0) AS trips,
                CASE
                    WHEN COALESCE(a.completed_trips, 0) = 0 THEN 'inactive'
                    WHEN COALESCE(a.completed_trips, 0) < 3 THEN 'low'
                    WHEN COALESCE(a.completed_trips, 0) < 8 THEN 'moderate'
                    ELSE 'active'
                END AS activity_trend
            FROM ops.driver_daily_activity_fact a
            WHERE a.activity_date = %(d)s
            ON CONFLICT (target_date, driver_id) DO UPDATE SET
                trips = EXCLUDED.trips,
                activity_trend = EXCLUDED.activity_trend
        """, {"d": target_date})
        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_activity_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 2: Activity Weekly ─────────────────────────────────────────────────

def _build_activity_weekly(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_activity_weekly WHERE target_date = %(d)s",
            {"d": target_date}
        )

        week_start = (date.fromisoformat(target_date) - timedelta(days=6)).isoformat()

        cur.execute("""
            INSERT INTO growth.yego_lima_v2_activity_weekly
                (target_date, driver_id, trips, active_days, activity_trend)
            SELECT
                %(d)s::date,
                a.driver_id::text,
                COALESCE(SUM(a.completed_trips), 0) AS trips,
                COUNT(DISTINCT a.activity_date) AS active_days,
                CASE
                    WHEN COALESCE(SUM(a.completed_trips), 0) = 0 THEN 'inactive'
                    WHEN COALESCE(SUM(a.completed_trips), 0) < 10 THEN 'low'
                    WHEN COALESCE(SUM(a.completed_trips), 0) < 30 THEN 'moderate'
                    ELSE 'active'
                END AS activity_trend
            FROM ops.driver_daily_activity_fact a
            WHERE a.activity_date >= %(ws)s AND a.activity_date <= %(d)s
            GROUP BY a.driver_id
            ON CONFLICT (target_date, driver_id) DO UPDATE SET
                trips = EXCLUDED.trips,
                active_days = EXCLUDED.active_days,
                activity_trend = EXCLUDED.activity_trend
        """, {"d": target_date, "ws": week_start})
        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_activity_weekly WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 3: Activity Monthly ────────────────────────────────────────────────

def _build_activity_monthly(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_activity_monthly WHERE target_date = %(d)s",
            {"d": target_date}
        )

        month_start = (date.fromisoformat(target_date) - timedelta(days=29)).isoformat()

        cur.execute("""
            INSERT INTO growth.yego_lima_v2_activity_monthly
                (target_date, driver_id, trips, active_days, activity_trend)
            SELECT
                %(d)s::date,
                a.driver_id::text,
                COALESCE(SUM(a.completed_trips), 0) AS trips,
                COUNT(DISTINCT a.activity_date) AS active_days,
                CASE
                    WHEN COALESCE(SUM(a.completed_trips), 0) = 0 THEN 'inactive'
                    WHEN COALESCE(SUM(a.completed_trips), 0) < 30 THEN 'low'
                    WHEN COALESCE(SUM(a.completed_trips), 0) < 80 THEN 'moderate'
                    ELSE 'active'
                END AS activity_trend
            FROM ops.driver_daily_activity_fact a
            WHERE a.activity_date >= %(ms)s AND a.activity_date <= %(d)s
            GROUP BY a.driver_id
            ON CONFLICT (target_date, driver_id) DO UPDATE SET
                trips = EXCLUDED.trips,
                active_days = EXCLUDED.active_days,
                activity_trend = EXCLUDED.activity_trend
        """, {"d": target_date, "ms": month_start})
        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_activity_monthly WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 4: Lifecycle Daily ─────────────────────────────────────────────────

def _build_lifecycle_daily(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_lifecycle_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )

        cur.execute("""
            INSERT INTO growth.yego_lima_v2_lifecycle_daily
                (target_date, driver_id, lifecycle_stage, days_in_stage,
                 first_trip_at, last_trip_at, total_trips, churn_risk)
            SELECT
                %(d)s::date,
                lc.driver_profile_id AS driver_id,
                lc.lifecycle_status AS lifecycle_stage,
                lc.days_since_last_completed_trip AS days_in_stage,
                lc.first_completed_trip_date::timestamptz AS first_trip_at,
                lc.last_completed_trip_date::timestamptz AS last_trip_at,
                COALESCE(lc.completed_trips_since_anchor, 0) AS total_trips,
                CASE
                    WHEN lc.last_completed_trip_date IS NULL THEN 'unknown'
                    WHEN lc.last_completed_trip_date < CURRENT_DATE - interval '60 days' THEN 'high'
                    WHEN lc.last_completed_trip_date < CURRENT_DATE - interval '30 days' THEN 'medium'
                    WHEN lc.last_completed_trip_date < CURRENT_DATE - interval '14 days' THEN 'low'
                    ELSE 'none'
                END AS churn_risk
            FROM growth.yego_lima_driver_lifecycle_daily lc
            WHERE lc.snapshot_date = %(d)s
            ON CONFLICT (target_date, driver_id) DO UPDATE SET
                lifecycle_stage = EXCLUDED.lifecycle_stage,
                days_in_stage = EXCLUDED.days_in_stage,
                first_trip_at = EXCLUDED.first_trip_at,
                last_trip_at = EXCLUDED.last_trip_at,
                total_trips = EXCLUDED.total_trips,
                churn_risk = EXCLUDED.churn_risk
        """, {"d": target_date})
        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_lifecycle_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 5: Taxonomy V2 Daily ───────────────────────────────────────────────

def _build_taxonomy_v2_daily(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_taxonomy_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )

        cur.execute("""
            INSERT INTO growth.yego_lima_v2_taxonomy_daily
                (target_date, driver_id, segment, sub_segment,
                 elite_tier, loyalty_tier, park_id, park_name, city, country)
            SELECT
                %(d)s::date,
                lc.driver_profile_id AS driver_id,
                lc.lifecycle_status AS segment,
                CASE
                    WHEN COALESCE(lc.completed_trips_since_anchor, 0) >= 200 THEN 'heavy'
                    WHEN COALESCE(lc.completed_trips_since_anchor, 0) >= 50  THEN 'regular'
                    WHEN COALESCE(lc.completed_trips_since_anchor, 0) >= 5   THEN 'occasional'
                    WHEN COALESCE(lc.completed_trips_since_anchor, 0) > 0    THEN 'light'
                    ELSE 'zero_trip'
                END AS sub_segment,
                NULL AS elite_tier,
                NULL AS loyalty_tier,
                lc.park_id,
                NULL AS park_name,
                NULL AS city,
                NULL AS country
            FROM growth.yego_lima_driver_lifecycle_daily lc
            WHERE lc.snapshot_date = %(d)s
            ON CONFLICT (target_date, driver_id) DO UPDATE SET
                segment = EXCLUDED.segment,
                sub_segment = EXCLUDED.sub_segment,
                elite_tier = EXCLUDED.elite_tier,
                loyalty_tier = EXCLUDED.loyalty_tier,
                park_id = EXCLUDED.park_id,
                park_name = EXCLUDED.park_name,
                city = EXCLUDED.city,
                country = EXCLUDED.country
        """, {"d": target_date})
        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_taxonomy_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 6: Program V2 Daily (Shadow) ───────────────────────────────────────

def _build_program_v2_daily(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_program_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )

        cur.execute("""
            INSERT INTO growth.yego_lima_v2_program_daily
                (target_date, driver_id, program_code, program_name,
                 eligibility_reason, priority_score, is_new_entry)
            SELECT
                %(d)s::date,
                lc.driver_profile_id AS driver_id,
                CASE
                    WHEN COALESCE(lc.completed_trips_7d, 0) >= 30
                        THEN 'PROGRAM_V2_HIGH_ACTIVITY'
                    WHEN COALESCE(lc.completed_trips_14d, 0) >= 30
                        THEN 'PROGRAM_V2_MEDIUM_ACTIVITY'
                    WHEN COALESCE(lc.completed_trips_30d, 0) > 0
                        THEN 'PROGRAM_V2_LOW_ACTIVITY'
                    ELSE 'PROGRAM_V2_INACTIVE'
                END AS program_code,
                CASE
                    WHEN COALESCE(lc.completed_trips_7d, 0) >= 30
                        THEN 'High Activity Drivers (7d >= 30 trips)'
                    WHEN COALESCE(lc.completed_trips_14d, 0) >= 30
                        THEN 'Medium Activity Drivers (14d >= 30 trips)'
                    WHEN COALESCE(lc.completed_trips_30d, 0) > 0
                        THEN 'Low Activity Drivers (30d > 0 trips)'
                    ELSE 'Inactive Drivers (no trips in 30d)'
                END AS program_name,
                CASE
                    WHEN COALESCE(lc.completed_trips_7d, 0) >= 30
                        THEN '7d trips >= 30'
                    WHEN COALESCE(lc.completed_trips_14d, 0) >= 30
                        THEN '14d trips >= 30'
                    WHEN COALESCE(lc.completed_trips_30d, 0) > 0
                        THEN '30d trips > 0'
                    ELSE 'No trips in 30d window'
                END AS eligibility_reason,
                COALESCE(lc.completed_trips_since_anchor, 0)::numeric AS priority_score,
                false AS is_new_entry
            FROM growth.yego_lima_driver_lifecycle_daily lc
            WHERE lc.snapshot_date = %(d)s
            ON CONFLICT (target_date, driver_id, program_code) DO UPDATE SET
                program_name = EXCLUDED.program_name,
                eligibility_reason = EXCLUDED.eligibility_reason,
                priority_score = EXCLUDED.priority_score,
                is_new_entry = EXCLUDED.is_new_entry
        """, {"d": target_date})
        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_program_daily WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 7: Movement Fact ───────────────────────────────────────────────────

def _build_movement_fact(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_movement_fact WHERE target_date = %(d)s",
            {"d": target_date}
        )

        inserted = 0

        # ── STATE_CHANGE from transition traces (primary source) ──
        cur.execute("""
            INSERT INTO growth.yego_lima_v2_movement_fact
                (target_date, driver_id, movement_type, from_state, to_state,
                 from_program, to_program, trigger_reason)
            SELECT
                %(d)s::date,
                driver_profile_id AS driver_id,
                'STATE_CHANGE' AS movement_type,
                state_before_json::text AS from_state,
                state_after_json::text AS to_state,
                NULL AS from_program,
                NULL AS to_program,
                trigger_reason
            FROM growth.yego_lima_state_transition_trace
            WHERE snapshot_after = %(d)s
            ON CONFLICT (target_date, driver_id, movement_type) DO NOTHING
        """, {"d": target_date})
        inserted += cur.rowcount

        # ── FALLBACK: STATE_CHANGE from taxonomy diff (when traces empty) ──
        if cur.rowcount == 0:
            prev_date = (date.fromisoformat(target_date) - timedelta(days=1)).isoformat()
            cur.execute("""
                INSERT INTO growth.yego_lima_v2_movement_fact
                    (target_date, driver_id, movement_type, from_state, to_state,
                     from_program, to_program, trigger_reason)
                SELECT
                    %(d)s::date,
                    t2.driver_id,
                    'STATE_CHANGE' AS movement_type,
                    COALESCE(t1.segment, 'UNKNOWN') AS from_state,
                    t2.segment AS to_state,
                    NULL AS from_program,
                    NULL AS to_program,
                    'segment_transition' AS trigger_reason
                FROM growth.yego_lima_v2_taxonomy_daily t2
                LEFT JOIN growth.yego_lima_v2_taxonomy_daily t1
                    ON t1.driver_id = t2.driver_id AND t1.target_date = %(prev)s
                WHERE t2.target_date = %(d)s
                  AND COALESCE(t1.segment, 'UNKNOWN') IS DISTINCT FROM t2.segment
                ON CONFLICT (target_date, driver_id, movement_type) DO NOTHING
            """, {"d": target_date, "prev": prev_date})
            inserted += cur.rowcount

        # ── PROGRAM_CHANGE from decision traces (primary source) ──
        cur.execute("""
            INSERT INTO growth.yego_lima_v2_movement_fact
                (target_date, driver_id, movement_type, from_state, to_state,
                 from_program, to_program, trigger_reason)
            SELECT
                %(d)s::date,
                driver_profile_id AS driver_id,
                'PROGRAM_CHANGE' AS movement_type,
                NULL AS from_state,
                NULL AS to_state,
                NULL AS from_program,
                selected_program_code AS to_program,
                selection_reason
            FROM growth.yego_lima_program_decision_trace
            WHERE snapshot_date = %(d)s
            ON CONFLICT (target_date, driver_id, movement_type) DO NOTHING
        """, {"d": target_date})
        inserted += cur.rowcount

        # ── FALLBACK: PROGRAM_CHANGE from program diff (when traces empty) ──
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO growth.yego_lima_v2_movement_fact
                    (target_date, driver_id, movement_type, from_state, to_state,
                     from_program, to_program, trigger_reason)
                SELECT
                    %(d)s::date,
                    p2.driver_id,
                    'PROGRAM_CHANGE' AS movement_type,
                    NULL AS from_state,
                    NULL AS to_state,
                    COALESCE(p1.program_code, 'UNASSIGNED') AS from_program,
                    p2.program_code AS to_program,
                    'program_assignment' AS trigger_reason
                FROM growth.yego_lima_v2_program_daily p2
                LEFT JOIN growth.yego_lima_v2_program_daily p1
                    ON p1.driver_id = p2.driver_id AND p1.target_date = %(prev)s
                WHERE p2.target_date = %(d)s
                  AND COALESCE(p1.program_code, 'UNASSIGNED') IS DISTINCT FROM p2.program_code
                ON CONFLICT (target_date, driver_id, movement_type) DO NOTHING
            """, {"d": target_date, "prev": prev_date})
            inserted += cur.rowcount

        conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_movement_fact WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 8: Observability Facts ─────────────────────────────────────────────

def _build_observability_facts(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_observability_fact WHERE target_date = %(d)s",
            {"d": target_date}
        )

        try:
            cur.execute("""
                INSERT INTO growth.yego_lima_v2_observability_fact
                    (target_date, module_name, artifact_count, with_refresh_count,
                     all_fresh, coverage_pct, latest_refresh_at)
                SELECT
                    %(d)s::date,
                    module_name,
                    artifact_count,
                    with_refresh_count,
                    all_fresh,
                    COALESCE(observability_coverage_pct, 0) AS coverage_pct,
                    latest_refresh_at
                FROM ops.v_observability_module_status
                ON CONFLICT (target_date, module_name) DO UPDATE SET
                    artifact_count = EXCLUDED.artifact_count,
                    with_refresh_count = EXCLUDED.with_refresh_count,
                    all_fresh = EXCLUDED.all_fresh,
                    coverage_pct = EXCLUDED.coverage_pct,
                    latest_refresh_at = EXCLUDED.latest_refresh_at
            """, {"d": target_date})
            conn.commit()
        except Exception:
            pass

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_observability_fact WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── STEP 9: Effectiveness Facts ─────────────────────────────────────────────

def _build_effectiveness_facts(target_date: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        _run_statement_timeout(cur, 120000)

        cur.execute(
            "DELETE FROM growth.yego_lima_v2_effectiveness_fact WHERE target_date = %(d)s",
            {"d": target_date}
        )

        try:
            cur.execute("""
                INSERT INTO growth.yego_lima_v2_effectiveness_fact
                    (target_date, campaign_id, campaign_name, total_members,
                     reactivated_count, reactivation_rate, avg_days_to_react)
                SELECT
                    %(d)s::date,
                    c.campaign_id::text,
                    c.campaign_name,
                    COUNT(DISTINCT cm.campaign_member_id) AS total_members,
                    COUNT(DISTINCT CASE WHEN ce.reactivated_flag THEN cm.campaign_member_id END) AS reactivated_count,
                    CASE WHEN COUNT(DISTINCT cm.campaign_member_id) > 0
                        THEN COUNT(DISTINCT CASE WHEN ce.reactivated_flag THEN cm.campaign_member_id END)::numeric
                             / COUNT(DISTINCT cm.campaign_member_id)::numeric
                        ELSE 0
                    END AS reactivation_rate,
                    AVG(ce.days_to_first_trip_after) AS avg_days_to_react
                FROM ops.driver_campaigns c
                LEFT JOIN ops.driver_campaign_members cm ON c.campaign_id = cm.campaign_id
                LEFT JOIN ops.driver_campaign_effectiveness ce
                    ON cm.campaign_member_id = ce.campaign_member_id
                WHERE c.created_at::date <= %(d)s
                GROUP BY c.campaign_id, c.campaign_name
                ON CONFLICT (target_date, campaign_id) DO UPDATE SET
                    campaign_name = EXCLUDED.campaign_name,
                    total_members = EXCLUDED.total_members,
                    reactivated_count = EXCLUDED.reactivated_count,
                    reactivation_rate = EXCLUDED.reactivation_rate,
                    avg_days_to_react = EXCLUDED.avg_days_to_react
            """, {"d": target_date})
            conn.commit()
        except Exception:
            pass

        cur.execute(
            "SELECT COUNT(*) FROM growth.yego_lima_v2_effectiveness_fact WHERE target_date = %(d)s",
            {"d": target_date}
        )
        return int(cur.fetchone()[0])


# ─── RUN LOG ──────────────────────────────────────────────────────────────────

def _create_run_log(run_id: str, target_date: str, status: str, triggered_by: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_RUN} (run_id, target_date, status, triggered_by) "
            f"VALUES (%(rid)s::uuid, %(d)s, %(st)s, %(tb)s)",
            {"rid": run_id, "d": target_date, "st": status, "tb": triggered_by}
        )
        conn.commit()


def _update_run_log(run_id: str, status: str, duration_ms: int,
                    steps: list, errors: list):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {TABLE_RUN} SET status = %(st)s, finished_at = now(), "
            f"duration_ms = %(dur)s, steps_json = %(steps)s::jsonb, "
            f"error_message = %(err)s "
            f"WHERE run_id = %(rid)s::uuid",
            {
                "st": status,
                "dur": duration_ms,
                "steps": json.dumps(steps, default=str),
                "err": errors[0][:500] if errors else None,
                "rid": run_id,
            }
        )
        conn.commit()


def _log_step(run_id: str, target_date: str, step_name: str, step_order: int,
              status: str, rows_before: int, rows_after: int,
              duration_ms: int, error_msg: Optional[str]):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_STEP} "
            f"(run_id, target_date, step_name, step_order, status, "
            f" rows_before, rows_after, duration_ms, error_message, finished_at) "
            f"VALUES (%(rid)s::uuid, %(d)s, %(sn)s, %(so)s, %(st)s, "
            f" %(rb)s, %(ra)s, %(dur)s, %(err)s, now())",
            {
                "rid": run_id, "d": target_date, "sn": step_name,
                "so": step_order, "st": status, "rb": rows_before,
                "ra": rows_after, "dur": duration_ms, "err": error_msg,
            }
        )
        conn.commit()


# ─── FRESHNESS REGISTRY V2 ────────────────────────────────────────────────────

def _update_freshness_registry(target_date: str, run_id: str,
                                steps: List[Dict[str, Any]]):
    step_lookup = {s["step"]: s for s in steps}
    now = _now_utc()

    component_map = {
        "build_activity_daily": "activity_daily",
        "build_activity_weekly": "activity_weekly",
        "build_activity_monthly": "activity_monthly",
        "build_lifecycle_daily": "lifecycle_daily",
        "build_taxonomy_v2_daily": "taxonomy_v2",
        "build_program_v2_daily": "program_v2",
        "build_movement_fact": "movement_fact",
        "build_observability_facts": "observability_fact",
        "build_effectiveness_facts": "effectiveness_fact",
    }

    with get_db() as conn:
        cur = conn.cursor()
        for step_name, _ in PIPELINE_STEPS:
            component = component_map.get(step_name, step_name)
            step_info = step_lookup.get(step_name, {})
            status = step_info.get("status", "UNKNOWN")
            rows = step_info.get("rows_after", 0)

            if status == STATUS_SUCCESS and rows > 0:
                freshness = "FRESH"
            elif status == STATUS_SUCCESS and rows == 0:
                freshness = "WARNING"
            elif status == STATUS_PARTIAL:
                freshness = "WARNING"
            elif status == STATUS_FAILED:
                freshness = "BROKEN"
            elif status == STATUS_SKIPPED_ALREADY_FRESH:
                freshness = "FRESH"
            elif status == STATUS_SKIPPED_NO_NEW_DATA:
                freshness = "STALE"
            else:
                freshness = "UNKNOWN"

            cur.execute(
                f"UPDATE {TABLE_FRESHNESS} SET "
                f"freshness_status = %(fs)s, last_refresh_at = %(now)s, "
                f"max_data_date = %(md)s, rows_count = %(rc)s, "
                f"run_id = %(rid)s, updated_at = %(now)s "
                f"WHERE component = %(c)s",
                {
                    "fs": freshness, "now": now, "md": target_date,
                    "rc": rows, "rid": run_id, "c": component,
                }
            )
        conn.commit()


# ─── STATUS ───────────────────────────────────────────────────────────────────

def get_v2_pipeline_status() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"SELECT * FROM {TABLE_RUN} ORDER BY started_at DESC LIMIT 1"
        )
        last_run = cur.fetchone()
        last_successful = None
        last_target_date = None

        if last_run:
            last_target_date = str(last_run["target_date"]) if last_run["target_date"] else None
            if last_run["status"] == STATUS_SUCCESS:
                last_successful = last_run["finished_at"].isoformat() if last_run["finished_at"] else None

        cur.execute(
            f"SELECT * FROM {TABLE_FRESHNESS} ORDER BY component"
        )
        freshness_rows = cur.fetchall()
        freshness = {}
        for r in freshness_rows:
            freshness[r["component"]] = {
                "status": r["freshness_status"],
                "last_refresh_at": r["last_refresh_at"].isoformat() if r["last_refresh_at"] else None,
                "max_data_date": str(r["max_data_date"]) if r["max_data_date"] else None,
                "rows_count": r["rows_count"],
            }

        cur.execute(
            f"SELECT step_name, status, rows_after, error_message "
            f"FROM {TABLE_STEP} WHERE target_date = %(d)s AND status = 'FAILED' "
            f"ORDER BY created_at DESC",
            {"d": last_target_date or _today_str()}
        )
        failed_steps = [dict(r) for r in cur.fetchall()]

    rows_by_fact = {}
    table_map = {
        "activity_daily": "growth.yego_lima_v2_activity_daily",
        "activity_weekly": "growth.yego_lima_v2_activity_weekly",
        "activity_monthly": "growth.yego_lima_v2_activity_monthly",
        "lifecycle_daily": "growth.yego_lima_v2_lifecycle_daily",
        "taxonomy_v2": "growth.yego_lima_v2_taxonomy_daily",
        "program_v2": "growth.yego_lima_v2_program_daily",
        "movement_fact": "growth.yego_lima_v2_movement_fact",
        "observability_fact": "growth.yego_lima_v2_observability_fact",
        "effectiveness_fact": "growth.yego_lima_v2_effectiveness_fact",
    }
    target = last_target_date or _today_str()

    with get_db() as conn:
        cur = conn.cursor()
        for label, table in table_map.items():
            try:
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE target_date = %(d)s",
                    {"d": target}
                )
                rows_by_fact[label] = int(cur.fetchone()[0])
            except Exception:
                rows_by_fact[label] = -1

    stale_count = sum(
        1 for v in freshness.values() if v["status"] in ("STALE", "BROKEN")
    )
    broken_count = sum(
        1 for v in freshness.values() if v["status"] == "BROKEN"
    )

    if broken_count > 0:
        operability = OPERABILITY_NOT_OPERABLE
    elif stale_count > 0:
        operability = OPERABILITY_DEGRADED
    else:
        operability = OPERABILITY_OPERABLE

    return {
        "last_successful_run": last_successful,
        "last_target_date": last_target_date,
        "freshness_by_layer": freshness,
        "failed_steps": failed_steps,
        "rows_by_fact": rows_by_fact,
        "operability": operability,
    }

