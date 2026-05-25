"""
Behavioral Diagnostic MVP Service — Fase 2A.3
Motor: Diagnostic Engine
Clasifica conductores usando solo senales disponibles en ops.driver_daily_activity_fact.

Senales: trips, active_days, days_since_last, weekend_share
NO usa: revenue, online_hours, cancellations, acceptance, zones, distance, trip_hour

Clasificacion deterministica — basada en thresholds existentes de driver_behavior_benchmarking.
NO genera recomendaciones. NO usa IA.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

FACT_TABLE = "ops.driver_daily_activity_fact"
DEFAULT_WINDOW_DAYS = 28

# ─── Classification thresholds (consistent with driver_behavior_benchmarking) ───
GROWING_DELTA_PCT = 25
DECLINING_DELTA_PCT = -25
AT_RISK_DELTA_PCT = -40
INACTIVE_RISK_DAYS = 14
CHURNED_DAYS = 30
TOP_ACTIVE_DAYS_FRACTION = 0.3


def get_behavioral_diagnosis_mvp(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    comparison_window_days: Optional[int] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Diagnostico conductual MVP — nivel conductor individual.

    Retorna lista de conductores con:
    - driver_id, status, avg_trips, trips_per_day, active_days,
      weekend_share, days_since_last, delta_pct,
      dominant_factor, severity, explanation
    - Resumen por status
    - Metadata de senales usadas / faltantes
    """
    comparison_days = comparison_window_days or window_days

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # ─── 1. Current window driver aggregation ───
            cur.execute("""
                SELECT
                    driver_id,
                    country,
                    city,
                    park_id,
                    SUM(completed_trips) AS total_trips,
                    COUNT(DISTINCT activity_date) AS active_days,
                    MAX(activity_date) AS last_active_date
                FROM ops.driver_daily_activity_fact
                WHERE activity_date >= CURRENT_DATE - %(window)s::int
                  AND activity_date < CURRENT_DATE
                  AND completed_trips > 0
                  AND (%(country)s::text IS NULL OR country = %(country)s)
                  AND (%(city)s::text IS NULL OR city = %(city)s)
                  AND (%(park_id)s::text IS NULL OR park_id = %(park_id)s)
                GROUP BY driver_id, country, city, park_id
            """, {"window": window_days, "country": country, "city": city, "park_id": park_id})
            current_rows = {r["driver_id"]: dict(r) for r in cur.fetchall()}

            if not current_rows:
                return _empty_response(window_days, country, city, park_id)

            driver_ids = list(current_rows.keys())

            # ─── 2. Previous window aggregation (for delta) ───
            cur.execute("""
                SELECT
                    driver_id,
                    SUM(completed_trips) AS prev_total_trips
                FROM ops.driver_daily_activity_fact
                WHERE activity_date >= CURRENT_DATE - %(window)s::int - %(comp)s::int
                  AND activity_date < CURRENT_DATE - %(window)s::int
                  AND completed_trips > 0
                  AND driver_id = ANY(%(ids)s)
                GROUP BY driver_id
            """, {"window": window_days, "comp": comparison_days, "ids": driver_ids})
            prev_map = {r["driver_id"]: r["prev_total_trips"] for r in cur.fetchall()}

            # ─── 3. Weekend share per driver ───
            cur.execute("""
                SELECT
                    driver_id,
                    SUM(CASE WHEN EXTRACT(ISODOW FROM activity_date) IN (6, 7)
                        THEN completed_trips ELSE 0 END) AS weekend_trips,
                    SUM(completed_trips) AS total_trips
                FROM ops.driver_daily_activity_fact
                WHERE activity_date >= CURRENT_DATE - %(window)s::int
                  AND activity_date < CURRENT_DATE
                  AND completed_trips > 0
                  AND driver_id = ANY(%(ids)s)
                GROUP BY driver_id
            """, {"window": window_days, "ids": driver_ids})
            weekend_map = {
                r["driver_id"]: round(r["weekend_trips"] / max(r["total_trips"], 1), 4)
                for r in cur.fetchall()
            }

            cur.close()

        # ─── 4. Build driver diagnostics ───
        drivers = []
        for did, row in current_rows.items():
            total_trips = row["total_trips"] or 0
            active_days = row["active_days"] or 0
            last_active = row["last_active_date"]
            days_since_last = _days_since(last_active) if last_active else window_days + 1
            weekend_share = weekend_map.get(did)
            trips_per_day = round(total_trips / max(active_days, 1), 2)
            prev_trips = prev_map.get(did) or 0
            delta_pct = round(((total_trips - prev_trips) / max(prev_trips, 1)) * 100, 1) if prev_trips > 0 else None

            status, severity, dominant_factor, explanation = _classify(
                total_trips, active_days, trips_per_day,
                days_since_last, delta_pct, weekend_share,
                window_days,
            )

            drivers.append({
                "driver_id": did,
                "country": row.get("country", ""),
                "city": row.get("city", ""),
                "park_id": row.get("park_id", ""),
                "status": status,
                "severity": severity,
                "avg_trips": total_trips,
                "trips_per_day": trips_per_day,
                "active_days": active_days,
                "weekend_share": weekend_share,
                "days_since_last": days_since_last,
                "delta_pct": delta_pct,
                "dominant_factor": dominant_factor,
                "explanation": explanation,
            })

        # ─── 5. Sort by severity ───
        drivers.sort(key=_severity_rank)

        # ─── 6. Summary ───
        summary = _build_summary(drivers)

        return {
            "drivers": drivers[:limit],
            "total_drivers": len(drivers),
            "returned": min(len(drivers), limit),
            "summary": summary,
            "period_days": window_days,
            "diagnostic_mode": "deterministic",
            "signals_used": [
                "completed_trips", "activity_date", "country", "city",
                "park_id", "weekend_share", "days_since_last",
            ],
            "signals_unavailable": [
                "revenue", "online_hours", "acceptance", "cancellation",
                "zone", "trip_hour", "distance", "duration",
                "avg_ticket", "tipo_servicio",
            ],
            "note": (
                "Diagnostico conductual MVP. Solo senales disponibles en "
                "ops.driver_daily_activity_fact. NO usa revenue, eficiencia, "
                "cancelaciones ni aceptacion. Interpretaciones diagnosticas, "
                "no recomendaciones."
            ),
            "filters_applied": {
                "country": country, "city": city, "park_id": park_id,
                "window_days": window_days,
            },
        }

    except Exception as e:
        logger.error("Behavioral MVP error: %s", e)
        return {
            "error": True,
            "detail": str(e),
            "drivers": [],
            "total_drivers": 0,
            "note": "Error consultando datos de diagnostico conductual.",
        }


