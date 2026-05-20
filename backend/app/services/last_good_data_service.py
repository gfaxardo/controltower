"""
Last Good Data Service — Snapshots + Serving Stability.
Fase 1E — Protege data cerrada con snapshots estables.

Provee:
  - create_snapshot_for_period()
  - get_active_snapshot()
  - validate_snapshot()
  - get_serving_source()
  - rollback_to_snapshot()
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_snapshot_for_period(
    grain: str = "monthly",
    period_start: Optional[date] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if period_start is None:
        period_start = date.today().replace(day=1)

    if grain == "monthly":
        fact_table = "ops.real_business_slice_month_fact"
        snap_table = "ops.real_business_slice_month_snapshot"
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - __import__("datetime").timedelta(days=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1, day=1) - __import__("datetime").timedelta(days=1)
    else:
        return {"created": False, "reason": f"Grain {grain} not supported"}

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get row count from fact
        cur.execute(f"SELECT COUNT(*) as cnt FROM {fact_table} WHERE month = %s", (str(period_start),))
        row = cur.fetchone()
        fact_rows = int(row["cnt"]) if row else 0

        if fact_rows == 0:
            cur.close()
            return {"created": False, "reason": "No fact data for this period"}

        # Check existing active snapshot
        cur.execute(f"""
            SELECT snapshot_id, snapshot_version FROM {snap_table}
            WHERE period_start = %s AND snapshot_status = 'active'
        """, (str(period_start),))
        existing = cur.fetchone()

        version = "1"
        if existing:
            try:
                version = str(int(existing["snapshot_version"]) + 1)
            except ValueError:
                version = "1"

        # Supersede previous
        cur.execute(f"""
            UPDATE {snap_table} SET snapshot_status = 'superseded'
            WHERE period_start = %s AND snapshot_status = 'active'
        """, (str(period_start),))

        # Compute checksum
        cur.execute(f"""
            SELECT MD5(STRING_AGG(
                COALESCE(business_slice_name,'') || '|' ||
                COALESCE(fleet_display_name,'') || '|' ||
                trips_completed::text || '|' ||
                COALESCE(active_drivers::text, '0'),
                '|' ORDER BY business_slice_name, fleet_display_name
            )) as csum
            FROM {fact_table}
            WHERE month = %s
        """, (str(period_start),))
        checksum_row = cur.fetchone()
        checksum = checksum_row["csum"] if checksum_row else None

        # Get closure registry ID
        cur.execute("""
            SELECT id FROM ops.period_closure_registry
            WHERE grain = 'monthly' AND period_start = %s AND status = 'locked'
            LIMIT 1
        """, (str(period_start),))
        closure = cur.fetchone()
        closure_id = int(closure["id"]) if closure else None

        # Create snapshot
        cur.execute(f"""
            INSERT INTO {snap_table} (
                month, country, city, business_slice_name, fleet_display_name,
                is_subfleet, subfleet_name, parent_fleet_name,
                trips_completed, trips_cancelled, active_drivers,
                connected_only_drivers, connected_only_drivers_status,
                avg_ticket, commission_pct, trips_per_driver,
                revenue_yego_net, precio_km, tiempo_km,
                completados_por_hora, cancelados_por_hora, refreshed_at,
                snapshot_version, snapshot_status, grain,
                period_start, period_end,
                closure_registry_id,
                source_fact_checksum, snapshot_checksum,
                row_count, created_by, created_at, notes
            )
            SELECT
                month, country, city, business_slice_name, fleet_display_name,
                is_subfleet, subfleet_name, parent_fleet_name,
                trips_completed, trips_cancelled, active_drivers,
                connected_only_drivers, connected_only_drivers_status,
                avg_ticket, commission_pct, trips_per_driver,
                revenue_yego_net, precio_km, tiempo_km,
                completados_por_hora, cancelados_por_hora, refreshed_at,
                %s, 'active', 'monthly',
                %s, %s,
                %s,
                %s, %s,
                %s, %s, NOW(), 'Snapshot created by last_good_data_service'
            FROM {fact_table}
            WHERE month = %s
        """, (
            version, str(period_start), str(period_end),
            closure_id,
            checksum, checksum,
            fact_rows, created_by or "system",
            str(period_start),
        ))
        inserted = cur.rowcount
        conn.commit()

        # Get new snapshot ID
        cur.execute(f"""
            SELECT snapshot_id FROM {snap_table}
            WHERE period_start = %s AND snapshot_status = 'active'
            ORDER BY snapshot_id DESC LIMIT 1
        """, (str(period_start),))
        snap = cur.fetchone()
        cur.close()

        return {
            "created": True,
            "snapshot_id": int(snap["snapshot_id"]) if snap else None,
            "version": version,
            "checksum": checksum,
            "row_count": fact_rows,
            "period_start": str(period_start),
            "period_end": str(period_end),
        }


def get_active_snapshot(
    grain: str = "monthly",
    period_start: Optional[date] = None,
) -> Dict[str, Any]:
    if period_start is None:
        period_start = date.today().replace(day=1)

    snap_table = "ops.real_business_slice_month_snapshot"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT snapshot_id, snapshot_version, snapshot_status,
                   snapshot_checksum, row_count, created_at, period_start, period_end
            FROM {snap_table}
            WHERE period_start = %s AND snapshot_status = 'active'
            ORDER BY snapshot_id DESC LIMIT 1
        """, (str(period_start),))
        row = cur.fetchone()
        cur.close()

    if not row:
        return {"active": False, "period_start": str(period_start)}

    return {
        "active": True,
        "snapshot_id": int(row["snapshot_id"]),
        "version": row["snapshot_version"],
        "status": row["snapshot_status"],
        "checksum": row["snapshot_checksum"],
        "row_count": int(row["row_count"]) if row["row_count"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "period_start": str(row["period_start"]),
        "period_end": str(row["period_end"]),
    }


def validate_snapshot(
    grain: str = "monthly",
    period_start: Optional[date] = None,
) -> Dict[str, Any]:
    snap = get_active_snapshot(grain, period_start)
    if not snap.get("active"):
        return {"valid": False, "reason": "No active snapshot"}

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT SUM(trips_completed) as trips
            FROM ops.real_business_slice_month_fact
            WHERE month = %s
        """, (snap["period_start"],))
        fact = cur.fetchone()
        cur.execute("""
            SELECT SUM(trips_completed) as trips
            FROM ops.real_business_slice_month_snapshot
            WHERE snapshot_id = %s
        """, (snap["snapshot_id"],))
        snap_row = cur.fetchone()
        cur.close()

    fact_trips = int(fact["trips"]) if fact and fact["trips"] else 0
    snap_trips = int(snap_row["trips"]) if snap_row and snap_row["trips"] else 0

    return {
        "valid": fact_trips == snap_trips and fact_trips > 0,
        "fact_trips": fact_trips,
        "snapshot_trips": snap_trips,
        "checksum": snap.get("checksum"),
        "row_count": snap.get("row_count"),
    }


def get_serving_source(
    grain: str = "monthly",
    period_start: Optional[date] = None,
) -> Dict[str, Any]:
    if period_start is None:
        period_start = date.today().replace(day=1)

    snap = get_active_snapshot(grain, period_start)

    # Check if period is locked
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT status FROM ops.period_closure_registry
            WHERE grain = %s AND period_start = %s
            ORDER BY updated_at DESC LIMIT 1
        """, (grain, str(period_start)))
        row = cur.fetchone()
        period_status = row["status"] if row else "open"
        cur.close()

    if period_status in ("locked", "closed") and snap.get("active"):
        return {
            "serving_source": "snapshot",
            "data_status": "locked_snapshot",
            "snapshot": snap,
            "period_status": period_status,
        }

    return {
        "serving_source": "working_fact",
        "data_status": period_status if period_status == "open" else f"{period_status}_no_snapshot",
        "period_status": period_status,
    }
