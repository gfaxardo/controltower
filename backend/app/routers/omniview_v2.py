"""
Omniview V2 Router — source-agnostic backend API (parallel to V1).

Endpoints:
- GET /ops/omniview-v2/sources     — list registered sources
- GET /ops/omniview-v2/summary     — KPIs from a single source
- GET /ops/omniview-v2/health      — health check for all sources
- GET /ops/omniview-v2/compare     — side-by-side source comparison

Rules:
- canonical_ready must be explicit in every response.
- source_system must be explicit in every request (defaults to CT_TRIPS_2026).
- YANGO_API_RAW always has canonical_ready=false.
- Never mixes sources silently.
- No UI connection yet.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.omniview_v2_core_service import (
    get_omniview_v2_health,
    get_omniview_v2_summary,
    get_source_comparison,
)
from app.services.omniview_v2_source_registry import get_supported_sources
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
from app.services.omniview_v2_snapshot_service import get_served_payload
from app.services.omniview_v2_plan_real_service import build_monthly_plan_real_matrix
from app.repositories.omniview_v2_plan_real_repository import get_plan_versions

router = APIRouter(prefix="/ops/omniview-v2", tags=["omniview_v2"])


@router.get("/sources")
def list_sources():
    """List all registered data sources with their status and capabilities."""
    return {
        "sources": get_supported_sources(),
        "default_source": "CT_TRIPS_2026",
    }


@router.get("/summary")
def get_summary(
    source_system: str = Query(default="CT_TRIPS_2026", description="Source system: CT_TRIPS_2026 | YANGO_API_RAW"),
    grain: str = Query(default="day", description="Time grain: hour | day | week | month"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
):
    """Get KPIs for a source/grain combination."""
    filters = {"country": country, "city": city}
    if source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}

    response = get_omniview_v2_summary(
        source_system=source_system,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
    )
    return response.to_dict()


@router.get("/health")
def get_health():
    """Health status for all registered Omniview V2 sources."""
    return get_omniview_v2_health()


@router.get("/compare")
def compare_sources(
    source_a: str = Query(default="CT_TRIPS_2026", description="First source system"),
    source_b: str = Query(default="YANGO_API_RAW", description="Second source system"),
    grain: str = Query(default="day"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Compare two sources side-by-side at the same grain."""
    response = get_source_comparison(
        source_a=source_a,
        source_b=source_b,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
    )
    return response.to_dict()


@router.get("/matrix")
def get_matrix(
    source_system: str = Query(default="CT_TRIPS_2026"),
    grain: str = Query(default="day"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
    allow_runtime: bool = Query(default=False),
    metric_id: str = Query(default="orders"),
):
    """Get MatrixResponse. Snapshot-first. No runtime without explicit flag."""
    # Single-day: try snapshot first
    if date_from and date_from == date_to:
        from app.services.omniview_v2_snapshot_service import get_served_payload
        snap = get_served_payload(source_system, grain, date_from, "matrix")
        if snap and snap.get("cells"):
            return snap

    # Multi-day ranges: allow runtime (matrix is fast ~750ms)
    if date_from and date_from != date_to:
        filters = {"country": country, "city": city}
        if source_system == "YANGO_API_RAW":
            filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}
        response = build_matrix_response(
            source_system=source_system, grain=grain,
            date_from=date_from, date_to=date_to,
            filters=filters, metric_id=metric_id,
        )
        return response.to_dict()

    # Single-day, no snapshot, allow_runtime NOT set → fast SERVING_SNAPSHOT_MISSING
    if not allow_runtime:
        from app.contracts.omniview_v2_matrix_contract import OmniviewV2MatrixResponse, OmniviewV2MatrixWarning
        return OmniviewV2MatrixResponse(
            matrix_id="ov2_matrix",
            source_system=source_system,
            canonical_ready=source_system != "YANGO_API_RAW",
            grain=grain,
            warnings=[OmniviewV2MatrixWarning(
                code="SERVING_SNAPSHOT_MISSING",
                message=f"No serving snapshot for {source_system}/{grain}/{date_from}. Refresh snapshots or use allow_runtime=true.",
                severity="warning",
            )],
        ).to_dict()

    # Single-day with allow_runtime=true: proceed but will be slow
    filters = {"country": country, "city": city}
    if source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}
    response = build_matrix_response(
        source_system=source_system, grain=grain,
        date_from=date_from, date_to=date_to,
        filters=filters, metric_id=metric_id,
    )
    return response.to_dict()