# ─── Classification ─────────────────────────────────────────────────────────

def _classify(
    total_trips: int,
    active_days: int,
    trips_per_day: float,
    days_since_last: int,
    delta_pct: Optional[float],
    weekend_share: Optional[float],
    window_days: int,
) -> tuple[str, str, str, str]:
    """Clasifica un conductor en status + severity + dominant_factor + explanation."""

    # CHURNED
    if days_since_last >= CHURNED_DAYS:
        return (
            "churned",
            "critical",
            "inactivity_churned",
            f"Inactivo por {days_since_last} dias. Sin actividad en las ultimas {window_days} semanas.",
        )

    # DORMANT / INACTIVE_RISK
    if days_since_last >= INACTIVE_RISK_DAYS or total_trips == 0:
        severity = "warning" if days_since_last >= INACTIVE_RISK_DAYS else "elevated"
        return (
            "inactive_risk",
            severity,
            "inactivity_risk",
            f"Sin actividad en los ultimos {days_since_last} dias. Riesgo de inactividad.",
        )

    # AT_RISK — severe decline
    if delta_pct is not None and delta_pct <= AT_RISK_DELTA_PCT:
        return (
            "at_risk",
            "critical",
            "severe_trip_decline",
            f"Caida severa de viajes ({delta_pct:+.1f}%). Trips actuales: {total_trips}. Requiere atencion.",
        )

    # DECLINING — moderate decline
    if delta_pct is not None and delta_pct <= DECLINING_DELTA_PCT:
        severity = "elevated" if delta_pct <= -35 else "warning"
        return (
            "declining",
            severity,
            "trip_decline",
            f"Reduccion de viajes ({delta_pct:+.1f}%). Trips actuales: {total_trips}, {active_days} dias activos.",
        )

    # TOP — needs percentile, approximate with trips_per_day threshold
    if trips_per_day >= 5 and active_days >= window_days * TOP_ACTIVE_DAYS_FRACTION:
        return (
            "top",
            "normal",
            "high_productivity",
            f"Alto rendimiento: {trips_per_day:.1f} viajes/dia, {active_days} dias activos.",
        )

    # GROWING
    if delta_pct is not None and delta_pct >= GROWING_DELTA_PCT:
        return (
            "growing",
            "normal",
            "trip_growth",
            f"Crecimiento de viajes ({delta_pct:+.1f}%). Trips actuales: {total_trips}.",
        )

    # STABLE — within normal range
    return (
        "stable",
        "normal",
        "stable_activity" if total_trips > 0 else "low_activity",
        f"Actividad estable. {total_trips} viajes, {active_days} dias activos."
        if total_trips > 0
        else "Actividad baja pero estable.",
    )


def _severity_rank(driver: dict) -> int:
    """Orden de severidad para sorting: critical > elevated > warning > normal."""
    order = {"critical": 0, "elevated": 1, "warning": 2, "normal": 3}
    return order.get(driver.get("severity", "normal"), 99)


def _days_since(date_val) -> int:
    """Calcula dias desde una fecha hasta hoy."""
    from datetime import date
    if hasattr(date_val, 'date'):
        date_val = date_val.date()
    return (date.today() - date_val).days


def _build_summary(drivers: list) -> dict:
    """Construye resumen por status."""
    counts = {}
    for d in drivers:
        s = d["status"]
        counts[s] = counts.get(s, 0) + 1

    total = len(drivers)
    return {
        "total": total,
        "by_status": counts,
        "active_drivers": total - counts.get("churned", 0),
        "at_risk_count": counts.get("at_risk", 0) + counts.get("inactive_risk", 0),
        "declining_count": counts.get("declining", 0),
        "top_count": counts.get("top", 0),
        "growing_count": counts.get("growing", 0),
        "stable_count": counts.get("stable", 0),
        "churned_count": counts.get("churned", 0),
    }


def _empty_response(window_days: int, country: str, city: str, park_id: str) -> dict:
    return {
        "drivers": [],
        "total_drivers": 0,
        "returned": 0,
        "summary": _build_summary([]),
        "period_days": window_days,
        "diagnostic_mode": "deterministic",
        "signals_used": ["completed_trips", "activity_date", "country", "city", "park_id", "weekend_share", "days_since_last"],
        "signals_unavailable": ["revenue", "online_hours", "acceptance", "cancellation", "zone", "trip_hour", "distance", "duration", "avg_ticket", "tipo_servicio"],
        "note": "Diagnostico conductual MVP. No se encontraron conductores para los filtros seleccionados.",
        "filters_applied": {"country": country, "city": city, "park_id": park_id, "window_days": window_days},
    }
