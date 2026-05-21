"""Fase 1F-5C — Statistical & Behavioral Fraud Routines (Calibrated).

Motor de fraude conductual con:
- Thresholds versionados desde fraud.rule_threshold_config
- Tiers: signal_flag / fraud_candidate / risk_case
- Case creation guardrails con batch limits
- SQL agregada (no trae filas completas a Python)
- Todas soportan dry_run
- F1F-5C: Case confidence scoring + behavioral profile class
"""
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

from app.db.connection import get_db
from psycopg2.extras import Json

# ── Fallback thresholds (usados si no hay config DB o baseline) ──
SHORT_TRIP_DISTANCE_M = 2000
SHORT_TRIP_DURATION_S = 180
SHORT_TRIP_AMOUNT_MAX = 8000
MIN_BASELINE_SAMPLE = 30
REPEATED_ORIGIN_MIN_COUNT = 3
REPEATED_ROUTE_MIN_COUNT = 2
COORDINATED_DRIVER_MIN = 6
LOOP_MIN_COUNT = 2

SOURCE = "public.trips_2026"
CONFIG_VERSION = "trip_behavior_v1_calibrated"

# ── Case Tier constants ──
TIER_SIGNAL = "signal_flag"
TIER_CANDIDATE = "fraud_candidate"
TIER_CASE = "risk_case"

# ── Distribution-based fallback baselines (from D-7 analysis) ──
DIST_FALLBACK = {
    "trips_24h": {"p50": 6, "p90": 23, "p95": 28, "p99": 41},
    "distance_m": {"p10": 2500, "p50": 6260, "p90": 11200},
    "duration_s": {"p10": 500, "p50": 1250, "p90": 2160},
    "short_trip_ratio": {"p90": 0.03, "p95": 0.06, "p99": 0.14},
    "drivers_per_origin": {"p90": 3, "p95": 4, "p99": 8},
}


# ═══════════════════════════════════════════════════════════════════
# BASELINE ENGINE
# ═══════════════════════════════════════════════════════════════════

def compute_baseline(conn, dimension_col: str, dimension_value: str,
                     window_days: int = 30) -> Dict[str, Any]:
    """Calcula baseline estadistico para una dimension (park_id o city/park).

    Usa SQL agregada para calcular:
    - avg_distance, avg_duration, avg_amount
    - percentiles p10, p25, p50, p75, p90 de distance
    - short_trip_ratio
    - avg_trips_per_day
    - variance_distance, variance_duration
    - total_sample_size

    Returns dict con metricas + fallback_used flag.
    """
    cur = conn.cursor()
    cutoff = datetime.now() - timedelta(days=window_days)

    # Dimension filter
    if dimension_col == "park_id":
        dim_filter = "t.park_id = %(dim_val)s"
    elif dimension_col == "city_park":
        # city via park_id como proxy
        dim_filter = "t.park_id = %(dim_val)s"
    else:
        dim_filter = "t.park_id = %(dim_val)s"

    params = {"dim_val": dimension_value, "cutoff": cutoff}

    # Sample size check
    cur.execute(f"""
        SELECT COUNT(*) FROM {SOURCE} t
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje >= %(cutoff)s
          AND {dim_filter}
    """, params)
    sample_size = cur.fetchone()[0] or 0

    if sample_size < MIN_BASELINE_SAMPLE:
        cur.close()
        return _fallback_baseline()

    # Estadisticos agregados
    cur.execute(f"""
        SELECT
            COUNT(*) AS n,
            AVG(t.distancia_km * 1000) AS avg_distance_m,
            AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS avg_duration_s,
            AVG(t.precio_yango_pro) AS avg_amount,
            STDDEV(t.distancia_km * 1000) AS stddev_distance_m,
            STDDEV(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS stddev_duration_s,
            STDDEV(t.precio_yango_pro) AS stddev_amount,
            PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY t.distancia_km * 1000) AS p10_distance_m,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY t.distancia_km * 1000) AS p25_distance_m,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY t.distancia_km * 1000) AS p50_distance_m,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY t.distancia_km * 1000) AS p75_distance_m,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY t.distancia_km * 1000) AS p90_distance_m
        FROM {SOURCE} t
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje >= %(cutoff)s
          AND {dim_filter}
          AND t.fecha_finalizacion IS NOT NULL
          AND t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_finalizacion > t.fecha_inicio_viaje
    """, params)
    r = cur.fetchone()

    # Short trip ratio
    cur.execute(f"""
        SELECT
            COUNT(*) FILTER (WHERE COALESCE(t.distancia_km, 0) * 1000 < %(short_dist)s
                               OR EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) < %(short_dur)s
                               AND EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) > 0)
                AS short_trips,
            COUNT(*) AS total
        FROM {SOURCE} t
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje >= %(cutoff)s
          AND {dim_filter}
    """, {
        **params,
        "short_dist": SHORT_TRIP_DISTANCE_M,
        "short_dur": SHORT_TRIP_DURATION_S,
    })
    sr = cur.fetchone()
    short_count = sr[0] or 0
    total_count = sr[1] or 1
    short_trip_ratio = round(short_count / total_count, 4) if total_count > 0 else 0.0

    # avg_trips_per_day
    cur.execute(f"""
        SELECT COUNT(DISTINCT t.conductor_id) AS driver_count,
               COUNT(*) AS total_trips
        FROM {SOURCE} t
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje >= %(cutoff)s
          AND {dim_filter}
    """, params)
    dr = cur.fetchone()
    driver_count = dr[0] or 1
    total_trips_dim = dr[1] or 0
    avg_trips_per_day = round(total_trips_dim / max(driver_count, 1) / max(window_days, 1), 2)

    cur.close()

    return {
        "sample_size": sample_size,
        "window_days": window_days,
        "dimension": f"{dimension_col}={dimension_value}",
        "avg_distance_m": round(float(r[1] or 0), 1),
        "avg_duration_s": round(float(r[2] or 0), 1),
        "avg_amount": round(float(r[3] or 0), 2),
        "stddev_distance_m": round(float(r[4] or 0), 1),
        "stddev_duration_s": round(float(r[5] or 0), 1),
        "stddev_amount": round(float(r[6] or 0), 2),
        "p10_distance_m": round(float(r[7] or 0), 1),
        "p25_distance_m": round(float(r[8] or 0), 1),
        "p50_distance_m": round(float(r[9] or 0), 1),
        "p75_distance_m": round(float(r[10] or 0), 1),
        "p90_distance_m": round(float(r[11] or 0), 1),
        "short_trip_ratio": short_trip_ratio,
        "avg_trips_per_day": avg_trips_per_day,
        "variance_distance": round(float(r[4] or 0) ** 2, 1),
        "variance_duration": round(float(r[5] or 0) ** 2, 1),
        "fallback_used": False,
    }


def _fallback_baseline() -> Dict[str, Any]:
    """Fallback thresholds cuando no hay suficiente data para baseline estadistico."""
    return {
        "sample_size": 0,
        "window_days": 30,
        "dimension": "fallback",
        "avg_distance_m": 4000,
        "avg_duration_s": 600,
        "avg_amount": 15000,
        "stddev_distance_m": 3000,
        "stddev_duration_s": 400,
        "stddev_amount": 10000,
        "p10_distance_m": 800,
        "p25_distance_m": 1500,
        "p50_distance_m": 3000,
        "p75_distance_m": 5500,
        "p90_distance_m": 8000,
        "short_trip_ratio": 0.15,
        "avg_trips_per_day": 5.0,
        "variance_distance": 9_000_000,
        "variance_duration": 160_000,
        "fallback_used": True,
    }


