"""
Behavioral Pattern Diagnosis Layer — Fase 2A.3.1 (Performance Hardened)
Explica patrones operativos diferenciales entre grupos de conductores.
v2: Cache compartido TTL + queries directas para evitar recomputación.

Arquitectura de cache:
  _get_full_benchmark_data() — fetch ONCE per (country, city, period_days, enrich)
  Todas las funciones públicas reutilizan los mismos datos cacheados.
  TTL: 300s. Expiración limpia de entradas antiguas.
"""
from __future__ import annotations

from typing import Any, Optional
import time
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

from app.services.driver_behavior_benchmarking_service import (
    get_behavior_benchmarking_groups,
    _resolve_primary_source,
    _detect_fact_columns,
    _build_available_metrics_info,
    _fetch_and_classify_drivers,
    _build_group_benchmarks,
    _date_range,
    LIFECYCLE_GROUPS,
    FACT_TABLE,
)

logger = logging.getLogger(__name__)

STRENGTH_HIGH = "HIGH"
STRENGTH_MEDIUM = "MEDIUM"
STRENGTH_LOW = "LOW"

CACHE_TTL = 300  # segundos — cache operacional, no fuente de verdad

DIMENSIONS = [
    "activity_volume", "consistency", "productivity", "recency",
    "weekday_weekend", "city_mix", "park_mix", "lob_mix",
    "revenue_efficiency", "time_efficiency", "distance_efficiency",
    "cancellation_behavior",
]

_full_cache: dict = {}


def _evict_expired():
    """Limpia entradas de cache expiradas (2x TTL)."""
    now = time.time()
    for k in list(_full_cache.keys()):
        if now - _full_cache[k]["ts"] > CACHE_TTL * 2:
            del _full_cache[k]


