"""Fase 1F-8 — Autocobro Eligibility Service.

Calcula elegibilidad de autocobro para cada driver usando politica deterministica.
Soporta dry_run. NO ejecuta accion real de autocobro.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.db.connection import get_db
from psycopg2.extras import Json


DEFAULT_POLICY = "autocobro_v1_preview"

STATUS_ORDER = {
    "unknown": 0,
    "restricted": 1,
    "review_required": 2,
    "eligible": 3,
}

RESTRICTED_ACTIONS = {"restrict_driver_review", "disable_autocobro", "hold_bonus_review"}


def _load_policy_config(policy_version: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT policy_config FROM fraud.autocobro_eligibility_policy
            WHERE policy_version = %s AND enabled = true
            LIMIT 1
        """, (policy_version,))
        row = cur.fetchone()
        cur.close()
    if not row:
        raise ValueError(f"Policy version not found or disabled: {policy_version}")
    return row[0] or {}


def _fetch_driver_signals(driver_id: str, park_id: str = None) -> Dict[str, Any]:
    signals = {
        "driver_id": driver_id,
        "park_id": park_id,
        "trust_tier": None,
        "total_completed_trips": 0,
        "first_completed_trip_at": None,
        "behavioral_profile_class": None,
        "behavioral_confidence_score": None,
        "risk_score": None,
        "severity": None,
        "recommended_action": None,
        "synthetic_identity": False,
        "short_trip_farming": False,
        "high_card_new_driver": False,
        "open_case_count": 0,
        "high_case_count": 0,
        "critical_case_count": 0,
        "max_case_confidence_score": None,
        "is_fraud_candidate": False,
    }

    with get_db() as conn:
        cur = conn.cursor()

        # Trust snapshot
        cur.execute("""
            SELECT trust_tier, total_completed_trips, first_completed_trip_at
            FROM fraud.driver_trust_snapshot
            WHERE driver_id = %s
        """, (driver_id,))
        trust = cur.fetchone()
        if trust:
            signals["trust_tier"] = trust[0]
            signals["total_completed_trips"] = trust[1] or 0
            signals["first_completed_trip_at"] = trust[2]

        # Risk snapshot
        cur.execute("""
            SELECT behavioral_profile_class, behavioral_confidence_score,
                   risk_score, severity, recommended_action
            FROM fraud.driver_risk_snapshot
            WHERE driver_id = %s
        """, (driver_id,))
        risk = cur.fetchone()
        if risk:
            signals["behavioral_profile_class"] = risk[0]
            signals["behavioral_confidence_score"] = float(risk[1]) if risk[1] is not None else None
            signals["risk_score"] = float(risk[2]) if risk[2] is not None else None
            signals["severity"] = risk[3]
            signals["recommended_action"] = risk[4]

        # Open cases
        cur.execute("""
            SELECT COUNT(*) AS open_count,
                   COUNT(*) FILTER (WHERE severity = 'high') AS high_count,
                   COUNT(*) FILTER (WHERE severity = 'critical') AS critical_count,
                   COALESCE(MAX(case_confidence_score), 0) AS max_confidence
            FROM fraud.risk_cases
            WHERE driver_id = %s AND status = 'open'
        """, (driver_id,))
        case_row = cur.fetchone()
        if case_row:
            signals["open_case_count"] = case_row[0] or 0
            signals["high_case_count"] = case_row[1] or 0
            signals["critical_case_count"] = case_row[2] or 0
            mx = float(case_row[3]) if case_row[3] is not None else None
            signals["max_case_confidence_score"] = mx

        # Is fraud candidate (has suspicious_trip_count or high risk_score)
        if signals["risk_score"] is not None and signals["risk_score"] >= 50:
            signals["is_fraud_candidate"] = True

        # Synthetic identity check via payment_identity_source
        try:
            cur.execute("""
                SELECT COUNT(*) FROM fraud.payment_identity_source
                WHERE driver_id = %s AND is_synthetic = true
            """, (driver_id,))
            syn = cur.fetchone()
            if syn and syn[0] > 0:
                signals["synthetic_identity"] = True
        except Exception:
            pass

        # Short trip farming check via trip_risk_features (D-30)
        try:
            cur.execute("""
                SELECT COUNT(*) FROM fraud.trip_risk_features
                WHERE driver_id = %s
                  AND computed_at >= NOW() - INTERVAL '30 days'
                  AND triggered_rules::text ILIKE '%short_trip_farming%'
            """, (driver_id,))
            stf = cur.fetchone()
            if stf and stf[0] > 0:
                signals["short_trip_farming"] = True
        except Exception:
            pass

        # High card amount new driver check
        try:
            cur.execute("""
                SELECT COUNT(*) FROM fraud.trip_risk_features
                WHERE driver_id = %s
                  AND computed_at >= NOW() - INTERVAL '30 days'
                  AND triggered_rules::text ILIKE '%high_card_amount_new_driver%'
            """, (driver_id,))
            hca = cur.fetchone()
            if hca and hca[0] > 0:
                signals["high_card_new_driver"] = True
        except Exception:
            pass

        cur.close()

    return signals


