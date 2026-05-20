"""Fase 1F-5B — Seed calibrated thresholds into fraud.rule_threshold_config."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import Json

CONFIG_VERSION = "trip_behavior_v1_calibrated"
RATIONALE = "Calibrado con distribuciones reales D-7 (2026-05-13 a 2026-05-20). p99 repeated_origin=3, p99 repeated_route=2, p99 short_ratio=14%, p95 coordinated_origin=4 drivers."

THRESHOLDS = [
    {
        "rule_code": "REPEATED_ORIGIN_PATTERN",
        "config": {
            "signal_flag": {"min_count": 3, "window_days": 7, "tier": "signal"},
            "fraud_candidate": {"min_count": 5, "window_days": 7, "tier": "candidate", "requires_trust": "new_or_unproven"},
            "risk_case": {"min_count": 5, "window_days": 7, "tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ROUTE_SIGNATURE", "LOW_AVG_DURATION_PATTERN", "LOW_AVG_DISTANCE_PATTERN", "EXTREME_SHORT_TRIP_RATIO", "BURST_ACTIVITY_NEW_DRIVER"]},
        },
    },
    {
        "rule_code": "REPEATED_ROUTE_SIGNATURE",
        "config": {
            "signal_flag": {"min_count": 2, "window_days": 7, "tier": "signal"},
            "fraud_candidate": {"min_count": 3, "window_days": 7, "tier": "candidate"},
            "risk_case": {"min_count": 3, "window_days": 7, "tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN", "LOW_AVG_DURATION_PATTERN", "LOW_AVG_DISTANCE_PATTERN"]},
        },
    },
    {
        "rule_code": "SHORT_TRIP_FARMING_PATTERN",
        "config": {
            "short_trip_distance_m": 2000,
            "short_trip_duration_s": 180,
            "signal_flag": {"short_trip_ratio": 0.15, "min_trips": 5, "tier": "signal"},
            "fraud_candidate": {"short_trip_ratio": 0.25, "min_trips": 5, "tier": "candidate"},
            "risk_case": {"short_trip_ratio": 0.25, "min_trips": 5, "tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN", "REPEATED_ROUTE_SIGNATURE", "BURST_ACTIVITY_NEW_DRIVER"]},
        },
    },
    {
        "rule_code": "ROUTE_LOOP_PATTERN",
        "config": {
            "signal_flag": {"min_loop_count": 2, "window_days": 7, "tier": "signal"},
            "fraud_candidate": {"min_loop_count": 3, "window_days": 7, "tier": "candidate"},
            "risk_case": {"min_loop_count": 3, "window_days": 7, "tier": "case", "requires_combo": True, "requires_trust": "new_or_unproven"},
        },
    },
    {
        "rule_code": "COORDINATED_ORIGIN_PATTERN",
        "config": {
            "signal_flag": {"min_drivers": 6, "window_days": 1, "tier": "signal"},
            "fraud_candidate": {"min_drivers": 10, "window_days": 1, "tier": "candidate"},
            "risk_case": {"min_drivers": 10, "window_days": 1, "tier": "case", "requires_combo": True, "requires_trust_ratio": 0.5},
        },
    },
    {
        "rule_code": "LOW_AVG_DISTANCE_PATTERN",
        "config": {
            "signal_flag": {"percentile": "p10", "multiplier": 1.0, "min_trips": 5, "tier": "signal"},
            "fraud_candidate": {"ratio": 0.35, "min_trips": 5, "tier": "candidate"},
            "risk_case": {"tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN", "REPEATED_ROUTE_SIGNATURE"]},
        },
    },
    {
        "rule_code": "LOW_AVG_DURATION_PATTERN",
        "config": {
            "signal_flag": {"percentile": "p10", "multiplier": 1.0, "min_trips": 5, "tier": "signal"},
            "fraud_candidate": {"ratio": 0.35, "min_trips": 5, "tier": "candidate"},
            "risk_case": {"tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN", "REPEATED_ROUTE_SIGNATURE"]},
        },
    },
    {
        "rule_code": "EXTREME_SHORT_TRIP_RATIO",
        "config": {
            "signal_flag": {"ratio": 0.15, "min_trips": 5, "tier": "signal"},
            "fraud_candidate": {"ratio": 0.25, "min_trips": 5, "tier": "candidate"},
            "risk_case": {"ratio": 0.25, "min_trips": 5, "tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN", "LOW_AVG_DISTANCE_PATTERN"]},
        },
    },
    {
        "rule_code": "LOW_VARIANCE_PATTERN",
        "config": {
            "signal_flag": {"percentile": "p10", "min_trips": 10, "tier": "signal"},
            "fraud_candidate": {"percentile": "p05", "min_trips": 10, "tier": "candidate"},
            "risk_case": {"tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN", "REPEATED_ROUTE_SIGNATURE", "SHORT_TRIP_FARMING_PATTERN"]},
        },
    },
    {
        "rule_code": "BURST_ACTIVITY_NEW_DRIVER",
        "config": {
            "signal_flag": {"trips_24h_pctl": "p90", "window_days": 7, "tier": "signal"},
            "fraud_candidate": {"trips_24h_pctl": "p95", "window_days": 7, "tier": "candidate"},
            "risk_case": {"trips_24h_pctl": "p99", "window_days": 7, "tier": "case", "requires_combo": True, "requires_trust": "new_or_unproven"},
        },
    },
    {
        "rule_code": "TIME_WINDOW_DENSITY",
        "config": {
            "signal_flag": {"trips_24h_pctl": "p95", "window_days": 7, "tier": "signal"},
            "fraud_candidate": {"trips_24h_pctl": "p99", "window_days": 7, "tier": "candidate"},
            "risk_case": {"tier": "case", "requires_combo": True, "combo_rules": ["REPEATED_ORIGIN_PATTERN"]},
        },
    },
]

# Fallback baseline thresholds (used when sample < 30)
BASELINE_FALLBACK = {
    "avg_distance_m": 7000,
    "avg_duration_s": 1400,
    "p10_distance_m": 2500,
    "p10_duration_s": 500,
    "p90_distance_m": 11200,
    "p95_distance_m": 13600,
    "variance_p50": 13525824560932,
    "trips_24h_p50": 6, "trips_24h_p90": 23, "trips_24h_p95": 28, "trips_24h_p99": 41,
}

# Case creation guardrails
CASE_GUARDRAILS = {
    "max_cases_per_run": 50,
    "max_cases_per_rule": 20,
    "max_cases_per_park": 10,
    "max_cases_per_driver": 1,
    "min_risk_score_for_case": 60,
    "create_case_if": "risk_score >= 80 OR (2+ high severity rules) OR (1 critical + new_or_unproven) OR HIGH_CARD_AMOUNT_NEW_DRIVER OR SHORT_TRIP_FARMING candidate with combo evidence",
    "suppression_reason": "exceeded_max_limits",
}


def seed():
    with get_db() as conn:
        cur = conn.cursor()

        for t in THRESHOLDS:
            cur.execute("""
                INSERT INTO fraud.rule_threshold_config
                    (rule_code, config_version, enabled, threshold_config, rationale, created_by)
                VALUES (%s, %s, true, %s, %s, 'system')
                ON CONFLICT (rule_code, config_version) DO UPDATE SET
                    threshold_config = EXCLUDED.threshold_config,
                    rationale = EXCLUDED.rationale
            """, (t["rule_code"], CONFIG_VERSION, Json(t["config"]), RATIONALE))

        # Insert guardrails as a special rule
        cur.execute("""
            INSERT INTO fraud.rule_threshold_config
                (rule_code, config_version, enabled, threshold_config, rationale, created_by)
            VALUES ('CASE_CREATION_GUARDRAILS', %s, true, %s, %s, 'system')
            ON CONFLICT (rule_code, config_version) DO UPDATE SET
                threshold_config = EXCLUDED.threshold_config,
                rationale = EXCLUDED.rationale
        """, (CONFIG_VERSION, Json(CASE_GUARDRAILS), "Global case creation limits and policy"))

        conn.commit()
        cur.close()

    print(f"Seeded {len(THRESHOLDS)} thresholds + guardrails for version {CONFIG_VERSION}")


if __name__ == "__main__":
    seed()
