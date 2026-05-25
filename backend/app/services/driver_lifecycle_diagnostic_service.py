"""
Driver Lifecycle Diagnostic Engine — Fase 2A.1.1 (Hardened)

Deterministic lifecycle state and risk assessment per driver.
Reads ops.driver_daily_activity_fact (pre-aggregated driver+day grain).
Fallback to direct trips_2026 query if fact table is empty.

Rules are deterministic, auditable, no ML/IA.
Outputs are dict-based, ready for API JSON serialization.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.driver_identity_resolver_service import resolve_driver_batch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FACT_TABLE = "ops.driver_daily_activity_fact"
FALLBACK_TABLE = "public.trips_2026"
COMPLETED_CONDITION = "Completado"

# Track which source is being used
_data_source: str | None = None
_data_source_meta: dict[str, Any] = {}

# Lifecycle state enum (precedence order: first match wins)
STATE_CHURNED = "CHURNED"
STATE_DORMANT = "DORMANT"
STATE_REACTIVATED = "REACTIVATED"
STATE_NEW = "NEW"
STATE_AT_RISK = "AT_RISK"
STATE_DECLINING = "DECLINING"
STATE_GROWING = "GROWING"
STATE_STABLE = "STABLE"
STATE_ACTIVATING = "ACTIVATING"

PRECEDENCE = [
    STATE_CHURNED,
    STATE_DORMANT,
    STATE_REACTIVATED,
    STATE_NEW,
    STATE_AT_RISK,
    STATE_DECLINING,
    STATE_GROWING,
    STATE_STABLE,
    STATE_ACTIVATING,
]

RISK_HIGH = "HIGH"
RISK_MEDIUM = "MEDIUM"
RISK_LOW = "LOW"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sanitize_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except (ValueError, TypeError):
            return None
    return None


def _rolling_trips_from_rows(rows: list[dict[str, Any]], days: int) -> int:
    """Count trips in the last `days` days from the list of daily counts."""
    cutoff = date.today() - timedelta(days=days)
    total = 0
    for r in rows:
        trip_date = _sanitize_date(r.get("trip_date"))
        if trip_date and trip_date >= cutoff:
            total += int(r.get("trips_count", 0) or 0)
    return total


# ---------------------------------------------------------------------------
# Core: fetch completed trips per driver
# ---------------------------------------------------------------------------
def _fetch_completed_trips(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = 60,
) -> list[dict[str, Any]]:
    """
    Returns one row per conductor_id with aggregated trip data
    from ops.driver_daily_activity_fact (pre-aggregated driver+day grain).
    Falls back to direct trips_2026 query if fact table is empty.

    Optimized: reads from indexed fact table instead of raw trips table.
    """
    global _data_source, _data_source_meta

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Try fact table first
        cur.execute(f"SELECT COUNT(*) AS c FROM {FACT_TABLE}")
        fact_count = cur.fetchone()["c"]

        if fact_count > 0:
            return _fetch_from_fact(cur, country, city, lookback_days)

        # Fallback to direct trips table
        logger.warning("Fact table %s is empty, falling back to %s", FACT_TABLE, FALLBACK_TABLE)
        return _fetch_from_raw_trips(cur, country, city, lookback_days)


def _fetch_from_fact(
    cur,
    country: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = 60,
) -> list[dict[str, Any]]:
    """Fetch from ops.driver_daily_activity_fact (optimized)."""
    global _data_source, _data_source_meta

    where_country = ""
    where_city = ""
    params: list[Any] = [lookback_days]

    if country and str(country).strip():
        where_country = "AND LOWER(COALESCE(f.country, '')) = LOWER(%s)"
        params.append(str(country).strip())
    if city and str(city).strip():
        where_city = "AND LOWER(COALESCE(f.city, '')) = LOWER(%s)"
        params.append(str(city).strip())

    sql = f"""
        SELECT
            f.driver_id,
            MIN(f.activity_date) AS first_trip_date,
            MAX(f.activity_date) AS last_trip_date,
            SUM(f.completed_trips) AS total_trips,
            SUM(f.completed_trips) FILTER (
                WHERE f.activity_date >= CURRENT_DATE - 7
            ) AS rolling_7d_trips,
            SUM(f.completed_trips) FILTER (
                WHERE f.activity_date >= CURRENT_DATE - 28
            ) AS rolling_28d_trips,
            SUM(f.completed_trips) FILTER (
                WHERE f.activity_date >= CURRENT_DATE - 35
                  AND f.activity_date < CURRENT_DATE - 7
            ) AS baseline_trips_21d,
            MIN(f.country) AS country,
            MIN(f.city) AS city,
            'fact_table' AS lob
        FROM {FACT_TABLE} f
        WHERE f.activity_date >= CURRENT_DATE - %s
          {where_country}
          {where_city}
        GROUP BY f.driver_id
        ORDER BY rolling_7d_trips DESC, total_trips DESC
    """
    cur.execute("SET statement_timeout = '60000'")
    cur.execute(sql, params)
    rows = cur.fetchall()

    # Track source metadata
    cur.execute(f"SELECT MIN(activity_date) AS mn, MAX(activity_date) AS mx, MAX(last_refreshed_at) AS ref FROM {FACT_TABLE}")
    row = cur.fetchone()
    mn = row["mn"] if row else None
    mx = row["mx"] if row else None
    ref = row["ref"] if row else None
    _data_source = FACT_TABLE
    _data_source_meta = {
        "data_source": FACT_TABLE,
        "min_activity_date": mn.isoformat() if hasattr(mn, "isoformat") else str(mn) if mn else None,
        "max_activity_date": mx.isoformat() if hasattr(mx, "isoformat") else str(mx) if mx else None,
        "last_refreshed_at": ref.isoformat() if hasattr(ref, "isoformat") else str(ref) if ref else None,
    }

    return rows


def _fetch_from_raw_trips(
    cur,
    country: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = 60,
) -> list[dict[str, Any]]:
    """Fallback: fetch from public.trips_2026 directly."""
    global _data_source, _data_source_meta
    _data_source = FALLBACK_TABLE
    _data_source_meta = {"data_source": FALLBACK_TABLE, "note": "fact table empty, using fallback"}

    where_country = ""
    where_city = ""
    params: list[Any] = [lookback_days]

    if country and str(country).strip():
        where_country = "AND LOWER(COALESCE(p.country, '')) = LOWER(%s)"
        params.append(str(country).strip())
    if city and str(city).strip():
        where_city = "AND LOWER(COALESCE(p.city, '')) = LOWER(%s)"
        params.append(str(city).strip())

    sql = f"""
        SELECT
            t.conductor_id AS driver_id,
            MIN(t.fecha_finalizacion) AS first_trip_date,
            MAX(t.fecha_finalizacion) AS last_trip_date,
            COUNT(*) AS total_trips,
            COUNT(*) FILTER (
                WHERE t.fecha_finalizacion >= CURRENT_DATE - 7
            ) AS rolling_7d_trips,
            COUNT(*) FILTER (
                WHERE t.fecha_finalizacion >= CURRENT_DATE - 28
            ) AS rolling_28d_trips,
            COUNT(*) FILTER (
                WHERE t.fecha_finalizacion >= CURRENT_DATE - 35
                  AND t.fecha_finalizacion < CURRENT_DATE - 7
            ) AS baseline_trips_21d,
            MIN(p.country) AS country,
            MIN(p.city) AS city,
            MIN(t.tipo_servicio) AS lob
        FROM {FALLBACK_TABLE} t
        LEFT JOIN dim.dim_park p ON t.park_id = p.park_id
        WHERE t.condicion = '{COMPLETED_CONDITION}'
          AND t.fecha_finalizacion >= CURRENT_DATE - %s
          {where_country}
          {where_city}
        GROUP BY t.conductor_id
        ORDER BY rolling_7d_trips DESC, total_trips DESC
    """
    cur.execute("SET statement_timeout = '120000'")
    cur.execute(sql, params)
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Deterministic lifecycle classifier
# ---------------------------------------------------------------------------
def _classify_lifecycle(driver: dict[str, Any]) -> str:
    """
    Apply deterministic precedence-based lifecycle classification.

    Rules:
      CHURNED      : days_since_last_trip >= 30
      DORMANT      : days_since_last_trip >= 14
      REACTIVATED  : rolling_7d > 0 AND was dormant (had >=14 days gap before recent trip)
      NEW          : first_trip_date within last 7 days
      AT_RISK      : days_since_last_trip >= 3 OR rolling_7d < 40% of baseline
      DECLINING    : rolling_7d between 40% and 70% of baseline
      GROWING      : rolling_7d >= 120% of baseline
      STABLE       : rolling_7d >= 70% of baseline
      ACTIVATING   : fallback if none matched
    """
    days_since = driver.get("days_since_last_trip")
    r7 = driver.get("rolling_7d_trips") or 0
    baseline_28 = driver.get("baseline_trips_28d") or 0
    first_date = _sanitize_date(driver.get("first_trip_date"))
    last_date = _sanitize_date(driver.get("last_trip_date"))
    today = date.today()

    # CHURNED
    if days_since is not None and days_since >= 30:
        driver["rule_reason"] = f"days_since_last_trip={days_since} >= 30"
        return STATE_CHURNED

    # DORMANT
    if days_since is not None and days_since >= 14:
        driver["rule_reason"] = f"days_since_last_trip={days_since} >= 14"
        return STATE_DORMANT

    # REACTIVATED: had trips in last 7d AND was dormant before
    if r7 > 0:
        # Check if there was a gap >= 14 days before the most recent trip block
        # Simple heuristic: if total_trips > rolling_28d, driver was active before dormancy
        total_trips = driver.get("total_trips") or 0
        rolling_28 = driver.get("rolling_28d_trips") or 0
        if total_trips > rolling_28 and rolling_28 > 0:
            # Had trips beyond 28d window, was dormant then came back
            driver["rule_reason"] = f"rolling_7d={r7} > 0 and total_trips({total_trips}) > rolling_28d({rolling_28})"
            return STATE_REACTIVATED
        # Alternative: check if first_trip_date in this week but last_trip was before
        if first_date and last_date and first_date != last_date and days_since is not None and days_since < 7:
            prev_cutoff = today - timedelta(days=14)
            if first_date >= prev_cutoff and last_date >= prev_cutoff:
                # First trip was during dormant window but now active
                driver["rule_reason"] = f"reactivated: rolling_7d={r7} > 0 with prior dormancy gap"
                return STATE_REACTIVATED

    # NEW
    if first_date and (today - first_date).days <= 7:
        driver["rule_reason"] = f"first_trip_date within 7d ({(today - first_date).days}d ago)"
        return STATE_NEW

    # Calculate baseline as 1/3 of baseline_trips_21d (approx 7d equivalent)
    baseline_7d_equiv = baseline_28 / 4.0 if baseline_28 > 0 else 0

    if baseline_7d_equiv > 0:
        ratio = r7 / baseline_7d_equiv if baseline_7d_equiv > 0 else 0

        # AT_RISK
        if days_since is not None and days_since >= 3:
            driver["rule_reason"] = f"days_since_last_trip={days_since} >= 3"
            return STATE_AT_RISK
        if ratio < 0.4:
            driver["rule_reason"] = f"rolling_7d({r7}) < 40% of baseline({baseline_7d_equiv:.1f}), ratio={ratio:.2f}"
            return STATE_AT_RISK

        # DECLINING
        if ratio < 0.7:
            driver["rule_reason"] = f"rolling_7d({r7}) between 40-70% of baseline({baseline_7d_equiv:.1f}), ratio={ratio:.2f}"
            return STATE_DECLINING

        # GROWING
        if ratio >= 1.2:
            driver["rule_reason"] = f"rolling_7d({r7}) >= 120% of baseline({baseline_7d_equiv:.1f}), ratio={ratio:.2f}"
            return STATE_GROWING

        # STABLE
        driver["rule_reason"] = f"rolling_7d({r7}) >= 70% of baseline({baseline_7d_equiv:.1f}), ratio={ratio:.2f}"
        return STATE_STABLE

    # ACTIVATING (first trip 8-21 days ago and rolling_7d > 0)
    if first_date and 8 <= (today - first_date).days <= 21 and r7 > 0:
        driver["rule_reason"] = f"first_trip {8}-{21}d ago, rolling_7d={r7} > 0"
        return STATE_ACTIVATING

    # Default
    driver["rule_reason"] = "no signals matched, fallback"
    return STATE_ACTIVATING


def _classify_risk(driver: dict[str, Any]) -> str:
    """Risk level based on lifecycle_state and decline severity."""
    state = driver.get("lifecycle_state", STATE_ACTIVATING)
    r7 = driver.get("rolling_7d_trips") or 0
    baseline_28 = driver.get("baseline_trips_28d") or 0
    baseline_7d_equiv = baseline_28 / 4.0 if baseline_28 > 0 else 0

    if state in (STATE_CHURNED, STATE_DORMANT, STATE_AT_RISK):
        return RISK_HIGH

    if state == STATE_DECLINING:
        return RISK_MEDIUM

    if baseline_7d_equiv > 0 and r7 > 0:
        decline_pct = ((baseline_7d_equiv - r7) / baseline_7d_equiv) * 100
        if decline_pct > 60:
            return RISK_HIGH
        if decline_pct > 30:
            return RISK_MEDIUM

    return RISK_LOW


# ---------------------------------------------------------------------------
# Enrich driver data
# ---------------------------------------------------------------------------
def _enrich_driver(driver: dict[str, Any]) -> dict[str, Any]:
    """Compute derived fields and classify lifecycle/risk."""
    today = date.today()

    # Support both fact table fields (date) and raw trips fields (timestamp)
    first_date = _sanitize_date(driver.get("first_trip_date") or driver.get("first_trip_ts"))
    last_date = _sanitize_date(driver.get("last_trip_date") or driver.get("last_trip_ts"))
    days_since = (today - last_date).days if last_date else None

    rolling_7d = int(driver.get("rolling_7d_trips") or 0)
    rolling_28d = int(driver.get("rolling_28d_trips") or 0)
    baseline_21d = int(driver.get("baseline_trips_21d") or 0)
    baseline_28d = baseline_21d  # proxy: 21d baseline approximated as 28d

    enriched = {
        "driver_id": driver.get("driver_id"),
        "country": driver.get("country") or "unknown",
        "city": driver.get("city") or "unknown",
        "lob": driver.get("lob") or "unknown",
        "first_trip_date": first_date.isoformat() if first_date else None,
        "last_trip_date": last_date.isoformat() if last_date else None,
        "days_since_last_trip": days_since,
        "total_trips": int(driver.get("total_trips") or 0),
        "rolling_7d_trips": rolling_7d,
        "rolling_28d_trips": rolling_28d,
        "baseline_trips_28d": baseline_28d,
        "decline_pct": round(((baseline_28d / 4.0 - rolling_7d) / max(baseline_28d / 4.0, 1)) * 100, 1) if baseline_28d > 0 else None,
    }

    # Classify
    enriched["lifecycle_state"] = _classify_lifecycle(enriched)
    enriched["risk_level"] = _classify_risk(enriched)

    return enriched


def _build_lifecycle_tags(driver: dict[str, Any]) -> list[str]:
    """Build visible tags for a driver based on lifecycle state."""
    tags = []
    state = driver.get("lifecycle_state", "")
    risk = driver.get("risk_level", "")

    if state == "AT_RISK" or risk == "HIGH":
        tags.append("AT_RISK")
    if state == "CHURNED":
        tags.append("CHURNED")
    if state == "DORMANT":
        tags.append("DORMANT")
    if state == "DECLINING":
        tags.append("DECLINING")
    if state == "GROWING":
        tags.append("GROWING")
    if state == "STABLE":
        tags.append("STABLE")
    if state == "NEW":
        tags.append("NEW")
    if state == "REACTIVATED":
        tags.append("REACTIVATED")

    return tags[:4]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_diagnostic_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 30,
) -> dict[str, Any]:
    """
    Returns aggregate diagnostic summary.

    GET /driver-lifecycle/summary
    """
    rows = _fetch_completed_trips(country=country, city=city, lookback_days=period_days)
    enriched = [_enrich_driver(r) for r in rows]

    total = len(enriched)
    if total == 0:
        return {
            "total_drivers_seen": 0, "active_7d": 0, "active_28d": 0,
            "new_drivers": 0, "activating_drivers": 0, "stable_drivers": 0,
            "growing_drivers": 0, "declining_drivers": 0, "at_risk_drivers": 0,
            "dormant_drivers": 0, "churned_drivers": 0, "reactivated_drivers": 0,
            "high_risk": 0, "medium_risk": 0, "low_risk": 0,
            "leakage_rate": 0.0, "retention_rate": 0.0,
        }

    state_counts = {}
    risk_counts = {}
    for d in enriched:
        s = d["lifecycle_state"]
        state_counts[s] = state_counts.get(s, 0) + 1
        r = d["risk_level"]
        risk_counts[r] = risk_counts.get(r, 0) + 1

    active_7d = sum(1 for d in enriched if (d.get("rolling_7d_trips") or 0) > 0)
    active_28d = sum(1 for d in enriched if (d.get("rolling_28d_trips") or 0) > 0)
    churned_dormant = state_counts.get(STATE_CHURNED, 0) + state_counts.get(STATE_DORMANT, 0)
    leakage_rate = round((churned_dormant / total) * 100, 1) if total > 0 else 0.0
    retention_rate = round((state_counts.get(STATE_STABLE, 0) + state_counts.get(STATE_GROWING, 0)) / total * 100, 1) if total > 0 else 0.0

    return {
        "total_drivers_seen": total,
        "active_7d": active_7d,
        "active_28d": active_28d,
        "new_drivers": state_counts.get(STATE_NEW, 0),
        "activating_drivers": state_counts.get(STATE_ACTIVATING, 0),
        "stable_drivers": state_counts.get(STATE_STABLE, 0),
        "growing_drivers": state_counts.get(STATE_GROWING, 0),
        "declining_drivers": state_counts.get(STATE_DECLINING, 0),
        "at_risk_drivers": state_counts.get(STATE_AT_RISK, 0),
        "dormant_drivers": state_counts.get(STATE_DORMANT, 0),
        "churned_drivers": state_counts.get(STATE_CHURNED, 0),
        "reactivated_drivers": state_counts.get(STATE_REACTIVATED, 0),
        "high_risk": risk_counts.get(RISK_HIGH, 0),
        "medium_risk": risk_counts.get(RISK_MEDIUM, 0),
        "low_risk": risk_counts.get(RISK_LOW, 0),
        "leakage_rate": leakage_rate,
        "retention_rate": retention_rate,
        **_data_source_meta,
    }


def get_diagnostic_funnel(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 30,
) -> dict[str, Any]:
    """
    Returns 4-layer funnel: input, retained, risk, leakage.

    GET /driver-lifecycle/funnel
    """
    rows = _fetch_completed_trips(country=country, city=city, lookback_days=period_days)
    enriched = [_enrich_driver(r) for r in rows]

    state_counts: dict[str, int] = {}
    for d in enriched:
        s = d["lifecycle_state"]
        state_counts[s] = state_counts.get(s, 0) + 1

    return {
        "input_layer": {
            "new_drivers": state_counts.get(STATE_NEW, 0),
            "first_trip_drivers": state_counts.get(STATE_NEW, 0) + state_counts.get(STATE_ACTIVATING, 0),
            "reactivated_drivers": state_counts.get(STATE_REACTIVATED, 0),
            "total_input": state_counts.get(STATE_NEW, 0) + state_counts.get(STATE_ACTIVATING, 0) + state_counts.get(STATE_REACTIVATED, 0),
        },
        "retained_layer": {
            "stable_drivers": state_counts.get(STATE_STABLE, 0),
            "growing_drivers": state_counts.get(STATE_GROWING, 0),
            "activating_drivers": state_counts.get(STATE_ACTIVATING, 0),
            "total_retained": state_counts.get(STATE_STABLE, 0) + state_counts.get(STATE_GROWING, 0) + state_counts.get(STATE_ACTIVATING, 0),
        },
        "risk_layer": {
            "declining_drivers": state_counts.get(STATE_DECLINING, 0),
            "at_risk_drivers": state_counts.get(STATE_AT_RISK, 0),
            "total_at_risk": state_counts.get(STATE_DECLINING, 0) + state_counts.get(STATE_AT_RISK, 0),
        },
        "leakage_layer": {
            "dormant_drivers": state_counts.get(STATE_DORMANT, 0),
            "churned_drivers": state_counts.get(STATE_CHURNED, 0),
            "total_leakage": state_counts.get(STATE_DORMANT, 0) + state_counts.get(STATE_CHURNED, 0),
        },
    }


def get_diagnostic_risk_list(
    country: Optional[str] = None,
    city: Optional[str] = None,
    risk_level: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Returns actionable driver list with lifecycle and risk data.

    GET /driver-lifecycle/risk-list
    """
    rows = _fetch_completed_trips(country=country, city=city, lookback_days=60)
    enriched = [_enrich_driver(r) for r in rows]

    if risk_level:
        enriched = [d for d in enriched if d["risk_level"] == risk_level.upper()]
    if lifecycle_state:
        enriched = [d for d in enriched if d["lifecycle_state"] == lifecycle_state.upper()]

    enriched.sort(key=lambda d: (d.get("days_since_last_trip") or 0), reverse=True)
    result = enriched[:limit]

    driver_ids = [d["driver_id"] for d in result]
    identities = resolve_driver_batch(driver_ids)

    return [
        {
            "driver_id": d["driver_id"],
            "display_name": identities.get(d["driver_id"], {}).get("display_name", d["driver_id"]),
            "country": d["country"],
            "city": d["city"],
            "lifecycle_state": d["lifecycle_state"],
            "risk_level": d["risk_level"],
            "rule_reason": d.get("rule_reason", ""),
            "first_trip_date": d["first_trip_date"],
            "last_trip_date": d["last_trip_date"],
            "days_since_last_trip": d["days_since_last_trip"],
            "rolling_7d_trips": d["rolling_7d_trips"],
            "baseline_trips_28d": d["baseline_trips_28d"],
            "decline_pct": d["decline_pct"],
            "tags": _build_lifecycle_tags(d),
        }
        for d in result
    ]


