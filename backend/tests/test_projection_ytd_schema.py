"""Contrato Pydantic meta.ytd_summary."""

import pytest
from pydantic import ValidationError

from app.models.projection_ytd_schema import (
    ProjectionYtdSummary,
    YtdSummaryErrorPayload,
    serialize_ytd_summary_for_api,
)


def _minimal_ok_payload():
    return {
        "grain": "monthly",
        "year": 2026,
        "through_period": "2026-04-30",
        "metric_trace": {"trips_completed": {"real": "x", "expected_plan": "y"}},
        "ytd_real_trips": 100.0,
        "ytd_plan_expected_trips": 120.0,
        "ytd_gap_trips": -20.0,
        "ytd_attainment_pct": 83.33,
        "ytd_real_revenue": None,
        "ytd_plan_expected_revenue": None,
        "ytd_gap_revenue": None,
        "ytd_avg_active_drivers_real": 10.0,
        "ytd_avg_active_drivers_expected": 10.0,
        "driver_productivity_ytd_real": 10.0,
        "driver_productivity_ytd_expected": 12.0,
        "ytd_avg_ticket_real": None,
        "ytd_avg_ticket_expected": None,
        "pacing_vs_expected": "behind",
        "ytd_trend": "flat",
        "ytd_trend_periods": [],
        "gap_decomposition": {"basis": "approximate_additive_decomposition"},
        "active_drivers_note": "note",
        "ytd_active_drivers_real": None,
        "ytd_plan_expected_active_drivers": None,
        "ytd_gap_active_drivers": None,
    }


def test_projection_ytd_summary_round_trip():
    raw = _minimal_ok_payload()
    m = ProjectionYtdSummary.model_validate(raw)
    out = m.model_dump(mode="json")
    assert out["grain"] == "monthly"
    assert out["ytd_gap_trips"] == -20.0


def test_serialize_success():
    d = serialize_ytd_summary_for_api(_minimal_ok_payload(), grain="monthly")
    assert d is not None
    assert "error" not in d
    assert d["ytd_trend"] == "flat"


def test_serialize_error_payload():
    d = serialize_ytd_summary_for_api({"error": "boom", "grain": "weekly"}, grain="weekly")
    assert d["error"] == "boom"


def test_serialize_none():
    assert serialize_ytd_summary_for_api(None, grain="monthly") is None


def test_ytd_error_extra_forbidden():
    with pytest.raises(ValidationError):
        YtdSummaryErrorPayload.model_validate({"error": "x", "grain": "y", "extra": 1})

