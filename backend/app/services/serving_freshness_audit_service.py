"""
LG-SERV-2A — Serving Freshness Audit Engine

Auto-audits freshness for all Lima Growth serving assets.
Calculates latest_data_date, last_refresh_at, freshness_age_hours.
Classifies: HEALTHY / WARNING / DEGRADED / CRITICAL.

Writes to growth.yego_lima_serving_freshness_fact.
Read-only on all source tables. NO modification of production data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_FRESHNESS_FACT = "growth.yego_lima_serving_freshness_fact"

STATUS_HEALTHY = "HEALTHY"
STATUS_WARNING = "WARNING"
STATUS_DEGRADED = "DEGRADED"
STATUS_CRITICAL = "CRITICAL"

_LIMA_TZ = timezone(timedelta(hours=-5))

SERVING_ASSETS: List[Dict[str, Any]] = [
    {
        "asset_name": "activity_daily",
        "schema": "growth",
        "table": "yego_lima_v2_activity_daily",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "ops.driver_daily_activity_fact",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "activity_weekly",
        "schema": "growth",
        "table": "yego_lima_v2_activity_weekly",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "ops.driver_daily_activity_fact (7d rolling)",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date (7d window)",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "activity_monthly",
        "schema": "growth",
        "table": "yego_lima_v2_activity_monthly",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "ops.driver_daily_activity_fact (30d rolling)",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date (30d window)",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "lifecycle_daily",
        "schema": "growth",
        "table": "yego_lima_v2_lifecycle_daily",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "growth.yego_lima_driver_lifecycle_daily",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "taxonomy_v2",
        "schema": "growth",
        "table": "yego_lima_v2_taxonomy_daily",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "growth.yego_lima_driver_lifecycle_daily",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "program_v2",
        "schema": "growth",
        "table": "yego_lima_v2_program_daily",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "growth.yego_lima_driver_lifecycle_daily",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "movement_fact",
        "schema": "growth",
        "table": "yego_lima_v2_movement_fact",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "growth.yego_lima_state_transition_trace + growth.yego_lima_program_decision_trace",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "observability_fact",
        "schema": "growth",
        "table": "yego_lima_v2_observability_fact",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "ops.v_observability_module_status",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "effectiveness_fact",
        "schema": "growth",
        "table": "yego_lima_v2_effectiveness_fact",
        "date_col": "target_date",
        "owner": "V2 Daily Pipeline",
        "source": "ops.driver_campaigns + ops.driver_campaign_effectiveness",
        "scheduler": "lima_growth_v2_daily_pipeline (04:45)",
        "refresh_method": "DELETE + INSERT per target_date",
        "expected_sla_hours": 25,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "program_assignment",
        "schema": "growth",
        "table": "yango_lima_program_eligibility_daily",
        "date_col": "eligibility_date",
        "owner": "Autonomous Tick Scheduler",
        "source": "growth.yango_lima_driver_state_snapshot",
        "scheduler": "lima_growth_autonomous_tick (every 5min)",
        "refresh_method": "build_program_eligibility per date",
        "expected_sla_hours": 5,
        "criticality": STATUS_CRITICAL,
    },
    {
        "asset_name": "serving_driver_explorer",
        "schema": "growth",
        "table": "yego_lima_serving_fact",
        "date_col": "fact_date",
        "owner": "Serving Facts Service",
        "source": "Multiple (8 fact types)",
        "scheduler": "lima_growth_autonomous_tick (every 5min)",
        "refresh_method": "generate_all_serving_facts per date",
        "expected_sla_hours": 5,
        "criticality": STATUS_CRITICAL,
    },
    {
        "asset_name": "driver_state_snapshot",
        "schema": "growth",
        "table": "yango_lima_driver_state_snapshot",
        "date_col": "snapshot_date",
        "owner": "Autonomous Tick Scheduler",
        "source": "Yango API + growth.yango_lima_driver_history_daily",
        "scheduler": "lima_growth_autonomous_tick (every 5min)",
        "refresh_method": "build_driver_state_snapshot per date",
        "expected_sla_hours": 5,
        "criticality": STATUS_CRITICAL,
    },
    {
        "asset_name": "RNA_serving",
        "schema": "growth",
        "table": "yango_lima_driver_history_daily",
        "date_col": "date",
        "owner": "Autonomous Tick Scheduler",
        "source": "raw_yango.orders_raw",
        "scheduler": "lima_growth_autonomous_tick (every 5min)",
        "refresh_method": "Incremental upsert from orders",
        "expected_sla_hours": 6,
        "criticality": STATUS_HEALTHY,
    },
    {
        "asset_name": "daily_opportunity_list",
        "schema": "growth",
        "table": "yango_lima_daily_opportunity_list",
        "date_col": "opportunity_date",
        "owner": "Autonomous Tick Scheduler",
        "source": "growth.yango_lima_program_eligibility_daily + growth.yango_lima_driver_state_snapshot",
        "scheduler": "lima_growth_autonomous_tick (every 5min)",
        "refresh_method": "build_daily_opportunity_lists per date",
        "expected_sla_hours": 8,
        "criticality": STATUS_CRITICAL,
    },
    {
        "asset_name": "control_loop_state",
        "schema": "growth",
        "table": "yego_lima_control_loop_state",
        "date_col": "created_at",
        "owner": "Autonomous Tick Scheduler",
        "source": "growth.yego_lima_assignment_queue",
        "scheduler": "lima_growth_autonomous_tick (every 5min)",
        "refresh_method": "sync_assignment_queue_to_control_loop (INSERT with NOT EXISTS guard)",
        "expected_sla_hours": 8,
        "criticality": STATUS_CRITICAL,
    },
    {
        "asset_name": "driver_history_weekly",
        "schema": "growth",
        "table": "yango_lima_driver_history_weekly",
        "date_col": "week_start_date",
        "owner": "Autonomous Tick Scheduler",
        "source": "growth.yango_lima_driver_history_daily",
        "scheduler": "lima_growth_autonomous_tick (every 5min, conditional)",
        "refresh_method": "refresh_weekly_history per tick (idempotent UPSERT)",
        "expected_sla_hours": 168,
        "criticality": STATUS_CRITICAL,
    },
]


def _ensure_freshness_fact_table():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS growth.yego_lima_serving_freshness_fact (
                    asset_name          text NOT NULL,
                    latest_data_date    date,
                    last_refresh_at     timestamptz,
                    freshness_age_hours numeric(10,2),
                    status              text NOT NULL DEFAULT 'UNKNOWN',
                    rows_count          integer DEFAULT 0,
                    expected_sla_hours  integer,
                    checked_at          timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (asset_name)
                )
            """)
            conn.commit()
    except Exception:
        pass


