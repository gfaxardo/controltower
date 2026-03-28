"""
Fase 9 — Validación Decision Engine.
Comprueba coherencia de la matriz trust_status × criticality y forzados.
Usa mock del Confidence Engine para no depender del estado real de datos.
"""
import pytest
from unittest.mock import patch


def _mock_confidence(trust_status, confidence_score, completeness_status="full", consistency_status="validated", details=None):
    return {
        "trust_status": trust_status,
        "confidence_score": confidence_score,
        "completeness_status": completeness_status,
        "consistency_status": consistency_status,
        "last_update": "2025-01-01T00:00:00",
        "details": details or {},
    }


@patch("app.services.confidence_engine.get_confidence_status")
def test_real_lob_incomplete_stop_decisions_p0(mock_conf):
    """1. real_lob incompleto → STOP_DECISIONS (P0)."""
    from app.services.decision_engine import get_decision_signal

    mock_conf.return_value = _mock_confidence(
        "blocked", 35, completeness_status="missing", consistency_status="unknown",
        details={"completeness": {"coverage_ratio": 0.57}},
    )
    out = get_decision_signal("real_lob")
    assert out["action"] == "STOP_DECISIONS"
    assert out["priority"] == "P0"
    assert out["reason"] == "completeness_missing"
    assert "view" in out and out["view"] == "real_lob"


@patch("app.services.confidence_engine.get_confidence_status")
def test_supply_warning_monitor_closely(mock_conf):
    """2. supply warning → MONITOR_CLOSELY."""
    from app.services.decision_engine import get_decision_signal

    mock_conf.return_value = _mock_confidence("warning", 65, "partial", "minor_diff")
    out = get_decision_signal("supply")
    assert out["criticality"] == "high"
    assert out["action"] == "MONITOR_CLOSELY"
    assert out["priority"] == "P2"


@patch("app.services.confidence_engine.get_confidence_status")
def test_behavioral_alerts_warning_monitor(mock_conf):
    """3. behavioral_alerts warning → MONITOR."""
    from app.services.decision_engine import get_decision_signal

    mock_conf.return_value = _mock_confidence("warning", 55, "partial", "unknown")
    out = get_decision_signal("behavioral_alerts")
    assert out["criticality"] == "medium"
    assert out["action"] == "MONITOR"
    assert out["priority"] == "P2"


@patch("app.services.confidence_engine.get_confidence_status")
def test_system_ok_operate_normal(mock_conf):
    """4. sistema OK → OPERATE_NORMAL."""
    from app.services.decision_engine import get_decision_signal

    mock_conf.return_value = _mock_confidence("ok", 85, "full", "validated")
    out = get_decision_signal("supply")
    assert out["action"] == "OPERATE_NORMAL"
    assert out["priority"] == "P3"
    assert out["reason"] == "ok"


@patch("app.services.confidence_engine.get_confidence_status")
def test_consistency_major_diff_force_stop(mock_conf):
    """consistency == major_diff → STOP_DECISIONS (P0)."""
    from app.services.decision_engine import get_decision_signal

    mock_conf.return_value = _mock_confidence("blocked", 45, "full", "major_diff")
    out = get_decision_signal("plan_vs_real")
    assert out["action"] == "STOP_DECISIONS"
    assert out["priority"] == "P0"
    assert out["reason"] == "consistency_major_diff"


@patch("app.services.confidence_engine.get_confidence_status")
def test_confidence_below_40_force_p0(mock_conf):
    """confidence_score < 40 → P0."""
    from app.services.decision_engine import get_decision_signal

    mock_conf.return_value = _mock_confidence("blocked", 35, "partial", "minor_diff")
    out = get_decision_signal("real_lob")
    assert out["action"] == "STOP_DECISIONS"
    assert out["priority"] == "P0"
    assert out["reason"] == "confidence_below_40"


def test_decision_signal_structure():
    """Estructura de get_decision_signal: view, trust_status, confidence_score, criticality, action, priority, message, reason, last_update, details."""
    from app.services.decision_engine import get_decision_signal

    with patch("app.services.confidence_engine.get_confidence_status") as mock_conf:
        mock_conf.return_value = _mock_confidence("ok", 90)
        out = get_decision_signal("resumen")
    for key in ("view", "trust_status", "confidence_score", "criticality", "action", "priority", "message", "reason", "last_update", "details"):
        assert key in out, f"falta clave {key}"


def test_decision_signal_summary_returns_list():
    """get_decision_signal_summary devuelve lista de { view, action, priority }."""
    from app.services.decision_engine import get_decision_signal_summary

    with patch("app.services.confidence_engine.get_confidence_status") as mock_conf:
        mock_conf.return_value = _mock_confidence("ok", 85)
        summary = get_decision_signal_summary()
    assert isinstance(summary, list)
    for item in summary:
        assert "view" in item and "action" in item and "priority" in item