def get_baseline_for_trip(park_id: str, window_days: int = 30) -> Dict[str, Any]:
    """Obtiene baseline para un park_id especifico."""
    with get_db() as conn:
        return compute_baseline(conn, "park_id", park_id, window_days)


# ═══════════════════════════════════════════════════════════════════
# THRESHOLD CONFIG LOADER
# ═══════════════════════════════════════════════════════════════════

def load_threshold_config(rule_code: str) -> Dict[str, Any]:
    """Carga config de thresholds versionada desde DB."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT threshold_config FROM fraud.rule_threshold_config
                WHERE rule_code = %s AND config_version = %s AND enabled = true
                ORDER BY active_from DESC LIMIT 1
            """, (rule_code, CONFIG_VERSION))
            r = cur.fetchone()
            cur.close()
            if r and r[0]:
                return r[0] if isinstance(r[0], dict) else {}
    except Exception:
        pass
    return {}


def load_guardrails() -> Dict[str, Any]:
    """Carga config de guardrails de creacion de casos."""
    return load_threshold_config("CASE_CREATION_GUARDRAILS")


def get_tier_config(rule_code: str, tier: str) -> Dict[str, Any]:
    """Obtiene config para un tier especifico de una regla."""
    config = load_threshold_config(rule_code)
    return config.get(tier, {})


def classify_tier(rule_code: str, evidence: Dict[str, Any], trust_tier: str = "unknown") -> str:
    """Clasifica una deteccion como signal_flag, fraud_candidate, o risk_case.

    Usa thresholds calibrados desde DB, con fallback a defaults.
    """
    config = load_threshold_config(rule_code)

    # Evaluar de mayor a menor tier
    case_cfg = config.get(TIER_CASE, {})
    cand_cfg = config.get(TIER_CANDIDATE, {})
    sig_cfg = config.get(TIER_SIGNAL, {})

    # Case tier
    if case_cfg.get("requires_combo") or case_cfg.get("requires_trust"):
        # Los combos se evaluan externamente (en la rutina)
        pass
    if case_cfg.get("requires_trust") and trust_tier not in ("new_or_unproven", "restricted"):
        pass  # No cumple trust requirement para case
    elif case_cfg:
        # Si no requiere combo ni trust, verificar thresholds directos
        if _match_thresholds(evidence, case_cfg):
            return TIER_CASE

    # Candidate tier
    if cand_cfg.get("requires_trust") and trust_tier not in ("new_or_unproven", "restricted"):
        pass
    elif cand_cfg:
        if _match_thresholds(evidence, cand_cfg):
            return TIER_CANDIDATE

    # Signal tier (todos los demas)
    if sig_cfg.get("requires_trust") and trust_tier not in ("new_or_unproven", "restricted"):
        return TIER_SIGNAL  # Aun con trust mismatch, es signal
    if sig_cfg:
        if _match_thresholds(evidence, sig_cfg):
            return TIER_SIGNAL

    return TIER_SIGNAL  # Default: cualquier deteccion es al menos signal


def _match_thresholds(evidence: Dict[str, Any], cfg: Dict[str, Any]) -> bool:
    """Verifica si la evidencia cumple los thresholds configurados."""
    for key, threshold in cfg.items():
        if key in ("tier", "requires_combo", "requires_trust", "requires_trust_ratio",
                    "combo_rules", "window_days"):
            continue
        ev_val = evidence.get(key)
        if ev_val is None:
            continue
        try:
            if float(ev_val) < float(threshold):
                return False
        except (ValueError, TypeError):
            pass
    return True


# ── Case creation counter (in-memory per run) ──
_case_counter = {"total": 0, "by_rule": {}, "by_park": {}, "by_driver": set()}

def _reset_case_counter():
    global _case_counter
    _case_counter = {"total": 0, "by_rule": {}, "by_park": {}, "by_driver": set()}


def _create_case_guarded(dry_run: bool, driver_id: str, park_id: str, severity: str,
                          score: float, triggered: List[Dict], action: str,
                          rule_code: str = None) -> Optional[Dict]:
    """Crea caso con guardrails. Auto-extrae rule_code de triggered si no se pasa."""
    if rule_code is None and triggered:
        rule_code = triggered[0].get("rule_code", "unknown") if isinstance(triggered[0], dict) else "unknown"
    if rule_code is None:
        rule_code = "unknown"
    guardrails = load_guardrails()

    max_per_run = guardrails.get("max_cases_per_run", 50)
    max_per_rule = guardrails.get("max_cases_per_rule", 20)
    max_per_park = guardrails.get("max_cases_per_park", 10)

    if dry_run:
        # In dry_run, compute confidence but don't store
        try:
            from app.services.fraud.fraud_confidence_scoring import compute_case_confidence, build_signal_bundle
            bundle = build_signal_bundle(triggered)
            conf_score, conf_reason = compute_case_confidence(bundle)
        except Exception:
            conf_score, conf_reason = None, None
        return {"id": None, "suppressed": False, "tier": "dry_run",
                "confidence_score": conf_score, "confidence_reason": conf_reason}

    # Check limits
    if _case_counter["total"] >= max_per_run:
        return {"id": None, "suppressed": True, "reason": "max_cases_per_run"}

    rc = rule_code
    if _case_counter["by_rule"].get(rc, 0) >= max_per_rule:
        return {"id": None, "suppressed": True, "reason": f"max_cases_per_rule:{rc}"}

    if park_id and _case_counter["by_park"].get(park_id, 0) >= max_per_park:
        return {"id": None, "suppressed": True, "reason": f"max_cases_per_park:{park_id}"}

    # Compute confidence
    conf_score = None
    conf_reason = None
    try:
        from app.services.fraud.fraud_confidence_scoring import compute_case_confidence, build_signal_bundle
        bundle = build_signal_bundle(triggered)
        conf_score, conf_reason = compute_case_confidence(bundle)
    except Exception:
        pass

    # Create case
    from app.services.fraud.fraud_case_service import create_or_update_case
    case = create_or_update_case(driver_id, park_id, severity, score, triggered, action,
                                 confidence_score=conf_score, confidence_reason=conf_reason)

    if case and case.get("id"):
        _case_counter["total"] += 1
        _case_counter["by_rule"][rc] = _case_counter["by_rule"].get(rc, 0) + 1
        _case_counter["by_park"][park_id or ""] = _case_counter["by_park"].get(park_id or "", 0) + 1
        _case_counter["by_driver"].add(driver_id)

    return case


def should_create_case(tier: str, score: float, triggered_rules: List[Dict],
                       trust_tier: str) -> bool:
    """Decide si una deteccion debe convertirse en caso operativo.

    Reglas:
    - Caso si score >= 80
    - Caso si 2+ reglas high severity
    - Caso si 1 critical + new_or_unproven
    - Caso si es candidate de SHORT_TRIP_FARMING con combo
    - Caso si es HIGH_CARD_AMOUNT_NEW_DRIVER
    """
    if score >= 80:
        return True

    high_count = sum(1 for r in triggered_rules
                     if r.get("severity") in ("high", "critical"))
    critical_count = sum(1 for r in triggered_rules
                         if r.get("severity") == "critical")

    if high_count >= 2:
        return True

    if critical_count >= 1 and trust_tier in ("new_or_unproven", "restricted"):
        return True

    rule_codes = [r.get("rule_code", "") for r in triggered_rules]
    if "HIGH_CARD_AMOUNT_NEW_DRIVER" in rule_codes:
        return True
    if "HIGH_CARD_AMOUNT_NEW_DRIVER_V2" in rule_codes:
        return True

    return False