def _rule_matches(rule: Dict[str, Any], signals: Dict[str, Any]) -> bool:
    """Evalua si una regla individual se cumple contra las senales."""
    field = rule.get("field")
    op = rule.get("op")
    value = rule.get("value")
    condition = rule.get("condition")

    if condition:
        if condition == "trust_tier_eq_new_or_unproven AND total_completed_trips_gte_30":
            return signals.get("trust_tier") == "new_or_unproven" and signals.get("total_completed_trips", 0) >= 30
        elif condition == "open_medium_cases_confidence_30_59":
            return (signals.get("open_case_count", 0) > 0
                    and signals.get("max_case_confidence_score") is not None
                    and 30 <= signals["max_case_confidence_score"] <= 59)
        elif condition == "is_fraud_candidate_no_high_critical_cases":
            return (signals.get("is_fraud_candidate")
                    and signals.get("high_case_count", 0) == 0
                    and signals.get("critical_case_count", 0) == 0)
        elif condition == "behavioral_profile_null_but_trusted_50plus":
            return (signals.get("behavioral_profile_class") is None
                    and signals.get("trust_tier") == "trusted"
                    and signals.get("total_completed_trips", 0) >= 50)
        # F1F-9 new conditions
        elif condition == "trusted_40_49_trips_normal_profile_no_cases":
            return (signals.get("trust_tier") == "trusted"
                    and 40 <= signals.get("total_completed_trips", 0) <= 49
                    and signals.get("behavioral_profile_class") in ("normal", "watchlist")
                    and signals.get("high_case_count", 0) == 0
                    and signals.get("critical_case_count", 0) == 0)
        elif condition == "new_or_unproven_40_49_trips_normal_profile_no_cases":
            return (signals.get("trust_tier") == "new_or_unproven"
                    and 40 <= signals.get("total_completed_trips", 0) <= 49
                    and signals.get("behavioral_profile_class") in ("normal", "watchlist")
                    and signals.get("high_case_count", 0) == 0
                    and signals.get("critical_case_count", 0) == 0)
        elif condition == "trusted_50plus_no_risk_snapshot":
            return (signals.get("trust_tier") == "trusted"
                    and signals.get("total_completed_trips", 0) >= 50
                    and signals.get("behavioral_profile_class") is None
                    and signals.get("risk_score") is None)
        elif condition == "trusted_50plus_in_risk_snapshot_no_profile":
            return (signals.get("trust_tier") == "trusted"
                    and signals.get("total_completed_trips", 0) >= 50
                    and signals.get("behavioral_profile_class") is None
                    and signals.get("risk_score") is not None)
        return False

    if field is None:
        return False

    field_val = signals.get(field)

    if op == "eq":
        return field_val == value
    elif op == "in":
        return field_val in (value or [])
    elif op == "not_in":
        return field_val not in (value or [])
    elif op == "gte":
        return field_val is not None and field_val >= value
    elif op == "gt":
        return field_val is not None and field_val > value
    elif op == "lt":
        return field_val is None or field_val < value
    elif op == "is_null":
        return field_val is None
    return False


