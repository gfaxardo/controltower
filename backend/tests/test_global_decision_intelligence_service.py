"""
Tests Global Decision Intelligence Layer (FASE 4.4) — sólo priorización global.

Sin ejecución; valida QA del spec (heurística v1 con strategic weights, saturación,
portfolio roles, dedup y trazabilidad). No toca engines previos.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.services.global_decision_intelligence_service import (
    POLICY_TYPE,
    POLICY_VERSION,
    STRATEGIC_WEIGHT_RULES,
    build_global_decision_queue,
    merge_integrity_with_global_decision_check,
    safe_build_global_decision_queue,
)


def _reco(
    *,
    entity: str,
    action_type: str,
    decision_score: float = 70.0,
    confidence: str = "medium",
    contextual_suggestion_id: str = "",
    action_name: str = None,
) -> Dict[str, Any]:
    return {
        "recommendation_id": f"rid-{entity}-{action_type}",
        "entity": entity,
        "recommended_action": {
            "action_type": action_type,
            "action_name": action_name or action_type,
        },
        "decision_status": "recommended",
        "decision_score": decision_score,
        "decision_factors": {
            "impact_score": 70.0,
            "speed_score": 90.0 if action_type.startswith("productivity") else 60.0,
            "operational_complexity_score": 80.0 if action_type.startswith("productivity") else 60.0,
            "confidence_score": 80.0,
            "cost_efficiency_score": 70.0,
        },
        "decision_constraints": {
            "requires_manual_validation": True,
            "execution_enabled": False,
            "data_confidence": confidence,
        },
        "contextual_suggestion_id": contextual_suggestion_id,
        "policy_trace": {"policy_version": "v1"},
    }


def _ctx(
    *,
    suggestion_id: str,
    leverage: float = 60.0,
    gap_recovery_pct: float = 8.0,
    weekly_recovery: float = 200.0,
    confidence: str = "medium",
    segment_label: str = "0–5 viajes / sem ISO",
    segment_drivers: int = 120,
) -> Dict[str, Any]:
    return {
        "suggestion_id": suggestion_id,
        "operational_leverage_score": leverage,
        "estimated_recovery": {
            "potential_gap_recovery_pct": gap_recovery_pct,
            "potential_trips_recovered_weekly": weekly_recovery,
            "recovery_method": "unit_test",
            "confidence_reason": "synthetic",
        },
        "operational_pool": {
            "segments": [
                {
                    "segment_id": "low_activity_0_5_7d",
                    "drivers": segment_drivers,
                    "display_name": segment_label,
                }
            ],
        },
        "confidence": confidence,
        "contextual_reasoning": {"main_problem_detected": "synthetic"},
    }


def _alert(
    *,
    entity: str,
    country: str = "Peru",
    city: str = "Lima",
    business_slice: str = "Auto Regular",
    gap_pct: float = 6.0,
    gap_trips: float = 1500.0,
    ytd_trend: str = "stable",
    pacing: str = "behind",
    principal_driver: str = "productivity",
) -> Dict[str, Any]:
    return {
        "entity": entity,
        "country": country,
        "city": city,
        "business_slice": business_slice,
        "gap_pct": gap_pct,
        "gap_trips": gap_trips,
        "ytd_trend": ytd_trend,
        "pacing_vs_expected": pacing,
        "principal_driver": principal_driver,
        "level": "warning",
        "dimension": "lob",
    }


def _ytd_summary() -> Dict[str, Any]:
    return {
        "grain": "monthly",
        "year": 2026,
        "through_period": "2026-05",
        "ytd_real_trips": 200_000.0,
        "ytd_gap_trips": -3_000.0,
    }


# ---------------------------------------------------------------------------
# QA del spec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("grain", ["daily", "weekly", "monthly"])
def test_grain_parameter_inert_but_accepted(grain: str):
    sid = "ctx-lima-prod"
    queue, chk = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation", contextual_suggestion_id=sid),
        ],
        contextual_suggestions=[_ctx(suggestion_id=sid)],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[_alert(entity="Lima - Auto Regular")],
        integrity_status={"status": "ok", "checks": {}},
        grain=grain,
    )
    assert chk in ("ok", "partial")
    assert len(queue) == 1
    assert queue[0]["global_priority_rank"] == 1
    assert queue[0]["entity"]["country"] == "Peru"
    assert queue[0]["entity"]["city"] == "Lima"
    assert queue[0]["entity"]["lob"] == "Auto Regular"


def test_lima_outranks_trujillo_when_impact_and_strategic_weight_higher():
    sid_lima = "ctx-lima"
    sid_truj = "ctx-truj"
    queue, _ = build_global_decision_queue(
        decision_recommendations=[
            _reco(
                entity="Lima - Auto Regular",
                action_type="productivity_reactivation",
                decision_score=72.0,
                contextual_suggestion_id=sid_lima,
            ),
            _reco(
                entity="Trujillo - Delivery",
                action_type="productivity_reactivation",
                decision_score=70.0,
                contextual_suggestion_id=sid_truj,
            ),
        ],
        contextual_suggestions=[
            _ctx(suggestion_id=sid_lima, leverage=70.0, gap_recovery_pct=10.0, weekly_recovery=320.0),
            _ctx(suggestion_id=sid_truj, leverage=55.0, gap_recovery_pct=6.0, weekly_recovery=110.0),
        ],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[
            _alert(entity="Lima - Auto Regular", gap_pct=8.0, gap_trips=4500.0, ytd_trend="deteriorating"),
            _alert(
                entity="Trujillo - Delivery",
                country="Peru",
                city="Trujillo",
                business_slice="Delivery",
                gap_pct=4.0,
                gap_trips=900.0,
                ytd_trend="stable",
            ),
        ],
        integrity_status={"status": "ok", "checks": {}},
    )
    assert queue[0]["entity"]["city"] == "Lima"
    assert queue[1]["entity"]["city"] == "Trujillo"
    assert queue[0]["global_decision_score"] >= queue[1]["global_decision_score"]


def test_quick_win_role_for_reactivation_and_growth_for_scouts():
    queue, _ = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation"),
            _reco(entity="Bogotá - Delivery", action_type="volume_scouts_push"),
            _reco(entity="Lima - Delivery", action_type="ticket_mix_review"),
            _reco(entity="Trujillo - Delivery", action_type="data_review"),
        ],
        contextual_suggestions=[],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[
            _alert(entity="Lima - Auto Regular"),
            _alert(entity="Bogotá - Delivery", country="Colombia", city="Bogotá", business_slice="Delivery"),
            _alert(entity="Lima - Delivery", business_slice="Delivery"),
            _alert(entity="Trujillo - Delivery", city="Trujillo", business_slice="Delivery"),
        ],
        integrity_status={"status": "ok", "checks": {}},
    )
    role_by_entity = {q["entity"]["label"]: q["portfolio_role"]["role_type"] for q in queue}
    assert role_by_entity["Lima - Auto Regular"] == "quick_win"
    assert role_by_entity["Bogotá - Delivery"] == "growth"
    assert role_by_entity["Lima - Delivery"] == "structural"
    assert role_by_entity["Trujillo - Delivery"] == "defensive"


def test_low_confidence_drops_position_and_marks_partial():
    sid_low = "ctx-low"
    sid_high = "ctx-high"
    queue, chk = build_global_decision_queue(
        decision_recommendations=[
            _reco(
                entity="Lima - Auto Regular",
                action_type="productivity_reactivation",
                decision_score=72.0,
                confidence="low",
                contextual_suggestion_id=sid_low,
            ),
            _reco(
                entity="Trujillo - Delivery",
                action_type="productivity_reactivation",
                decision_score=68.0,
                confidence="high",
                contextual_suggestion_id=sid_high,
            ),
        ],
        contextual_suggestions=[
            _ctx(suggestion_id=sid_low, confidence="low"),
            _ctx(suggestion_id=sid_high, confidence="high"),
        ],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[
            _alert(entity="Lima - Auto Regular"),
            _alert(entity="Trujillo - Delivery", city="Trujillo", business_slice="Delivery"),
        ],
        integrity_status={"status": "ok", "checks": {}},
    )
    assert chk == "partial"
    # La low confidence cap a 50 antes de ajuste; high se mantiene → high arriba.
    assert queue[0]["entity"]["label"] == "Trujillo - Delivery"
    low_item = next(q for q in queue if q["entity"]["label"] == "Lima - Auto Regular")
    assert low_item["global_decision_score"] <= 50.0
    assert low_item["decision_constraints"]["data_confidence"] == "low"


def test_integrity_broken_returns_empty_queue():
    queue, chk = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation"),
        ],
        contextual_suggestions=[],
        ytd_alerts=[],
        integrity_status={"status": "broken", "checks": {}},
    )
    assert queue == []
    assert chk == "missing"


def test_no_decision_recommendations_yields_missing():
    queue, chk = build_global_decision_queue(
        decision_recommendations=[],
        contextual_suggestions=[],
        ytd_alerts=[],
        integrity_status={"status": "ok", "checks": {}},
    )
    assert queue == []
    assert chk == "missing"


def test_saturation_emits_warning_text_and_partial_check():
    recos: List[Dict[str, Any]] = [
        _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation"),
        _reco(entity="Lima - Delivery", action_type="productivity_reactivation"),
        _reco(entity="Trujillo - Delivery", action_type="productivity_reactivation"),
        _reco(entity="Bogotá - Delivery", action_type="productivity_reactivation"),
    ]
    alerts = [
        _alert(entity="Lima - Auto Regular"),
        _alert(entity="Lima - Delivery", business_slice="Delivery"),
        _alert(entity="Trujillo - Delivery", city="Trujillo", business_slice="Delivery"),
        _alert(entity="Bogotá - Delivery", country="Colombia", city="Bogotá", business_slice="Delivery"),
    ]
    queue, chk = build_global_decision_queue(
        decision_recommendations=recos,
        contextual_suggestions=[],
        ytd_summary=_ytd_summary(),
        ytd_alerts=alerts,
        integrity_status={"status": "ok", "checks": {}},
    )
    assert chk == "partial"
    sat = queue[0]["global_policy_trace"]["saturation_summary"]
    assert "productivity_reactivation" in sat["saturated_actions"]
    risks = [q["decision_risks"]["operational_saturation_risk"] for q in queue]
    assert any("Saturación V1" in r for r in risks)


def test_no_duplicate_entities_in_queue():
    queue, _ = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation", decision_score=70.0),
            # Duplicado misma clave → debe descartarse el de menor score
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation", decision_score=55.0),
            _reco(entity="Trujillo - Delivery", action_type="productivity_reactivation"),
        ],
        contextual_suggestions=[],
        ytd_alerts=[
            _alert(entity="Lima - Auto Regular"),
            _alert(entity="Trujillo - Delivery", city="Trujillo", business_slice="Delivery"),
        ],
        integrity_status={"status": "ok", "checks": {}},
    )
    labels = [q["entity"]["label"] for q in queue]
    assert labels.count("Lima - Auto Regular") == 1
    # El que sobrevive es el de mayor decision_score → sus dimensions reflejan local 70
    lima = next(q for q in queue if q["entity"]["label"] == "Lima - Auto Regular")
    assert lima["priority_dimensions"]["local_decision_strength"] == 70.0


def test_global_policy_trace_present_and_well_formed():
    sid = "ctx-1"
    queue, _ = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation", contextual_suggestion_id=sid),
        ],
        contextual_suggestions=[_ctx(suggestion_id=sid)],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[_alert(entity="Lima - Auto Regular")],
        integrity_status={"status": "ok", "checks": {}},
    )
    trace = queue[0]["global_policy_trace"]
    assert trace["policy_version"] == POLICY_VERSION
    assert trace["policy_type"] == POLICY_TYPE
    assert isinstance(trace["inputs_used"], list) and trace["inputs_used"]
    weights = trace["weights"]
    assert pytest.approx(sum(weights.values()), abs=1e-6) == 1.0
    bd = trace["score_breakdown"]
    for k in (
        "local_decision_strength",
        "business_impact",
        "urgency",
        "reachability",
        "operational_feasibility",
        "strategic",
        "strategic_multiplier",
        "composite_pre_confidence",
        "confidence_applied",
    ):
        assert k in bd


def test_strategic_weight_rules_applied():
    assert STRATEGIC_WEIGHT_RULES["country"]["peru"] > 1.0
    assert STRATEGIC_WEIGHT_RULES["city"]["lima"] > 1.0
    sid = "ctx-1"
    # Lima Auto Regular debería terminar con un strategic component sobre 50
    queue, _ = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation", contextual_suggestion_id=sid),
        ],
        contextual_suggestions=[_ctx(suggestion_id=sid)],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[_alert(entity="Lima - Auto Regular")],
        integrity_status={"status": "ok", "checks": {}},
    )
    strat = queue[0]["priority_dimensions"]["strategic_weight"]
    assert strat > 50.0


def test_resource_profile_matches_action_type():
    queue, _ = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="volume_scouts_push"),
            _reco(entity="Trujillo - Delivery", action_type="productivity_reactivation"),
        ],
        contextual_suggestions=[],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[
            _alert(entity="Lima - Auto Regular"),
            _alert(entity="Trujillo - Delivery", city="Trujillo", business_slice="Delivery"),
        ],
        integrity_status={"status": "ok", "checks": {}},
    )
    by_label = {q["entity"]["label"]: q for q in queue}
    scouts = by_label["Lima - Auto Regular"]["resource_profile"]
    react = by_label["Trujillo - Delivery"]["resource_profile"]
    assert scouts["estimated_operational_load"] == "high"
    assert "field_supply" in scouts["required_team_type"]
    assert react["estimated_operational_load"] == "low"
    assert "outbound" in react["required_team_type"]


def test_merge_integrity_helper_adds_check_key():
    merged = merge_integrity_with_global_decision_check(
        {"status": "ok", "checks": {"decision_policy_engine": "ok"}},
        "partial",
    )
    assert merged["checks"]["global_decision_engine"] == "partial"
    assert merged["checks"]["decision_policy_engine"] == "ok"


def test_safe_wrapper_swallows_exception():
    queue, chk = safe_build_global_decision_queue(
        decision_recommendations="not-a-list",  # tipo inválido → branch interno
        integrity_status={"status": "ok", "checks": {}},
    )
    assert queue == []
    assert chk == "missing"


def test_warning_integrity_yields_partial_when_otherwise_ok():
    sid = "ctx-1"
    queue, chk = build_global_decision_queue(
        decision_recommendations=[
            _reco(entity="Lima - Auto Regular", action_type="productivity_reactivation", contextual_suggestion_id=sid),
        ],
        contextual_suggestions=[_ctx(suggestion_id=sid, confidence="high")],
        ytd_summary=_ytd_summary(),
        ytd_alerts=[_alert(entity="Lima - Auto Regular")],
        integrity_status={"status": "warning", "checks": {}},
    )
    assert chk == "partial"
    assert len(queue) == 1