def _get_full_benchmark_data(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict:
    """Fetch completo de datos de benchmarking con cache TTL.
    Retorna grupos, mapa, drivers clasificados, metadatos de fuente.
    Todas las funciones públicas deben usar esto en vez de llamar
    get_behavior_benchmarking_groups() directamente."""
    key = (country or "", city or "", period_days, enrich_from_trips)
    now = time.time()

    if key in _full_cache:
        entry = _full_cache[key]
        if now - entry["ts"] < CACHE_TTL:
            return entry["data"]

    _evict_expired()

    with get_db() as conn:
        source_info = _resolve_primary_source(conn)
        fact_available = _detect_fact_columns(conn)
        all_drivers, classified, thresholds, date_tuple = _fetch_and_classify_drivers(
            conn, country, city, period_days, source_info,
        )

    groups_list = []
    for gname in LIFECYCLE_GROUPS:
        drivers_in_group = classified.get(gname, [])
        benchmark = _build_group_benchmarks(drivers_in_group, gname, period_days)
        groups_list.append(benchmark)

    groups_map = {g["group_name"]: g for g in groups_list}
    avail, missing = _build_available_metrics_info(source_info, fact_available)

    current_start, current_end = date_tuple[0], date_tuple[1]

    data = {
        "groups": groups_list,
        "groups_map": groups_map,
        "classified": classified,
        "all_drivers": all_drivers,
        "source_info": source_info,
        "fact_available": fact_available,
        "available_metrics": avail,
        "missing_metrics": missing,
        "date_range": {"from": current_start, "to": current_end},
        "period_days": period_days,
    }

    _full_cache[key] = {"data": data, "ts": now}
    return data


def _query_top_dimension_from_fact(
    dimension: str,
    driver_keys: list,
    current_start: str,
    current_end: str,
    limit: int = 5,
) -> list[dict]:
    """Consulta directa al fact table para top ciudades/parks de un grupo.
    Mucho más rápido que get_behavior_benchmarking_distributions()
    porque no re-clasifica drivers."""
    if not driver_keys:
        return []

    driver_list = "', '".join(str(k) for k in driver_keys)

    if dimension == "city":
        dim_col = "COALESCE(NULLIF(TRIM(f.city), ''), 'UNKNOWN')"
    elif dimension == "park":
        dim_col = "COALESCE(NULLIF(TRIM(f.park_id), ''), 'UNKNOWN')"
    else:
        return []

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT {dim_col} AS label,
                   SUM(f.completed_trips) AS trips,
                   COUNT(DISTINCT f.driver_id) AS driver_count
            FROM {FACT_TABLE} f
            WHERE f.driver_id IN ('{driver_list}')
              AND f.activity_date >= '{current_start}'::date
              AND f.activity_date < '{current_end}'::date + INTERVAL '1 day'
            GROUP BY label
            ORDER BY trips DESC
            LIMIT {limit}
        """)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


def _determine_strength(gap_pct: float, metric_type: str) -> Optional[str]:
    abs_gap = abs(gap_pct)
    if metric_type in ("ratio",):
        if abs_gap >= 30: return STRENGTH_HIGH
        if abs_gap >= 15: return STRENGTH_MEDIUM
        if abs_gap >= 5: return STRENGTH_LOW
    else:
        if abs_gap >= 100: return STRENGTH_HIGH
        if abs_gap >= 50: return STRENGTH_MEDIUM
        if abs_gap >= 25: return STRENGTH_LOW
    return None


def _compare_groups_for_patterns(
    group_a: dict, group_b: dict,
    label_a: str, label_b: str,
) -> list[dict]:
    patterns = []
    if group_a.get("drivers_count", 0) == 0 or group_b.get("drivers_count", 0) == 0:
        return patterns

    comparison_label = f"{label_a} vs {label_b}"
    sample_size = group_a.get("drivers_count", 0) + group_b.get("drivers_count", 0)

    comparisons = [
        ("avg_trips_per_driver", "activity_volume", "trips", "Mayor volumen de viajes", "presenta mayor volumen promedio de viajes"),
        ("avg_active_days", "consistency", "days", "Más días activos", "presenta más días activos promedio"),
        ("trips_per_active_day", "productivity", "trips/day", "Mayor productividad por día", "concentra más viajes por día activo"),
        ("consistency_score", "consistency", "ratio", "Mayor consistencia operativa", "muestra mayor consistencia operativa"),
    ]

    for metric_key, dimension, metric_type, title_prefix, interpretation_tmpl in comparisons:
        val_a = group_a.get(metric_key) or 0
        val_b = group_b.get(metric_key) or 0
        if val_a == 0 and val_b == 0:
            continue

        reference_val = max(val_a, val_b)
        comparison_val = min(val_a, val_b)
        if reference_val == 0:
            continue

        gap_abs = round(val_a - val_b, 4 if metric_type == "ratio" else 2)
        gap_pct = round(abs(gap_abs) / max(comparison_val, 0.0001) * 100, 1)
        strength = _determine_strength(gap_pct, metric_type)
        if strength is None:
            continue

        if gap_abs > 0:
            title = f"{title_prefix} en {label_a}"
            interpretation = f"{label_a} {interpretation_tmpl} que {label_b}."
            top_value, comp_value = val_a, val_b
        else:
            title = f"{title_prefix} en {label_b}"
            interpretation = f"{label_b} {interpretation_tmpl} que {label_a}."
            top_value, comp_value = val_b, val_a

        patterns.append({
            "pattern_id": f"{dimension}_{label_a.lower()}_vs_{label_b.lower()}",
            "dimension": dimension, "title": title, "strength": strength,
            "comparison_groups": comparison_label, "metric_name": metric_key,
            "top_value": top_value, "comparison_value": comp_value,
            "gap_abs": abs(gap_abs), "gap_pct": gap_pct,
            "sample_size": sample_size, "interpretation": interpretation,
            "available": True, "source": FACT_TABLE,
        })

    weekend_a = group_a.get("weekend_share")
    weekend_b = group_b.get("weekend_share")
    if weekend_a is not None and weekend_b is not None:
        gap = round(abs((weekend_a or 0) - (weekend_b or 0)) * 100, 1)
        strength_we = _determine_strength(gap, "ratio")
        if strength_we:
            if (weekend_a or 0) > (weekend_b or 0):
                title = f"Mayor actividad en fin de semana: {label_a}"
                interpretation = f"Existe diferencia relevante en concentración de actividad de fin de semana: {label_a} presenta {gap:.1f} puntos más que {label_b}."
                top_val, comp_val = weekend_a, weekend_b
            else:
                title = f"Mayor actividad en fin de semana: {label_b}"
                interpretation = f"Existe diferencia relevante en concentración de actividad de fin de semana: {label_b} presenta {gap:.1f} puntos más que {label_a}."
                top_val, comp_val = weekend_b, weekend_a
            patterns.append({
                "pattern_id": f"weekend_{label_a.lower()}_vs_{label_b.lower()}",
                "dimension": "weekday_weekend", "title": title,
                "strength": strength_we, "comparison_groups": comparison_label,
                "metric_name": "weekend_share",
                "top_value": top_val, "comparison_value": comp_val,
                "gap_abs": round(abs((weekend_a or 0) - (weekend_b or 0)), 4),
                "gap_pct": gap, "sample_size": sample_size,
                "interpretation": interpretation, "available": True, "source": FACT_TABLE,
            })

    return patterns


def _build_decline_signals(groups_map: dict) -> list[dict]:
    stable = groups_map.get("STABLE", {})
    declining = groups_map.get("DECLINING", {})
    at_risk = groups_map.get("AT_RISK", {})
    signals = []

    def make_signal(name, metric, dim, unit, description_tmpl):
        s_val = stable.get(metric)
        if s_val is None or s_val == 0:
            return None
        rows = []
        for label, val in [("DECLINING", declining.get(metric)), ("AT_RISK", at_risk.get(metric))]:
            if val is None or s_val == 0:
                continue
            gap_pct = round(abs(s_val - val) / s_val * 100, 1)
            strength = _determine_strength(gap_pct, unit)
            if strength is None:
                continue
            rows.append({
                "comparison": f"STABLE vs {label}",
                "stable_value": s_val, "comparison_value": val,
                "gap_pct": gap_pct,
                "interpretation": description_tmpl.format(label=label),
                "strength": strength,
            })
        if not rows:
            return None
        best = max(rows, key=lambda r: r["gap_pct"])
        return {
            "signal_name": name, "dimension": dim, "metric": metric,
            "stable_value": s_val,
            "declining_value": declining.get(metric),
            "at_risk_value": at_risk.get(metric),
            "max_gap_pct": best["gap_pct"],
            "max_gap_vs": best["comparison"],
            "interpretation": best["interpretation"],
            "strength": best["strength"],
            "details": rows,
        }

    signal_defs = [
        ("Disminución de volumen de viajes", "avg_trips_per_driver", "activity_volume", "trips",
         "Se observa que {label} tiene menos viajes por conductor que STABLE."),
        ("Reducción de días activos", "avg_active_days", "consistency", "days",
         "El grupo {label} muestra menos días activos promedio que STABLE."),
        ("Caída de productividad diaria", "trips_per_active_day", "productivity", "trips/day",
         "{label} presenta menos viajes por día activo comparado con STABLE."),
        ("Pérdida de consistencia", "consistency_score", "consistency", "ratio",
         "Existe menor consistencia operativa en {label} frente a STABLE."),
    ]

    for name, metric, dim, unit, tmpl in signal_defs:
        signal = make_signal(name, metric, dim, unit, tmpl)
        if signal:
            signals.append(signal)

    weekend_s = stable.get("weekend_share")
    weekend_d = declining.get("weekend_share")
    weekend_r = at_risk.get("weekend_share")
    if weekend_s is not None and (weekend_d is not None or weekend_r is not None):
        best_gap, best_label = 0, ""
        for label, val in [("DECLINING", weekend_d), ("AT_RISK", weekend_r)]:
            if val is None: continue
            gap = round(abs((weekend_s or 0) - (val or 0)) * 100, 1)
            if gap > best_gap: best_gap, best_label = gap, label
        strength = _determine_strength(best_gap, "ratio")
        if strength:
            signals.append({
                "signal_name": "Cambio en patrón de fin de semana",
                "dimension": "weekday_weekend", "metric": "weekend_share",
                "stable_value": weekend_s, "declining_value": weekend_d,
                "at_risk_value": weekend_r,
                "max_gap_pct": best_gap,
                "max_gap_vs": f"STABLE vs {best_label}",
                "interpretation": "Se observa una diferencia en la actividad de fin de semana entre STABLE y los grupos en deterioro.",
                "strength": strength, "details": [],
            })

    return signals


def _compute_all_patterns(groups_map: dict) -> list[dict]:
    """Computa todos los patrones desde el groups_map ya cacheados."""
    all_patterns = []
    pairings = [
        ("TOP_PERFORMER", "AT_RISK"), ("TOP_PERFORMER", "DECLINING"),
        ("TOP_PERFORMER", "STABLE"), ("STABLE", "DECLINING"),
        ("STABLE", "AT_RISK"), ("GROWING", "DECLINING"),
        ("DECLINING", "AT_RISK"),
    ]
    for label_a, label_b in pairings:
        group_a = groups_map.get(label_a)
        group_b = groups_map.get(label_b)
        if group_a and group_b:
            all_patterns.extend(_compare_groups_for_patterns(group_a, group_b, label_a, label_b))
    return all_patterns


# ─── Public API ─────────────────────────────────────────────────────────


def get_pattern_diagnosis_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict[str, Any]:
    data = _get_full_benchmark_data(country, city, period_days, enrich_from_trips)
    groups_map = data["groups_map"]

    all_patterns = _compute_all_patterns(groups_map)

    high = sum(1 for p in all_patterns if p["strength"] == STRENGTH_HIGH)
    medium = sum(1 for p in all_patterns if p["strength"] == STRENGTH_MEDIUM)
    low = sum(1 for p in all_patterns if p["strength"] == STRENGTH_LOW)

    available_dimensions = list(set(p["dimension"] for p in all_patterns))
    missing_dimensions = [d for d in DIMENSIONS if d not in available_dimensions]

    return {
        "total_patterns_detected": len(all_patterns),
        "high_strength_patterns": high,
        "medium_strength_patterns": medium,
        "low_strength_patterns": low,
        "dimensions_available": available_dimensions,
        "dimensions_missing": missing_dimensions,
        "available_metrics": data["available_metrics"],
        "missing_metrics": data["missing_metrics"],
        "data_source": data["source_info"]["data_source"],
        "source_warning": data["source_info"]["source_warning"],
        "diagnostic_mode": "deterministic",
        "period_days": period_days,
        "date_range": data["date_range"],
    }


def get_pattern_diagnosis_patterns(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
    dimension: Optional[str] = None,
    min_strength: Optional[str] = None,
) -> dict[str, Any]:
    data = _get_full_benchmark_data(country, city, period_days, enrich_from_trips)
    groups_map = data["groups_map"]

    all_patterns = _compute_all_patterns(groups_map)

    if dimension:
        all_patterns = [p for p in all_patterns if p["dimension"] == dimension]

    if min_strength:
        strength_order = {STRENGTH_HIGH: 3, STRENGTH_MEDIUM: 2, STRENGTH_LOW: 1}
        min_order = strength_order.get(min_strength.upper(), 0)
        all_patterns = [p for p in all_patterns if strength_order.get(p["strength"], 0) >= min_order]

    all_patterns.sort(key=lambda p: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(p["strength"], 3),
        -(p.get("gap_pct", 0)),
    ))

    return {
        "patterns": all_patterns,
        "total": len(all_patterns),
        "diagnostic_mode": "deterministic",
        "period_days": period_days,
        "date_range": data["date_range"],
        "data_source": data["source_info"]["data_source"],
        "source_warning": data["source_info"]["source_warning"],
    }


def get_pattern_diagnosis_group_profile(
    group_name: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict[str, Any]:
    if group_name not in LIFECYCLE_GROUPS:
        return {
            "group_name": group_name, "available": False,
            "reason": f"Grupo '{group_name}' no válido. Grupos válidos: {', '.join(LIFECYCLE_GROUPS)}.",
        }

    data = _get_full_benchmark_data(country, city, period_days, enrich_from_trips)
    groups_map = data["groups_map"]
    profile = groups_map.get(group_name)

    if not profile or profile.get("drivers_count", 0) == 0:
        return {
            "group_name": group_name, "drivers_count": 0,
            "available": False,
            "reason": f"Grupo '{group_name}' no encontrado en los datos del periodo.",
        }

    classified = data["classified"]
    drivers_in_group = classified.get(group_name, [])
    driver_keys = [d["driver_key"] for d in drivers_in_group]

    current_start = data["date_range"]["from"]
    current_end = data["date_range"]["to"]

    top_cities = _query_top_dimension_from_fact("city", driver_keys, current_start, current_end, 5)
    top_parks = _query_top_dimension_from_fact("park", driver_keys, current_start, current_end, 5)

    return {
        "group_name": group_name,
        "drivers_count": profile.get("drivers_count", 0),
        "total_trips": profile.get("total_trips", 0),
        "avg_trips_per_driver": profile.get("avg_trips_per_driver", 0),
        "avg_active_days": profile.get("avg_active_days", 0),
        "trips_per_active_day": profile.get("trips_per_active_day", 0),
        "consistency_score": profile.get("consistency_score", 0),
        "weekend_share": profile.get("weekend_share"),
        "avg_ticket": profile.get("avg_ticket"),
        "revenue_per_driver": profile.get("revenue_per_driver"),
        "peak_hour_share": profile.get("peak_hour_share"),
        "top_cities": top_cities,
        "top_parks": top_parks,
        "available_metrics": data["available_metrics"],
        "missing_metrics": data["missing_metrics"],
        "data_source": data["source_info"]["data_source"],
        "source_warning": data["source_info"]["source_warning"],
    }


def get_pattern_diagnosis_decline_signals(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict[str, Any]:
    data = _get_full_benchmark_data(country, city, period_days, enrich_from_trips)
    groups_map = data["groups_map"]

    signals = _build_decline_signals(groups_map)

    return {
        "signals": signals,
        "total": len(signals),
        "diagnostic_mode": "deterministic",
        "period_days": period_days,
        "date_range": data["date_range"],
        "data_source": data["source_info"]["data_source"],
        "source_warning": data["source_info"]["source_warning"],
        "note": (
            "Señales de deterioro operativo detectadas comparando STABLE vs DECLINING / AT_RISK. "
            "Las interpretaciones son diagnósticas, no recomendaciones."
        ),
    }