def _now():
    return datetime.now(timezone.utc)


def run_freshness_audit() -> Dict[str, Any]:
    _ensure_freshness_fact_table()

    now = _now()
    results: List[Dict[str, Any]] = []

    for asset in SERVING_ASSETS:
        asset_name = asset["asset_name"]
        schema = asset["schema"]
        table = asset["table"]
        date_col = asset["date_col"]
        sla_hours = asset.get("expected_sla_hours", 25)

        latest_data_date = None
        rows_count = 0
        last_refresh_at = now

        try:
            with get_db() as conn:
                cur = conn.cursor()
                full_table = f"{schema}.{table}"
                cur.execute(f"SELECT MAX({date_col}), COUNT(*) FROM {full_table}")
                row = cur.fetchone()
                if row:
                    latest_data_date = row[0]
                    rows_count = int(row[1]) if row[1] else 0
        except Exception as e:
            logger.warning("Freshness audit: cannot read %s.%s: %s", schema, table, e)

        freshness_age_hours = None
        status = STATUS_CRITICAL

        if latest_data_date:
            if isinstance(latest_data_date, datetime):
                data_dt = latest_data_date
            elif isinstance(latest_data_date, str):
                try:
                    data_dt = datetime.fromisoformat(latest_data_date[:10])
                except (ValueError, TypeError):
                    data_dt = None
            else:
                data_dt = latest_data_date

            if data_dt:
                if not isinstance(data_dt, datetime):
                    try:
                        data_dt = datetime.combine(data_dt, datetime.min.time())
                    except (TypeError, ValueError):
                        data_dt = None

            if data_dt:
                if data_dt.tzinfo is None:
                    data_dt = data_dt.replace(tzinfo=timezone.utc)
                freshness_age_hours = round((now - data_dt).total_seconds() / 3600, 2)

        if freshness_age_hours is None:
            status = STATUS_CRITICAL
        elif freshness_age_hours <= sla_hours:
            status = STATUS_HEALTHY
        elif freshness_age_hours <= sla_hours * 1.5:
            status = STATUS_WARNING
        elif freshness_age_hours <= sla_hours * 3:
            status = STATUS_DEGRADED
        else:
            status = STATUS_CRITICAL

        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"INSERT INTO {TABLE_FRESHNESS_FACT} "
                    f"(asset_name, latest_data_date, last_refresh_at, "
                    f" freshness_age_hours, status, rows_count, expected_sla_hours, checked_at) "
                    f"VALUES (%(a)s, %(ld)s, %(lr)s, %(fh)s, %(st)s, %(rc)s, %(sl)s, %(now)s) "
                    f"ON CONFLICT (asset_name) DO UPDATE SET "
                    f"latest_data_date = EXCLUDED.latest_data_date, "
                    f"last_refresh_at = EXCLUDED.last_refresh_at, "
                    f"freshness_age_hours = EXCLUDED.freshness_age_hours, "
                    f"status = EXCLUDED.status, "
                    f"rows_count = EXCLUDED.rows_count, "
                    f"expected_sla_hours = EXCLUDED.expected_sla_hours, "
                    f"checked_at = EXCLUDED.checked_at",
                    {
                        "a": asset_name,
                        "ld": latest_data_date,
                        "lr": now,
                        "fh": freshness_age_hours,
                        "st": status,
                        "rc": rows_count,
                        "sl": sla_hours,
                        "now": now,
                    }
                )
                conn.commit()
        except Exception as e:
            logger.warning("Freshness audit: cannot write %s: %s", asset_name, e)

        results.append({
            "asset_name": asset_name,
            "latest_data_date": str(latest_data_date)[:10] if latest_data_date else None,
            "freshness_age_hours": freshness_age_hours,
            "status": status,
            "rows_count": rows_count,
            "expected_sla_hours": sla_hours,
            "owner": asset["owner"],
            "scheduler": asset["scheduler"],
        })

    healthy = sum(1 for r in results if r["status"] == STATUS_HEALTHY)
    warning = sum(1 for r in results if r["status"] == STATUS_WARNING)
    degraded = sum(1 for r in results if r["status"] == STATUS_DEGRADED)
    critical = sum(1 for r in results if r["status"] == STATUS_CRITICAL)

    if critical > 0:
        overall = STATUS_CRITICAL
    elif degraded > 0:
        overall = STATUS_DEGRADED
    elif warning > 2:
        overall = STATUS_WARNING
    else:
        overall = STATUS_HEALTHY

    return {
        "overall_status": overall,
        "checked_at": now.isoformat(),
        "assets": results,
        "summary": {
            "healthy": healthy,
            "warning": warning,
            "degraded": degraded,
            "critical": critical,
            "total": len(results),
        },
    }


