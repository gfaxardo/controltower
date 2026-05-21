"""Fase 1F-5C — Case Confidence Score & Behavioral Profile Class.

Computo deterministico de confidence para cases y behavioral profile para drivers.
No ejecuta acciones. Solo ayuda a priorizar revision.
"""
from typing import Dict, Any, List, Optional, Tuple


# ── Valid behavioral_profile_class values ──
PROFILE_NORMAL = "normal"
PROFILE_WATCHLIST = "watchlist"
PROFILE_SUSPICIOUS = "suspicious"
PROFILE_HIGH_RISK = "high_risk"
PROFILE_CRITICAL = "critical_pattern"

VALID_PROFILES = {PROFILE_NORMAL, PROFILE_WATCHLIST, PROFILE_SUSPICIOUS, PROFILE_HIGH_RISK, PROFILE_CRITICAL}


def compute_case_confidence(signal_bundle: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Calcula case_confidence_score 0-100 deterministically.

    signal_bundle debe contener:
      - triggered_rules: List[Dict] con rule_code, severity, evidence
      - trust_tier: str del driver
      - fallback_used: bool opcional
      - sample_size: int opcional
      - has_repeated_origin: bool
      - has_repeated_route: bool
      - has_low_duration: bool
      - has_low_distance: bool
      - has_short_trip_farming: bool
      - has_burst: bool
      - has_coordinated_origin: bool
      - has_critical: bool

    Returns (score, reason_dict).
    """
    score = 0.0
    reasons = []

    triggered = signal_bundle.get("triggered_rules", [])
    if isinstance(triggered, dict):
        triggered = [triggered]
    if not isinstance(triggered, list):
        triggered = []

    trust_tier = signal_bundle.get("trust_tier", "unknown")

    # Count by severity
    high_count = 0
    critical_count = 0
    for r in triggered:
        sev = r.get("severity", "") if isinstance(r, dict) else ""
        if sev == "critical":
            critical_count += 1
        elif sev == "high":
            high_count += 1

    # +20 si driver new_or_unproven
    if trust_tier in ("new_or_unproven", "restricted"):
        score += 20
        reasons.append({"factor": "new_or_unproven_driver", "score_delta": 20})

    # +20 si 2+ high rules
    if high_count >= 2:
        score += 20
        reasons.append({"factor": "2plus_high_rules", "score_delta": 20, "high_count": high_count})

    # +30 si 1 critical rule
    if critical_count >= 1:
        score += 30
        reasons.append({"factor": "critical_rule_present", "score_delta": 30, "critical_count": critical_count})

    # +15 si repeated_route + low_duration/low_distance
    has_rep_route = signal_bundle.get("has_repeated_route", False)
    has_low_dur = signal_bundle.get("has_low_duration", False)
    has_low_dist = signal_bundle.get("has_low_distance", False)
    if has_rep_route and (has_low_dur or has_low_dist):
        score += 15
        reasons.append({"factor": "repeated_route_low_duration_distance", "score_delta": 15})

    # +15 si short_trip_farming candidate
    if signal_bundle.get("has_short_trip_farming", False):
        score += 15
        reasons.append({"factor": "short_trip_farming", "score_delta": 15})

    # +10 si burst_activity
    if signal_bundle.get("has_burst", False):
        score += 10
        reasons.append({"factor": "burst_activity", "score_delta": 10})

    # +10 si coordinated_origin con new drivers
    if signal_bundle.get("has_coordinated_origin", False) and signal_bundle.get("coordinated_new_drivers", False):
        score += 10
        reasons.append({"factor": "coordinated_origin_new_drivers", "score_delta": 10})

    # -20 si solo repeated_origin
    has_rep_origin = signal_bundle.get("has_repeated_origin", False)
    only_rep_origin = has_rep_origin and not (
        has_rep_route or has_low_dur or has_low_dist or
        signal_bundle.get("has_short_trip_farming") or
        signal_bundle.get("has_burst") or
        signal_bundle.get("has_critical")
    )
    if only_rep_origin:
        score -= 20
        reasons.append({"factor": "repeated_origin_only_discount", "score_delta": -20})

    # -15 si high_traffic_origin
    if signal_bundle.get("high_traffic_origin", False):
        score -= 15
        reasons.append({"factor": "high_traffic_origin_discount", "score_delta": -15})

    # -20 si sample bajo o fallback_used=true
    fallback_used = signal_bundle.get("fallback_used", False)
    sample_size = signal_bundle.get("sample_size", 0)
    if fallback_used or sample_size < 30:
        score -= 20
        reasons.append({"factor": "low_sample_or_fallback", "score_delta": -20, "sample_size": sample_size, "fallback_used": fallback_used})

    # Clamp 0-100
    score = max(0.0, min(100.0, score))
    score = round(score, 1)

    # Classification
    if score >= 80:
        confidence_label = "very_high_confidence"
    elif score >= 60:
        confidence_label = "high_confidence"
    elif score >= 40:
        confidence_label = "medium_confidence"
    else:
        confidence_label = "low_confidence"

    return score, {
        "confidence_label": confidence_label,
        "confidence_score": score,
        "factors": reasons,
        "high_rules_count": high_count,
        "critical_rules_count": critical_count,
        "trust_tier": trust_tier,
    }


def compute_behavioral_profile(
    driver_risk_snapshot: Dict[str, Any],
    signals: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], float]:
    """Calcula behavioral_profile_class para un driver.

    driver_risk_snapshot debe contener:
      - risk_score: float
      - severity: str
      - triggered_rules: List[Dict] (rule_code, severity)

    signals debe contener:
      - has_behavioral_flags: bool
      - behavioral_risk_score: float
      - behavioral_severity: str
      - triggered_behavioral_rules: List[str]

    Returns (profile_class, reason_dict, confidence_score).
    """
    risk_score = float(driver_risk_snapshot.get("risk_score", 0) or 0)
    severity = driver_risk_snapshot.get("severity", "low")
    triggered = driver_risk_snapshot.get("triggered_rules", [])
    if isinstance(triggered, dict):
        triggered = [triggered]
    if not isinstance(triggered, list):
        triggered = []

    behavioral_score = float(signals.get("behavioral_risk_score", 0) or 0)

    # Count triggered rule severities
    high_count = 0
    critical_count = 0
    for r in triggered:
        sev = r.get("severity", "") if isinstance(r, dict) else ""
        if sev == "critical":
            critical_count += 1
        elif sev == "high":
            high_count += 1

    # Compute effective score (max of risk_score and behavioral_score)
    effective_score = max(risk_score, behavioral_score)

    profile_class = PROFILE_NORMAL
    reason_parts = []

    # critical_pattern: score >= 85 o critical rule confirmada
    if effective_score >= 85 or critical_count >= 1:
        profile_class = PROFILE_CRITICAL
        reason_parts.append(f"effective_score={effective_score}, critical_rules={critical_count}")
    # high_risk: score 70-84 o 2+ high rules
    elif effective_score >= 70 or high_count >= 2:
        profile_class = PROFILE_HIGH_RISK
        reason_parts.append(f"effective_score={effective_score}, high_rules={high_count}")
    # suspicious: score 50-69 o candidate
    elif effective_score >= 50 or signals.get("is_candidate", False):
        profile_class = PROFILE_SUSPICIOUS
        reason_parts.append(f"effective_score={effective_score}, candidate={signals.get('is_candidate', False)}")
    # watchlist: score 30-49 o flags debiles
    elif effective_score >= 30 or signals.get("has_behavioral_flags", False):
        profile_class = PROFILE_WATCHLIST
        reason_parts.append(f"effective_score={effective_score}, behavioral_flags={signals.get('has_behavioral_flags', False)}")
    # normal: score < 30 y sin high/critical
    else:
        reason_parts.append(f"effective_score={effective_score}, no_high_no_critical")

    # Confidence score for profile: maps profile to mid-range confidence
    profile_confidence = {
        PROFILE_NORMAL: 10.0,
        PROFILE_WATCHLIST: 30.0,
        PROFILE_SUSPICIOUS: 55.0,
        PROFILE_HIGH_RISK: 75.0,
        PROFILE_CRITICAL: 92.0,
    }.get(profile_class, 0.0)

    # Adjust by severity match
    if severity in ("high", "critical") and profile_class in (PROFILE_NORMAL, PROFILE_WATCHLIST):
        profile_confidence = min(profile_confidence + 20, 100)

    reason = {
        "profile_class": profile_class,
        "effective_score": effective_score,
        "risk_score": risk_score,
        "behavioral_score": behavioral_score,
        "severity": severity,
        "high_rules_count": high_count,
        "critical_rules_count": critical_count,
        "reason": " / ".join(reason_parts),
    }

    return profile_class, reason, round(profile_confidence, 1)


def build_signal_bundle(
    triggered_rules: List[Dict],
    trust_tier: str = "unknown",
    fallback_used: bool = False,
    sample_size: int = 0,
    high_traffic_origin: bool = False,
    coordinated_new_drivers: bool = False,
) -> Dict[str, Any]:
    """Construye signal_bundle desde triggered_rules para compute_case_confidence.

    Extrae automaticamente los flags desde los rule_codes presentes.
    """
    rule_codes = [
        r.get("rule_code", "") if isinstance(r, dict) else ""
        for r in triggered_rules
    ]

    return {
        "triggered_rules": triggered_rules,
        "trust_tier": trust_tier,
        "fallback_used": fallback_used,
        "sample_size": sample_size,
        "high_traffic_origin": high_traffic_origin,
        "coordinated_new_drivers": coordinated_new_drivers,
        "has_repeated_origin": "REPEATED_ORIGIN_PATTERN" in rule_codes,
        "has_repeated_route": "REPEATED_ROUTE_SIGNATURE" in rule_codes,
        "has_low_duration": "LOW_AVG_DURATION_PATTERN" in rule_codes,
        "has_low_distance": "LOW_AVG_DISTANCE_PATTERN" in rule_codes,
        "has_short_trip_farming": "SHORT_TRIP_FARMING_PATTERN" in rule_codes,
        "has_burst": any(c in rule_codes for c in ["BURST_ACTIVITY_NEW_DRIVER", "BURST_ACTIVITY_NEW_DRIVER_V2"]),
        "has_coordinated_origin": "COORDINATED_ORIGIN_PATTERN" in rule_codes,
        "has_critical": any(
            (isinstance(r, dict) and r.get("severity") == "critical")
            for r in triggered_rules
        ),
    }
