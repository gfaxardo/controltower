"""
Omniview V2 Shadow Router — parallel API for raw_yango MVs.
Shadow mode: independent from Omniview V1. canonical_ready always false.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.omniview_v2_shadow_service import build_shadow_response

router = APIRouter(prefix="/ops/omniview-v2-shadow", tags=["omniview_v2_shadow"])


@router.get("/daily")
def shadow_daily(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """KPIs from raw_yango MVs: orders, revenue, coverage per day."""
    return build_shadow_response(park_id=park_id, date_from=date_from, date_to=date_to)


@router.get("/coverage")
def shadow_coverage(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Source coverage by day from raw_yango MVs."""
    from app.repositories.omniview_v2_shadow_repository import (
        get_coverage_by_day,
        get_source_health,
    )
    return {
        "source": "YANGO_API_SHADOW",
        "status": "SHADOW_ONLY",
        "health": get_source_health(park_id),
        "daily": get_coverage_by_day(park_id, date_from, date_to),
    }


@router.get("/reconciliation")
def shadow_reconciliation(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Reconciliation of raw_yango MVs vs CT day_fact."""
    from app.repositories.omniview_v2_shadow_repository import (
        get_reconciliation_vs_ct,
    )
    return {
        "source": "YANGO_API_SHADOW",
        "status": "SHADOW_ONLY",
        "canonical_ready": False,
        "reconciliation": get_reconciliation_vs_ct(park_id, date_from, date_to),
    }


@router.get("/health")
def shadow_health(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
):
    """Health check for shadow API — coverage status, warnings."""
    from app.services.omniview_v2_shadow_service import build_shadow_response
    return build_shadow_response(park_id=park_id)


@router.get("/multipark-health")
def multipark_shadow_health():
    """CF-H2E.3: Consolidated multipark shadow health.
    Shows per-park: freshness, watermark, ingestion status, reconciliation delta.
    """
    from app.db.connection import get_db
    from datetime import datetime, timezone, timedelta

    PILOT_PARKS = [
        ("08e20910d81d42658d4334d3f6d10ac0", "Yego Lima", "Lima", "peru"),
        ("851e30755bba4d298e2e837f571b4ab8", "Yego Trujillo", "Trujillo", "peru"),
        ("56e4607dfc354e0a9cde4f0aa7973003", "Yego Arequipa", "Arequipa", "peru"),
        ("64085dd85e124e2c808806f70d527ea8", "Yego Pro", "Lima", "peru"),
        ("e3e07c00ed914f82a59c03283a178d6e", "Yego TukTuk", "Lima", "peru"),
    ]

    now = datetime.now(timezone.utc)
    parks_health = []

    try:
        with get_db() as conn:
            cur = conn.cursor()
            for pid, pname, city, country in PILOT_PARKS:
                # Watermark freshness
                cur.execute(
                    "SELECT endpoint_group, last_event_at, last_run_at, status "
                    "FROM raw_yango.ingestion_watermark WHERE park_id=%s",
                    (pid,),
                )
                wms = cur.fetchall()
                wm_info = {}
                for wm in wms:
                    ep = wm[0]
                    last_evt = wm[1]
                    last_run = wm[2]
                    wm_status = wm[3]
                    freshness_min = None
                    if last_run:
                        delta = (now - last_run.replace(tzinfo=timezone.utc) if last_run.tzinfo is None else (now - last_run))
                        freshness_min = round(delta.total_seconds() / 60, 1)
                    fresh_status = "FRESH"
                    if freshness_min and freshness_min > 1440:
                        fresh_status = "STALE"
                    elif freshness_min and freshness_min > 360:
                        fresh_status = "WARNING"
                    elif not last_run:
                        fresh_status = "FAILED"
                    wm_info[ep] = {
                        "last_event_at": str(last_evt)[:19] if last_evt else None,
                        "last_run_at": str(last_run)[:19] if last_run else None,
                        "freshness_minutes": freshness_min,
                        "freshness_status": fresh_status,
                        "watermark_status": wm_status,
                    }

                # Record counts
                cur.execute("SELECT COUNT(*) FROM raw_yango.orders_raw WHERE park_id=%s", (pid,))
                orders_count = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM raw_yango.transactions_raw WHERE park_id=%s", (pid,))
                txns_count = cur.fetchone()[0] or 0

                # Recent reconciliation (CT vs Yango for yesterday)
                yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
                reconciliation = None
                try:
                    cur.execute("""
                        SELECT SUM(COALESCE(orders_completed,0)), SUM(COALESCE(unique_drivers,0))
                        FROM raw_yango.mv_orders_day
                        WHERE park_id=%s AND order_date=%s
                    """, (pid, yesterday))
                    y_row = cur.fetchone()
                    y_trips = int(y_row[0] or 0) if y_row else 0
                    y_drivers = int(y_row[1] or 0) if y_row else 0

                    if y_trips > 0:
                        reconciliation = {
                            "date": yesterday,
                            "yango_trips": y_trips,
                            "yango_drivers": y_drivers,
                            "status": "DATA_AVAILABLE",
                        }
                    else:
                        reconciliation = {"date": yesterday, "status": "NO_DATA"}
                except Exception:
                    reconciliation = {"date": yesterday, "status": "ERROR"}

                parks_health.append({
                    "park_id": pid,
                    "park_name": pname,
                    "city": city,
                    "country": country,
                    "watermarks": wm_info,
                    "total_orders_ingested": orders_count,
                    "total_transactions_ingested": txns_count,
                    "reconciliation_yesterday": reconciliation,
                })
            cur.close()
    except Exception as e:
        return {"error": str(e)[:200], "parks": []}

    fresh_count = sum(1 for p in parks_health
                      if all(w.get("freshness_status") == "FRESH" for w in p.get("watermarks", {}).values()))
    stale_count = sum(1 for p in parks_health
                      if any(w.get("freshness_status") == "STALE" for w in p.get("watermarks", {}).values()))
    failed_count = sum(1 for p in parks_health
                       if any(w.get("freshness_status") == "FAILED" for w in p.get("watermarks", {}).values()))

    return {
        "generated_at": now.isoformat(),
        "shadow_status": "OPERATIONAL" if failed_count == 0 else "DEGRADED",
        "parks_monitored": len(parks_health),
        "fresh_parks": fresh_count,
        "stale_parks": stale_count,
        "failed_parks": failed_count,
        "parks": parks_health,
    }
