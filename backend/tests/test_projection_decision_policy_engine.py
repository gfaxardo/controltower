"""
Tests motor de política de decisión (FASE 4.3) — priorización sólo lectura.

Sin ejecución; valida QA del spec (heurística v1).
"""
from __future__ import annotations

import pytest

from app.services.projection_decision_policy_engine import build_projection_decision_recommendations


def _ctx(
    action_type: str,
    *,
    entity: str = "Trujillo - Delivery",
    confidence: str = "medium",
    leverage: float = 58.0,
    gap_pct: float = 7.0,
    pool_candidates: int = 90,
):
    return {
        "suggestion_id": f"sid-{action_type}-{entity}",
        "entity": entity,
        "action_type": action_type,
        "confidence": confidence,
        "priority_score": 55,
        "operational_leverage_score": leverage,
        "recommended_action_name": None,
        "estimated_recovery": {
            "potential_gap_recovery_pct": gap_pct,
            "potential_trips_recovered_weekly": 140.0,
            "recovery_method": "unit-test",
            "confidence_reason": "synthetic",
        },
        "operational_pool": {"total_candidates": pool_candidates, "segments": []},
        "contextual_reasoning": {
            "main_problem_detected": "Synthetic gap for QA",
            "expected_operational_effect": "Test effect string",
        },
    }


@pytest.mark.parametrize("grain", ["daily", "weekly", "monthly"])
def test_grain_parameter_inert_but_accepted(grain: str):
    ent = "Perú - Lima - Auto regular"
    out, chk = build_projection_decision_recommendations(
        contextual_suggestions=[
            _ctx("productivity_reactivation", entity=ent),
            _ctx("volume_scouts_push", entity=ent),
        ],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[{"entity": ent, "principal_driver": "productivity", "gap_pct": 4.0}],
        grain=grain,
    )
    assert len(out) == 1
    assert chk in ("ok", "partial")
    assert out[0]["recommended_action"]["action_type"] == "productivity_reactivation"


@pytest.mark.parametrize(
    "entity",
    [
        "Trujillo - Delivery",
        "Lima - Auto regular",
        "Perú - Lima - Delivery",
    ],
)
def test_productivity_reactivation_beats_scouts_when_driver_is_productivity(entity: str):
    out, _chk = build_projection_decision_recommendations(
        contextual_suggestions=[
            _ctx("productivity_reactivation", entity=entity),
            _ctx("volume_scouts_push", entity=entity),
        ],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[{"entity": entity, "principal_driver": "productivity", "gap_pct": 4.0}],
    )
    assert out[0]["entity"] == entity
    win = out[0]["recommended_action"]["action_type"]
    assert win == "productivity_reactivation"
    alts = out[0]["alternatives"]
    assert any(a["action_type"] == "volume_scouts_push" for a in alts)


def test_scouts_can_take_lead_under_severe_volume_and_small_onboarding_pipeline():
    entity = "Lima - Delivery"
    out, _chk = build_projection_decision_recommendations(
        contextual_suggestions=[
            _ctx("volume_scouts_push", entity=entity, leverage=62.0, gap_pct=14.0),
            _ctx("productivity_reactivation", entity=entity, leverage=55.0, gap_pct=14.0),
            _ctx(
                "volume_onboarding_followup",
                entity=entity,
                pool_candidates=22,
                gap_pct=14.0,
            ),
        ],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[
            {
                "entity": entity,
                "principal_driver": "volume",
                "gap_pct": 15.0,
                "gap_trips": 3200.0,
            },
        ],
    )
    assert out[0]["recommended_action"]["action_type"] == "volume_scouts_push"
    trace = out[0]["policy_trace"]
    assert trace["policy_version"] == "v1"
    assert trace["policy_type"] == "heuristic_weighted_policy"
    assert isinstance(trace.get("inputs_used"), list) and trace["inputs_used"]


def test_low_confidence_never_high_score_and_principal_is_alternative():
    entity = "Trujillo - Delivery"
    out, chk = build_projection_decision_recommendations(
        contextual_suggestions=[
            _ctx("productivity_reactivation", entity=entity, confidence="low"),
            _ctx("volume_scouts_push", entity=entity, confidence="low"),
        ],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[{"entity": entity, "principal_driver": "productivity"}],
    )
    assert chk == "partial"
    assert out[0]["decision_status"] == "alternative"
    assert float(out[0]["decision_score"]) <= 52.0 + 1e-6


def test_integrity_broken_yields_empty_recommendations():
    out, chk = build_projection_decision_recommendations(
        contextual_suggestions=[_ctx("productivity_reactivation")],
        integrity_status={"status": "broken", "checks": {}},
        ytd_alerts=[],
    )
    assert out == []
    assert chk == "missing"


def test_merge_integrity_check_function():
    from app.services.projection_decision_policy_engine import merge_integrity_with_decision_policy_check

    merged = merge_integrity_with_decision_policy_check(
        {"status": "ok", "checks": {"contextual_suggestions": "ok"}},
        "partial",
    )
    assert merged["checks"]["decision_policy_engine"] == "partial"
    assert merged["checks"]["contextual_suggestions"] == "ok"


def test_alternatives_and_why_not_populated_with_two_actions():
    entity = "X"
    out, _ = build_projection_decision_recommendations(
        contextual_suggestions=[
            _ctx("ticket_mix_review", entity=entity),
            _ctx("data_review", entity=entity),
        ],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[{"entity": entity, "principal_driver": "ticket"}],
    )
    reco = out[0]
    assert len(reco["alternatives"]) >= 1
    wno = reco["decision_reasoning"]["why_not_other_actions"]
    assert isinstance(wno, list) and len(wno) >= 1
    assert reco.get("policy_trace") and reco["policy_trace"].get("policy_version") == "v1"


def test_no_valid_action_type_yields_missing():
    out, chk = build_projection_decision_recommendations(
        contextual_suggestions=[{"entity": "Trujillo - Delivery", "confidence": "high"}],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[],
    )
    assert out == []
    assert chk == "missing"


def test_incomplete_winner_context_marks_partial():
    entity = "Perú - Delivery"
    ctx = _ctx("productivity_reactivation", entity=entity)
    del ctx["contextual_reasoning"]
    out, chk = build_projection_decision_recommendations(
        contextual_suggestions=[ctx, _ctx("volume_scouts_push", entity=entity)],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[{"entity": entity, "principal_driver": "productivity"}],
    )
    assert len(out) == 1
    assert chk == "partial"


def test_trujillo_delivery_label_stable():
    entity = "Trujillo - Delivery"
    out, chk = build_projection_decision_recommendations(
        contextual_suggestions=[
            _ctx("productivity_reactivation", entity=entity),
            _ctx("volume_scouts_push", entity=entity),
        ],
        integrity_status={"status": "ok", "checks": {}},
        ytd_alerts=[{"entity": entity, "principal_driver": "productivity", "gap_pct": 5.0}],
    )
    assert out[0]["entity"] == entity
    assert chk == "ok"
    assert "Reactivar" in (out[0]["decision_reasoning"].get("why_selected") or "")