# ═══════════════════════════════════════════════════════════════════
# LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════

def _log_start(run_code, routine_name, mode, dry_run, date_from, date_to):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO fraud.routine_run_log
                    (run_code, routine_name, mode, dry_run, date_from, date_to, status, started_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'started', now())
            """, (run_code, routine_name, mode, dry_run, date_from, date_to))
            conn.commit()
            cur.close()
    except Exception:
        pass


def _log_end(run_code, status, elapsed, results):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            safe_summary = {
                "status": status,
                "elapsed_seconds": elapsed,
                "signal_flags": results.get("signal_flags", 0) if isinstance(results, dict) else 0,
                "candidates": results.get("candidates", 0) if isinstance(results, dict) else 0,
                "cases_created": results.get("cases_created", 0) if isinstance(results, dict) else 0,
                "suppressed": results.get("suppressed", 0) if isinstance(results, dict) else 0,
                "dry_run": results.get("dry_run", True) if isinstance(results, dict) else True,
            }
            cur.execute("""
                UPDATE fraud.routine_run_log
                SET status = %s, finished_at = now(), duration_seconds = %s, result_summary = %s
                WHERE run_code = %s
            """, (status, elapsed, Json(safe_summary), run_code))
            conn.commit()
            cur.close()
    except Exception:
        pass


def make_result(dry_run=True):
    """Factory para result dict con tracking de tiers."""
    return {
        "dry_run": dry_run,
        "signal_flags": 0,
        "candidates": 0,
        "cases_created": 0,
        "suppressed": 0,
        "drivers_flagged": 0,
        "errors": [],
    }


# ═══════════════════════════════════════════════════════════════════
# ROUTINES
# ═══════════════════════════════════════════════════════════════════

def _process_detection(dry_run, driver_id, park_id, rule_code, rule_name,
                        severity, weight, evidence, trust_tier="unknown",
                        tier=None):
    """Procesa una deteccion a traves de la pipeline flag->candidate->case."""
    if tier is None:
        tier = classify_tier(rule_code, evidence, trust_tier)

    triggered = [{
        "rule_code": rule_code,
        "rule_name": rule_name,
        "severity": severity,
        "weight": weight,
        "evidence": evidence,
    }]

    score = weight
    if tier == TIER_CASE:
        score = min(weight + 30, 100)

    should_case = should_create_case(tier, score, triggered, trust_tier)

    case_result = None
    if should_case and tier in (TIER_CANDIDATE, TIER_CASE):
        action = "restrict_driver_review" if severity == "critical" else "review"
        case_result = _create_case_guarded(dry_run, driver_id, park_id, severity, score, triggered, action, rule_code)

    return {
        "tier": tier,
        "score": score,
        "triggered": triggered,
        "should_case": should_case,
        "case_created": case_result and case_result.get("id") and not case_result.get("suppressed"),
        "case_suppressed": case_result and case_result.get("suppressed", False),
        "suppression_reason": (case_result or {}).get("reason") if case_result else None,
    }


def routine_repeated_origin_pattern(
    date_from=None, date_to=None, park_id=None, window_days=7,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta drivers con multiples viajes desde el mismo origin_cluster_key.
    F1F-5B: Calibrado con tiers flag/candidate/case.
    """
    run_code = f"REPEATED_ORIGIN-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "repeated_origin_pattern", "D-" + str(window_days), dry_run, date_from, date_to)

    result = make_result(dry_run)

    # Calibrated: signal >= 3, candidate >= 5
    sig_cfg = get_tier_config("REPEATED_ORIGIN_PATTERN", TIER_SIGNAL)
    cand_cfg = get_tier_config("REPEATED_ORIGIN_PATTERN", TIER_CANDIDATE)
    sig_min = sig_cfg.get("min_count", 3)
    cand_min = cand_cfg.get("min_count", 5)

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        park_filter = ""
        params = {}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            park_filter = "AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            WITH parsed AS (
                SELECT
                    t.conductor_id AS driver_id,
                    t.park_id,
                    SPLIT_PART(t.direccion, '->', 1) AS origin_raw,
                    TRIM(LOWER(REGEXP_REPLACE(
                        SPLIT_PART(t.direccion, '->', 1),
                        '[^a-z0-9 ]', '', 'g'
                    ))) AS origin_norm,
                    t.fecha_inicio_viaje
                FROM {SOURCE} t
                WHERE t.condicion = 'Completado'
                  AND t.direccion IS NOT NULL
                  AND t.direccion LIKE '%%->%%'
                  {date_filter} {park_filter}
            ),
            grouped AS (
                SELECT
                    driver_id, park_id,
                    LEFT(origin_norm, 100) AS origin_cluster_key,
                    COUNT(*) AS trip_count,
                    MIN(fecha_inicio_viaje) AS first_trip,
                    MAX(fecha_inicio_viaje) AS last_trip
                FROM parsed
                WHERE origin_norm IS NOT NULL AND LENGTH(origin_norm) >= 3
                GROUP BY driver_id, park_id, LEFT(origin_norm, 100)
                HAVING COUNT(*) >= %(min_count)s
                ORDER BY COUNT(*) DESC
                LIMIT %(limit)s
            )
            SELECT * FROM grouped
        """, {**params, "min_count": sig_min, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        origin_key = r[2]
        count = r[3]

        evidence = {
            "origin_cluster_key": origin_key,
            "repeat_count": count,
            "first_trip": r[4].isoformat() if r[4] else None,
            "last_trip": r[5].isoformat() if r[5] else None,
            "window_days": window_days,
            "signal_min_count": sig_min,
            "candidate_min_count": cand_min,
        }

        # Tier classification
        if count >= cand_min:
            tier = TIER_CANDIDATE
        else:
            tier = TIER_SIGNAL

        # Solo candidate se convierte en caso si cumple should_create_case
        if tier == TIER_CANDIDATE:
            triggered = [{
                "rule_code": "REPEATED_ORIGIN_PATTERN",
                "rule_name": "Patron de origen repetido",
                "severity": "high",
                "weight": 30,
                "evidence": evidence,
            }]
            if should_create_case(tier, 30, triggered, "unknown"):
                case_r = _create_case_guarded(dry_run, driver_id, pk_id, "high", 30, triggered, "review", "REPEATED_ORIGIN_PATTERN")
                if case_r and case_r.get("id"):
                    result["cases_created"] += 1
                elif case_r and case_r.get("suppressed"):
                    result["suppressed"] += 1
                else:
                    result["candidates"] += 1
            else:
                result["candidates"] += 1
        else:
            result["signal_flags"] += 1

        result["drivers_flagged"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_repeated_route_signature(
    date_from=None, date_to=None, park_id=None, window_days=7,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta drivers con la misma ruta origen->destino repetida multiples veces."""
    run_code = f"REPEATED_ROUTE-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "repeated_route_signature", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "routes_detected": 0, "cases_created": 0, "dry_run": dry_run}

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            WITH parsed AS (
                SELECT
                    t.conductor_id AS driver_id,
                    t.park_id,
                    TRIM(LOWER(REGEXP_REPLACE(t.direccion, '[^a-z0-9 >-]', '', 'g'))) AS route_sig,
                    t.fecha_inicio_viaje
                FROM {SOURCE} t
                WHERE t.condicion = 'Completado'
                  AND t.direccion IS NOT NULL
                  AND t.direccion LIKE '%%->%%'
                  {date_filter}
            ),
            grouped AS (
                SELECT
                    driver_id, park_id,
                    LEFT(route_sig, 200) AS route_signature,
                    COUNT(*) AS trip_count,
                    MIN(fecha_inicio_viaje) AS first_trip,
                    MAX(fecha_inicio_viaje) AS last_trip
                FROM parsed
                WHERE route_sig IS NOT NULL AND LENGTH(route_sig) >= 10
                GROUP BY driver_id, park_id, LEFT(route_sig, 200)
                HAVING COUNT(*) >= %(min_count)s
                ORDER BY COUNT(*) DESC
                LIMIT %(limit)s
            )
            SELECT * FROM grouped
        """, {**params, "min_count": REPEATED_ROUTE_MIN_COUNT, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        route_sig = r[2]
        count = r[3]
        result["drivers_flagged"] += 1
        result["routes_detected"] += 1

        triggered = [{
            "rule_code": "REPEATED_ROUTE_SIGNATURE",
            "rule_name": "Firma de ruta repetida",
            "severity": "high",
            "weight": 35,
            "evidence": {
                "route_signature": route_sig,
                "repeat_count": count,
                "first_trip": r[4].isoformat() if r[4] else None,
                "last_trip": r[5].isoformat() if r[5] else None,
                "window_days": window_days,
            },
        }]
        cas = _create_case_guarded(dry_run, driver_id, pk_id, "high", 35, triggered, "review", "REPEATED_ROUTE_SIGNATURE")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_low_avg_distance_pattern(
    date_from=None, date_to=None, park_id=None, window_days=30,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta drivers con avg_distance significativamente debajo del baseline.

    F1F-6: Signature corrected to match orchestrator expectations.
    """
    run_code = f"LOW_AVG_DIST-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "low_avg_distance_pattern", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "cases_created": 0, "dry_run": dry_run, "fallback_used": False}

    baseline = get_baseline_for_trip(park_id or "all", window_days)
    if baseline.get("fallback_used"):
        result["fallback_used"] = True

    avg_baseline_m = baseline["avg_distance_m"]
    # Threshold: driver avg < 30% of baseline avg
    threshold_m = avg_baseline_m * 0.3

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"threshold": threshold_m}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            SELECT
                t.conductor_id AS driver_id,
                t.park_id,
                COUNT(*) AS trip_count,
                AVG(t.distancia_km * 1000) AS avg_distance_m,
                MIN(t.distancia_km * 1000) AS min_distance_m,
                MAX(t.distancia_km * 1000) AS max_distance_m
            FROM {SOURCE} t
            WHERE t.condicion = 'Completado'
              AND t.distancia_km IS NOT NULL
              {date_filter}
            GROUP BY t.conductor_id, t.park_id
            HAVING COUNT(*) >= 3
               AND AVG(t.distancia_km * 1000) < %(threshold)s
            ORDER BY AVG(t.distancia_km * 1000) ASC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        count = r[2]
        avg_dist = round(float(r[3] or 0), 1)
        result["drivers_flagged"] += 1

        triggered = [{
            "rule_code": "LOW_AVG_DISTANCE_PATTERN",
            "rule_name": "Distancia promedio baja",
            "severity": "high",
            "weight": 35,
            "evidence": {
                "avg_distance_m": avg_dist,
                "baseline_avg_distance_m": avg_baseline_m,
                "threshold_m": round(threshold_m, 1),
                "ratio": round(avg_dist / max(avg_baseline_m, 1), 4),
                "trip_count": count,
                "fallback_used": baseline.get("fallback_used", False),
            },
        }]
        cas = _create_case_guarded(dry_run, driver_id, pk_id, "high", 35, triggered, "review", "LOW_AVG_DISTANCE_PATTERN")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_low_avg_duration_pattern(
    date_from=None, date_to=None, park_id=None, window_days=30,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta drivers con avg_duration significativamente debajo del baseline."""
    run_code = f"LOW_AVG_DUR-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "low_avg_duration_pattern", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "cases_created": 0, "dry_run": dry_run, "fallback_used": False}

    baseline = get_baseline_for_trip(park_id or "all", window_days)
    if baseline.get("fallback_used"):
        result["fallback_used"] = True

    avg_baseline_s = baseline["avg_duration_s"]
    threshold_s = avg_baseline_s * 0.3

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"threshold": threshold_s}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            SELECT
                t.conductor_id AS driver_id,
                t.park_id,
                COUNT(*) AS trip_count,
                AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS avg_duration_s
            FROM {SOURCE} t
            WHERE t.condicion = 'Completado'
              AND t.fecha_finalizacion IS NOT NULL
              AND t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_finalizacion > t.fecha_inicio_viaje
              {date_filter}
            GROUP BY t.conductor_id, t.park_id
            HAVING COUNT(*) >= 3
               AND AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) < %(threshold)s
            ORDER BY AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) ASC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        count = r[2]
        avg_dur = round(float(r[3] or 0), 1)
        result["drivers_flagged"] += 1

        triggered = [{
            "rule_code": "LOW_AVG_DURATION_PATTERN",
            "rule_name": "Duracion promedio baja",
            "severity": "high",
            "weight": 35,
            "evidence": {
                "avg_duration_s": avg_dur,
                "baseline_avg_duration_s": baseline["avg_duration_s"],
                "threshold_s": round(threshold_s, 1),
                "ratio": round(avg_dur / max(baseline["avg_duration_s"], 1), 4),
                "trip_count": count,
                "fallback_used": baseline.get("fallback_used", False),
            },
        }]
        cas = _create_case_guarded(dry_run, driver_id, pk_id, "high", 35, triggered, "review")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_extreme_short_trip_ratio(
    date_from=None, date_to=None, park_id=None, window_days=30,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta drivers con ratio extremo de viajes cortos."""
    run_code = f"EXTREME_SHORT-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "extreme_short_trip_ratio", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "cases_created": 0, "dry_run": dry_run}

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"short_dist": SHORT_TRIP_DISTANCE_M, "short_dur": SHORT_TRIP_DURATION_S, "min_trips": 10}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            SELECT
                t.conductor_id AS driver_id,
                t.park_id,
                COUNT(*) AS total_trips,
                COUNT(*) FILTER (
                    WHERE COALESCE(t.distancia_km, 0) * 1000 < %(short_dist)s
                       OR (
                           t.fecha_finalizacion IS NOT NULL
                           AND t.fecha_inicio_viaje IS NOT NULL
                           AND t.fecha_finalizacion > t.fecha_inicio_viaje
                           AND EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) < %(short_dur)s
                       )
                ) AS short_trips
            FROM {SOURCE} t
            WHERE t.condicion = 'Completado'
              {date_filter}
            GROUP BY t.conductor_id, t.park_id
            HAVING COUNT(*) >= %(min_trips)s
            ORDER BY COUNT(*) FILTER (
                WHERE COALESCE(t.distancia_km, 0) * 1000 < %(short_dist)s
                   OR (
                       t.fecha_finalizacion IS NOT NULL
                       AND t.fecha_inicio_viaje IS NOT NULL
                       AND t.fecha_finalizacion > t.fecha_inicio_viaje
                       AND EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) < %(short_dur)s
                   )
            )::float / NULLIF(COUNT(*), 0) DESC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        total = r[2] or 0
        short = r[3] or 0
        ratio = round(short / max(total, 1), 4)

        # Solo flag si ratio > 50% (mucho mas alto que baseline tipico de 15%)
        if ratio < 0.5:
            continue

        result["drivers_flagged"] += 1

        triggered = [{
            "rule_code": "EXTREME_SHORT_TRIP_RATIO",
            "rule_name": "Ratio extremo de viajes cortos",
            "severity": "critical" if ratio > 0.75 else "high",
            "weight": 40,
            "evidence": {
                "total_trips": total,
                "short_trips": short,
                "short_trip_ratio": ratio,
                "threshold_short_distance_m": SHORT_TRIP_DISTANCE_M,
                "threshold_short_duration_s": SHORT_TRIP_DURATION_S,
            },
        }]
        sev = "critical" if ratio > 0.75 else "high"
        cas = _create_case_guarded(dry_run, driver_id, pk_id, sev, 40, triggered, "restrict_driver_review" if ratio > 0.75 else "review")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_low_variance_pattern(
    date_from=None, date_to=None, park_id=None, window_days=30,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta drivers con varianza extremadamente baja en distancia/duracion/amount."""
    run_code = f"LOW_VARIANCE-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "low_variance_pattern", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "cases_created": 0, "dry_run": dry_run}

    baseline = get_baseline_for_trip(park_id or "all", window_days)
    # Threshold: driver variance < 5% of baseline variance
    var_dist_threshold = baseline.get("variance_distance", 9_000_000) * 0.05

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"var_threshold": var_dist_threshold, "min_trips": 5}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            SELECT
                t.conductor_id AS driver_id,
                t.park_id,
                COUNT(*) AS trip_count,
                VARIANCE(t.distancia_km * 1000) AS var_distance,
                VARIANCE(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS var_duration,
                VARIANCE(t.precio_yango_pro) AS var_amount,
                AVG(t.distancia_km * 1000) AS avg_distance_m,
                AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS avg_duration_s
            FROM {SOURCE} t
            WHERE t.condicion = 'Completado'
              AND t.distancia_km IS NOT NULL
              AND t.fecha_finalizacion IS NOT NULL
              AND t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_finalizacion > t.fecha_inicio_viaje
              {date_filter}
            GROUP BY t.conductor_id, t.park_id
            HAVING COUNT(*) >= %(min_trips)s
               AND VARIANCE(t.distancia_km * 1000) < %(var_threshold)s
            ORDER BY VARIANCE(t.distancia_km * 1000) ASC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        count = r[2]
        var_dist = round(float(r[3] or 0), 1)
        var_dur = round(float(r[4] or 0), 1)
        var_amount = round(float(r[5] or 0), 1)
        avg_dist = round(float(r[6] or 0), 1)
        result["drivers_flagged"] += 1

        triggered = [{
            "rule_code": "LOW_VARIANCE_PATTERN",
            "rule_name": "Patron de varianza baja",
            "severity": "medium",
            "weight": 30,
            "evidence": {
                "trip_count": count,
                "var_distance": var_dist,
                "var_duration": var_dur,
                "var_amount": var_amount,
                "avg_distance_m": avg_dist,
                "baseline_var_distance": baseline.get("variance_distance"),
                "threshold_var": round(var_dist_threshold, 1),
                "fallback_used": baseline.get("fallback_used", False),
            },
        }]
        cas = _create_case_guarded(dry_run, driver_id, pk_id, "medium", 30, triggered, "monitor")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_short_trip_farming(
    date_from=None, date_to=None, park_id=None, window_days=7,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta farming combinando: repeated origin + repeated route + low distance + low duration + short ratio + low variance + burst.

    Esta es la senal mas fuerte del sistema. Combina multiples dimensiones.
    """
    run_code = f"FARMING-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "short_trip_farming", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "cases_created": 0, "dry_run": dry_run}

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {
            "short_dist": SHORT_TRIP_DISTANCE_M,
            "short_dur": SHORT_TRIP_DURATION_S,
            "short_amount": SHORT_TRIP_AMOUNT_MAX,
            "min_trips": 5,
            "short_ratio": 0.6,
        }
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            WITH driver_stats AS (
                SELECT
                    t.conductor_id AS driver_id,
                    t.park_id,
                    COUNT(*) AS total_trips,
                    AVG(t.distancia_km * 1000) AS avg_distance_m,
                    AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS avg_duration_s,
                    AVG(t.precio_yango_pro) AS avg_amount,
                    COUNT(*) FILTER (
                        WHERE COALESCE(t.distancia_km, 0) * 1000 < %(short_dist)s
                           OR (
                               t.fecha_finalizacion IS NOT NULL
                               AND t.fecha_inicio_viaje IS NOT NULL
                               AND t.fecha_finalizacion > t.fecha_inicio_viaje
                               AND EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) < %(short_dur)s
                           )
                    ) AS short_trips,
                    VARIANCE(t.distancia_km * 1000) AS var_distance,
                    COUNT(DISTINCT SPLIT_PART(t.direccion, '->', 1)) AS unique_origins,
                    COUNT(DISTINCT t.direccion) AS unique_routes,
                    MIN(t.fecha_inicio_viaje) AS first_trip,
                    MAX(t.fecha_inicio_viaje) AS last_trip
                FROM {SOURCE} t
                WHERE t.condicion = 'Completado'
                  AND t.distancia_km IS NOT NULL
                  {date_filter}
                GROUP BY t.conductor_id, t.park_id
            )
            SELECT *,
                short_trips::float / NULLIF(total_trips, 0) AS short_ratio,
                total_trips::float / NULLIF(unique_origins, 0) AS origin_concentration,
                total_trips::float / NULLIF(unique_routes, 0) AS route_concentration
            FROM driver_stats
            WHERE total_trips >= %(min_trips)s
              AND avg_distance_m < %(short_dist)s * 2
              AND short_trips::float / NULLIF(total_trips, 0) >= %(short_ratio)s
            ORDER BY short_trips::float / NULLIF(total_trips, 0) DESC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        total = r[2] or 0
        avg_dist = round(float(r[3] or 0), 1)
        avg_dur = round(float(r[4] or 0), 1)
        avg_amount = round(float(r[5] or 0), 2)
        short = r[6] or 0
        short_ratio = round(short / max(total, 1), 4)
        unique_origins = r[8] or 1
        unique_routes = r[9] or 1
        result["drivers_flagged"] += 1

        farming_score = round(short_ratio * 40 + min(total / max(unique_origins, 1), 10) * 3, 1)

        triggered = [{
            "rule_code": "SHORT_TRIP_FARMING_PATTERN",
            "rule_name": "Patron de farming con viajes cortos",
            "severity": "critical",
            "weight": 40,
            "evidence": {
                "total_trips": total,
                "short_trips": short,
                "short_trip_ratio": short_ratio,
                "avg_distance_m": avg_dist,
                "avg_duration_s": avg_dur,
                "avg_amount": avg_amount,
                "unique_origins": unique_origins,
                "unique_routes": unique_routes,
                "origin_concentration": round(total / max(unique_origins, 1), 2),
                "route_concentration": round(total / max(unique_routes, 1), 2),
                "farming_score": farming_score,
            },
        }]
        cas = _create_case_guarded(dry_run, driver_id, pk_id, "critical", 40, triggered, "restrict_driver_review")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_long_trip_outlier_v2(
    date_from=None, date_to=None, park_id=None, window_days=30,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta viajes con distancia/amount/duracion que exceden p90 del baseline."""
    run_code = f"LONG_OUTLIER-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "long_trip_outlier_v2", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "trips_flagged": 0, "cases_created": 0, "dry_run": dry_run}

    baseline = get_baseline_for_trip(park_id or "all", window_days)
    p90_dist = baseline["p90_distance_m"]
    p90_amount = baseline.get("avg_amount", 15000) * 3  # 3x avg como fallback

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"p90_dist": p90_dist * 2, "p90_amount": p90_amount}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            SELECT
                t.conductor_id AS driver_id,
                t.park_id,
                t.codigo_pedido AS trip_id,
                t.precio_yango_pro AS amount,
                t.distancia_km * 1000 AS distance_m,
                EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) AS duration_s,
                t.fecha_inicio_viaje
            FROM {SOURCE} t
            WHERE t.condicion = 'Completado'
              AND t.distancia_km IS NOT NULL
              {date_filter}
              AND (
                  t.distancia_km * 1000 > %(p90_dist)s
                  OR t.precio_yango_pro > %(p90_amount)s
              )
            ORDER BY t.distancia_km DESC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    seen_drivers = set()
    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        amount = float(r[3] or 0)
        distance_m = float(r[4] or 0)
        duration_s = float(r[5] or 0) if r[5] else None
        result["trips_flagged"] += 1

        if driver_id not in seen_drivers:
            seen_drivers.add(driver_id)
            result["drivers_flagged"] += 1

            triggered = [{
                "rule_code": "LONG_TRIP_OUTLIER_V2",
                "rule_name": "Viaje atipico largo (baseline)",
                "severity": "medium",
                "weight": 30,
                "evidence": {
                    "amount": amount,
                    "distance_m": distance_m,
                    "duration_s": duration_s,
                    "baseline_p90_distance_m": p90_dist,
                    "baseline_threshold_amount": p90_amount,
                    "fallback_used": baseline.get("fallback_used", False),
                },
            }]
            cas = _create_case_guarded(dry_run, driver_id, pk_id, "medium", 30, triggered, "monitor")
            if cas and cas.get("id"):
                result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_route_loop_pattern(
    date_from=None, date_to=None, park_id=None, window_days=7,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta patrones A->B, B->A repetidos."""
    run_code = f"ROUTE_LOOP-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "route_loop_pattern", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_flagged": 0, "loops_detected": 0, "cases_created": 0, "dry_run": dry_run}

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"min_loop": LOOP_MIN_COUNT}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        # Detectar loops comparando route_signature con su inversa
        cur.execute(f"""
            WITH parsed AS (
                SELECT
                    t.conductor_id AS driver_id,
                    t.park_id,
                    TRIM(LOWER(SPLIT_PART(t.direccion, '->', 1))) AS origin_raw,
                    TRIM(LOWER(SPLIT_PART(t.direccion, '->', 2))) AS dest_raw,
                    t.fecha_inicio_viaje
                FROM {SOURCE} t
                WHERE t.condicion = 'Completado'
                  AND t.direccion IS NOT NULL
                  AND t.direccion LIKE '%%->%%'
                  {date_filter}
            ),
            routes AS (
                SELECT
                    driver_id, park_id,
                    origin_raw, dest_raw,
                    origin_raw || ' -> ' || dest_raw AS route_a,
                    dest_raw || ' -> ' || origin_raw AS route_b
                FROM parsed
                WHERE origin_raw IS NOT NULL AND dest_raw IS NOT NULL
                  AND origin_raw != dest_raw
            )
            SELECT
                a.driver_id, a.park_id,
                a.route_a, a.route_b,
                COUNT(DISTINCT a.route_a) AS forward_count,
                COUNT(DISTINCT b.route_a) AS reverse_count
            FROM routes a
            JOIN routes b ON a.driver_id = b.driver_id
                AND a.route_a = b.route_b
            GROUP BY a.driver_id, a.park_id, a.route_a, a.route_b
            HAVING COUNT(DISTINCT b.route_a) >= %(min_loop)s
            ORDER BY COUNT(DISTINCT b.route_a) DESC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        route_a = r[2]
        route_b = r[3]
        forward = r[4]
        reverse = r[5]
        result["drivers_flagged"] += 1
        result["loops_detected"] += 1

        triggered = [{
            "rule_code": "ROUTE_LOOP_PATTERN",
            "rule_name": "Patron de bucle de ruta",
            "severity": "high",
            "weight": 35,
            "evidence": {
                "route_a": route_a[:200],
                "route_b": route_b[:200],
                "forward_trips": forward,
                "reverse_trips": reverse,
                "loop_count": min(forward, reverse),
            },
        }]
        cas = _create_case_guarded(dry_run, driver_id, pk_id, "high", 35, triggered, "review")
        if cas and cas.get("id"):
            result["cases_created"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_coordinated_origin_pattern(
    date_from=None, date_to=None, park_id=None, window_days=7,
    dry_run=True, limit=5000
) -> Dict[str, Any]:
    """Detecta multiples drivers distintos saliendo del mismo origen en ventana corta.
    F1F-5B: Calibrado — signal >= 6 drivers, candidate >= 10, case >= 10 + combo.
    F1F-6: Optimized — row count estimation + early exit, date-first filtering,
           high_traffic_origin detection. No longer creates cases for purely high-traffic origins.
    """
    run_code = f"COORD_ORIGIN-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "coordinated_origin_pattern", "D-" + str(window_days), dry_run, date_from, date_to)

    result = make_result(dry_run)
    result["origins_flagged"] = 0
    result["drivers_involved"] = 0

    sig_cfg = get_tier_config("COORDINATED_ORIGIN_PATTERN", TIER_SIGNAL)
    cand_cfg = get_tier_config("COORDINATED_ORIGIN_PATTERN", TIER_CANDIDATE)
    sig_min = sig_cfg.get("min_drivers", 6)
    cand_min = cand_cfg.get("min_drivers", 10)

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"min_drivers": sig_min}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        # ── F1F-6: Row count estimation for early exit ──
        try:
            cur.execute(f"""
                SELECT COUNT(*) FROM {SOURCE} t
                WHERE t.condicion = 'Completado'
                  AND t.direccion IS NOT NULL
                  AND t.direccion LIKE '%%->%%'
                  {date_filter}
            """, params)
            est_rows = cur.fetchone()[0] or 0
        except Exception:
            est_rows = 0

        result["rows_estimated"] = est_rows

        # ── Main query: compute origin clusters with date-first filtering ──
        # The CTE computes origin_cluster_key from direccion.
        # Performance: ~33s at limit=10 on 16M rows due to REGEXP_REPLACE.
        # Optimization: date_filter reduces scanned set; LIMIT applied after aggregation.
        cur.execute(f"""
            WITH parsed AS (
                SELECT
                    t.conductor_id AS driver_id,
                    t.park_id,
                    LEFT(TRIM(LOWER(REGEXP_REPLACE(
                        SPLIT_PART(t.direccion, '->', 1),
                        '[^a-z0-9 ]', '', 'g'
                    ))), 100) AS origin_cluster_key,
                    t.fecha_inicio_viaje
                FROM {SOURCE} t
                WHERE t.condicion = 'Completado'
                  AND t.direccion IS NOT NULL
                  AND t.direccion LIKE '%%->%%'
                  {date_filter}
            )
            SELECT
                park_id,
                origin_cluster_key,
                COUNT(DISTINCT driver_id) AS driver_count,
                ARRAY_AGG(DISTINCT driver_id) AS drivers,
                MIN(fecha_inicio_viaje) AS first_trip,
                MAX(fecha_inicio_viaje) AS last_trip
            FROM parsed
            WHERE origin_cluster_key IS NOT NULL AND LENGTH(origin_cluster_key) >= 3
            GROUP BY park_id, origin_cluster_key
            HAVING COUNT(DISTINCT driver_id) >= %(min_drivers)s
            ORDER BY COUNT(DISTINCT driver_id) DESC
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    # ── F1F-6: High-traffic origin detection ──
    # Origin with > 50 drivers is likely a natural high-traffic location (airport, terminal).
    # These should NOT create cases unless there's additional evidence.
    HIGH_TRAFFIC_THRESHOLD = 50

    for r in rows:
        pk_id = r[0]
        origin_key = r[1]
        driver_count = r[2]
        drivers_list = r[3] or []
        is_high_traffic = driver_count >= HIGH_TRAFFIC_THRESHOLD

        sev = "critical" if driver_count >= cand_min else "high"

        result["origins_flagged"] += 1
        result["drivers_involved"] += driver_count

        # Tier
        if driver_count >= cand_min:
            tier = TIER_CANDIDATE
            result["candidates"] += 1
        else:
            tier = TIER_SIGNAL
            result["signal_flags"] += 1

        if is_high_traffic:
            # High-traffic origin: signal only, NO cases unless candidate tier
            if tier != TIER_CANDIDATE:
                continue

        # Solo crear casos para candidate tier (>=10 drivers) que NO sean high-traffic
        if tier == TIER_CANDIDATE:
            for driver_id in drivers_list[:5]:
                triggered = [{
                    "rule_code": "COORDINATED_ORIGIN_PATTERN",
                    "rule_name": "Patron de origen coordinado",
                    "severity": sev,
                    "weight": 45,
                    "evidence": {
                        "origin_cluster_key": origin_key,
                        "total_drivers_at_origin": driver_count,
                        "high_traffic_origin": is_high_traffic,
                    },
                }]
                case_r = _create_case_guarded(dry_run, driver_id, pk_id, sev, 45, triggered,
                                              "restrict_driver_review", "COORDINATED_ORIGIN_PATTERN")
                if case_r and case_r.get("id"):
                    result["cases_created"] += 1
                elif case_r and case_r.get("suppressed"):
                    result["suppressed"] += 1

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_park_behavior_concentration(
    dry_run=True
) -> Dict[str, Any]:
    """Detecta parks con concentracion de patrones sospechosos (behavioral)."""
    run_code = f"PARK_CONC-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "park_behavior_concentration", "latest", dry_run, None, None)

    result = {"parks_flagged": 0, "cases_created": 0, "dry_run": dry_run}

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT park_id,
                       COUNT(DISTINCT driver_id) AS suspicious_driver_count,
                       COUNT(*) AS case_count
                FROM fraud.risk_cases
                WHERE status = 'open'
                  AND severity IN ('high', 'critical')
                  AND park_id IS NOT NULL
                GROUP BY park_id
                HAVING COUNT(DISTINCT driver_id) >= 3
                ORDER BY COUNT(DISTINCT driver_id) DESC
            """)
            rows = cur.fetchall()
            cur.close()

        for r in rows:
            pk_id = r[0]
            driver_count = r[1]
            result["parks_flagged"] += 1

            if not dry_run:
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO fraud.driver_risk_snapshot
                            (driver_id, park_id, risk_score, severity, triggered_rules,
                             suspicious_trip_count, completed_trip_count,
                             recommended_action, action_reason, computed_at)
                        VALUES ('PARK_LEVEL', %s, %s, 'high',
                            '[{"rule_code":"PARK_CONCENTRATION_RISK_V2"}]'::jsonb,
                            %s, 0, 'monitor', %s::jsonb, now())
                        ON CONFLICT (driver_id, park_id) DO UPDATE SET
                            severity = 'high',
                            triggered_rules = '[{"rule_code":"PARK_CONCENTRATION_RISK_V2"}]'::jsonb,
                            suspicious_trip_count = %s,
                            computed_at = now()
                    """, (
                        pk_id,
                        min(driver_count * 5, 80),
                        driver_count,
                        Json({"suspicious_driver_count": driver_count, "rule": "PARK_CONCENTRATION_RISK_V2"}),
                        driver_count,
                    ))
                    conn.commit()
                    cur.close()
    except Exception:
        pass

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


