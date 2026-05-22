"""
Recoverability Intelligence Service - Fase 2C.1
Shadow mode: calcula scores y estados de recoverability.
NO genera recomendaciones. NO automatiza acciones. NO usa ML/IA.

Scoring model (deterministico, 0-100):
  C1 (25%) Historical Consistency
  C2 (25%) Degradation Severity
  C3 (20%) Recency & Churn Duration
  C4 (15%) Archetype Compatibility
  C5 (10%) Efficiency Legacy
  C6 (±10) Modifiers

States: HIGHLY_RECOVERABLE(80-100), RECOVERABLE(60-79),
        LOW_RECOVERABLE(40-59), HARD_TO_RECOVER(20-39), NON_RECOVERABLE(0-19)
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import date, datetime, timedelta
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

TIMEOUT_MS = 120000

FACT_TRIP_DAILY = "ops.driver_trip_behavior_daily_fact"
FACT_SESSION = "ops.driver_session_fact"

# Weights per architecture doc
WEIGHTS = {
    "historical_consistency": 0.25,
    "degradation_severity": 0.25,
    "recency": 0.20,
    "archetype_compatibility": 0.15,
    "efficiency_legacy": 0.10,
}

# States
STATES = [
    {"state": "HIGHLY_RECOVERABLE", "min": 80, "max": 100, "label": "Highly Recoverable",
     "severity": "low", "color": "#22c55e", "description": "Recuperacion altamente probable"},
    {"state": "RECOVERABLE", "min": 60, "max": 79, "label": "Recoverable",
     "severity": "moderate", "color": "#3b82f6", "description": "Buen candidato para intervencion"},
    {"state": "LOW_RECOVERABLE", "min": 40, "max": 59, "label": "Low Recoverable",
     "severity": "elevated", "color": "#eab308", "description": "Seniales mixtas, recuperacion incierta"},
    {"state": "HARD_TO_RECOVER", "min": 20, "max": 39, "label": "Hard to Recover",
     "severity": "high", "color": "#f97316", "description": "Degradacion severa, baja probabilidad"},
    {"state": "NON_RECOVERABLE", "min": 0, "max": 19, "label": "Non Recoverable",
     "severity": "critical", "color": "#ef4444", "description": "Churn consolidado"},
]

# Archetype -> C4 score mapping
ARCHETYPE_C4 = {
    "FULLTIMER": 100,
    "CONSISTENT_OPERATOR": 90,
    "HIGH_EFFICIENCY": 85,
    "PART_TIMER": 65,
    "WEEKEND_SPECIALIST": 55,
    "PEAK_HOUR_SPECIALIST": 55,
    "HIGH_VOLUME_LOW_EFFICIENCY": 40,
    "INCONSISTENT_OPERATOR": 25,
    "BURNOUT_PATTERN": 15,
    "UNCLASSIFIED": 40,
}

# Recency -> C3 score mapping
RECENCY_C3 = [
    (7, 100), (14, 85), (21, 65), (30, 45), (45, 25), (60, 10), (90, 5), (9999, 0),
]

# Consistency -> C1 score mapping
CONSISTENCY_C1 = [
    (0.85, 100), (0.70, 80), (0.55, 60), (0.40, 40), (0.25, 20), (0, 0),
]

# Degradation -> C2 score mapping
DEGRADATION_C2 = {
    "none": 100,
    "early_warning_1": 80,
    "early_warning_2plus": 65,
    "moderate_1": 50,
    "moderate_2plus": 35,
    "strong_1": 20,
    "strong_2plus": 0,
}


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(timeout_ms),))
    return c


def _safe_num(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _score_from_steps(val: float, steps: list) -> float:
    """Map a value to score using ordered thresholds (descending)."""
    for threshold, score in steps:
        if val >= threshold:
            return float(score)
    return 0.0


def _score_from_steps_asc(val: float, steps: list) -> float:
    """Map a value to score using ascending thresholds."""
    for threshold, score in steps:
        if val <= threshold:
            return float(score)
    return 0.0


def _get_state(score: float) -> dict:
    for s in STATES:
        if s["min"] <= score <= s["max"]:
            return s
    return STATES[-1]


def _compute_archetypes(driver: dict) -> tuple:
    """Classify driver into archetypes using same rules as 2B."""
    trips = driver.get("trips", 0) or 0
    active_days = driver.get("active_days", 0) or 0
    rev_per_hour = _safe_num(driver.get("revenue_per_hour"))
    peak_share = _safe_num(driver.get("peak_hour_share"))
    weekend_share = _safe_num(driver.get("weekend_share"))
    trips_per_hour = _safe_num(driver.get("trips_per_hour"))
    zones_used = driver.get("zones_used", 0) or 0
    weekday_trips = driver.get("weekday_trips", 0) or 0

    archetypes = []
    if active_days >= 5 and trips >= 40:
        archetypes.append("FULLTIMER")
    if 1 <= active_days <= 4:
        archetypes.append("PART_TIMER")
    if weekend_share > 0.50 and trips >= 10:
        archetypes.append("WEEKEND_SPECIALIST")
    if peak_share > 0.60 and trips >= 10:
        archetypes.append("PEAK_HOUR_SPECIALIST")
    # We don't have population medians in per-driver context, use reasonable defaults
    if rev_per_hour > 15 and trips_per_hour > 0:
        archetypes.append("HIGH_EFFICIENCY")
    if trips > 30 and rev_per_hour < 8:
        archetypes.append("HIGH_VOLUME_LOW_EFFICIENCY")
    if active_days >= 5 and trips >= 20:
        archetypes.append("CONSISTENT_OPERATOR")
    if active_days <= 2 and trips < 10:
        archetypes.append("INCONSISTENT_OPERATOR")
    if active_days >= 6 and trips > 0 and active_days > 0 and (trips / active_days) < 4:
        archetypes.append("BURNOUT_PATTERN")

    return tuple(archetypes) if archetypes else ("UNCLASSIFIED",)


def _c4_score(archetypes: tuple) -> float:
    if not archetypes:
        return 40.0
    scores = [ARCHETYPE_C4.get(a, 40) for a in archetypes]
    return sum(scores) / len(scores)


def _get_driver_data(period_days: int, country=None, city=None) -> list[dict]:
    """Fetch per-driver aggregated metrics from trip_daily_fact."""
    with get_db() as conn:
        cur = _cursor(conn)

        where_parts = [f"f.activity_date >= CURRENT_DATE - {period_days}"]
        params: dict = {}
        if country:
            where_parts.append("f.country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("f.city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        cur.execute(
            f"""
            SELECT f.driver_id, f.country, f.city,
                   SUM(f.trips)::INTEGER AS trips,
                   SUM(f.cancelled_trips)::INTEGER AS cancelled_trips,
                   COUNT(DISTINCT f.activity_date) AS active_days,
                   SUM(f.revenue) AS total_revenue,
                   SUM(f.distance_km) AS total_distance_km,
                   SUM(f.duration_min) AS total_duration_min,
                   SUM(f.peak_hour_trips) AS peak_hour_trips,
                   SUM(f.weekend_trips) AS weekend_trips,
                   SUM(f.weekday_trips) AS weekday_trips,
                   COUNT(DISTINCT f.park_id) AS zones_used,
                   MAX(f.activity_date) AS last_activity_date,
                   CASE WHEN SUM(f.duration_min) > 0
                        THEN SUM(f.revenue) / (SUM(f.duration_min) / 60.0) END AS revenue_per_hour,
                   CASE WHEN SUM(f.trips) > 0
                        THEN SUM(f.peak_hour_trips)::numeric / SUM(f.trips) END AS peak_hour_share,
                   CASE WHEN SUM(f.trips) > 0
                        THEN SUM(f.weekend_trips)::numeric / SUM(f.trips) END AS weekend_share,
                   CASE WHEN SUM(f.duration_min) > 0
                        THEN SUM(f.trips)::numeric / (SUM(f.duration_min) / 60.0) END AS trips_per_hour,
                   CASE WHEN SUM(f.distance_km) > 0
                        THEN SUM(f.revenue) / SUM(f.distance_km) END AS revenue_per_km,
                   CASE WHEN SUM(f.trips) > 0
                        THEN SUM(f.revenue) / SUM(f.trips) END AS revenue_per_trip,
                   CASE WHEN COUNT(DISTINCT f.activity_date) > 0
                        THEN SUM(f.trips)::numeric / COUNT(DISTINCT f.activity_date) END AS avg_trips_per_day
            FROM {FACT_TRIP_DAILY} f
            WHERE {where_sql} AND f.trips > 0
            GROUP BY f.driver_id, f.country, f.city
            """,
            params,
        )
        return [dict(r) for r in (cur.fetchall() or [])]


def _get_prior_data(period_days: int, half: int, country=None, city=None) -> dict:
    """Fetch prior-period data for modifier calculation (TOP_PERFORMER detection)."""
    with get_db() as conn:
        cur = _cursor(conn)
        where_parts = [
            f"f.activity_date >= CURRENT_DATE - {period_days}",
            f"f.activity_date < CURRENT_DATE - {half}",
        ]
        params: dict = {}
        if country:
            where_parts.append("f.country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("f.city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        cur.execute(
            f"""
            SELECT f.driver_id,
                   SUM(f.revenue) AS prior_revenue,
                   SUM(f.trips)::INTEGER AS prior_trips,
                   COUNT(DISTINCT f.activity_date) AS prior_active_days
            FROM {FACT_TRIP_DAILY} f
            WHERE {where_sql} AND f.trips > 0 AND f.revenue IS NOT NULL
            GROUP BY f.driver_id
            """,
            params,
        )
        rows = cur.fetchall() or []
        return {r["driver_id"]: dict(r) for r in rows}


def compute_recoverability_score(driver: dict, period_days: int, prior_data: dict,
                                  pop_p50_rev_hour: float, pop_p75_rev_hour: float) -> dict:
    """Compute full recoverability score for a single driver."""
    driver_id = driver["driver_id"]
    active_days = driver.get("active_days", 0) or 0
    trips = driver.get("trips", 0) or 0
    last_date = driver.get("last_activity_date")
    revenue_per_hour = _safe_num(driver.get("revenue_per_hour"))
    peak_share = _safe_num(driver.get("peak_hour_share"))
    weekend_share = _safe_num(driver.get("weekend_share"))
    total_revenue = _safe_num(driver.get("total_revenue"))

    # C1: Historical Consistency
    consistency_score = active_days / max(period_days, 1) if period_days > 0 else 0
    c1 = _score_from_steps(consistency_score, CONSISTENCY_C1)

    # C2: Degradation Severity (compute from trips vs expected)
    # Compare actual trips to expected based on active_days and avg_trips_per_day
    avg_trips_per_day = _safe_num(driver.get("avg_trips_per_day"), 0)
    expected_trips = active_days * max(avg_trips_per_day, 1) if active_days > 0 else max(trips, 1)
    trips_change_pct = (trips - expected_trips) / expected_trips if expected_trips > 0 else 0
    c2 = _compute_c2(trips_change_pct, active_days, period_days)

    # C3: Recency
    days_since = 999
    if last_date:
        try:
            if hasattr(last_date, 'date'):
                last_date = last_date.date()
            elif isinstance(last_date, str):
                last_date = datetime.strptime(last_date[:10], "%Y-%m-%d").date()
            days_since = (date.today() - last_date).days
        except Exception:
            pass
    c3 = _score_from_steps_asc(days_since, RECENCY_C3)

    # C4: Archetype Compatibility
    archetypes = _compute_archetypes(driver)
    c4 = _c4_score(archetypes)

    # C5: Efficiency Legacy
    if revenue_per_hour > 0 and pop_p75_rev_hour > 0:
        if revenue_per_hour > pop_p75_rev_hour:
            c5 = 100.0
        elif revenue_per_hour > pop_p50_rev_hour:
            c5 = 70.0
        elif revenue_per_hour > pop_p50_rev_hour * 0.5:
            c5 = 40.0
        else:
            c5 = 10.0
    else:
        c5 = 0.0

    # Weighted subtotal
    subtotal = (
        c1 * WEIGHTS["historical_consistency"] +
        c2 * WEIGHTS["degradation_severity"] +
        c3 * WEIGHTS["recency"] +
        c4 * WEIGHTS["archetype_compatibility"] +
        c5 * WEIGHTS["efficiency_legacy"]
    )

    # C6: Modifiers
    modifiers = []
    mod_total = 0.0

    # Prior classification
    prior = prior_data.get(driver_id)
    if prior and prior.get("prior_revenue", 0) > 0:
        prior_rev = _safe_num(prior.get("prior_revenue"))
        prior_trips = prior.get("prior_trips", 0) or 0
        prior_days = prior.get("prior_active_days", 0) or 0
        if prior_trips > 0 and prior_days > 0:
            prior_avg = prior_rev / prior_trips if prior_trips > 0 else 0
            current_avg = total_revenue / trips if trips > 0 else 0
            # Prior TOP_PERFORMER: revenue in top 20%
            if prior_rev > pop_p75_rev_hour * prior_days * 2:
                modifiers.append({"modifier": "Prior TOP_PERFORMER", "points": 5, "evidence": f"Alto revenue en periodo anterior"})
                mod_total += 5
            elif prior_trips >= trips * 0.9:
                modifiers.append({"modifier": "Prior STABLE", "points": 3, "evidence": f"Trips estables vs periodo anterior"})
                mod_total += 3
            elif prior_trips < trips * 0.5:
                modifiers.append({"modifier": "Prior DECLINING", "points": -5, "evidence": f"Caida de trips vs periodo anterior"})
                mod_total -= 5

    # Balanced schedule
    if 0.3 < weekend_share < 0.7 and 0.3 < peak_share < 0.7:
        modifiers.append({"modifier": "Balanced Schedule", "points": 2, "evidence": f"weekend_share={weekend_share:.2f}, peak_share={peak_share:.2f}"})
        mod_total += 2

    # Extreme specialist
    if weekend_share > 0.9 or peak_share > 0.9:
        modifiers.append({"modifier": "Extreme Specialist", "points": -2, "evidence": f"weekend_share={weekend_share:.2f}, peak_share={peak_share:.2f}"})
        mod_total -= 2

    score = max(0.0, min(100.0, subtotal + mod_total))
    score = round(score, 1)
    state = _get_state(score)

    # Explainability
    consistency_pct = round(consistency_score * 100)
    explain_parts = [
        _explain_consistency(consistency_score, consistency_pct, period_days),
        _explain_degradation(c2, trips_change_pct),
        _explain_recency(days_since, last_date),
        _explain_archetype(archetypes),
        _explain_efficiency(c5, revenue_per_hour, pop_p50_rev_hour),
    ]
    if modifiers:
        mod_text = "Modificadores: " + "; ".join(
            f"{m['modifier']} ({'+' if m['points'] > 0 else ''}{m['points']} pts)" for m in modifiers
        ) + "."
        explain_parts.append(mod_text)

    intervention_urgency = "NONE"
    if score >= 80:
        intervention_urgency = "HIGH"
    elif score >= 60:
        intervention_urgency = "MEDIUM"
    elif score >= 40:
        intervention_urgency = "LOW"

    return {
        "driver_id": driver_id,
        "country": driver.get("country", ""),
        "city": driver.get("city", ""),
        "recoverability_state": state["state"],
        "recoverability_score": score,
        "state_metadata": {
            "label": state["label"],
            "severity": state["severity"],
            "color": state["color"],
            "description": state["description"],
        },
        "score_breakdown": {
            "historical_consistency": {
                "score": round(c1, 1),
                "weight": WEIGHTS["historical_consistency"],
                "contribution": round(c1 * WEIGHTS["historical_consistency"], 1),
                "evidence": f"consistency_score = {consistency_score:.2f} (activo {active_days} de {period_days} dias)",
                "raw_value": round(consistency_score, 3),
            },
            "degradation_severity": {
                "score": round(c2, 1),
                "weight": WEIGHTS["degradation_severity"],
                "contribution": round(c2 * WEIGHTS["degradation_severity"], 1),
                "evidence": f"trips_change = {round(trips_change_pct * 100)}%, severity = {_c2_label(c2)}",
                "raw_value": round(trips_change_pct, 3),
            },
            "recency": {
                "score": round(c3, 1),
                "weight": WEIGHTS["recency"],
                "contribution": round(c3 * WEIGHTS["recency"], 1),
                "evidence": f"Ultimo viaje: hace {days_since} dias" + (f" ({last_date})" if last_date else ""),
                "raw_value": days_since,
            },
            "archetype_compatibility": {
                "score": round(c4, 1),
                "weight": WEIGHTS["archetype_compatibility"],
                "contribution": round(c4 * WEIGHTS["archetype_compatibility"], 1),
                "evidence": f"Arquetipos: {', '.join(archetypes)}",
                "raw_value": list(archetypes),
            },
            "efficiency_legacy": {
                "score": round(c5, 1),
                "weight": WEIGHTS["efficiency_legacy"],
                "contribution": round(c5 * WEIGHTS["efficiency_legacy"], 1),
                "evidence": f"revenue_per_hour = {revenue_per_hour:.2f} (p50={pop_p50_rev_hour:.2f})",
                "raw_value": round(revenue_per_hour, 2),
            },
            "modifiers": modifiers,
        },
        "explainability_text": " ".join(explain_parts),
        "intervention_urgency": intervention_urgency,
        "risk_flags": [],
    }


def _compute_c2(trips_change_pct: float, active_days: int, period_days: int) -> float:
    """Compute C2 degradation severity score."""
    # Determine severity from trips_change and active_days
    if trips_change_pct >= -0.10 or active_days >= period_days * 0.8:
        return 100.0  # No degradation
    elif trips_change_pct >= -0.15:
        return 80.0  # Early warning - 1 signal
    elif trips_change_pct >= -0.30:
        return 65.0  # Early warning - 2+ signals
    elif trips_change_pct >= -0.40:
        return 50.0  # Moderate - 1 signal
    elif trips_change_pct >= -0.50:
        return 35.0  # Moderate - 2+ signals
    elif trips_change_pct >= -0.70:
        return 20.0  # Strong - 1 signal
    else:
        return 0.0  # Strong - 2+ signals or churn


def _c2_label(c2: float) -> str:
    if c2 >= 100: return "none"
    if c2 >= 80: return "early_warning"
    if c2 >= 50: return "moderate"
    return "strong"


def _explain_consistency(cs: float, pct: int, period_days: int) -> str:
    if cs > 0.85:
        return f"Consistencia historica excepcional ({pct}% dias activos)."
    elif cs > 0.70:
        return f"Buena consistencia historica ({pct}% dias activos)."
    elif cs > 0.55:
        return f"Consistencia historica moderada ({pct}% dias activos)."
    elif cs > 0.40:
        return f"Consistencia historica baja ({pct}% dias activos)."
    else:
        return f"Consistencia historica muy baja ({pct}% dias activos)."


def _explain_degradation(c2: float, change_pct: float) -> str:
    if c2 >= 100:
        return "Sin seniales de degradacion."
    pct_abs = round(abs(change_pct) * 100)
    if c2 >= 80:
        return f"Degradacion leve ({pct_abs}% caida de viajes, etapa temprana)."
    elif c2 >= 50:
        return f"Degradacion moderada ({pct_abs}% caida de viajes)."
    else:
        return f"Degradacion severa ({pct_abs}% caida de viajes)."


def _explain_recency(days: int, last_date) -> str:
    date_str = ""
    if last_date:
        try:
            if hasattr(last_date, 'strftime'):
                date_str = f" ({last_date.strftime('%Y-%m-%d')})"
            elif isinstance(last_date, str):
                date_str = f" ({last_date[:10]})"
        except Exception:
            pass
    if days <= 7:
        return f"Activo esta semana{date_str}. Ventana optima de intervencion."
    elif days <= 14:
        return f"Activo recientemente{date_str}."
    elif days <= 30:
        return f"Inactivo {days} dias{date_str}. Urgente."
    elif days <= 60:
        return f"Inactivo {days} dias{date_str}. Probabilidad baja."
    else:
        return f"Inactivo {days} dias{date_str}. Churn consolidado."


def _explain_archetype(archetypes: tuple) -> str:
    if not archetypes or archetypes[0] == "UNCLASSIFIED":
        return "Sin arquetipo definido."
    if "FULLTIMER" in archetypes:
        return "Perfil FULLTIMER. Alta dependencia de la plataforma."
    if "CONSISTENT_OPERATOR" in archetypes:
        return "Perfil CONSISTENT_OPERATOR. Patron estable."
    if "HIGH_EFFICIENCY" in archetypes:
        return "Perfil HIGH_EFFICIENCY. Alto valor operativo."
    if "PART_TIMER" in archetypes:
        return "Perfil PART_TIMER. Ingreso complementario."
    return f"Perfil {archetypes[0]}."


def _explain_efficiency(c5: float, rev_hour: float, p50: float) -> str:
    if c5 >= 100:
        return f"Eficiencia historica excepcional (revenue/h={rev_hour:.0f})."
    elif c5 >= 70:
        return f"Buena eficiencia historica (revenue/h={rev_hour:.0f})."
    elif c5 >= 40:
        return f"Eficiencia historica media (revenue/h={rev_hour:.0f})."
    elif c5 > 0:
        return f"Eficiencia historica baja (revenue/h={rev_hour:.0f})."
    else:
        return "Sin datos de eficiencia historica."


# ========== PUBLIC API ==========

def get_recoverability_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """Aggregate recoverability summary across all drivers in scope."""
    drivers = _get_driver_data(period_days, country, city)
    if not drivers:
        return {"summary": {}, "distribution": {}, "available": False, "reason": "No drivers in scope"}

    half = period_days // 2
    prior = _get_prior_data(period_days, half, country, city)

    rev_hours = [_safe_num(d.get("revenue_per_hour")) for d in drivers if _safe_num(d.get("revenue_per_hour")) > 0]
    pop_p50_rev_hour = sorted(rev_hours)[len(rev_hours) // 2] if rev_hours else 10.0
    pop_p75_rev_hour = sorted(rev_hours)[int(len(rev_hours) * 0.75)] if len(rev_hours) > 3 else pop_p50_rev_hour * 1.5

    scores = []
    states_count = {}
    for d in drivers:
        result = compute_recoverability_score(d, period_days, prior, pop_p50_rev_hour, pop_p75_rev_hour)
        scores.append(result)
        st = result["recoverability_state"]
        states_count[st] = states_count.get(st, 0) + 1

    avg_score = round(sum(s["recoverability_score"] for s in scores) / max(len(scores), 1), 1)

    distribution = {}
    for s in STATES:
        distribution[s["state"]] = {
            "count": states_count.get(s["state"], 0),
            "label": s["label"],
            "color": s["color"],
            "severity": s["severity"],
        }
    distribution["TOTAL"] = {"count": len(scores)}

    return {
        "summary": {
            "total_drivers": len(scores),
            "avg_recoverability_score": avg_score,
            "highly_recoverable_count": states_count.get("HIGHLY_RECOVERABLE", 0),
            "recoverable_count": states_count.get("RECOVERABLE", 0),
            "low_recoverable_count": states_count.get("LOW_RECOVERABLE", 0),
            "hard_to_recover_count": states_count.get("HARD_TO_RECOVER", 0),
            "non_recoverable_count": states_count.get("NON_RECOVERABLE", 0),
            "period_days": period_days,
            "population_p50_rev_per_hour": round(pop_p50_rev_hour, 2),
            "population_p75_rev_per_hour": round(pop_p75_rev_hour, 2),
        },
        "distribution": distribution,
        "states_definition": STATES,
        "weights": WEIGHTS,
        "available": True,
        "shadow_mode": True,
        "note": "Shadow mode only. No automated interventions. No recommendations generated.",
    }


def get_top_recoverable(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    limit: int = 20,
) -> dict:
    """Top recoverable drivers, ranked by score descending."""
    drivers = _get_driver_data(period_days, country, city)
    if not drivers:
        return {"drivers": [], "available": False}

    half = period_days // 2
    prior = _get_prior_data(period_days, half, country, city)

    rev_hours = [_safe_num(d.get("revenue_per_hour")) for d in drivers if _safe_num(d.get("revenue_per_hour")) > 0]
    pop_p50 = sorted(rev_hours)[len(rev_hours) // 2] if rev_hours else 10.0
    pop_p75 = sorted(rev_hours)[int(len(rev_hours) * 0.75)] if len(rev_hours) > 3 else pop_p50 * 1.5

    results = []
    for d in drivers:
        result = compute_recoverability_score(d, period_days, prior, pop_p50, pop_p75)
        results.append(result)

    results.sort(key=lambda x: x["recoverability_score"], reverse=True)
    top = results[:limit]

    for i, r in enumerate(top):
        r["rank"] = i + 1
        r["percentile"] = round((1 - (i / max(len(results), 1))) * 100, 1)

    return {
        "drivers": top,
        "total_in_scope": len(results),
        "available": True,
        "shadow_mode": True,
    }


def get_recoverability_distribution(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """Distribution of recoverability states + per-state stats."""
    drivers = _get_driver_data(period_days, country, city)
    if not drivers:
        return {"distribution": [], "available": False}

    half = period_days // 2
    prior = _get_prior_data(period_days, half, country, city)

    rev_hours = [_safe_num(d.get("revenue_per_hour")) for d in drivers if _safe_num(d.get("revenue_per_hour")) > 0]
    pop_p50 = sorted(rev_hours)[len(rev_hours) // 2] if rev_hours else 10.0
    pop_p75 = sorted(rev_hours)[int(len(rev_hours) * 0.75)] if len(rev_hours) > 3 else pop_p50 * 1.5

    state_data = {s["state"]: {"count": 0, "drivers": [], "avg_score": 0.0} for s in STATES}

    for d in drivers:
        result = compute_recoverability_score(d, period_days, prior, pop_p50, pop_p75)
        st = result["recoverability_state"]
        state_data[st]["count"] += 1
        state_data[st]["drivers"].append(result)

    distribution = []
    for s in STATES:
        sd = state_data[s["state"]]
        scores_in_state = [d["recoverability_score"] for d in sd["drivers"]]
        avg = round(sum(scores_in_state) / max(len(scores_in_state), 1), 1) if scores_in_state else 0
        distribution.append({
            "state": s["state"],
            "label": s["label"],
            "color": s["color"],
            "severity": s["severity"],
            "count": sd["count"],
            "pct": round(sd["count"] / max(len(drivers), 1) * 100, 1),
            "avg_score": avg,
        })

    return {
        "distribution": distribution,
        "total_drivers": len(drivers),
        "available": True,
        "shadow_mode": True,
    }


def get_driver_recoverability(
    driver_id: str,
    period_days: int = 28,
) -> dict:
    """Detailed recoverability for a single driver."""
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            f"""
            SELECT f.driver_id, f.country, f.city,
                   SUM(f.trips)::INTEGER AS trips,
                   SUM(f.cancelled_trips)::INTEGER AS cancelled_trips,
                   COUNT(DISTINCT f.activity_date) AS active_days,
                   SUM(f.revenue) AS total_revenue,
                   SUM(f.distance_km) AS total_distance_km,
                   SUM(f.duration_min) AS total_duration_min,
                   SUM(f.peak_hour_trips) AS peak_hour_trips,
                   SUM(f.weekend_trips) AS weekend_trips,
                   SUM(f.weekday_trips) AS weekday_trips,
                   COUNT(DISTINCT f.park_id) AS zones_used,
                   MAX(f.activity_date) AS last_activity_date,
                   CASE WHEN SUM(f.duration_min) > 0 THEN SUM(f.revenue) / (SUM(f.duration_min) / 60.0) END AS revenue_per_hour,
                   CASE WHEN SUM(f.trips) > 0 THEN SUM(f.peak_hour_trips)::numeric / SUM(f.trips) END AS peak_hour_share,
                   CASE WHEN SUM(f.trips) > 0 THEN SUM(f.weekend_trips)::numeric / SUM(f.trips) END AS weekend_share,
                   CASE WHEN SUM(f.duration_min) > 0 THEN SUM(f.trips)::numeric / (SUM(f.duration_min) / 60.0) END AS trips_per_hour,
                   CASE WHEN SUM(f.distance_km) > 0 THEN SUM(f.revenue) / SUM(f.distance_km) END AS revenue_per_km
            FROM {FACT_TRIP_DAILY} f
            WHERE f.driver_id = %(driver_id)s
              AND f.activity_date >= CURRENT_DATE - %(period)s
              AND f.trips > 0
            GROUP BY f.driver_id, f.country, f.city
            """,
            {"driver_id": driver_id, "period": period_days},
        )
        driver = dict(cur.fetchone() or {})
        if not driver:
            return {"driver_id": driver_id, "available": False, "reason": "Driver not found or no trips in period"}

    half = period_days // 2
    prior = _get_prior_data(period_days, half)

    pop_p50 = _safe_num(driver.get("revenue_per_hour"), 10)
    pop_p75 = pop_p50 * 1.5

    result = compute_recoverability_score(driver, period_days, prior, pop_p50, pop_p75)
    result["available"] = True
    result["shadow_mode"] = True
    return result


def get_shadow_priority(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    limit: int = 50,
) -> dict:
    """Shadow priority ranking - visual only, no queue/automation."""
    drivers = _get_driver_data(period_days, country, city)
    if not drivers:
        return {"priority": [], "available": False}

    half = period_days // 2
    prior = _get_prior_data(period_days, half, country, city)

    rev_hours = [_safe_num(d.get("revenue_per_hour")) for d in drivers if _safe_num(d.get("revenue_per_hour")) > 0]
    pop_p50 = sorted(rev_hours)[len(rev_hours) // 2] if rev_hours else 10.0
    pop_p75 = sorted(rev_hours)[int(len(rev_hours) * 0.75)] if len(rev_hours) > 3 else pop_p50 * 1.5

    results = []
    for d in drivers:
        result = compute_recoverability_score(d, period_days, prior, pop_p50, pop_p75)
        results.append(result)

    # Sort by recoverability_score descending, then by total_revenue for ties
    results.sort(key=lambda x: (x["recoverability_score"], x.get("driver_id", "")), reverse=True)
    total = len(results)

    priority = []
    for i, r in enumerate(results[:limit]):
        tier = "TIER_1" if i < total * 0.2 else ("TIER_2" if i < total * 0.5 else "TIER_3")
        priority.append({
            "rank": i + 1,
            "percentile": round((1 - (i / total)) * 100, 1),
            "priority_tier_shadow": tier,
            "driver_id": r["driver_id"],
            "country": r["country"],
            "city": r["city"],
            "recoverability_score": r["recoverability_score"],
            "recoverability_state": r["recoverability_state"],
            "intervention_urgency": r["intervention_urgency"],
        })

    return {
        "priority": priority,
        "total_in_scope": total,
        "available": True,
        "shadow_mode": True,
        "note": "Shadow priority only. Visual ranking. No automated actions. No SAC queue routing.",
    }