def get_diagnostic_cohorts_basic(
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Basic cohort retention by first_trip_month.

    GET /driver-lifecycle/cohorts-basic
    """
    rows = _fetch_completed_trips(country=country, city=city, lookback_days=180)
    enriched = [_enrich_driver(r) for r in rows]

    # Group by first_trip_month
    cohorts: dict[str, list[dict]] = {}
    for d in enriched:
        first = d.get("first_trip_date")
        if not first:
            continue
        cohort_key = first[:7]  # YYYY-MM
        if cohort_key not in cohorts:
            cohorts[cohort_key] = []
        cohorts[cohort_key].append(d)

    result = []
    today = date.today()
    for cohort_key, drivers in sorted(cohorts.items()):
        total = len(drivers)
        if total == 0:
            continue
        cohort_date = date.fromisoformat(cohort_key + "-01")
        days_since = (today - cohort_date).days

        retained_7d = sum(1 for d in drivers if (d.get("rolling_7d_trips") or 0) > 0)
        retained_14d = sum(1 for d in drivers if (d.get("rolling_28d_trips") or 0) > 0)
        retained_30d = sum(1 for d in drivers if (d.get("days_since_last_trip") or 999) < 30)

        result.append({
            "cohort": cohort_key,
            "drivers_started": total,
            "retained_7d": retained_7d,
            "retained_14d": retained_14d,
            "retained_30d": retained_30d,
            "retention_7d_pct": round(retained_7d / total * 100, 1) if total > 0 else 0.0,
            "retention_14d_pct": round(retained_14d / total * 100, 1) if total > 0 else 0.0,
            "retention_30d_pct": round(retained_30d / total * 100, 1) if total > 0 else 0.0,
        })

    return result