def _evaluate_eligibility(signals: Dict[str, Any], policy_config: Dict[str, Any]) -> Dict[str, Any]:
    rules = policy_config.get("rules", {})
    evaluation_order = policy_config.get("evaluation_order", ["unknown", "restricted", "review_required", "eligible"])
    matched_rules = []
    status = "unclassified"  # F1F-9: default is unclassified, not eligible

    for category in evaluation_order:
        cat_rules = rules.get(category, [])
        if not cat_rules:
            continue

        if category == "eligible":
            # AND: todas las reglas deben cumplirse
            all_match = True
            for rule in cat_rules:
                if not _rule_matches(rule, signals):
                    all_match = False
                    break
            if all_match:
                status = category
                matched_rules = [r.get("id", "") for r in cat_rules]
                break
        else:
            # OR: al menos una regla debe cumplirse
            cat_matches = []
            for rule in cat_rules:
                if _rule_matches(rule, signals):
                    cat_matches.append(rule.get("id", ""))
            if cat_matches:
                status = category
                matched_rules = cat_matches
                break

    return {
        "status": status,
        "matched_rules": matched_rules,
        "signals_snapshot": {
            "trust_tier": signals.get("trust_tier"),
            "total_completed_trips": signals.get("total_completed_trips"),
            "behavioral_profile_class": signals.get("behavioral_profile_class"),
            "behavioral_confidence_score": signals.get("behavioral_confidence_score"),
            "open_high_cases": signals.get("high_case_count", 0),
            "open_critical_cases": signals.get("critical_case_count", 0),
            "max_case_confidence": signals.get("max_case_confidence_score"),
            "recommended_action": signals.get("recommended_action"),
            "synthetic_identity": signals.get("synthetic_identity"),
            "short_trip_farming": signals.get("short_trip_farming"),
            "high_card_new_driver": signals.get("high_card_new_driver"),
        },
    }


def compute_driver_autocobro_eligibility(
    driver_id: str, park_id: str = None, policy_version: str = DEFAULT_POLICY,
) -> Dict[str, Any]:
    """Calcula elegibilidad de autocobro para un driver.

    NO modifica estado real de autocobro.
    """
    policy_config = _load_policy_config(policy_version)
    signals = _fetch_driver_signals(driver_id, park_id)
    eligibility = _evaluate_eligibility(signals, policy_config)

    trace = {
        "driver_id": driver_id,
        "park_id": park_id,
        "policy_version": policy_version,
        "eligibility_status": eligibility["status"],
        "eligibility_reason": {
            "status": eligibility["status"],
            "matched_rules": eligibility["matched_rules"],
            "signals": eligibility["signals_snapshot"],
            "computed_at": datetime.now().isoformat(),
            "policy_version": policy_version,
        },
        "trust_tier": signals["trust_tier"],
        "total_completed_trips": signals["total_completed_trips"],
        "behavioral_profile_class": signals["behavioral_profile_class"],
        "behavioral_confidence_score": signals["behavioral_confidence_score"],
        "max_case_confidence_score": signals["max_case_confidence_score"],
        "open_case_count": signals["open_case_count"],
        "high_case_count": signals["high_case_count"],
        "critical_case_count": signals["critical_case_count"],
        "recommended_action": signals["recommended_action"],
    }

    return trace