def get_freshness_audit_status() -> Dict[str, Any]:
    _ensure_freshness_fact_table()

    now = _now()
    results: List[Dict[str, Any]] = []

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT asset_name, latest_data_date, last_refresh_at, "
                f"freshness_age_hours, status, rows_count, expected_sla_hours, checked_at "
                f"FROM {TABLE_FRESHNESS_FACT} ORDER BY asset_name"
            )
            for row in cur.fetchall():
                results.append({
                    "asset_name": row[0],
                    "latest_data_date": str(row[1])[:10] if row[1] else None,
                    "last_refresh_at": row[2].isoformat() if row[2] else None,
                    "freshness_age_hours": round(float(row[3]), 2) if row[3] else None,
                    "status": row[4],
                    "rows_count": row[5] or 0,
                    "expected_sla_hours": row[6],
                    "checked_at": row[7].isoformat() if row[7] else None,
                })
    except Exception as e:
        logger.warning("Cannot read freshness_fact: %s", e)
        return {"overall_status": STATUS_CRITICAL, "error": str(e), "assets": []}

    critical = sum(1 for r in results if r["status"] == STATUS_CRITICAL)
    degraded = sum(1 for r in results if r["status"] == STATUS_DEGRADED)
    warning = sum(1 for r in results if r["status"] == STATUS_WARNING)
    healthy = sum(1 for r in results if r["status"] == STATUS_HEALTHY)

    if critical > 0:
        overall = STATUS_CRITICAL
    elif degraded > 0:
        overall = STATUS_DEGRADED
    elif warning > 2:
        overall = STATUS_WARNING
    else:
        overall = STATUS_HEALTHY

    return {
        "overall_status": overall,
        "checked_at": now.isoformat(),
        "assets": results,
        "summary": {
            "healthy": healthy,
            "warning": warning,
            "degraded": degraded,
            "critical": critical,
            "total": len(results),
        },
    }
