from __future__ import annotations

from datetime import date

from app.services.projection_expected_progress_service import (
    _build_plan_distribution,
    _build_no_plan_row,
    _distribution_debug_entry,
    _normalize_projection_scope,
    _projection_join_key,
    _semantic_ui_revenue,
)


def test_projection_join_key_normalizes_country_city_and_slice():
    key = _projection_join_key("2026-02-01", "PE", "Líma", "Delívery")
    assert key == ("2026-02-01", "peru", "lima", "delivery")


def test_semantic_ui_revenue_returns_positive_value():
    assert _semantic_ui_revenue(-55.2) == 55.2
    assert _semantic_ui_revenue(55.2) == 55.2
    assert _semantic_ui_revenue(None) is None


def test_normalize_projection_scope_ignores_month_for_weekly():
    year, month, ignored = _normalize_projection_scope("weekly", 2026, 4)
    assert year == 2026
    assert month is None
    assert ignored is True

    year, month, ignored = _normalize_projection_scope("daily", 2026, 4)
    assert year == 2026
    assert month == 4
    assert ignored is False


def test_build_no_plan_row_keeps_auxiliary_real_metrics():
    row = _build_no_plan_row(
        {
            "country": "peru",
            "city": "lima",
            "business_slice_name": "Delivery",
            "real_trips": 10,
            "real_revenue": 20.0,
            "real_active_drivers": 4,
            "real_avg_ticket": 2.5,
            "real_trips_per_driver": 2.5,
            "real_revenue_raw": -20.0,
        },
        "2026-02-01",
        "monthly",
    )
    assert row["avg_ticket"] == 2.5
    assert row["trips_per_driver"] == 2.5
    assert row["revenue_yego_net_audit_raw"] == -20.0


def test_build_plan_distribution_preserves_monthly_totals_via_daily_calendar():
    plan = {
        "country": "peru",
        "city": "lima",
        "business_slice_name": "Delivery",
        "projected_trips": 100.0,
        "projected_revenue": 1000.0,
        "projected_active_drivers": 50.0,
    }

    distribution = _build_plan_distribution(plan, date(2026, 4, 1))

    assert distribution["days_in_month"] == 30
    assert len(distribution["daily_rows"]) == 30
    assert len(distribution["weekly_rows"]) == 5
    assert distribution["weekly_sum"]["trips_completed"] == 100.0
    assert distribution["weekly_sum"]["revenue_yego_net"] == 1000.0
    assert distribution["weekly_sum"]["active_drivers"] == 50.0

    daily_trips = list(distribution["daily_plans"]["trips_completed"].values())
    assert round(sum(daily_trips), 2) == 100.0
    assert all(value is not None for value in daily_trips)


def test_daily_distribution_is_consistent_with_weekly_distribution():
    plan = {
        "country": "peru",
        "city": "lima",
        "business_slice_name": "Delivery",
        "projected_trips": 93.0,
        "projected_revenue": 930.0,
        "projected_active_drivers": 31.0,
    }

    distribution = _build_plan_distribution(plan, date(2026, 3, 1))

    for week in distribution["weekly_rows"]:
        trip_dates = week["trip_dates"]
        week_start = week["week_start"]
        for kpi in ("trips_completed", "revenue_yego_net", "active_drivers"):
            daily_sum = round(
                sum(distribution["daily_plans"][kpi][trip_date] for trip_date in trip_dates),
                2,
            )
            assert daily_sum == distribution["weekly_plans"][kpi][week_start]


def test_distribution_debug_entry_exposes_iso_week_metadata_and_sums():
    plan = {
        "country": "peru",
        "city": "lima",
        "business_slice_name": "Delivery",
        "projected_trips": 100.0,
        "projected_revenue": 1000.0,
        "projected_active_drivers": 50.0,
    }
    plan_key = ("2026-04-01", "peru", "lima", "delivery")
    distribution = _build_plan_distribution(plan, date(2026, 4, 1))

    debug = _distribution_debug_entry(plan, plan_key, distribution, grain="daily")

    assert debug["days_in_month"] == 30
    assert debug["weekly_sum"]["trips_completed"] == 100.0
    assert debug["daily_sum"]["trips_completed"] == 100.0
    assert debug["weeks"][0]["week_label"].startswith("S")
    assert debug["weeks"][0]["week_range_label"]
    assert debug["weeks"][0]["days_by_month"]
    assert "daily_plan" in debug["weeks"][0]