def recompute_autocobro_eligibility(
    policy_version: str = DEFAULT_POLICY,
    dry_run: bool = True,
    limit: int = None,
    park_id: str = None,
) -> Dict[str, Any]:
    """Re-computa elegibilidad de autocobro para todo el universo de drivers.

    F1F-8: Bulk-optimized. Fetch all signals in 3 queries, evaluate in Python,
    bulk INSERT results. Si dry_run=False, escribe en fraud.autocobro_eligibility_snapshot.
    """
    policy_config = _load_policy_config(policy_version)

    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    with get_db() as conn:
        cur = conn.cursor()

        # 1. Fetch all trust snapshots
        cur.execute(f"""
            SELECT driver_id, park_id, trust_tier, total_completed_trips
            FROM fraud.driver_trust_snapshot
            ORDER BY driver_id
            {limit_clause}
        """)
        trust_rows = cur.fetchall()

        driver_ids = [r[0] for r in trust_rows]

        # 2. Fetch all risk snapshots for these drivers
        cur.execute("""
            SELECT driver_id, behavioral_profile_class, behavioral_confidence_score,
                   risk_score, severity, recommended_action
            FROM fraud.driver_risk_snapshot
            WHERE driver_id = ANY(%s)
        """, (driver_ids,))
        risk_rows = cur.fetchall()
        risk_by_driver = {r[0]: r for r in risk_rows}

        # 3. Fetch open case counts for these drivers
        cur.execute("""
            SELECT driver_id,
                   COUNT(*) AS open_count,
                   COUNT(*) FILTER (WHERE severity = 'high') AS high_count,
                   COUNT(*) FILTER (WHERE severity = 'critical') AS critical_count,
                   COALESCE(MAX(case_confidence_score), 0) AS max_confidence
            FROM fraud.risk_cases
            WHERE status = 'open' AND driver_id = ANY(%s)
            GROUP BY driver_id
        """, (driver_ids,))
        case_rows = cur.fetchall()
        cases_by_driver = {r[0]: r for r in case_rows}

        cur.close()

    total_evaluated = 0
    distribution = {"eligible": 0, "review_required": 0, "restricted": 0, "unknown": 0}
    top_reasons = {}
    errors = []
    snapshots = []

    for trust_row in trust_rows:
        driver_id = trust_row[0]
        park_id = trust_row[1]

        try:
            # Build signals from bulk-fetched data
            risk = risk_by_driver.get(driver_id)
            case = cases_by_driver.get(driver_id)

            signals = {
                "driver_id": driver_id,
                "park_id": park_id,
                "trust_tier": trust_row[2],
                "total_completed_trips": trust_row[3] or 0,
                "behavioral_profile_class": risk[1] if risk else None,
                "behavioral_confidence_score": float(risk[2]) if risk and risk[2] is not None else None,
                "risk_score": float(risk[3]) if risk and risk[3] is not None else None,
                "severity": risk[4] if risk else None,
                "recommended_action": risk[5] if risk else None,
                "synthetic_identity": False,
                "short_trip_farming": False,
                "high_card_new_driver": False,
                "open_case_count": case[1] if case else 0,
                "high_case_count": case[2] if case else 0,
                "critical_case_count": case[3] if case else 0,
                "max_case_confidence_score": float(case[4]) if case and case[4] is not None and case[4] > 0 else None,
                "is_fraud_candidate": False,
            }

            if signals["risk_score"] is not None and signals["risk_score"] >= 50:
                signals["is_fraud_candidate"] = True

            eligibility = _evaluate_eligibility(signals, policy_config)
            total_evaluated += 1
            status = eligibility["status"]
            distribution[status] = distribution.get(status, 0) + 1

            reason_summary = ", ".join(eligibility.get("matched_rules", [])[:3]) or status
            top_reasons[reason_summary] = top_reasons.get(reason_summary, 0) + 1

            if not dry_run:
                snapshots.append((
                    driver_id, park_id, policy_version,
                    status,
                    Json({
                        "status": status,
                        "matched_rules": eligibility["matched_rules"],
                        "signals": eligibility["signals_snapshot"],
                        "computed_at": datetime.now().isoformat(),
                        "policy_version": policy_version,
                    }),
                    signals["trust_tier"],
                    signals["total_completed_trips"],
                    signals["behavioral_profile_class"],
                    signals["behavioral_confidence_score"],
                    signals["max_case_confidence_score"],
                    signals["open_case_count"],
                    signals["high_case_count"],
                    signals["critical_case_count"],
                    signals["recommended_action"],
                ))
        except Exception as e:
            errors.append({"driver_id": driver_id, "error": str(e)})

    if not dry_run and snapshots:
        with get_db() as conn:
            cur = conn.cursor()
            from psycopg2.extras import execute_values
            execute_values(cur, """
                INSERT INTO fraud.autocobro_eligibility_snapshot
                    (driver_id, park_id, policy_version, eligibility_status,
                     eligibility_reason, trust_tier, total_completed_trips,
                     behavioral_profile_class, behavioral_confidence_score,
                     max_case_confidence_score, open_case_count, high_case_count,
                     critical_case_count, recommended_action)
                VALUES %s
                ON CONFLICT (driver_id, park_id, policy_version) DO UPDATE SET
                    eligibility_status = EXCLUDED.eligibility_status,
                    eligibility_reason = EXCLUDED.eligibility_reason,
                    trust_tier = EXCLUDED.trust_tier,
                    total_completed_trips = EXCLUDED.total_completed_trips,
                    behavioral_profile_class = EXCLUDED.behavioral_profile_class,
                    behavioral_confidence_score = EXCLUDED.behavioral_confidence_score,
                    max_case_confidence_score = EXCLUDED.max_case_confidence_score,
                    open_case_count = EXCLUDED.open_case_count,
                    high_case_count = EXCLUDED.high_case_count,
                    critical_case_count = EXCLUDED.critical_case_count,
                    recommended_action = EXCLUDED.recommended_action,
                    computed_at = now()
            """, snapshots)
            conn.commit()
            cur.close()

    top = sorted(top_reasons.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "policy_version": policy_version,
        "dry_run": dry_run,
        "total_evaluated": total_evaluated,
        "distribution": distribution,
        "top_reasons": [{"reason": r, "count": c} for r, c in top],
        "errors": errors,
        "actions_executed": 0,
        "external_execution": False,
    }


