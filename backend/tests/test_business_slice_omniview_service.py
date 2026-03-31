"""Tests unitarios: business_slice_omniview_service (sin BD salvo integración opcional)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.business_slice_omniview_service import (
    THRESHOLD_DELTA_PP,
    THRESHOLD_DELTA_PCT_POINTS,
    METRIC_DIRECTIONS,
    build_metrics_from_components,
    cancel_rate_pct_from_counts,
    commission_pct_from_sums,
    compute_deltas,
    compute_signal_for_metric,
    merge_component_rows_for_rollup,
    resolve_period_windows,
    trips_per_driver_from_counts,
    validate_omniview_params,
)


def test_validate_weekly_requires_country():
    with pytest.raises(ValueError, match="country"):
        validate_omniview_params("weekly", None, 90)


def test_validate_daily_requires_country():
    with pytest.raises(ValueError, match="country"):
        validate_omniview_params("daily", "", 90)


def test_validate_daily_window_max():
    with pytest.raises(ValueError, match="daily_window_days"):
        validate_omniview_params("daily", "PE", 121)


def test_validate_granularity():
    with pytest.raises(ValueError, match="granularity"):
        validate_omniview_params("hourly", None, 90)


def test_monthly_windows_mom():
    win = resolve_period_windows("monthly", date(2026, 3, 1))
    assert win.current_start == date(2026, 3, 1)
    assert win.previous_start == date(2026, 2, 1)
    assert win.comparison_rule == "MoM"


def test_weekly_windows_wow():
    win = resolve_period_windows("weekly", date(2026, 3, 30))
    assert win.current_start.weekday() == 0
    assert win.previous_start == win.current_start - timedelta(days=7)
    assert win.comparison_rule == "WoW"


def test_daily_windows_minus_7():
    d = date(2026, 3, 30)
    win = resolve_period_windows("daily", d)
    assert win.current_start == d
    assert win.previous_start == d - timedelta(days=7)


def test_commission_pct_from_sums_matches_loader_semantics():
    assert commission_pct_from_sums(18.0, 100.0) == pytest.approx(0.18)
    assert commission_pct_from_sums(10.0, 0) is None
    assert commission_pct_from_sums(None, 100.0) is None


def test_trips_per_driver():
    assert trips_per_driver_from_counts(100, 10) == pytest.approx(10.0)
    assert trips_per_driver_from_counts(100, 0) is None


def test_cancel_rate_pct():
    assert cancel_rate_pct_from_counts(90, 10) == pytest.approx(10.0)
    assert cancel_rate_pct_from_counts(0, 0) is None


def test_merge_rollup_commission_not_averaged():
    rows = [
        {
            "trips_completed": 100,
            "trips_cancelled": 10,
            "completed_revenue_sum": 10.0,
            "completed_total_fare_sum": 100.0,
            "avg_ticket": 5.0,
        },
        {
            "trips_completed": 100,
            "trips_cancelled": 0,
            "completed_revenue_sum": 30.0,
            "completed_total_fare_sum": 200.0,
            "avg_ticket": 3.0,
        },
    ]
    m = merge_component_rows_for_rollup(rows)
    assert m["trips_completed"] == 200
    assert m["commission_pct"] == pytest.approx(40.0 / 300.0)
    assert m["avg_ticket"] == pytest.approx((5 * 100 + 3 * 100) / 200.0)


def test_build_metrics_from_components_with_sums():
    c = {
        "trips_completed": 50,
        "trips_cancelled": 5,
        "active_drivers": 10,
        "avg_ticket": 12.0,
        "completed_revenue_sum": 24.0,
        "completed_total_fare_sum": 120.0,
        "revenue_yego_net": 24.0,
    }
    m = build_metrics_from_components(c)
    assert m["commission_pct"] == pytest.approx(0.2)
    assert m["trips_per_driver"] == pytest.approx(5.0)
    assert m["cancel_rate_pct"] == pytest.approx(100.0 * 5 / 55)


def test_compute_deltas_normal():
    cur = {
        "trips_completed": 120,
        "trips_cancelled": 10,
        "active_drivers": 12,
        "avg_ticket": 10.0,
        "revenue_yego_net": 100.0,
        "commission_pct": 0.2,
        "trips_per_driver": 10.0,
        "cancel_rate_pct": 8.0,
    }
    prev = {
        "trips_completed": 100,
        "trips_cancelled": 10,
        "active_drivers": 10,
        "avg_ticket": 10.0,
        "revenue_yego_net": 80.0,
        "commission_pct": 0.18,
        "trips_per_driver": 10.0,
        "cancel_rate_pct": 9.09,
    }
    d, sig, ncmp, _ = compute_deltas(cur, prev)
    assert d["trips_completed"]["delta_abs"] == 20
    assert d["trips_completed"]["delta_pct"] == pytest.approx(20.0)
    assert d["commission_pct"]["delta_abs_pp"] == pytest.approx((0.2 - 0.18) * 100.0)
    assert not ncmp
    assert sig["trips_completed"] in ("positive", "neutral", "negative")


def test_compute_deltas_previous_missing():
    cur = {k: 1 if k == "trips_completed" else (0.1 if k == "commission_pct" else None) for k in METRIC_DIRECTIONS}
    cur["trips_cancelled"] = 0
    cur["revenue_yego_net"] = 1.0
    cur["avg_ticket"] = 1.0
    cur["trips_per_driver"] = 1.0
    cur["cancel_rate_pct"] = 0.0
    cur["active_drivers"] = 1
    prev = {k: None for k in METRIC_DIRECTIONS}
    d, _, ncmp, reason = compute_deltas(cur, prev)
    assert ncmp
    assert reason == "previous_missing"
    assert d["trips_completed"]["delta_pct"] is None


def test_compute_deltas_previous_zero_pct():
    cur = {
        "trips_completed": 10,
        "trips_cancelled": 0,
        "active_drivers": 2,
        "avg_ticket": 1.0,
        "revenue_yego_net": 5.0,
        "commission_pct": 0.1,
        "trips_per_driver": 5.0,
        "cancel_rate_pct": 0.0,
    }
    prev = dict(cur)
    prev["trips_completed"] = 0
    d, _, ncmp, reason = compute_deltas(cur, prev)
    assert d["trips_completed"]["delta_pct"] is None
    assert ncmp
    assert reason == "pct_base_zero"


def test_signals_higher_better():
    assert (
        compute_signal_for_metric("trips_completed", 110, 100, 10.0, None) == "positive"
    )
    assert (
        compute_signal_for_metric("trips_completed", 90, 100, -10.0, None) == "negative"
    )
    assert (
        compute_signal_for_metric("trips_completed", 102, 100, 2.0, None) == "neutral"
    )


def test_signals_lower_better_cancel_rate():
    assert (
        compute_signal_for_metric("cancel_rate_pct", 5.0, 10.0, None, -5.0) == "positive"
    )
    assert (
        compute_signal_for_metric("cancel_rate_pct", 12.0, 10.0, None, 2.0) == "negative"
    )


def test_signals_neutral_avg_ticket():
    assert compute_signal_for_metric("avg_ticket", 10.0, 9.0, 11.0, None) == "neutral"


def test_signals_neutral_commission():
    assert compute_signal_for_metric("commission_pct", 0.2, 0.18, 10.0, 2.0) == "neutral"


def test_pp_threshold_uses_half_point():
    assert (
        compute_signal_for_metric("cancel_rate_pct", 10.3, 10.0, None, 0.3) == "neutral"
    )
    assert (
        compute_signal_for_metric("cancel_rate_pct", 10.6, 10.0, None, 0.6) == "negative"
    )


def test_rel_threshold_uses_five_percent():
    assert (
        compute_signal_for_metric("revenue_yego_net", 104.0, 100.0, 4.0, None) == "neutral"
    )
    assert (
        compute_signal_for_metric("revenue_yego_net", 106.0, 100.0, 6.0, None) == "positive"
    )


def test_constants_documented():
    assert THRESHOLD_DELTA_PCT_POINTS == 5.0
    assert THRESHOLD_DELTA_PP == 0.5
