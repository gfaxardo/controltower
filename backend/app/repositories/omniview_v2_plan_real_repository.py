"""
Omniview V2 Plan vs Real Repository — monthly plan vs actual queries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

PLAN_TABLE = "ops.plan_trips_monthly"
REAL_TABLE = "ops.real_business_slice_month_fact"
CT_COUNTRY = "peru"
CT_CITY = "lima"

_COUNTRY_CODE = {"peru": "PE", "colombia": "CO", "pe": "PE", "co": "CO"}
_CITY_CAPS = {"lima": "Lima", "arequipa": "Arequipa", "trujillo": "Trujillo",
              "bogota": "Bogota", "medellin": "Medellin", "cali": "Cali",
              "barranquilla": "Barranquilla", "bucaramanga": "Bucaramanga", "cucuta": "Cucuta"}


def _plan_country(country: str) -> str:
    return _COUNTRY_CODE.get(country.lower(), country)


def _plan_city(city: str) -> str:
    return _CITY_CAPS.get(city.lower(), city)

# TODO(OV2-D.2B): Replace with ops.plan_lob_to_business_slice mapping table
# The plan_lob_mapping.canonical_lob_base doesn't directly match business_slice_name in
# ops.real_business_slice_*_fact. This is a known gap per OV2_D2A_PLAN_SOURCE_CERTIFICATION.md.
_LOB_TO_SLICE = {
    "auto_taxi": "Auto regular",
    "carga": "Carga",
    "delivery": "Delivery",
    "pro": "PRO",
    "tuk_tuk": "Tuk Tuk",
    "yma": "YMA",
    "ymm": "YMA",
    "taxi_moto": "Tuk Tuk",
}


def _normalize_to_business_slice(lob_canonical: str) -> str:
    """Map plan_lob_mapping canonical_lob_base to real table business_slice_name."""
    return _LOB_TO_SLICE.get(lob_canonical.lower(), lob_canonical)


def _query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception as e:
        logger.error("Plan/Real repo error: %s", str(e)[:200])
        return []


def get_plan_versions() -> List[Dict[str, Any]]:
    return _query(
        f"SELECT DISTINCT plan_version, MIN(month) AS first_month, MAX(month) AS last_month, COUNT(*) AS rows "
        f"FROM {PLAN_TABLE} GROUP BY plan_version ORDER BY MAX(month) DESC"
    )


def get_latest_plan_version() -> Optional[str]:
    rows = _query(f"SELECT plan_version FROM {PLAN_TABLE} ORDER BY created_at DESC LIMIT 1")
    return rows[0]["plan_version"] if rows else None


def get_best_plan_version(metric_col: str = "projected_trips") -> Optional[str]:
    """Pick latest version that has non-zero data for the requested metric column."""
    rows = _query(
        f"SELECT plan_version, SUM(COALESCE({metric_col}, 0)) AS total "
        f"FROM {PLAN_TABLE} WHERE {metric_col} > 0 "
        f"GROUP BY plan_version ORDER BY MAX(created_at) DESC LIMIT 1"
    )
    if rows and rows[0]["total"] and rows[0]["total"] > 0:
        return rows[0]["plan_version"]
    return get_latest_plan_version()


def get_monthly_plan_real(
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    metric_id: str = "trips",
    plan_version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    # Metric mapping: metric_id → (plan_column, real_column)
    metric_map = {
        "orders": ("projected_trips", "trips_completed"),
        "trips": ("projected_trips", "trips_completed"),
        "revenue": ("projected_revenue", "revenue_yego_final"),
        "active_drivers": ("projected_drivers", "active_drivers"),
        "avg_ticket": ("projected_ticket", "avg_ticket"),
        "trips_per_driver": ("projected_trips_per_driver", "trips_per_driver"),
    }

    if metric_id not in metric_map:
        metric_id = "trips"
    plan_col, real_col = metric_map[metric_id]

    if not plan_version:
        plan_version = get_best_plan_version(plan_col) if metric_id == "revenue" else get_latest_plan_version()

    if not plan_version:
        return []

    # Plan: aggregate by month + LOB (normalized to business_slice)
    plan_country = _plan_country(country)
    plan_city = _plan_city(city)
    plan_rows = _query(
        f"""
        WITH plan AS (
            SELECT
                month,
                LOWER(TRIM(lob_base)) AS lob_raw,
                SUM(COALESCE({plan_col}, 0)) AS plan_value
            FROM {PLAN_TABLE}
            WHERE TRIM(country) = %s
              AND TRIM(city) = %s
              AND plan_version = %s
              AND (%s::date IS NULL OR month >= %s::date)
              AND (%s::date IS NULL OR month <= %s::date)
            GROUP BY month, LOWER(TRIM(lob_base))
        ),
        lob_map AS (
            SELECT DISTINCT LOWER(TRIM(raw_lob_name)) AS raw_lob, canonical_lob_base
            FROM ops.plan_lob_mapping WHERE status = 'active'
        )
        SELECT p.month, COALESCE(m.canonical_lob_base, p.lob_raw) AS business_slice_name,
               p.plan_value
        FROM plan p
        LEFT JOIN lob_map m ON p.lob_raw = m.raw_lob
        ORDER BY p.month, business_slice_name
        """,
        (plan_country, plan_city, plan_version, date_from, date_from, date_to, date_to),
    )

    # Real: aggregate by month + business_slice
    real_rows = _query(
        f"""
        SELECT month, business_slice_name,
               SUM(COALESCE({real_col}, 0)) AS real_value
        FROM {REAL_TABLE}
        WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
          AND (%s::date IS NULL OR month >= %s::date)
          AND (%s::date IS NULL OR month <= %s::date)
        GROUP BY month, business_slice_name
        ORDER BY month, business_slice_name
        """,
        (country, city, date_from, date_from, date_to, date_to),
    )

    # Build combined result
    real_index = {(r["month"].isoformat()[:10] if hasattr(r["month"], "isoformat") else str(r["month"])[:10],
                   r["business_slice_name"]): r for r in real_rows}

    combined = []
    for p in plan_rows:
        month_str = p["month"].isoformat()[:10] if hasattr(p["month"], "isoformat") else str(p["month"])[:10]
        slice_name = _normalize_to_business_slice(p["business_slice_name"])
        key = (month_str, slice_name)
        real_val = float(real_index[key]["real_value"] or 0) if key in real_index else None
        plan_val = float(p["plan_value"] or 0)

        gap_abs = (real_val - plan_val) if real_val is not None else None
        gap_pct = round(gap_abs / plan_val * 100, 1) if plan_val != 0 and gap_abs is not None else None

        if real_val is None:
            status = "NO_REAL"
        elif plan_val == 0:
            status = "NO_PLAN"
        elif gap_pct is not None:
            status = "ON_TRACK" if abs(gap_pct) <= 5 else "WATCH" if abs(gap_pct) <= 15 else "OFF_TRACK"
        else:
            status = "NO_PLAN"

        combined.append({
            "period": month_str,
            "business_slice_name": slice_name,
            "plan_value": plan_val,
            "real_value": real_val,
            "gap_abs": gap_abs,
            "gap_pct": gap_pct,
            "status": status,
            "plan_version": plan_version,
            "metric_id": metric_id,
        })

    # Add real-only rows (no plan)
    plan_index = {(p["month"].isoformat()[:10] if hasattr(p["month"], "isoformat") else str(p["month"])[:10],
                   _normalize_to_business_slice(p["business_slice_name"])) for p in plan_rows}
    for r in real_rows:
        month_str = r["month"].isoformat()[:10] if hasattr(r["month"], "isoformat") else str(r["month"])[:10]
        key = (month_str, r["business_slice_name"])
        if key not in plan_index:
            combined.append({
                "period": month_str,
                "business_slice_name": r["business_slice_name"],
                "plan_value": 0,
                "real_value": float(r["real_value"] or 0),
                "gap_abs": None,
                "gap_pct": None,
                "status": "NO_PLAN",
                "plan_version": plan_version,
                "metric_id": metric_id,
            })

    return combined