def routine_behavioral_driver_profile(
    date_from=None, date_to=None, park_id=None, window_days=30,
    dry_run=True, limit=10000
) -> Dict[str, Any]:
    """Construye perfil conductual completo por driver y lo guarda en driver_risk_snapshot."""
    run_code = f"BEHAVIORAL_PROFILE-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    _log_start(run_code, "behavioral_driver_profile", "D-" + str(window_days), dry_run, date_from, date_to)

    result = {"drivers_profiled": 0, "dry_run": dry_run}

    baseline = get_baseline_for_trip(park_id or "all", window_days)

    with get_db() as conn:
        cur = conn.cursor()

        date_filter = "AND t.fecha_inicio_viaje >= NOW() - INTERVAL '%s days'" % window_days
        params = {"short_dist": SHORT_TRIP_DISTANCE_M, "short_dur": SHORT_TRIP_DURATION_S, "min_trips": 3}
        if date_from:
            date_filter = "AND t.fecha_inicio_viaje >= %(date_from)s"
            params["date_from"] = date_from
        if date_to:
            date_filter += " AND t.fecha_inicio_viaje < %(date_to)s"
            params["date_to"] = date_to
        if park_id:
            date_filter += " AND t.park_id = %(park_id)s"
            params["park_id"] = park_id

        cur.execute(f"""
            SELECT
                t.conductor_id AS driver_id,
                t.park_id,
                COUNT(*) AS total_trips,
                AVG(t.distancia_km * 1000) AS avg_distance_m,
                AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS avg_duration_s,
                AVG(t.precio_yango_pro) AS avg_amount,
                COUNT(*) FILTER (
                    WHERE COALESCE(t.distancia_km, 0) * 1000 < %(short_dist)s
                       OR (
                           t.fecha_finalizacion IS NOT NULL
                           AND t.fecha_inicio_viaje IS NOT NULL
                           AND t.fecha_finalizacion > t.fecha_inicio_viaje
                           AND EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) < %(short_dur)s
                       )
                ) AS short_trips,
                VARIANCE(t.distancia_km * 1000) AS var_distance,
                VARIANCE(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje))) AS var_duration,
                COUNT(DISTINCT LEFT(TRIM(LOWER(SPLIT_PART(t.direccion, '->', 1))), 100)) AS unique_origins,
                COUNT(DISTINCT TRIM(LOWER(t.direccion))) AS unique_routes,
                MIN(t.fecha_inicio_viaje) AS first_trip,
                MAX(t.fecha_inicio_viaje) AS last_trip
            FROM {SOURCE} t
            WHERE t.condicion = 'Completado'
              AND t.distancia_km IS NOT NULL
              {date_filter}
            GROUP BY t.conductor_id, t.park_id
            HAVING COUNT(*) >= %(min_trips)s
            LIMIT %(limit)s
        """, {**params, "limit": limit})

        rows = cur.fetchall()
        cur.close()

    for r in rows:
        driver_id = r[0]
        pk_id = r[1]
        total = r[2] or 0
        avg_dist = round(float(r[3] or 0), 1)
        avg_dur = round(float(r[4] or 0), 1)
        avg_amount = round(float(r[5] or 0), 2)
        short = r[6] or 0
        var_dist = round(float(r[7] or 0), 1)
        var_dur = round(float(r[8] or 0), 1)
        unique_origins = r[9] or 0
        unique_routes = r[10] or 0
        card_trips = 0  # card trips feature not available in trips_2026 schema

        short_ratio = round(short / max(total, 1), 4)
        origin_conc = round(total / max(unique_origins, 1), 2)
        route_conc = round(total / max(unique_routes, 1), 2)

        # Behavioral risk score: 0-100
        behavioral_score = 0.0
        behavioral_score += min(short_ratio * 50, 30)
        behavioral_score += min(origin_conc / 10 * 15, 15)
        behavioral_score += min(route_conc / 10 * 15, 15)
        if avg_dist < baseline.get("avg_distance_m", 4000) * 0.3:
            behavioral_score += 20
        if var_dist < (baseline.get("variance_distance", 9_000_000) * 0.05) and var_dist > 0:
            behavioral_score += 20
        behavioral_score = min(behavioral_score, 100)

        profile = {
            "avg_distance_m": avg_dist,
            "avg_duration_s": avg_dur,
            "avg_amount": avg_amount,
            "short_trip_ratio": short_ratio,
            "var_distance": var_dist,
            "var_duration": var_dur,
            "unique_origins": unique_origins,
            "unique_routes": unique_routes,
            "origin_concentration": origin_conc,
            "route_concentration": route_conc,
            "card_trips": card_trips,
            "total_trips_window": total,
            "behavioral_risk_score": round(behavioral_score, 1),
        }

        result["drivers_profiled"] += 1

        # ── F1F-5C: Behavioral Profile Class ──
        profile_class = "normal"
        profile_reason = None
        profile_conf = 0.0
        try:
            from app.services.fraud.fraud_confidence_scoring import compute_behavioral_profile
            snapshot_data = {
                "risk_score": profile["behavioral_risk_score"],
                "severity": "high" if behavioral_score > 60 else ("medium" if behavioral_score > 30 else "low"),
                "triggered_rules": [{"rule_code": "BEHAVIORAL_DRIVER_PROFILE", "severity": "high" if behavioral_score > 60 else "medium"}],
            }
            signals_data = {
                "has_behavioral_flags": behavioral_score > 30,
                "behavioral_risk_score": profile["behavioral_risk_score"],
                "behavioral_severity": "high" if behavioral_score > 60 else ("medium" if behavioral_score > 30 else "low"),
                "triggered_behavioral_rules": ["BEHAVIORAL_DRIVER_PROFILE"],
                "is_candidate": behavioral_score >= 50,
            }
            profile_class, profile_reason, profile_conf = compute_behavioral_profile(snapshot_data, signals_data)
        except Exception:
            pass

        if not dry_run:
            try:
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO fraud.driver_risk_snapshot
                            (driver_id, park_id, risk_score, severity, triggered_rules,
                             suspicious_trip_count, completed_trip_count,
                             recommended_action, action_reason,
                             behavioral_profile_class, behavioral_profile_reason,
                             behavioral_confidence_score,
                             computed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (driver_id, park_id) DO UPDATE SET
                            risk_score = EXCLUDED.risk_score,
                            severity = EXCLUDED.severity,
                            triggered_rules = COALESCE(fraud.driver_risk_snapshot.triggered_rules, '[]'::jsonb) || EXCLUDED.triggered_rules,
                            action_reason = EXCLUDED.action_reason,
                            behavioral_profile_class = EXCLUDED.behavioral_profile_class,
                            behavioral_profile_reason = EXCLUDED.behavioral_profile_reason,
                            behavioral_confidence_score = EXCLUDED.behavioral_confidence_score,
                            computed_at = now()
                    """, (
                        driver_id, pk_id,
                        profile["behavioral_risk_score"],
                        "high" if behavioral_score > 60 else ("medium" if behavioral_score > 30 else "low"),
                        Json([{"rule_code": "BEHAVIORAL_DRIVER_PROFILE", "rule_name": "Perfil conductual", "weight": behavioral_score}]),
                        short, total,
                        "review" if behavioral_score > 60 else "monitor",
                        Json(profile),
                        profile_class,
                        Json(profile_reason) if profile_reason else None,
                        profile_conf,
                    ))
                    conn.commit()
                    cur.close()
            except Exception:
                pass

    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    _log_end(run_code, "completed", elapsed, result)
    return result


# ═══════════════════════════════════════════════════════════════════
# ORQUESTADOR
# ═══════════════════════════════════════════════════════════════════

ROUTINE_MAP = {
    "repeated_origin_pattern": routine_repeated_origin_pattern,
    "repeated_route_signature": routine_repeated_route_signature,
    "low_avg_distance_pattern": routine_low_avg_distance_pattern,
    "low_avg_duration_pattern": routine_low_avg_duration_pattern,
    "extreme_short_trip_ratio": routine_extreme_short_trip_ratio,
    "low_variance_pattern": routine_low_variance_pattern,
    "short_trip_farming": routine_short_trip_farming,
    "long_trip_outlier_v2": routine_long_trip_outlier_v2,
    "route_loop_pattern": routine_route_loop_pattern,
    "coordinated_origin_pattern": routine_coordinated_origin_pattern,
    "park_behavior_concentration": routine_park_behavior_concentration,
    "behavioral_driver_profile": routine_behavioral_driver_profile,
}


def run_trip_behavior_routines(
    date_from=None, date_to=None, park_id=None, driver_id=None,
    window_days=7, dry_run=True, limit=5000,
    routines: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Ejecuta rutinas de comportamiento de viaje.

    F1F-5B: Tracking de tiers (signal_flags, candidates, cases_created, suppressed).
    Reset del contador de casos al inicio.
    """
    _reset_case_counter()

    if routines is None:
        routines = list(ROUTINE_MAP.keys())

    all_results = {
        "dry_run": dry_run,
        "date_from": date_from,
        "date_to": date_to,
        "window_days": window_days,
        "config_version": CONFIG_VERSION,
        "routines": {},
        "total_signal_flags": 0,
        "total_candidates": 0,
        "total_cases_created": 0,
        "total_suppressed": 0,
        "total_drivers_flagged": 0,
        "errors": [],
    }

    for routine_name in routines:
        if routine_name not in ROUTINE_MAP:
            all_results["errors"].append({"routine": routine_name, "error": "unknown_routine"})
            continue

        try:
            fn = ROUTINE_MAP[routine_name]
            if routine_name in ("park_behavior_concentration",):
                res = fn(dry_run=dry_run)
            elif routine_name == "behavioral_driver_profile":
                res = fn(date_from=date_from, date_to=date_to, park_id=park_id,
                        window_days=window_days, dry_run=dry_run, limit=limit)
            else:
                res = fn(date_from=date_from, date_to=date_to, park_id=park_id,
                        window_days=window_days, dry_run=dry_run, limit=limit)
            all_results["routines"][routine_name] = res
            all_results["total_signal_flags"] += res.get("signal_flags", 0)
            all_results["total_candidates"] += res.get("candidates", 0)
            all_results["total_cases_created"] += res.get("cases_created", 0)
            all_results["total_suppressed"] += res.get("suppressed", 0)
            all_results["total_drivers_flagged"] += res.get("drivers_flagged", 0)
        except Exception as e:
            all_results["errors"].append({"routine": routine_name, "error": str(e)})

    return all_results
