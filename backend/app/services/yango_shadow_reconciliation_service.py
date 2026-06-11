"""
CF-H2C — Yango Shadow Reconciliation Service

Compares Yango API raw data against trips_2026 for daily shadow reconciliation.
Produces ops.yango_shadow_reconciliation_day rows.
Does NOT modify any production facts or serving tables.

Runs per (source_date, park_id) — idempotent via ON CONFLICT update.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

LIMA_PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def _classify_delta(delta_pct: Optional[float]) -> str:
    if delta_pct is None:
        return "MISSING"
    if abs(delta_pct) < 1.0:
        return "MATCH"
    if abs(delta_pct) < 5.0:
        return "MINOR_DELTA"
    if abs(delta_pct) < 20.0:
        return "MAJOR_DELTA"
    return "CRITICAL_DELTA"


def reconcile_day(park_id: str, source_date: str) -> Dict[str, Any]:
    result = {
        "source_date": source_date,
        "park_id": park_id,
        "trips_ct_completed": 0, "trips_yango_completed": 0,
        "trips_ct_cancelled": 0, "trips_yango_cancelled": 0,
        "revenue_ct_total": 0, "revenue_yango_total": 0,
        "drivers_ct_active": 0, "drivers_yango_unique": 0,
        "gmv_ct_total": 0, "gmv_yango_total": 0,
        "orders_yango_only": 0, "orders_ct_only": 0, "orders_both": 0,
        "drivers_yango_only": 0, "drivers_ct_only": 0, "drivers_both": 0,
        "parks_without_credentials": 0,
        "overall_status": "PENDING",
    }

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # --- Trips completed: CT ---
            cur.execute(
                """
                SELECT COUNT(*) AS ct_completed,
                       COUNT(*) FILTER (WHERE condicion = 'Cancelado') AS ct_cancelled
                FROM public.trips_2026
                WHERE park_id = %(park_id)s
                  AND fecha_finalizacion::date = %(source_date)s
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            ct_row = cur.fetchone()
            if ct_row:
                result["trips_ct_completed"] = int(ct_row["ct_completed"] or 0)
                result["trips_ct_cancelled"] = int(ct_row["ct_cancelled"] or 0)

            # --- Trips completed: Yango ---
            cur.execute(
                """
                SELECT COUNT(*) AS yango_total,
                       COUNT(*) FILTER (WHERE order_status = 'complete') AS yango_completed,
                       COUNT(*) FILTER (WHERE order_status = 'cancelled') AS yango_cancelled
                FROM raw_yango.orders_raw
                WHERE park_id = %(park_id)s
                  AND order_ended_at::date = %(source_date)s
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            ya_row = cur.fetchone()
            if ya_row:
                result["trips_yango_completed"] = int(ya_row["yango_completed"] or 0)
                result["trips_yango_cancelled"] = int(ya_row["yango_cancelled"] or 0)

            # --- Revenue: CT (from day_fact) ---
            cur.execute(
                """
                SELECT COALESCE(SUM(revenue_yego_final), 0) AS ct_rev
                FROM ops.real_business_slice_day_fact
                WHERE trip_date = %(source_date)s
                  AND city = 'lima'
                  AND country = 'peru'
                """,
                {"source_date": source_date},
            )
            rev_ct = cur.fetchone()
            if rev_ct:
                result["revenue_ct_total"] = float(rev_ct["ct_rev"] or 0)

            # --- Revenue: Yango (Partner fee) ---
            cur.execute(
                """
                SELECT COALESCE(SUM(ABS(amount)), 0) AS yango_rev
                FROM raw_yango.transactions_raw
                WHERE park_id = %(park_id)s
                  AND category_name = 'Partner fee for trip'
                  AND event_at::date = %(source_date)s
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            rev_ya = cur.fetchone()
            if rev_ya:
                result["revenue_yango_total"] = float(rev_ya["yango_rev"] or 0)

            # --- Active drivers: CT ---
            cur.execute(
                """
                SELECT COUNT(DISTINCT conductor_id) AS ct_drivers
                FROM public.trips_2026
                WHERE park_id = %(park_id)s
                  AND fecha_finalizacion::date = %(source_date)s
                  AND condicion = 'Completado'
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            dr_ct = cur.fetchone()
            if dr_ct:
                result["drivers_ct_active"] = int(dr_ct["ct_drivers"] or 0)

            # --- Unique drivers: Yango ---
            cur.execute(
                """
                SELECT COUNT(DISTINCT driver_profile_id) AS ya_drivers
                FROM raw_yango.orders_raw
                WHERE park_id = %(park_id)s
                  AND order_ended_at::date = %(source_date)s
                  AND order_status = 'complete'
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            dr_ya = cur.fetchone()
            if dr_ya:
                result["drivers_yango_unique"] = int(dr_ya["ya_drivers"] or 0)

            # --- GMV: CT ---
            cur.execute(
                """
                SELECT COALESCE(SUM(efectivo + tarjeta + pago_corporativo), 0) AS ct_gmv
                FROM public.trips_2026
                WHERE park_id = %(park_id)s
                  AND fecha_finalizacion::date = %(source_date)s
                  AND condicion = 'Completado'
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            gmv_ct = cur.fetchone()
            if gmv_ct:
                result["gmv_ct_total"] = float(gmv_ct["ct_gmv"] or 0)

            # --- GMV: Yango (Cash + Card) ---
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS ya_gmv
                FROM raw_yango.transactions_raw
                WHERE park_id = %(park_id)s
                  AND category_name IN ('Cash', 'Card payment')
                  AND event_at::date = %(source_date)s
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            gmv_ya = cur.fetchone()
            if gmv_ya:
                result["gmv_yango_total"] = float(gmv_ya["ya_gmv"] or 0)

            # --- Order overlap (Yango order_ids vs CT codigo_pedido) ---
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE y.order_id IS NOT NULL AND t.codigo_pedido IS NULL) AS y_only,
                    COUNT(*) FILTER (WHERE y.order_id IS NULL AND t.codigo_pedido IS NOT NULL) AS ct_only,
                    COUNT(*) FILTER (WHERE y.order_id IS NOT NULL AND t.codigo_pedido IS NOT NULL) AS both
                FROM (
                    SELECT DISTINCT order_id FROM raw_yango.orders_raw
                    WHERE park_id = %(park_id)s AND order_ended_at::date = %(source_date)s
                ) y
                FULL OUTER JOIN (
                    SELECT DISTINCT codigo_pedido FROM public.trips_2026
                    WHERE park_id = %(park_id)s AND fecha_finalizacion::date = %(source_date)s
                ) t ON y.order_id = t.codigo_pedido
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            overlap = cur.fetchone()
            if overlap:
                result["orders_yango_only"] = int(overlap["y_only"] or 0)
                result["orders_ct_only"] = int(overlap["ct_only"] or 0)
                result["orders_both"] = int(overlap["both"] or 0)

            # --- Driver overlap ---
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE y.driver_profile_id IS NOT NULL AND t.conductor_id IS NULL) AS y_only,
                    COUNT(*) FILTER (WHERE y.driver_profile_id IS NULL AND t.conductor_id IS NOT NULL) AS ct_only,
                    COUNT(*) FILTER (WHERE y.driver_profile_id IS NOT NULL AND t.conductor_id IS NOT NULL) AS both
                FROM (
                    SELECT DISTINCT driver_profile_id FROM raw_yango.orders_raw
                    WHERE park_id = %(park_id)s AND order_ended_at::date = %(source_date)s
                ) y
                FULL OUTER JOIN (
                    SELECT DISTINCT conductor_id FROM public.trips_2026
                    WHERE park_id = %(park_id)s AND fecha_finalizacion::date = %(source_date)s
                ) t ON y.driver_profile_id = t.conductor_id
                """,
                {"park_id": park_id, "source_date": source_date},
            )
            d_overlap = cur.fetchone()
            if d_overlap:
                result["drivers_yango_only"] = int(d_overlap["y_only"] or 0)
                result["drivers_ct_only"] = int(d_overlap["ct_only"] or 0)
                result["drivers_both"] = int(d_overlap["both"] or 0)

        finally:
            cur.close()

    # --- Compute deltas and classifications ---
    ct_trips = result["trips_ct_completed"]
    ya_trips = result["trips_yango_completed"]
    result["trips_delta_abs"] = abs(ct_trips - ya_trips) if ct_trips or ya_trips else None
    result["trips_delta_pct"] = round(abs(ct_trips - ya_trips) / max(ct_trips, 1) * 100, 4) if ct_trips > 0 else None
    result["trips_classification"] = _classify_delta(result["trips_delta_pct"])

    ct_rev = result["revenue_ct_total"]
    ya_rev = result["revenue_yango_total"]
    result["revenue_delta_abs"] = round(abs(ct_rev - ya_rev), 4) if ct_rev or ya_rev else None
    result["revenue_delta_pct"] = round(abs(ct_rev - ya_rev) / max(ct_rev, 0.01) * 100, 4) if ct_rev > 0 else None
    result["revenue_classification"] = _classify_delta(result["revenue_delta_pct"])

    ct_dr = result["drivers_ct_active"]
    ya_dr = result["drivers_yango_unique"]
    result["drivers_delta_abs"] = abs(ct_dr - ya_dr) if ct_dr or ya_dr else None
    result["drivers_delta_pct"] = round(abs(ct_dr - ya_dr) / max(ct_dr, 1) * 100, 4) if ct_dr > 0 else None
    result["drivers_classification"] = _classify_delta(result["drivers_delta_pct"])

    ct_gmv = result["gmv_ct_total"]
    ya_gmv = result["gmv_yango_total"]
    result["gmv_delta_abs"] = round(abs(ct_gmv - ya_gmv), 4) if ct_gmv or ya_gmv else None
    result["gmv_delta_pct"] = round(abs(ct_gmv - ya_gmv) / max(ct_gmv, 0.01) * 100, 4) if ct_gmv > 0 else None
    result["gmv_classification"] = _classify_delta(result["gmv_delta_pct"])

    # --- Determine overall status ---
    classifications = [
        result.get("trips_classification"),
        result.get("revenue_classification"),
        result.get("drivers_classification"),
        result.get("gmv_classification"),
    ]
    if all(c == "MATCH" for c in classifications if c):
        result["overall_status"] = "MATCH"
    elif any(c == "CRITICAL_DELTA" for c in classifications if c):
        result["overall_status"] = "CRITICAL"
    elif any(c == "MAJOR_DELTA" for c in classifications if c):
        result["overall_status"] = "MAJOR_DELTA"
    elif any(c == "MINOR_DELTA" for c in classifications if c):
        result["overall_status"] = "MINOR_DELTA"
    elif any(c == "MISSING" for c in classifications if c):
        result["overall_status"] = "PARTIAL"
    else:
        result["overall_status"] = "PENDING"

    return result


def upsert_shadow_reconciliation(rec: Dict[str, Any]) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO ops.yango_shadow_reconciliation_day (
                    source_date, park_id,
                    trips_ct_completed, trips_yango_completed,
                    trips_delta_abs, trips_delta_pct, trips_classification,
                    trips_ct_cancelled, trips_yango_cancelled,
                    revenue_ct_total, revenue_yango_total,
                    revenue_delta_abs, revenue_delta_pct, revenue_classification,
                    drivers_ct_active, drivers_yango_unique,
                    drivers_delta_abs, drivers_delta_pct, drivers_classification,
                    gmv_ct_total, gmv_yango_total,
                    gmv_delta_abs, gmv_delta_pct, gmv_classification,
                    orders_yango_only, orders_ct_only, orders_both,
                    drivers_yango_only, drivers_ct_only, drivers_both,
                    overall_status
                ) VALUES (
                    %(source_date)s, %(park_id)s,
                    %(trips_ct_completed)s, %(trips_yango_completed)s,
                    %(trips_delta_abs)s, %(trips_delta_pct)s, %(trips_classification)s,
                    %(trips_ct_cancelled)s, %(trips_yango_cancelled)s,
                    %(revenue_ct_total)s, %(revenue_yango_total)s,
                    %(revenue_delta_abs)s, %(revenue_delta_pct)s, %(revenue_classification)s,
                    %(drivers_ct_active)s, %(drivers_yango_unique)s,
                    %(drivers_delta_abs)s, %(drivers_delta_pct)s, %(drivers_classification)s,
                    %(gmv_ct_total)s, %(gmv_yango_total)s,
                    %(gmv_delta_abs)s, %(gmv_delta_pct)s, %(gmv_classification)s,
                    %(orders_yango_only)s, %(orders_ct_only)s, %(orders_both)s,
                    %(drivers_yango_only)s, %(drivers_ct_only)s, %(drivers_both)s,
                    %(overall_status)s
                )
                ON CONFLICT (source_date, park_id) DO UPDATE SET
                    trips_ct_completed = EXCLUDED.trips_ct_completed,
                    trips_yango_completed = EXCLUDED.trips_yango_completed,
                    trips_delta_abs = EXCLUDED.trips_delta_abs,
                    trips_delta_pct = EXCLUDED.trips_delta_pct,
                    trips_classification = EXCLUDED.trips_classification,
                    trips_ct_cancelled = EXCLUDED.trips_ct_cancelled,
                    trips_yango_cancelled = EXCLUDED.trips_yango_cancelled,
                    revenue_ct_total = EXCLUDED.revenue_ct_total,
                    revenue_yango_total = EXCLUDED.revenue_yango_total,
                    revenue_delta_abs = EXCLUDED.revenue_delta_abs,
                    revenue_delta_pct = EXCLUDED.revenue_delta_pct,
                    revenue_classification = EXCLUDED.revenue_classification,
                    drivers_ct_active = EXCLUDED.drivers_ct_active,
                    drivers_yango_unique = EXCLUDED.drivers_yango_unique,
                    drivers_delta_abs = EXCLUDED.drivers_delta_abs,
                    drivers_delta_pct = EXCLUDED.drivers_delta_pct,
                    drivers_classification = EXCLUDED.drivers_classification,
                    gmv_ct_total = EXCLUDED.gmv_ct_total,
                    gmv_yango_total = EXCLUDED.gmv_yango_total,
                    gmv_delta_abs = EXCLUDED.gmv_delta_abs,
                    gmv_delta_pct = EXCLUDED.gmv_delta_pct,
                    gmv_classification = EXCLUDED.gmv_classification,
                    orders_yango_only = EXCLUDED.orders_yango_only,
                    orders_ct_only = EXCLUDED.orders_ct_only,
                    orders_both = EXCLUDED.orders_both,
                    drivers_yango_only = EXCLUDED.drivers_yango_only,
                    drivers_ct_only = EXCLUDED.drivers_ct_only,
                    drivers_both = EXCLUDED.drivers_both,
                    overall_status = EXCLUDED.overall_status,
                    computed_at = now()
                """,
                rec,
            )
            logger.info(
                "Shadow reconciliation upserted: date=%s park=%s status=%s "
                "trips(ct=%s ya=%s) rev(ct=%.2f ya=%.2f) dr(ct=%s ya=%s)",
                rec["source_date"], rec["park_id"][:8] + "***",
                rec["overall_status"],
                rec["trips_ct_completed"], rec["trips_yango_completed"],
                rec["revenue_ct_total"], rec["revenue_yango_total"],
                rec["drivers_ct_active"], rec["drivers_yango_unique"],
            )
            return True
        except Exception as e:
            logger.error("Failed to upsert shadow reconciliation: %s", e)
            return False
        finally:
            cur.close()