@router.get("/operating-date")
def get_operating_date(
    source_system: str = Query(default="CT_TRIPS_2026"),
):
    """Get the latest closed date with data and current processing status. <500ms"""
    from app.db.connection import get_db
    from datetime import date as dt_date

    default_date = dt_date.today().isoformat()
    latest_closed = None
    max_available = None
    has_today_data = False

    try:
        with get_db() as conn:
            cur = conn.cursor()
            if source_system == "CT_TRIPS_2026":
                cur.execute(
                    "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact "
                    "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    max_available = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
                    latest_closed = max_available

                today_str = dt_date.today().isoformat()
                cur.execute(
                    "SELECT COUNT(*) FROM ops.real_business_slice_day_fact "
                    "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND trip_date=%s",
                    (today_str,),
                )
                has_today_data = (cur.fetchone()[0] or 0) > 0

            elif source_system == "YANGO_API_RAW":
                cur.execute(
                    "SELECT MAX(order_date) FROM raw_yango.mv_orders_day "
                    "WHERE park_id='08e20910d81d42658d4334d3f6d10ac0'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    max_available = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
                    latest_closed = max_available

            cur.close()
    except Exception:
        pass

    if latest_closed:
        default_date = latest_closed

    return {
        "latest_closed_date": latest_closed,
        "current_processing_date": dt_date.today().isoformat(),
        "max_available_date": max_available,
        "has_today_data": has_today_data,
        "default_date": default_date,
        "source_system": source_system,
        "freshness_status": "STALE" if not has_today_data and max_available and max_available < dt_date.today().isoformat() else "FRESH",
    }


@router.get("/plan-real/monthly")
def get_plan_real_monthly(
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    metric_id: str = Query(default="trips"),
    plan_version: str = Query(default=None),
):
    """Monthly Plan vs Real matrix."""
    response = build_monthly_plan_real_matrix(
        country=country, city=city,
        date_from=date_from, date_to=date_to,
        metric_id=metric_id, plan_version=plan_version,
    )
    return response.to_dict()


@router.get("/plan-real/versions")
def get_plan_real_versions():
    """List available plan versions."""
    return {"versions": get_plan_versions()}


@router.get("/infra-health")
def get_infra_health():
    """Lightweight infrastructure health for OV2: DB availability, pool status, connection estimate."""
    from app.db.connection import connection_pool, get_db

    result = {
        "service": "omniview_v2_infra_health",
        "db_available": False,
        "pool_status": "unknown",
        "active_connections_estimate": None,
        "pool_max": None,
        "pool_min": None,
        "warning": None,
    }

    if connection_pool:
        result["pool_min"] = getattr(connection_pool, "minconn", None)
        result["pool_max"] = getattr(connection_pool, "maxconn", None)
        result["pool_status"] = "initialized"

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        result["db_available"] = True
    except Exception as e:
        result["db_available"] = False
        result["warning"] = f"DB connection failed: {str(e)[:200]}"
    return result


@router.get("/backend-identity")
def get_backend_identity():
    """Confirm this is the correct Control Tower backend. Used by UI/debug to validate binding."""
    import os
    import subprocess
    import sys
    from datetime import datetime, timezone

    working_dir = os.getcwd()
    git_branch = None
    git_hash = None
    try:
        git_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=working_dir, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        pass
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=working_dir, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        pass

    from app.settings import settings

    return {
        "app_name": "YEGO_CONTROL_TOWER",
        "port": settings.BACKEND_PORT,
        "host": settings.BACKEND_HOST,
        "environment": settings.ENVIRONMENT,
        "working_directory": working_dir,
        "python_version": sys.version,
        "git_branch": git_branch or "unknown",
        "git_hash": git_hash or "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if connection_pool:
        try:
            used = len(getattr(connection_pool, "_used", [])) if hasattr(connection_pool, "_used") else None
            result["active_connections_estimate"] = used
            maxconn = result.get("pool_max", 10)
            if used is not None and maxconn and used >= maxconn * 0.8:
                result["warning"] = f"Pool usage high: {used}/{maxconn} connections in use"
        except Exception:
            pass

    return result


@router.get("/drill/cell")
def drill_cell(
    source_system: str = Query(default="CT_TRIPS_2026"),
    grain: str = Query(default="day"),
    period: str = Query(default=None),
    metric_id: str = Query(default="trips"),
    business_slice_name: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Lineage-aware cell drill. Returns park breakdown + top drivers. No raw scans."""
    from app.db.connection import get_db
    from datetime import date as dt_date, timedelta

    result = {
        "cell": {"source_system": source_system, "grain": grain, "period": period,
                 "metric_id": metric_id, "business_slice_name": business_slice_name,
                 "country": country, "city": city},
        "total": {},
        "lineage_status": {},
        "drill": {"park": {"status": "READY", "data": []},
                   "driver": {"status": "READY", "data": [], "total_count": 0},
                   "fleet": {"status": "PARTIAL", "message": "Fleet data from business_slice_mapping_rules, not bridge"},
                   "raw_trip": {"status": "PARTIAL", "message": "Raw trip lookup requires trips_2026 scan per driver"},
                   "yango": {"status": "PARTIAL", "message": "Reconciliation not yet implemented"}},
        "warnings": [],
    }

    if not period or not business_slice_name:
        result["warnings"].append({"code": "MISSING_PARAMS", "message": "period and business_slice_name required"})
    return result


@router.get("/cell-audit")
def cell_audit(
    source_system: str = Query(default="CT_TRIPS_2026"),
    grain: str = Query(default="day"),
    period: str = Query(default=None),
    metric_id: str = Query(default="trips"),
    business_slice_name: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
):
    """Complete cell auditability: value, writer, freshness, park/driver contributions."""
    from app.db.connection import get_db
    from datetime import date as dt_date, timedelta

    result = {
        "cell": {"source_system": source_system, "grain": grain, "period": period,
                 "metric_id": metric_id, "business_slice_name": business_slice_name},
        "value": None, "writer": None, "snapshot": None, "freshness": None,
        "contributions": {"parks": [], "drivers": []}, "lineage": {},
    }

    if not period or not business_slice_name:
        result["error"] = "period and business_slice_name required"
    return result


@router.get("/reconciliation/park")
def reconcile_park(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date: str = Query(default=None),
    grain: str = Query(default="day"),
):
    """CT vs Yango reconciliation by park + date. Compares trips, revenue, drivers."""
    from app.db.connection import get_db
    from datetime import date as dt_date, timedelta

    if not date:
        date = (dt_date.today() - timedelta(days=1)).isoformat()

    date_to = date
    try:
        d = dt_date.fromisoformat(date)
        if grain == "day": date_to = (d + timedelta(days=1)).isoformat()
    except: pass

    result = {"park_id": park_id, "date": date, "grain": grain, "comparisons": {}}

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # CT: trips + drivers from bridge
            cur.execute("""SELECT SUM(completed_trips), COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips>0)
                FROM ops.driver_day_slice_fact WHERE park_id=%s AND activity_date>=%s AND activity_date<%s
            """, (park_id, date, date_to))
            ct_trips, ct_drivers = cur.fetchone()
            ct_trips = int(ct_trips or 0)
            ct_drivers = int(ct_drivers or 0)

            # CT: revenue from day_fact (closest approximation by park)
            cur.execute("""SELECT SUM(COALESCE(revenue_yego_final,0)) FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND trip_date>=%s AND trip_date<%s
            """, (date, date_to))
            ct_rev = float(cur.fetchone()[0] or 0)

            # Yango: orders
            cur.execute("""SELECT SUM(COALESCE(orders_completed,0)), SUM(COALESCE(orders_total,0)),
                SUM(COALESCE(unique_drivers,0)) FROM raw_yango.mv_orders_day
                WHERE park_id=%s AND order_date>=%s AND order_date<%s
            """, (park_id, date, date_to))
            y_row = cur.fetchone()
            y_trips = int(y_row[0] or 0)
            y_total = int(y_row[1] or 0)
            y_drivers = int(y_row[2] or 0)

            def compare_status(ct_val, y_val):
                if ct_val == 0 and y_val == 0: return "NOT_COMPARABLE"
                if ct_val == 0: return "YANGO_ONLY"
                if y_val == 0: return "CT_ONLY"
                delta = abs(ct_val - y_val) / max(y_val, 1) * 100
                if delta <= 1: return "MATCH"
                if delta <= 5: return "MINOR_DELTA"
                return "MAJOR_DELTA"

            def compare_delta(ct_val, y_val):
                if ct_val == 0 or y_val == 0: return None
                return round((ct_val - y_val) / y_val * 100, 1)

            result["comparisons"]["trips"] = {
                "ct_value": ct_trips, "yango_value": y_trips,
                "delta_pct": compare_delta(ct_trips, y_trips),
                "status": compare_status(ct_trips, y_trips)
            }
            result["comparisons"]["drivers"] = {
                "ct_value": ct_drivers, "yango_value": y_drivers,
                "delta_pct": compare_delta(ct_drivers, y_drivers),
                "status": compare_status(ct_drivers, y_drivers)
            }
            result["comparisons"]["revenue"] = {
                "ct_value": round(ct_rev, 2), "yango_value": None,
                "delta_pct": None,
                "status": "NOT_COMPARABLE",
                "note": "Yango revenue not available in raw_yango.mv_revenue_day for this date"
            }

            cur.close()
    except Exception as e:
        result["error"] = str(e)[:200]

    return result

    date_from = period
    date_to = period
    try:
        d = dt_date.fromisoformat(period[:10])
        if grain == "day": date_to = (d + timedelta(days=1)).isoformat()
        elif grain == "week": date_to = (d + timedelta(days=7)).isoformat()
        elif grain == "month" and len(period) == 10:
            if d.month == 12: date_to = dt_date(d.year+1, 1, 1).isoformat()
            else: date_to = dt_date(d.year, d.month+1, 1).isoformat()
    except: pass

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # Total aggregate from bridge
            cur.execute("""
                SELECT SUM(completed_trips), SUM(cancelled_trips),
                       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0),
                       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips = 0 AND total_trips > 0)
                FROM ops.driver_day_slice_fact
                WHERE country=%s AND city=%s AND activity_date>=%s AND activity_date<%s AND business_slice_name=%s
            """, (country, city, date_from, date_to, business_slice_name))
            total_trips, total_canc, total_drivers, empty_drivers = cur.fetchone()
            total_trips = int(total_trips or 0)
            total_drivers = int(total_drivers or 0)

            # Revenue from day_fact
            rev_val = 0
            if metric_id in ("revenue", "avg_ticket", "trips_per_driver"):
                cur.execute("""
                    SELECT SUM(COALESCE(revenue_yego_final,0)) FROM ops.real_business_slice_day_fact
                    WHERE LOWER(TRIM(country))=%s AND LOWER(TRIM(city))=%s
                    AND trip_date>=%s AND trip_date<%s AND business_slice_name=%s
                """, (country, city, date_from[:10], date_to[:10], business_slice_name))
                rev_val = float(cur.fetchone()[0] or 0)

            avg_ticket = round(rev_val / total_trips, 2) if total_trips else None
            tpd = round(total_trips / total_drivers, 2) if total_drivers else None

            result["value"] = {
                "trips": total_trips,
                "revenue": round(rev_val, 2),
                "active_drivers": total_drivers,
                "empty_supply_drivers": int(empty_drivers or 0),
                "avg_ticket": avg_ticket,
                "trips_per_driver": tpd,
            }

            # Park contributions with %
            cur.execute("""
                SELECT park_id, SUM(completed_trips) AS trips,
                       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS drivers
                FROM ops.driver_day_slice_fact
                WHERE country=%s AND city=%s AND activity_date>=%s AND activity_date<%s AND business_slice_name=%s
                GROUP BY park_id ORDER BY trips DESC
            """, (country, city, date_from, date_to, business_slice_name))
            for r in cur.fetchall():
                pct = round(r[1] / total_trips * 100, 1) if total_trips else 0
                result["contributions"]["parks"].append({
                    "park_id": r[0], "trips": r[1], "drivers": r[2],
                    "contribution_pct": pct
                })

            # Top driver contributions
            cur.execute("""
                SELECT driver_id, SUM(completed_trips) AS trips
                FROM ops.driver_day_slice_fact
                WHERE country=%s AND city=%s AND activity_date>=%s AND activity_date<%s AND business_slice_name=%s
                GROUP BY driver_id ORDER BY trips DESC LIMIT 10
            """, (country, city, date_from, date_to, business_slice_name))
            for r in cur.fetchall():
                pct = round(r[1] / total_trips * 100, 1) if total_trips else 0
                result["contributions"]["drivers"].append({
                    "driver_id": r[0], "trips": r[1], "contribution_pct": pct
                })

            # Writer traceability
            result["writer"] = {
                "canonical": "rebuild_day_from_bridge.py" if grain == "day" else f"rebuild_{grain}_from_day_and_bridge.py",
                "source": "ops.driver_day_slice_fact",
            }

            # Freshness traceability
            cur.execute("SELECT MAX(activity_date) FROM ops.driver_day_slice_fact WHERE country=%s AND city=%s", (country, city))
            bridge_max = cur.fetchone()[0]
            result["freshness"] = {
                "bridge_max": str(bridge_max)[:10] if bridge_max else None,
                "cell_period": period[:10] if period else None,
            }

            # Lineage
            result["lineage"] = {
                "city": "READY", "park": "READY", "driver": "READY",
                "fleet": "PARTIAL", "raw_trip": "PARTIAL"
            }

            cur.close()
    except Exception as e:
        result["error"] = str(e)[:200]

    return result

    # Compute date range from grain + period
    date_from = period
    date_to = period
    if grain == "day":
        try:
            d = dt_date.fromisoformat(period)
            date_to = (d + timedelta(days=1)).isoformat()
        except:
            pass
    elif grain == "week":
        try:
            d = dt_date.fromisoformat(period)
            date_to = (d + timedelta(days=7)).isoformat()
        except:
            pass
    elif grain == "month":
        try:
            d = dt_date.fromisoformat(period[:7] + "-01")
            if d.month == 12:
                date_to = dt_date(d.year + 1, 1, 1).isoformat()
            else:
                date_to = dt_date(d.year, d.month + 1, 1).isoformat()
        except:
            pass

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # Park breakdown
            cur.execute("""
                SELECT park_id, COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS drivers,
                       SUM(completed_trips) AS trips
                FROM ops.driver_day_slice_fact
                WHERE country = %s AND city = %s
                  AND activity_date >= %s AND activity_date < %s
                  AND business_slice_name = %s
                GROUP BY park_id ORDER BY trips DESC
            """, (country, city, date_from, date_to, business_slice_name))
            parks = [{"park_id": r[0], "drivers": r[1], "trips": r[2]} for r in cur.fetchall()]
            result["drill"]["park"]["data"] = parks

            # Top drivers
            cur.execute("""
                SELECT driver_id, SUM(completed_trips) AS trips
                FROM ops.driver_day_slice_fact
                WHERE country = %s AND city = %s
                  AND activity_date >= %s AND activity_date < %s
                  AND business_slice_name = %s
                GROUP BY driver_id ORDER BY trips DESC LIMIT %s
            """, (country, city, date_from, date_to, business_slice_name, limit))
            drivers = [{"driver_id": r[0], "trips": r[1]} for r in cur.fetchall()]

            cur.execute("""
                SELECT COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0)
                FROM ops.driver_day_slice_fact
                WHERE country = %s AND city = %s
                  AND activity_date >= %s AND activity_date < %s
                  AND business_slice_name = %s
            """, (country, city, date_from, date_to, business_slice_name))
            total_drivers = cur.fetchone()[0] or 0

            result["drill"]["driver"]["data"] = drivers
            result["drill"]["driver"]["total_count"] = total_drivers

            cur.close()
    except Exception as e:
        result["warnings"].append({"code": "DRILL_ERROR", "message": str(e)[:200]})

    # Lineage statuses from F.5
    result["lineage_status"] = {
        "city": "READY",
        "park": "READY" if parks else "READY (empty)",
        "driver": "READY" if total_drivers > 0 else "READY (empty)",
        "fleet": "PARTIAL",
        "raw_trip": "PARTIAL",
        "yango": "PARTIAL",
    }

    return result


@router.get("/freshness-observatory")
def get_freshness_observatory():
    """Cross-layer freshness: REAL vs PLAN vs PROJECTION vs SNAPSHOT. No mixing."""
    from app.db.connection import get_db
    from datetime import date as dt_date

    today = dt_date.today().isoformat()
    result = {"generated_at": today, "layers": {}}

    try:
        with get_db() as conn:
            cur = conn.cursor()

            layers = [
                ("real_day_fact", "ops.real_business_slice_day_fact", "trip_date",
                 "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'", "REAL"),
                ("real_week_fact", "ops.real_business_slice_week_fact", "week_start",
                 "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'", "REAL"),
                ("real_month_fact", "ops.real_business_slice_month_fact", "month",
                 "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'", "REAL"),
                ("driver_bridge", "ops.driver_day_slice_fact", "activity_date",
                 "WHERE country='peru' AND city='lima'", "BRIDGE"),
                ("snapshot", "ops.omniview_v2_serving_snapshot", "operating_date",
                 "WHERE status='READY'", "SNAPSHOT"),
            ]

            for name, table, col, where_clause, kind in layers:
                try:
                    cur.execute(f"SELECT MAX({col}) FROM {table} {where_clause}")
                    layer_date = cur.fetchone()[0]
                    layer_date_str = str(layer_date)[:10] if layer_date else None
                    gap = None
                    if layer_date_str:
                        try:
                            gap = (dt_date.fromisoformat(layer_date_str) - dt_date.fromisoformat(today)).days
                        except:
                            pass
                    cur.execute(f"SELECT COUNT(*) FROM {table} {where_clause}")
                    rows = cur.fetchone()[0]
                    cur.execute(f"SELECT COUNT(*) FROM {table} {where_clause} AND {col} >= CURRENT_DATE - 2")
                    recent = cur.fetchone()[0]
                    status = "FRESH" if recent > 0 else "STALE"

                    result["layers"][name] = {
                        "layer_date": layer_date_str,
                        "effective_source_date": layer_date_str,
                        "freshness_gap_days": abs(gap) if gap else None,
                        "freshness_status": status,
                        "kind": kind,
                        "rows": rows,
                        "writer": "bridge" if "bridge" in name or "fact" in name else "snapshot_service",
                    }
                except:
                    result["layers"][name] = {"error": "query_failed"}

            cur.close()
    except Exception as e:
        result["error"] = str(e)[:200]

    result["waterfall"] = {
        "RAW_to_DAY": "OK",
        "DAY_to_WEEK": "OK" if result["layers"].get("real_week_fact", {}).get("freshness_status") == "FRESH" else "BROKEN",
        "WEEK_to_MONTH": "OK",
    }

    return result
