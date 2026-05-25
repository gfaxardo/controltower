"""
Yango Loyalty / Oro Tracker Service

Tracks monthly Yango Loyalty program KPIs per city with official rules.
Official category rules (Performance = AD + Supply Hours + Nuevos/Reactivados):
  - ORO: 3 metas cumplidas
  - PLATA: 2 metas cumplidas
  - BRONCE: 0 o 1 meta cumplida

Calls: llamadas efectivas + conversion (nuevos o reactivados)
UFC: Lima Oro >= 40%, Plata >= 30%; Provincias Oro >= 25%, Plata >= 20%
Comms: Oro >= 100, Plata 65-99, min 30% educacion
Support: Oro >= 80, Plata 50-79
Social: Oro >= 70, Plata 40-69

NO recommendations. NO automation. NO AI. Deterministic scoring only.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 60000

LOYALTY_KPIS = [
    {"key": "ad", "label": "AD (Active Drivers)", "source": "auto", "group": "performance", "tooltip": "Active Drivers mensuales. Fuente: mv_driver_lifecycle_monthly_kpis."},
    {"key": "supply_hours", "label": "Supply Hours", "source": "manual", "group": "performance", "tooltip": "Horas de supply totales del mes. Carga manual."},
    {"key": "nuevos_reactivados", "label": "Nuevos + Reactivados", "source": "auto", "group": "performance", "tooltip": "Suma de activaciones + reactivaciones del mes. Fuente: mv_driver_lifecycle_monthly_kpis."},
    {"key": "calls_efectivas", "label": "Calls Efectivas", "source": "manual", "group": "calls", "tooltip": "Llamadas efectivas realizadas. Carga manual."},
    {"key": "conversion_nuevos", "label": "Conversion Nuevos", "source": "manual", "group": "calls", "tooltip": "Tasa de conversion de nuevos (%). Calls + conversion definen cumplimiento conjunto."},
    {"key": "conversion_reactivados", "label": "Conversion Reactivados", "source": "manual", "group": "calls", "tooltip": "Tasa de conversion de reactivados (%). Alternativa a conversion nuevos."},
    {"key": "ufc", "label": "UFC", "source": "manual", "group": "ufc", "tooltip": "Tasa UFC. Lima: Oro >= 40%, Plata >= 30%. Provincias: Oro >= 25%, Plata >= 20%."},
    {"key": "comms", "label": "Comms", "source": "manual", "group": "comms", "tooltip": "Comunicaciones enviadas. Oro >= 100, Plata 65-99. Minimo 30% educacion."},
    {"key": "support", "label": "Support", "source": "manual", "group": "support", "tooltip": "Tickets de soporte resueltos. Oro >= 80, Plata 50-79."},
    {"key": "social", "label": "Social", "source": "manual", "group": "social", "tooltip": "Interacciones en redes sociales. Oro >= 70, Plata 40-69."},
]

CATEGORY_THRESHOLDS = [
    {"category": "ORO", "label": "Oro", "threshold_pct": 90, "color": "#f59e0b", "icon": ""},
    {"category": "PLATA", "label": "Plata", "threshold_pct": 70, "color": "#9ca3af", "icon": ""},
    {"category": "BRONCE", "label": "Bronce", "threshold_pct": 0, "color": "#b45309", "icon": ""},
]

REACHABILITY_RULES = [
    {"state": "ON_TRACK", "label": "On Track", "color": "#22c55e", "max_gap_pct": 5, "description": "Dentro del objetivo. Mantener ritmo."},
    {"state": "SLIGHTLY_BEHIND", "label": "Slightly Behind", "color": "#3b82f6", "max_gap_pct": 15, "description": "Ligero retraso. Recuperable sin accion extraordinaria."},
    {"state": "RECOVERABLE", "label": "Recoverable", "color": "#eab308", "max_gap_pct": 30, "description": "Retraso moderado. Requiere aceleracion."},
    {"state": "HIGH_RISK", "label": "High Risk", "color": "#f97316", "max_gap_pct": 50, "description": "Riesgo alto. Meta comprometida sin accion fuerte."},
    {"state": "UNREACHABLE", "label": "Unreachable", "color": "#ef4444", "max_gap_pct": 100, "description": "Meta practicamente inalcanzable este mes."},
    {"state": "DATA_MISSING", "label": "Data Missing", "color": "#6b7280", "max_gap_pct": 999, "description": "Faltan datos para evaluar este KPI."},
]

# Official per-KPI threshold rules
def _get_kpi_oro_threshold(kpi_key: str, city: str) -> float:
    """Official Oro threshold per KPI. Returns attainment % needed."""
    city_lower = (city or "").lower()
    is_lima = city_lower in ("lima", "lima metropolitana")

    thresholds = {
        "ad": 90,
        "supply_hours": 90,
        "nuevos_reactivados": 90,
        "calls_efectivas": 90,
        "conversion_nuevos": 90,
        "conversion_reactivados": 90,
        "ufc": 40 if is_lima else 25,  # UFC % directa, no attainment
        "comms": 100,  # Valor absoluto: >= 100
        "support": 80,   # Valor absoluto: >= 80
        "social": 70,    # Valor absoluto: >= 70
    }
    return thresholds.get(kpi_key, 90)

def _get_kpi_plata_threshold(kpi_key: str, city: str) -> float:
    """Official Plata threshold per KPI."""
    city_lower = (city or "").lower()
    is_lima = city_lower in ("lima", "lima metropolitana")

    thresholds = {
        "ad": 70,
        "supply_hours": 70,
        "nuevos_reactivados": 70,
        "calls_efectivas": 70,
        "conversion_nuevos": 70,
        "conversion_reactivados": 70,
        "ufc": 30 if is_lima else 20,
        "comms": 65,
        "support": 50,
        "social": 40,
    }
    return thresholds.get(kpi_key, 70)

def _check_kpi_oro(kpi_key: str, real_val: float, target_val: float, city: str) -> bool:
    """Check if KPI meets Oro threshold using official rules."""
    if not target_val or target_val <= 0:
        return False
    if real_val is None:
        return False

    if kpi_key in ("comms", "support", "social"):
        return real_val >= _get_kpi_oro_threshold(kpi_key, city)
    if kpi_key == "ufc":
        return real_val >= _get_kpi_oro_threshold(kpi_key, city)
    attainment = (real_val / target_val) * 100
    return attainment >= _get_kpi_oro_threshold(kpi_key, city)

def _check_kpi_plata(kpi_key: str, real_val: float, target_val: float, city: str) -> bool:
    """Check if KPI meets Plata threshold."""
    if not target_val or target_val <= 0:
        return False
    if real_val is None:
        return False

    if kpi_key in ("comms", "support", "social"):
        return real_val >= _get_kpi_plata_threshold(kpi_key, city)
    if kpi_key == "ufc":
        return real_val >= _get_kpi_plata_threshold(kpi_key, city)
    attainment = (real_val / target_val) * 100
    return attainment >= _get_kpi_plata_threshold(kpi_key, city)

def _determine_city_category(city_kpis: list[dict]) -> dict:
    """Determine category per official rules: 3 = Oro, 2 = Plata, 0-1 = Bronce."""
    oro_count = sum(1 for k in city_kpis if k.get("meets_oro"))
    plata_count = sum(1 for k in city_kpis if k.get("meets_plata"))

    if oro_count >= 3:
        return {"category": "ORO", "label": "Oro", "color": "#f59e0b", "oro_kpis": oro_count, "plata_kpis": plata_count}
    if plata_count >= 2:
        return {"category": "PLATA", "label": "Plata", "color": "#9ca3af", "oro_kpis": oro_count, "plata_kpis": plata_count}
    return {"category": "BRONCE", "label": "Bronce", "color": "#b45309", "oro_kpis": oro_count, "plata_kpis": plata_count}


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

def _get_current_month() -> str:
    return date.today().strftime("%Y-%m")

def _get_day_of_month() -> int:
    return date.today().day

def _days_in_month() -> int:
    today = date.today()
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    last_day = next_month - __import__("datetime").timedelta(days=1)
    return last_day.day

def _get_available_cities() -> list[str]:
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute("SELECT DISTINCT city FROM ops.v_dim_park_resolved WHERE city IS NOT NULL ORDER BY city")
            return [r["city"] for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.warning("Failed to get cities: %s", e)
        return []

def _get_auto_kpi_value(kpi_key: str, city: str, month: str) -> Optional[float]:
    kpi_def = next((k for k in LOYALTY_KPIS if k["key"] == kpi_key), None)
    if not kpi_def or kpi_def["source"] != "auto":
        return None
    try:
        with get_db() as conn:
            cur = _cursor(conn, 15000)
            if kpi_key == "ad":
                cur.execute("SELECT COALESCE(SUM(active_drivers), 0) AS val FROM ops.mv_driver_lifecycle_monthly_kpis WHERE TO_CHAR(month_start, 'YYYY-MM') = %(month)s", {"month": month})
                row = cur.fetchone()
                return _safe_num(row["val"]) if row else 0.0
            if kpi_key == "nuevos_reactivados":
                cur.execute("SELECT COALESCE(SUM(activations), 0) + COALESCE(SUM(reactivated), 0) AS val FROM ops.mv_driver_lifecycle_monthly_kpis WHERE TO_CHAR(month_start, 'YYYY-MM') = %(month)s", {"month": month})
                row = cur.fetchone()
                if row and row["val"] is not None:
                    return _safe_num(row["val"])
                # Fallback: try without reactivated column
                cur.execute("SELECT COALESCE(SUM(activations), 0) AS val FROM ops.mv_driver_lifecycle_monthly_kpis WHERE TO_CHAR(month_start, 'YYYY-MM') = %(month)s", {"month": month})
                row = cur.fetchone()
                return _safe_num(row["val"]) if row else 0.0
            return None
    except Exception as e:
        logger.warning("Failed auto KPI %s: %s", kpi_key, e)
        return None


# Pre-fetch cache for auto KPIs (shared across cities)
_auto_kpi_cache: dict = {}

def _get_auto_kpi_cached(kpi_key: str, month: str) -> Optional[float]:
    cache_key = f"{kpi_key}:{month}"
    if cache_key in _auto_kpi_cache:
        return _auto_kpi_cache[cache_key]
    val = _get_auto_kpi_value(kpi_key, "", month)
    _auto_kpi_cache[cache_key] = val
    return val

def _get_manual_kpi_value(kpi_key: str, city: str, month: str) -> Optional[float]:
    try:
        with get_db() as conn:
            cur = _cursor(conn, 10000)
            cur.execute("SELECT kpi_value FROM ops.yango_loyalty_kpi_manual WHERE kpi_key = %(key)s AND (city = %(city)s OR (city IS NULL AND %(city)s IS NULL)) AND month_key = %(month)s ORDER BY updated_at DESC LIMIT 1", {"key": kpi_key, "city": city, "month": month})
            row = cur.fetchone()
            return _safe_num(row["kpi_value"]) if row else None
    except Exception:
        return None


def _prefetch_all_data(month: str, cities: list[str]) -> dict:
    """Prefetch all auto KPIs, manual KPIs, and targets in 3 DB queries total."""
    data = {"auto": {}, "manuals": {}, "targets": {}}

    # 1. Auto KPIs (single query)
    try:
        with get_db() as conn:
            cur = _cursor(conn, 15000)
            cur.execute("SELECT COALESCE(SUM(active_drivers), 0) AS ad, COALESCE(SUM(activations), 0) AS n_r FROM ops.mv_driver_lifecycle_monthly_kpis WHERE TO_CHAR(month_start, 'YYYY-MM') = %(month)s", {"month": month})
            row = cur.fetchone()
            if row:
                data["auto"]["ad"] = _safe_num(row["ad"])
                data["auto"]["nuevos_reactivados"] = _safe_num(row["n_r"])
    except Exception as e:
        logger.warning("Prefetch auto KPIs failed: %s", e)

    # 2. Manual KPIs across all cities (single query)
    try:
        with get_db() as conn:
            cur = _cursor(conn, 15000)
            cur.execute("SELECT kpi_key, city, kpi_value FROM ops.yango_loyalty_kpi_manual WHERE month_key = %(month)s", {"month": month})
            for row in (cur.fetchall() or []):
                c = row["city"] or ""
                if c not in data["manuals"]:
                    data["manuals"][c] = {}
                k = row["kpi_key"]
                if k not in data["manuals"][c]:
                    data["manuals"][c][k] = _safe_num(row["kpi_value"])
    except Exception:
        pass

    # 3. Targets across all cities (single query)
    try:
        with get_db() as conn:
            cur = _cursor(conn, 15000)
            cur.execute("SELECT kpi_key, city, target_value FROM ops.yango_loyalty_targets WHERE month_key = %(month)s", {"month": month})
            for row in (cur.fetchall() or []):
                c = row["city"] or ""
                if c not in data["targets"]:
                    data["targets"][c] = {}
                data["targets"][c][row["kpi_key"]] = _safe_num(row["target_value"])
    except Exception:
        pass

    return data

def get_loyalty_rules() -> dict:
    """Return official loyalty rules for frontend tooltips."""
    return {
        "category_rules": {
            "ORO": "3 o mas KPIs en nivel Oro",
            "PLATA": "2 KPIs en nivel Plata o superior",
            "BRONCE": "0 o 1 KPI en nivel Plata",
        },
        "performance_group": "AD + Supply Hours + Nuevos/Reactivados. 3 metas = Oro, 2 = Plata, 0-1 = Bronce.",
        "calls_group": "Calls efectivas + Conversion (nuevos o reactivados). Se evalua en conjunto.",
        "kpi_thresholds": {
            "ufc": {"lima_oro": 40, "lima_plata": 30, "provincia_oro": 25, "provincia_plata": 20, "unit": "%"},
            "comms": {"oro": 100, "plata": 65, "unit": "mensajes", "extra": "Minimo 30% educacion"},
            "support": {"oro": 80, "plata": 50, "unit": "tickets"},
            "social": {"oro": 70, "plata": 40, "unit": "interacciones"},
        },
    }


def get_loyalty_summary() -> dict[str, Any]:
    month = _get_current_month()
    day_of_month = _get_day_of_month()
    total_days = _days_in_month()
    expected_progress = round(min(day_of_month / total_days, 1.0) * 100, 1)

    cities = _get_available_cities()

    # Pre-fetch ALL data in 3 queries (not per-city)
    prefetch = _prefetch_all_data(month, cities)

    kpi_results = []
    city_categories = {}

    for kpi_def in LOYALTY_KPIS:
        kpi_data = {
            "kpi_key": kpi_def["key"], "kpi_label": kpi_def["label"],
            "source": kpi_def["source"], "group": kpi_def.get("group", "other"),
            "tooltip": kpi_def.get("tooltip", ""),
            "values": [], "has_data": False,
            "has_manual_pending": kpi_def["source"] == "manual",
            "freshness": None,
        }

        for city in cities:
            real_val = None
            if kpi_def["source"] == "auto":
                real_val = prefetch["auto"].get(kpi_def["key"])
            else:
                city_manuals = prefetch["manuals"].get(city, {})
                real_val = city_manuals.get(kpi_def["key"])

            city_targets = prefetch["targets"].get(city, {})
            target_val = city_targets.get(kpi_def["key"])

            if real_val is not None:
                kpi_data["has_data"] = True
            if kpi_def["source"] == "manual" and real_val is not None:
                kpi_data["has_manual_pending"] = False

            gap_abs = round((target_val or 0) - (real_val or 0), 1)
            gap_pct = round((gap_abs / max(target_val or 1, 1)) * 100, 1)
            attainment_pct = round(((real_val or 0) / max(target_val or 1, 1)) * 100, 1) if target_val else None
            meets_oro = _check_kpi_oro(kpi_def["key"], real_val, target_val, city) if target_val else False
            meets_plata = _check_kpi_plata(kpi_def["key"], real_val, target_val, city) if target_val else False

            city_data = {
                "city": city, "target": round(target_val, 1) if target_val else None,
                "real": round(real_val, 1) if real_val else None,
                "expected_progress": round(expected_progress, 1),
                "gap_abs": gap_abs, "gap_pct": gap_pct,
                "attainment_pct": attainment_pct,
                "reachability": _determine_reachability(gap_pct, kpi_data["has_data"]),
                "meets_oro": meets_oro, "meets_plata": meets_plata,
                "freshness": None, "source": kpi_def["source"],
            }
            kpi_data["values"].append(city_data)

        kpi_results.append(kpi_data)

    # Per-city categories using official rules
    for city in cities:
        city_kpis = []
        for kpi in kpi_results:
            cv = next((v for v in kpi["values"] if v["city"] == city), None)
            if cv:
                city_kpis.append({**cv, "kpi_key": kpi["kpi_key"], "group": kpi["group"]})
        city_categories[city] = _determine_city_category(city_kpis)

    data_complete = all(kpi["has_data"] for kpi in kpi_results)
    manual_pending = sum(1 for kpi in kpi_results if kpi["has_manual_pending"])
    has_any_targets = any(
        v["target"] is not None
        for kpi in kpi_results for v in kpi["values"]
    )

    return {
        "month": month, "day_of_month": day_of_month, "total_days": total_days,
        "expected_progress_pct": expected_progress,
        "cities": cities,
        "data_complete": data_complete,
        "manual_kpis_pending": manual_pending,
        "has_any_targets": has_any_targets,
        "city_categories": city_categories,
        "rules": get_loyalty_rules(),
        "kpis": kpi_results,
    }


def get_loyalty_reachability(city: Optional[str] = None) -> dict[str, Any]:
    month = _get_current_month()
    cities = [city] if city else _get_available_cities()
    prefetch = _prefetch_all_data(month, cities)
    rows = []

    for c in cities:
        manuals = prefetch["manuals"].get(c, {})
        targets = prefetch["targets"].get(c, {})
        city_row = {"city": c, "kpis": {}}
        for kpi_def in LOYALTY_KPIS:
            real_val = None
            if kpi_def["source"] == "auto":
                real_val = prefetch["auto"].get(kpi_def["key"])
            else:
                real_val = manuals.get(kpi_def["key"])
            target_val = targets.get(kpi_def["key"])
            gap_pct = round(((target_val or 0) - (real_val or 0)) / max(target_val or 1, 1) * 100, 1)
            has_data = real_val is not None
            reach = _determine_reachability(gap_pct, has_data)
            city_row["kpis"][kpi_def["key"]] = {
                "reachability": reach["state"], "label": reach["label"], "color": reach["color"],
                "gap_pct": gap_pct, "has_data": has_data,
                "target": target_val, "real": real_val,
            }
        rows.append(city_row)
    return {"month": month, "reachability": rows}


def get_loyalty_kpis(city: Optional[str] = None) -> dict[str, Any]:
    month = _get_current_month()
    day_of_month = _get_day_of_month()
    total_days = _days_in_month()
    expected_progress = round(min(day_of_month / total_days, 1.0) * 100, 1)
    cities = [city] if city else _get_available_cities()
    prefetch = _prefetch_all_data(month, cities)
    rows = []

    for c in cities:
        manuals = prefetch["manuals"].get(c, {})
        targets = prefetch["targets"].get(c, {})
        for kpi_def in LOYALTY_KPIS:
            real_val = None
            if kpi_def["source"] == "auto":
                real_val = prefetch["auto"].get(kpi_def["key"])
            else:
                real_val = manuals.get(kpi_def["key"])

            target_val = targets.get(kpi_def["key"])
            gap_pct = round(((target_val or 0) - (real_val or 0)) / max(target_val or 1, 1) * 100, 1)
            has_data = real_val is not None
            reach = _determine_reachability(gap_pct, has_data)

            city_row["kpis"][kpi_def["key"]] = {
                "reachability": reach["state"],
                "label": reach["label"],
                "color": reach["color"],
                "gap_pct": gap_pct,
                "has_data": has_data,
                "target": target_val,
                "real": real_val,
            }
        rows.append(city_row)

    return {"month": month, "reachability": rows}


def get_loyalty_kpis(city: Optional[str] = None) -> dict[str, Any]:
    month = _get_current_month()
    day_of_month = _get_day_of_month()
    total_days = _days_in_month()
    expected_progress = round(min(day_of_month / total_days, 1.0) * 100, 1)
    cities = [city] if city else _get_available_cities()
    prefetch = _prefetch_all_data(month, cities)
    rows = []

    for c in cities:
        manuals = prefetch["manuals"].get(c, {})
        targets = prefetch["targets"].get(c, {})
        for kpi_def in LOYALTY_KPIS:
            real_val = None
            if kpi_def["source"] == "auto":
                real_val = prefetch["auto"].get(kpi_def["key"])
            else:
                real_val = manuals.get(kpi_def["key"])
            target_val = targets.get(kpi_def["key"])
            gap_abs = round((target_val or 0) - (real_val or 0), 1)
            gap_pct = round((gap_abs / max(target_val or 1, 1)) * 100, 1)
            attainment_pct = round(((real_val or 0) / max(target_val or 1, 1)) * 100, 1) if target_val else None
            meets_oro = _check_kpi_oro(kpi_def["key"], real_val, target_val, c) if target_val else False
            meets_plata = _check_kpi_plata(kpi_def["key"], real_val, target_val, c) if target_val else False

            rows.append({
                "city": c, "kpi_key": kpi_def["key"], "kpi_label": kpi_def["label"],
                "source": kpi_def["source"], "group": kpi_def.get("group", "other"),
                "tooltip": kpi_def.get("tooltip", ""),
                "target": round(target_val, 1) if target_val else None,
                "real": round(real_val, 1) if real_val else None,
                "expected_progress": round(expected_progress, 1),
                "gap_abs": gap_abs, "gap_pct": gap_pct,
                "attainment_pct": attainment_pct,
                "reachability": _determine_reachability(gap_pct, real_val is not None),
                "meets_oro": meets_oro, "meets_plata": meets_plata,
                "freshness": None,
            })

    return {"month": month, "expected_progress_pct": expected_progress, "kpis": rows}


def _determine_reachability(gap_pct: float, data_complete: bool) -> dict:
    if not data_complete:
        return REACHABILITY_RULES[-1]
    for rule in REACHABILITY_RULES[:-1]:
        if gap_pct <= rule["max_gap_pct"]:
            return rule
    return REACHABILITY_RULES[-2]


def upsert_manual_kpi(kpi_key: str, city: str, month: str, kpi_value: float) -> dict:
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute("INSERT INTO ops.yango_loyalty_kpi_manual (kpi_key, city, month_key, kpi_value, updated_at) VALUES (%(key)s, %(city)s, %(month)s, %(val)s, NOW()) ON CONFLICT (kpi_key, city, month_key) DO UPDATE SET kpi_value = EXCLUDED.kpi_value, updated_at = NOW()", {"key": kpi_key, "city": city, "month": month, "val": kpi_value})
            conn.commit()
        return {"success": True, "kpi_key": kpi_key, "city": city, "month": month, "value": kpi_value}
    except Exception as e:
        logger.exception("Failed upsert manual KPI: %s", e)
        return {"success": False, "error": str(e)}


def upsert_target(kpi_key: str, city: str, month: str, target_value: float) -> dict:
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute("INSERT INTO ops.yango_loyalty_targets (kpi_key, city, month_key, target_value, updated_at) VALUES (%(key)s, %(city)s, %(month)s, %(val)s, NOW()) ON CONFLICT (kpi_key, city, month_key) DO UPDATE SET target_value = EXCLUDED.target_value, updated_at = NOW()", {"key": kpi_key, "city": city, "month": month, "val": target_value})
            conn.commit()
        return {"success": True, "kpi_key": kpi_key, "city": city, "month": month, "target": target_value}
    except Exception as e:
        logger.exception("Failed upsert target: %s", e)
        return {"success": False, "error": str(e)}


def upsert_batch_targets(city: str, month: str, targets: dict[str, float]) -> dict:
    """Batch upsert multiple KPI targets for a city/month."""
    results = []
    for kpi_key, val in targets.items():
        r = upsert_target(kpi_key, city, month, val)
        results.append(r)
    return {"success": True, "city": city, "month": month, "results": results}


def ensure_loyalty_tables() -> dict:
    results = {}
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute("CREATE TABLE IF NOT EXISTS ops.yango_loyalty_targets (id SERIAL PRIMARY KEY, kpi_key VARCHAR(50) NOT NULL, city VARCHAR(100), month_key VARCHAR(7) NOT NULL, target_value DOUBLE PRECISION NOT NULL, updated_at TIMESTAMP DEFAULT NOW(), UNIQUE(kpi_key, city, month_key))")
            cur.execute("CREATE TABLE IF NOT EXISTS ops.yango_loyalty_kpi_manual (id SERIAL PRIMARY KEY, kpi_key VARCHAR(50) NOT NULL, city VARCHAR(100), month_key VARCHAR(7) NOT NULL, kpi_value DOUBLE PRECISION NOT NULL, updated_at TIMESTAMP DEFAULT NOW(), UNIQUE(kpi_key, city, month_key))")
            conn.commit()
            results["status"] = "ok"
            results["tables"] = ["ops.yango_loyalty_targets", "ops.yango_loyalty_kpi_manual"]
    except Exception as e:
        logger.exception("Failed create loyalty tables: %s", e)
        results["status"] = "error"
        results["error"] = str(e)
    return results
