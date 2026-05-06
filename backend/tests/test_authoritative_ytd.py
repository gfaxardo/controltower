"""FASE 3.8B — agregación autoritativa YTD (backend)."""

from app.services.projection_ytd_period_service import (
    _aggregate_ytd_slice_payloads_for_scope,
    ytd_summary_api_to_authoritative_total_slice,
)


def test_total_slice_copies_summary_api_fields():
    api = {
        "grain": "weekly",
        "ytd_real_trips": 100.5,
        "ytd_plan_expected_trips": 80.0,
        "ytd_gap_trips": 20.5,
        "ytd_attainment_pct": 125.62,
        "pacing_vs_expected": "ahead",
        "ytd_trend": "flat",
        "ytd_real_revenue": 1000.0,
        "ytd_plan_expected_revenue": 900.0,
        "ytd_gap_revenue": 100.0,
        "ytd_avg_active_drivers_real": 5.0,
        "ytd_avg_active_drivers_expected": 4.0,
        "driver_productivity_ytd_real": 20.1,
        "driver_productivity_ytd_expected": 20.0,
    }
    sl = ytd_summary_api_to_authoritative_total_slice(api, grain="weekly")
    assert sl["slice_level"] == "total"
    assert sl["slice_key"] == "__PORTFOLIO__"
    assert sl["ytd_real_trips"] == 100.5
    assert sl["ytd_plan_expected_trips"] == 80.0
    assert sl["ytd_attainment_pct"] == 125.62
    assert sl["pacing_vs_expected"] == "ahead"


def test_aggregate_city_slices_sums_trips():
    s1 = {
        "slice_key": "peru::lima::a::0::",
        "slice_level": "lob",
        "ytd_real_trips": 10.0,
        "ytd_plan_expected_trips": 10.0,
        "ytd_real_revenue": 100.0,
        "ytd_plan_expected_revenue": 100.0,
        "ytd_avg_active_drivers_real": 2.0,
        "ytd_avg_active_drivers_expected": 2.0,
    }
    s2 = {
        "slice_key": "peru::lima::b::0::",
        "slice_level": "lob",
        "ytd_real_trips": 30.0,
        "ytd_plan_expected_trips": 20.0,
        "ytd_real_revenue": 300.0,
        "ytd_plan_expected_revenue": 200.0,
        "ytd_avg_active_drivers_real": 3.0,
        "ytd_avg_active_drivers_expected": 2.5,
    }
    out = _aggregate_ytd_slice_payloads_for_scope(
        [s1, s2],
        grain="weekly",
        slice_key="peru::lima",
        slice_level="city",
    )
    assert out["ytd_real_trips"] == 40.0
    assert out["ytd_plan_expected_trips"] == 30.0
    assert out["slice_level"] == "city"
    assert out["ytd_attainment_pct"] == round((40 / 30) * 100, 2)
    assert out["metric_trace"]["basis"] == "authoritative_backend_additive_rollup"