def get_autocobro_eligibility_summary(policy_version: str = DEFAULT_POLICY) -> Dict[str, Any]:
    """Resumen de distribucion de elegibilidad desde snapshot."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT eligibility_status, COUNT(*)
            FROM fraud.autocobro_eligibility_snapshot
            WHERE policy_version = %s
            GROUP BY eligibility_status
            ORDER BY COUNT(*) DESC
        """, (policy_version,))
        rows = cur.fetchall()

        cur.execute("""
            SELECT MAX(computed_at) FROM fraud.autocobro_eligibility_snapshot
            WHERE policy_version = %s
        """, (policy_version,))
        last_computed = cur.fetchone()
        cur.close()

    distribution = {}
    total = 0
    for row in rows:
        distribution[row[0]] = row[1]
        total += row[1]

    return {
        "policy_version": policy_version,
        "total": total,
        "distribution": distribution,
        "computed_at": last_computed[0].isoformat() if last_computed and last_computed[0] else None,
        "mode": "preview_only",
    }


def get_autocobro_eligibility_list(
    policy_version: str = DEFAULT_POLICY,
    status: str = None,
    park_id: str = None,
    driver_id: str = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Lista de elegibilidad con filtros."""
    conditions = ["policy_version = %(policy)s"]
    params: Dict[str, Any] = {"policy": policy_version, "limit": limit, "offset": offset}

    if status:
        conditions.append("eligibility_status = %(status)s")
        params["status"] = status
    if park_id:
        conditions.append("park_id = %(park_id)s")
        params["park_id"] = park_id
    if driver_id:
        conditions.append("driver_id = %(driver_id)s")
        params["driver_id"] = driver_id

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT driver_id, park_id, eligibility_status, trust_tier,
                   total_completed_trips, behavioral_profile_class,
                   max_case_confidence_score, open_case_count,
                   recommended_action, eligibility_reason, computed_at
            FROM fraud.autocobro_eligibility_snapshot
            WHERE {where_clause}
            ORDER BY computed_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """, params)
        rows = cur.fetchall()
        cur.close()

    return [
        {
            "driver_id": r[0],
            "park_id": r[1],
            "eligibility_status": r[2],
            "trust_tier": r[3],
            "total_completed_trips": r[4],
            "behavioral_profile_class": r[5],
            "max_case_confidence_score": float(r[6]) if r[6] is not None else None,
            "open_case_count": r[7],
            "recommended_action": r[8],
            "reason_summary": ", ".join((r[9] or {}).get("matched_rules", [])[:3]) if r[9] else None,
            "computed_at": r[10].isoformat() if r[10] else None,
        }
        for r in rows
    ]
