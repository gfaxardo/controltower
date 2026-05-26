"""
Yango Loyalty Reachability Service — Fase 3A + 3A.1 Operating Layer.

Fase 3A:
  - Plan vs Real de KPIs Yango Oro/Plata/Bronce
  - Reachability mensual (ON_TRACK → DATA_MISSING)

Fase 3A.1 — Operating Layer:
  - compute_loyalty_data_completeness()
  - compute_kpi_freshness()
  - get_daily_snapshot()
  - get_historical_monthly()
  - copy_goals_from_month()
  - Validaciones de input
  - Bulk input con validación

NO genera recomendaciones. NO automatiza acciones.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from calendar import monthrange

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

CITIES = ["Lima", "Trujillo", "Arequipa"]
VALID_CITIES = set(CITIES)
VALID_KPI_CODES = {"AD", "SH", "N_R", "CALLS", "CONV_NEW", "CONV_REA", "UFC", "COMMS", "SUPPORT", "SOCIAL"}
FRESHNESS_WARNING_HOURS = 48
FRESHNESS_STALE_HOURS = 96

COMPLETENESS_STATES = {
    "AVAILABLE": "available_now — automatizado",
    "COMPLETE": "manual_input con real_value presente",
    "MANUAL_PENDING": "manual_input sin real_value ni target",
    "PARTIAL": "manual_input con target pero sin real_value",
    "STALE": "manual_input con real_value pero > 48h sin update",
    "MISSING": "sin target ni real_value",
}

FRESHNESS_STATES = {
    "FRESH": "actualizado hace < 48h",
    "WARNING": "actualizado hace 48–96h",
    "STALE": "actualizado hace > 96h",
    "MISSING": "sin datos",
}

KPIS_AVAILABLE_SQL = {
    "AD": {
        "query": """
            SELECT COALESCE(SUM(active_drivers), 0)::numeric AS val
            FROM ops.real_business_slice_month_fact
            WHERE period = %(month)s
              AND LOWER(TRIM(country::text)) = LOWER(TRIM(%(country)s))
              AND LOWER(TRIM(city::text)) = LOWER(TRIM(%(city)s))
        """,
        "aggregation": "sum",
    },
    "N_R": {
        "query": """
            WITH weekly AS (
                SELECT SUM(activations) AS act, SUM(reactivated) AS rea
                FROM ops.mv_driver_lifecycle_weekly_kpis
                WHERE week_start >= %(month_start)s::date
                  AND week_start <  (%(month_start)s::date + INTERVAL '1 month')
            )
            SELECT COALESCE(act, 0) + COALESCE(rea, 0) AS val FROM weekly
        """,
        "aggregation": "sum",
    },
}

# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _day_of_month() -> int:
    return datetime.now(timezone.utc).day

def _days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]

def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _prev_month(month_str: str) -> str:
    year, mon = int(month_str.split("-")[0]), int(month_str.split("-")[1])
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"

def _get_registry(conn) -> list[dict]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM ops.yango_loyalty_kpi_registry ORDER BY kpi_code")
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()

def _get_goals(conn, month: str, country: str, city: Optional[str] = None) -> list[dict]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if city:
            cur.execute(
                """SELECT * FROM ops.yango_loyalty_monthly_goals
                   WHERE month = %s AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
                     AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))""",
                (month, country, city),
            )
        else:
            cur.execute(
                """SELECT * FROM ops.yango_loyalty_monthly_goals
                   WHERE month = %s AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))""",
                (month, country),
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()

def _get_manual_results(conn, month: str, country: str, city: Optional[str] = None) -> list[dict]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if city:
            cur.execute(
                """SELECT * FROM ops.yango_loyalty_manual_results
                   WHERE month = %s AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
                     AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))""",
                (month, country, city),
            )
        else:
            cur.execute(
                """SELECT * FROM ops.yango_loyalty_manual_results
                   WHERE month = %s AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))""",
                (month, country),
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()

def _fetch_available_kpi(conn, kpi_code: str, month: str, country: str, city: str) -> Optional[float]:
    spec = KPIS_AVAILABLE_SQL.get(kpi_code)
    if not spec:
        return None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        year, mon = month.split("-")
        cur.execute(
            spec["query"],
            {
                "month": month,
                "month_start": f"{year}-{mon}-01",
                "country": country,
                "city": city,
            },
        )
        row = cur.fetchone()
        cur.close()
        if row and row.get("val") is not None:
            return float(row["val"])
        return None
    except Exception:
        logger.debug("No se pudo obtener %s para %s/%s", kpi_code, city, month, exc_info=True)
        return None

def _compute_reachability(
    real: Optional[float],
    target: Optional[float],
    expected_pct: float,
    total_days: int,
    today: int,
) -> dict:
    if real is None or target is None or target == 0:
        return {
            "real_value": real,
            "target_value": target,
            "gap_abs": None,
            "gap_pct": None,
            "expected_progress_pct": round(expected_pct * 100, 1),
            "expected_value_today": round(target * expected_pct, 2) if target else None,
            "velocity_required": None,
            "reachability_status": "DATA_MISSING",
            "projected_end_value": None,
        }
    expected_value = target * expected_pct
    gap_abs = round(real - expected_value, 2)
    gap_pct = round((gap_abs / target) * 100, 2) if target else None
    remaining_days = total_days - today
    remaining_target = target - real
    velocity_required = round(remaining_target / remaining_days, 2) if remaining_days > 0 else None
    projected = round(real + (velocity_required * remaining_days if velocity_required else 0), 2)
    if real >= expected_value:
        status = "ON_TRACK"
    elif gap_pct is not None and gap_pct >= -10:
        status = "SLIGHTLY_BEHIND"
    elif gap_pct is not None and gap_pct >= -25:
        status = "RECOVERABLE"
    elif projected >= target and gap_pct is not None and gap_pct < -25:
        status = "HIGH_RISK"
    elif projected < target:
        status = "UNREACHABLE"
    else:
        status = "HIGH_RISK"
    return {
        "real_value": real,
        "target_value": target,
        "gap_abs": gap_abs,
        "gap_pct": gap_pct,
        "expected_progress_pct": round(expected_pct * 100, 1),
        "expected_value_today": round(expected_value, 2),
        "velocity_required": velocity_required,
        "reachability_status": status,
        "projected_end_value": projected,
    }

def _category_from_pct(pct: Optional[float], thresholds: dict, higher_is_better: bool) -> str:
    if pct is None:
        return "DATA_MISSING"
    g = thresholds.get("gold", 95)
    s = thresholds.get("silver", 85)
    b = thresholds.get("bronze", 70)
    if higher_is_better:
        if pct >= g: return "ORO"
        if pct >= s: return "PLATA"
        if pct >= b: return "BRONCE"
    else:
        if pct <= (100 - g): return "ORO"
        if pct <= (100 - s): return "PLATA"
        if pct <= (100 - b): return "BRONCE"
    return "SIN_CATEGORIA"

def _build_kpi_row(
    registry_entry: dict,
    goal: Optional[dict],
    manual: Optional[dict],
    real_val: Optional[float],
    month: str, country: str, city: str,
    today: int, total_days: int,
) -> dict:
    kpi_code = registry_entry["kpi_code"]
    source_type = registry_entry["source_type"]
    higher_is_better = registry_entry["higher_is_better"]
    gold_th = registry_entry.get("gold_threshold") or 95
    silver_th = registry_entry.get("silver_threshold") or 85
    bronze_th = registry_entry.get("bronze_threshold") or 70
    target_value = float(goal["target_value"]) if goal and goal.get("target_value") is not None else None
    resolved_real = real_val
    if resolved_real is None and manual and manual.get("real_value") is not None:
        resolved_real = float(manual["real_value"])
    expected_pct = today / total_days
    reach = _compute_reachability(resolved_real, target_value, expected_pct, total_days, today)
    attainment_pct = round((resolved_real / target_value) * 100, 2) if resolved_real is not None and target_value else None
    current_cat = _category_from_pct(attainment_pct, {"gold": gold_th, "silver": silver_th, "bronze": bronze_th}, higher_is_better)
    projected_attainment = (
        round((reach["projected_end_value"] / target_value) * 100, 2)
        if reach["projected_end_value"] is not None and target_value else None
    )
    projected_cat = _category_from_pct(projected_attainment, {"gold": gold_th, "silver": silver_th, "bronze": bronze_th}, higher_is_better)
    # freshness
    freshness = None
    if manual and manual.get("updated_at"):
        freshness = _compute_freshness_from_updated_at(manual["updated_at"])
    return {
        "kpi_code": kpi_code,
        "kpi_name": registry_entry["kpi_name"],
        "category": registry_entry["category"],
        "source_type": source_type,
        "unit": registry_entry["unit"],
        "higher_is_better": higher_is_better,
        "target_value": target_value,
        "real_value": resolved_real,
        "attainment_pct": attainment_pct,
        "current_category": current_cat,
        "projected_category": projected_cat,
        "gap_abs": reach["gap_abs"],
        "gap_pct": reach["gap_pct"],
        "expected_progress_pct": reach["expected_progress_pct"],
        "expected_value_today": reach["expected_value_today"],
        "velocity_required": reach["velocity_required"],
        "reachability_status": reach["reachability_status"],
        "projected_end_value": reach["projected_end_value"],
        "gold_threshold": gold_th,
        "silver_threshold": silver_th,
        "bronze_threshold": bronze_th,
        "freshness_status": freshness["status"] if freshness else "MISSING",
        "freshness_hours": freshness["hours"] if freshness else None,
        "updated_at": str(manual["updated_at"]) if manual and manual.get("updated_at") else None,
        "updated_by": manual.get("updated_by") if manual else None,
    }

def _compute_freshness_from_updated_at(updated_at_val) -> dict:
    try:
        if isinstance(updated_at_val, str):
            utc_dt = datetime.fromisoformat(updated_at_val.replace("Z", "+00:00"))
        elif isinstance(updated_at_val, datetime):
            utc_dt = updated_at_val
        else:
            return {"status": "MISSING", "hours": None}
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        delta = _now_utc() - utc_dt
        hours = round(delta.total_seconds() / 3600, 1)
        if hours < FRESHNESS_WARNING_HOURS:
            return {"status": "FRESH", "hours": hours}
        elif hours < FRESHNESS_STALE_HOURS:
            return {"status": "WARNING", "hours": hours}
        else:
            return {"status": "STALE", "hours": hours}
    except Exception:
        return {"status": "MISSING", "hours": None}

# ═══════════════════════════════════════════════
# 3A.1 — Data Completeness
# ═══════════════════════════════════════════════

def compute_loyalty_data_completeness(
    month: Optional[str] = None,
    country: str = "PE",
    city: Optional[str] = None,
) -> dict:
    month = month or _current_month()
    with get_db() as conn:
        registry = _get_registry(conn)
        goals = _get_goals(conn, month, country, city)
        manual_results = _get_manual_results(conn, month, country, city)
    goals_map = {(g["city"], g["kpi_code"]): g for g in goals}
    manual_map = {(m["city"], m["kpi_code"]): m for m in manual_results}
    cities_to_use = [city] if city else CITIES
    kpi_statuses = []
    for c in cities_to_use:
        for reg in registry:
            goal = goals_map.get((c, reg["kpi_code"]))
            manual = manual_map.get((c, reg["kpi_code"]))
            source = reg["source_type"]
            has_target = goal is not None and goal.get("target_value") is not None
            has_real = manual is not None and manual.get("real_value") is not None
            freshness = None
            if manual and manual.get("updated_at"):
                freshness = _compute_freshness_from_updated_at(manual["updated_at"])
            if source == "available_now":
                state = "AVAILABLE"
            elif has_real and freshness and freshness["status"] == "STALE":
                state = "STALE"
            elif has_real and has_target:
                state = "COMPLETE"
            elif has_target and not has_real:
                state = "PARTIAL"
            elif not has_target and not has_real:
                state = "MANUAL_PENDING"
            else:
                state = "COMPLETE" if has_real else "MANUAL_PENDING"
            kpi_statuses.append({
                "city": c,
                "kpi_code": reg["kpi_code"],
                "kpi_name": reg["kpi_name"],
                "source_type": source,
                "completeness_state": state,
                "has_target": has_target,
                "has_real": has_real,
                "freshness_status": freshness["status"] if freshness else "MISSING",
                "freshness_hours": freshness["hours"] if freshness else None,
                "updated_at": str(manual["updated_at"]) if manual and manual.get("updated_at") else None,
            })
    city_completeness = {}
    for c in cities_to_use:
        c_items = [k for k in kpi_statuses if k["city"] == c]
        complete_count = sum(1 for k in c_items if k["completeness_state"] in ("AVAILABLE", "COMPLETE"))
        total = len(c_items)
        city_completeness[c] = {
            "total_kpis": total,
            "complete_count": complete_count,
            "completeness_pct": round((complete_count / total) * 100, 1) if total else 0,
            "states": {s: sum(1 for k in c_items if k["completeness_state"] == s) for s in ("AVAILABLE", "COMPLETE", "PARTIAL", "MANUAL_PENDING", "STALE")},
        }
    all_items = kpi_statuses
    global_complete = sum(1 for k in all_items if k["completeness_state"] in ("AVAILABLE", "COMPLETE"))
    total_global = len(all_items)
    return {
        "month": month,
        "country": country,
        "global_completeness_pct": round((global_complete / total_global) * 100, 1) if total_global else 0,
        "global_complete_count": global_complete,
        "global_total": total_global,
        "global_states": {s: sum(1 for k in all_items if k["completeness_state"] == s) for s in ("AVAILABLE", "COMPLETE", "PARTIAL", "MANUAL_PENDING", "STALE")},
        "city_completeness": city_completeness,
        "kpi_statuses": kpi_statuses,
    }


# ═══════════════════════════════════════════════
# 3A.1 — KPI Freshness
# ═══════════════════════════════════════════════

def compute_kpi_freshness(
    month: Optional[str] = None,
    country: str = "PE",
    city: Optional[str] = None,
) -> dict:
    month = month or _current_month()
    with get_db() as conn:
        manual_results = _get_manual_results(conn, month, country, city)
    items = []
    for m in manual_results:
        freshness = _compute_freshness_from_updated_at(m.get("updated_at")) if m.get("updated_at") else {"status": "MISSING", "hours": None}
        items.append({
            "city": m["city"],
            "kpi_code": m["kpi_code"],
            "real_value": float(m["real_value"]) if m.get("real_value") is not None else None,
            "freshness_status": freshness["status"],
            "freshness_hours": freshness["hours"],
            "updated_at": str(m["updated_at"]) if m.get("updated_at") else None,
            "updated_by": m.get("updated_by"),
        })
    dist = {"FRESH": 0, "WARNING": 0, "STALE": 0, "MISSING": 0}
    for i in items:
        s = i["freshness_status"]
        if s in dist:
            dist[s] += 1
    return {
        "month": month,
        "country": country,
        "freshness_distribution": dist,
        "total_manual_kpis": len(items),
        "warning_count": dist.get("WARNING", 0) + dist.get("STALE", 0),
        "items": items,
    }


# ═══════════════════════════════════════════════
# 3A.1 — Daily Snapshot
# ═══════════════════════════════════════════════

def get_daily_snapshot(
    month: Optional[str] = None,
    country: str = "PE",
    city: Optional[str] = None,
) -> dict:
    month = month or _current_month()
    year, mon_num = int(month.split("-")[0]), int(month.split("-")[1])
    today = _day_of_month()
    total_days = _days_in_month(year, mon_num)
    expected_pct = today / total_days
    summary = get_summary(month=month, country=country, city=city)
    kpis = summary["kpis"]
    snapshot_items = []
    for k in kpis:
        daily_delta = None
        if k["real_value"] is not None and k["expected_value_today"] is not None and today > 0:
            daily_delta = round(k["real_value"] - (k["expected_value_today"] * ((today - 1) / today)) if today > 1 else 0, 2)
        color = "green"
        if k["reachability_status"] in ("UNREACHABLE", "HIGH_RISK"):
            color = "red"
        elif k["reachability_status"] in ("RECOVERABLE", "SLIGHTLY_BEHIND"):
            color = "amber"
        elif k["reachability_status"] == "DATA_MISSING":
            color = "gray"
        snapshot_items.append({
            "city": k["city"],
            "kpi_code": k["kpi_code"],
            "kpi_name": k["kpi_name"],
            "real_value": k["real_value"],
            "target_value": k["target_value"],
            "expected_value_today": k["expected_value_today"],
            "gap_abs": k["gap_abs"],
            "gap_pct": k["gap_pct"],
            "expected_progress_pct": k["expected_progress_pct"],
            "attainment_pct": k["attainment_pct"],
            "daily_delta": daily_delta,
            "reachability_status": k["reachability_status"],
            "semaphore_color": color,
        })
    on_track = sum(1 for s in snapshot_items if s["reachability_status"] == "ON_TRACK")
    at_risk = sum(1 for s in snapshot_items if s["reachability_status"] in ("HIGH_RISK", "UNREACHABLE"))
    ahead = sum(1 for s in snapshot_items if s["gap_abs"] is not None and s["gap_abs"] > 0)
    behind = sum(1 for s in snapshot_items if s["gap_abs"] is not None and s["gap_abs"] < 0)
    return {
        "month": month,
        "today_day": today,
        "total_days": total_days,
        "expected_progress_pct": round(expected_pct * 100, 1),
        "on_track_count": on_track,
        "at_risk_count": at_risk,
        "ahead_count": ahead,
        "behind_count": behind,
        "items": snapshot_items,
    }


# ═══════════════════════════════════════════════
# 3A.1 — Historical Monthly Tracking
# ═══════════════════════════════════════════════

def get_historical_monthly(
    country: str = "PE",
    city: Optional[str] = None,
    months_back: int = 6,
    kpi_code: Optional[str] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    months = []
    for i in range(months_back):
        y = now.year if now.month - i > 0 else now.year - 1
        m = now.month - i if now.month - i > 0 else now.month - i + 12
        months.append(f"{y}-{m:02d}")
    historical = []
    for month in months:
        try:
            summary = get_summary(month=month, country=country, city=city)
            kpis = summary["kpis"]
            if kpi_code:
                kpis = [k for k in kpis if k["kpi_code"] == kpi_code]
            for k in kpis:
                historical.append({
                    "month": month,
                    "city": k["city"],
                    "kpi_code": k["kpi_code"],
                    "kpi_name": k["kpi_name"],
                    "target_value": k["target_value"],
                    "real_value": k["real_value"],
                    "attainment_pct": k["attainment_pct"],
                    "current_category": k["current_category"],
                    "reachability_status": k["reachability_status"],
                    "gap_pct": k["gap_pct"],
                })
        except Exception:
            logger.debug("No se pudo obtener histórico para %s", month, exc_info=True)
    return {
        "country": country,
        "city": city,
        "months_back": months_back,
        "kpi_code": kpi_code,
        "months_queried": months,
        "historical": historical,
    }


# ═══════════════════════════════════════════════
# 3A.1 — Copy Goals from Previous Month
# ═══════════════════════════════════════════════

def copy_goals_from_month(
    from_month: str,
    to_month: str,
    country: str = "PE",
    city: Optional[str] = None,
    owner: Optional[str] = None,
) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            if city:
                cur.execute(
                    """INSERT INTO ops.yango_loyalty_monthly_goals
                       (month, country, city, kpi_code, target_value, gold_min, silver_min, bronze_min, source_type, owner, updated_by, updated_at)
                     SELECT %s, country, city, kpi_code, target_value, gold_min, silver_min, bronze_min, source_type, %s, %s, now()
                     FROM ops.yango_loyalty_monthly_goals
                     WHERE month = %s AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
                       AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))
                     ON CONFLICT (month, country, city, kpi_code) DO UPDATE SET
                       target_value = EXCLUDED.target_value,
                       gold_min     = EXCLUDED.gold_min,
                       silver_min   = EXCLUDED.silver_min,
                       bronze_min   = EXCLUDED.bronze_min,
                       owner        = EXCLUDED.owner,
                       updated_by   = EXCLUDED.updated_by,
                       updated_at   = now()""",
                    (to_month, owner, owner, from_month, country, city),
                )
            else:
                cur.execute(
                    """INSERT INTO ops.yango_loyalty_monthly_goals
                       (month, country, city, kpi_code, target_value, gold_min, silver_min, bronze_min, source_type, owner, updated_by, updated_at)
                     SELECT %s, country, city, kpi_code, target_value, gold_min, silver_min, bronze_min, source_type, %s, %s, now()
                     FROM ops.yango_loyalty_monthly_goals
                     WHERE month = %s AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))
                     ON CONFLICT (month, country, city, kpi_code) DO UPDATE SET
                       target_value = EXCLUDED.target_value,
                       gold_min     = EXCLUDED.gold_min,
                       silver_min   = EXCLUDED.silver_min,
                       bronze_min   = EXCLUDED.bronze_min,
                       owner        = EXCLUDED.owner,
                       updated_by   = EXCLUDED.updated_by,
                       updated_at   = now()""",
                    (to_month, owner, owner, from_month, country),
                )
            copied = cur.rowcount
        finally:
            cur.close()
    return {"from_month": from_month, "to_month": to_month, "copied": copied}


# ═══════════════════════════════════════════════
# 3A.1 — Validation Helpers
# ═══════════════════════════════════════════════

def validate_kpi_input(kpi_code: str, value: float, month: str, city: str) -> list[str]:
    errors = []
    if kpi_code not in VALID_KPI_CODES:
        errors.append(f"KPI '{kpi_code}' no válido. Opciones: {sorted(VALID_KPI_CODES)}")
    if city not in VALID_CITIES:
        errors.append(f"Ciudad '{city}' no válida. Opciones: {sorted(VALID_CITIES)}")
    try:
        y, m = month.split("-")
        if not (len(y) == 4 and 1 <= int(m) <= 12):
            errors.append(f"Mes '{month}' no válido. Formato: YYYY-MM")
    except Exception:
        errors.append(f"Mes '{month}' no válido. Formato: YYYY-MM")
    if value < 0:
        errors.append(f"Valor no puede ser negativo: {value}")
    pct_kpis = {"CONV_NEW", "CONV_REA", "UFC"}
    score_kpis = {"COMMS", "SUPPORT", "SOCIAL"}
    if kpi_code in pct_kpis and not (0 <= value <= 100):
        errors.append(f"Porcentaje debe estar entre 0 y 100: {value}")
    if kpi_code in score_kpis and not (0 <= value <= 100):
        errors.append(f"Score debe estar entre 0 y 100: {value}")
    return errors

def validate_bulk_input(items: list[dict]) -> dict:
    valid_items = []
    errors = []
    for i, item in enumerate(items):
        item_errors = []
        kpi = item.get("kpi_code", "")
        if kpi not in VALID_KPI_CODES:
            item_errors.append(f"KPI '{kpi}' no válido")
        city = item.get("city", "")
        if city not in VALID_CITIES:
            item_errors.append(f"Ciudad '{city}' no válida")
        month = item.get("month", "")
        try:
            y, m = month.split("-")
            if not (len(y) == 4 and 1 <= int(m) <= 12):
                item_errors.append(f"Mes '{month}' no válido")
        except Exception:
            item_errors.append(f"Mes '{month}' no válido")
        value = item.get("real_value") or item.get("target_value")
        if value is not None:
            try:
                v = float(value)
                if v < 0:
                    item_errors.append(f"Valor negativo: {v}")
                if kpi in ("CONV_NEW", "CONV_REA", "UFC", "COMMS", "SUPPORT", "SOCIAL") and not (0 <= v <= 100):
                    item_errors.append(f"Valor fuera de rango 0-100: {v}")
            except (TypeError, ValueError):
                item_errors.append(f"Valor no numérico: {value}")
        if item_errors:
            errors.append({"index": i, "item": item, "errors": item_errors})
        else:
            valid_items.append(item)
    dupe_keys = set()
    for v in valid_items:
        key = (v["month"], v.get("country", "PE"), v["city"], v["kpi_code"])
        if key in dupe_keys:
            errors.append({"index": -1, "item": v, "errors": [f"Duplicado: {key}"]})
        dupe_keys.add(key)
    return {"valid_items": valid_items, "errors": errors, "total": len(items), "valid_count": len(valid_items), "error_count": len(errors)}


# ═══════════════════════════════════════════════
# Fase 3A — Core (unchanged signatures, enhanced)
# ═══════════════════════════════════════════════

def get_summary(
    month: Optional[str] = None,
    country: str = "PE",
    city: Optional[str] = None,
) -> dict:
    month = month or _current_month()
    year, mon_num = int(month.split("-")[0]), int(month.split("-")[1])
    today = _day_of_month()
    total_days = _days_in_month(year, mon_num)
    with get_db() as conn:
        registry = _get_registry(conn)
        goals = _get_goals(conn, month, country, city)
        manual_results = _get_manual_results(conn, month, country, city)
    goals_map = {(g["city"], g["kpi_code"]): g for g in goals}
    manual_map = {(m["city"], m["kpi_code"]): m for m in manual_results}
    cities_to_use = [city] if city else CITIES
    result_rows = []
    for c in cities_to_use:
        for reg in registry:
            goal = goals_map.get((c, reg["kpi_code"]))
            manual = manual_map.get((c, reg["kpi_code"]))
            real_val = None
            if reg["source_type"] == "available_now":
                with get_db() as conn:
                    real_val = _fetch_available_kpi(conn, reg["kpi_code"], month, country, c)
            row = _build_kpi_row(reg, goal, manual, real_val, month, country, c, today, total_days)
            row["city"] = c
            row["month"] = month
            result_rows.append(row)
    missing_kpis = [r for r in result_rows if r["reachability_status"] == "DATA_MISSING"]
    has_missing = len(missing_kpis) > 0
    city_summaries = {}
    for c in cities_to_use:
        city_rows = [r for r in result_rows if r["city"] == c]
        statuses = [r["reachability_status"] for r in city_rows]
        categories = [r["current_category"] for r in city_rows if r["current_category"] != "DATA_MISSING"]
        city_summaries[c] = {
            "dominant_status": max(set(statuses), key=statuses.count) if statuses else "DATA_MISSING",
            "dominant_category": max(set(categories), key=categories.count) if categories else "DATA_MISSING",
            "kpi_count": len(city_rows),
            "data_missing_count": sum(1 for r in city_rows if r["reachability_status"] == "DATA_MISSING"),
        }
    return {
        "month": month, "country": country,
        "today_day": today, "total_days": total_days,
        "has_data_missing": has_missing,
        "cities": cities_to_use,
        "city_summaries": city_summaries,
        "kpis": result_rows,
        "total_kpis": len(result_rows),
    }


def get_kpis(month: Optional[str] = None) -> list[dict]:
    month = month or _current_month()
    with get_db() as conn:
        return _get_registry(conn)


def get_city_status(
    month: Optional[str] = None,
    country: str = "PE",
    city: str = "Lima",
) -> dict:
    month = month or _current_month()
    year, mon_num = int(month.split("-")[0]), int(month.split("-")[1])
    today = _day_of_month()
    total_days = _days_in_month(year, mon_num)
    with get_db() as conn:
        registry = _get_registry(conn)
        goals = _get_goals(conn, month, country, city)
        manual_results = _get_manual_results(conn, month, country, city)
    goals_map = {g["kpi_code"]: g for g in goals}
    manual_map = {m["kpi_code"]: m for m in manual_results}
    rows = []
    for reg in registry:
        goal = goals_map.get(reg["kpi_code"])
        manual = manual_map.get(reg["kpi_code"])
        real_val = None
        if reg["source_type"] == "available_now":
            with get_db() as conn:
                real_val = _fetch_available_kpi(conn, reg["kpi_code"], month, country, city)
        rows.append(_build_kpi_row(reg, goal, manual, real_val, month, country, city, today, total_days))
    statuses = [r["reachability_status"] for r in rows]
    categories = [r["current_category"] for r in rows if r["current_category"] != "DATA_MISSING"]
    return {
        "month": month, "city": city, "country": country,
        "today_day": today, "total_days": total_days,
        "dominant_status": max(set(statuses), key=statuses.count) if statuses else "DATA_MISSING",
        "dominant_category": max(set(categories), key=categories.count) if categories else "DATA_MISSING",
        "kpis": rows,
    }


def get_gaps(
    month: Optional[str] = None,
    country: str = "PE",
    city: Optional[str] = None,
    min_gap_pct: Optional[float] = None,
) -> dict:
    summary = get_summary(month=month, country=country, city=city)
    kpis = summary["kpis"]
    gaps = [k for k in kpis if k["gap_abs"] is not None and k["gap_abs"] < 0]
    if min_gap_pct is not None:
        gaps = [g for g in gaps if g["gap_pct"] is not None and abs(g["gap_pct"]) >= min_gap_pct]
    gaps_sorted = sorted(gaps, key=lambda x: x["gap_pct"] if x["gap_pct"] is not None else 0)
    return {"month": summary["month"], "country": summary["country"], "total_gaps": len(gaps_sorted), "gaps": gaps_sorted}


def get_reachability(
    month: Optional[str] = None,
    country: str = "PE",
    city: Optional[str] = None,
) -> dict:
    summary = get_summary(month=month, country=country, city=city)
    kpis = summary["kpis"]
    reachability_dist = {"ON_TRACK": 0, "SLIGHTLY_BEHIND": 0, "RECOVERABLE": 0, "HIGH_RISK": 0, "UNREACHABLE": 0, "DATA_MISSING": 0}
    for k in kpis:
        s = k["reachability_status"]
        if s in reachability_dist:
            reachability_dist[s] += 1
    unreachable = [k for k in kpis if k["reachability_status"] == "UNREACHABLE"]
    at_risk = [k for k in kpis if k["reachability_status"] in ("HIGH_RISK", "UNREACHABLE")]
    total_valid = sum(v for k, v in reachability_dist.items() if k != "DATA_MISSING")
    on_track_pct = round((reachability_dist["ON_TRACK"] / total_valid) * 100, 1) if total_valid else 0
    return {
        "month": summary["month"], "country": summary["country"],
        "reachability_distribution": reachability_dist,
        "on_track_pct": on_track_pct,
        "unreachable_count": len(unreachable), "at_risk_count": len(at_risk),
        "unreachable": unreachable, "at_risk": at_risk,
    }


def upsert_goals(goals: list[dict], owner: Optional[str] = None) -> dict:
    validation = validate_bulk_input([{**g, "real_value": g.get("target_value")} for g in goals])
    if validation["error_count"] > 0:
        return {"inserted": 0, "updated": 0, "total": len(goals), "errors": validation["errors"]}
    inserted = 0
    updated = 0
    with get_db() as conn:
        cur = conn.cursor()
        try:
            for g in goals:
                cur.execute(
                    """
                    INSERT INTO ops.yango_loyalty_monthly_goals
                        (month, country, city, kpi_code, target_value, gold_min, silver_min, bronze_min, source_type, owner, updated_by, updated_at)
                    VALUES (%(month)s, %(country)s, %(city)s, %(kpi_code)s, %(target_value)s, %(gold_min)s, %(silver_min)s, %(bronze_min)s, %(source_type)s, %(owner)s, %(updated_by)s, now())
                    ON CONFLICT (month, country, city, kpi_code) DO UPDATE SET
                        target_value = EXCLUDED.target_value, gold_min = EXCLUDED.gold_min,
                        silver_min = EXCLUDED.silver_min, bronze_min = EXCLUDED.bronze_min,
                        owner = EXCLUDED.owner, updated_by = EXCLUDED.updated_by, updated_at = now()
                    """,
                    {
                        "month": g["month"], "country": g.get("country", "PE"),
                        "city": g["city"], "kpi_code": g["kpi_code"],
                        "target_value": g["target_value"],
                        "gold_min": g.get("gold_min"), "silver_min": g.get("silver_min"),
                        "bronze_min": g.get("bronze_min"),
                        "source_type": g.get("source_type", "manual_input"),
                        "owner": owner, "updated_by": owner,
                    },
                )
                if cur.rowcount == 1: updated += 1
                else: inserted += 1
        finally:
            cur.close()
    return {"inserted": inserted, "updated": updated, "total": len(goals)}


def upsert_manual_results(results: list[dict], owner: Optional[str] = None) -> dict:
    validation = validate_bulk_input(results)
    if validation["error_count"] > 0:
        return {"inserted": 0, "updated": 0, "total": len(results), "errors": validation["errors"]}
    inserted = 0
    updated = 0
    with get_db() as conn:
        cur = conn.cursor()
        try:
            for r in results:
                cur.execute(
                    """
                    INSERT INTO ops.yango_loyalty_manual_results
                        (month, country, city, kpi_code, real_value, source_note, owner, updated_by, updated_at)
                    VALUES (%(month)s, %(country)s, %(city)s, %(kpi_code)s, %(real_value)s, %(source_note)s, %(owner)s, %(updated_by)s, now())
                    ON CONFLICT (month, country, city, kpi_code) DO UPDATE SET
                        real_value = EXCLUDED.real_value, source_note = EXCLUDED.source_note,
                        owner = EXCLUDED.owner, updated_by = EXCLUDED.updated_by, updated_at = now()
                    """,
                    {
                        "month": r["month"], "country": r.get("country", "PE"),
                        "city": r["city"], "kpi_code": r["kpi_code"],
                        "real_value": r["real_value"],
                        "source_note": r.get("source_note"),
                        "owner": owner, "updated_by": owner,
                    },
                )
                if cur.rowcount == 1: updated += 1
                else: inserted += 1
        finally:
            cur.close()
    return {"inserted": inserted, "updated": updated, "total": len(results)}


def upsert_manual_results_bulk(results: list[dict], owner: Optional[str] = None) -> dict:
    """Bulk con validación completa. Retorna errores si los hay."""
    validation = validate_bulk_input(results)
    if validation["error_count"] > 0:
        return {"inserted": 0, "updated": 0, "total": len(results), "errors": validation["errors"], "validated": False}
    return upsert_manual_results(results, owner=owner)
