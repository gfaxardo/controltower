from __future__ import annotations

from datetime import date

from app.config.kpi_aggregation_rules import get_omniview_kpi_rule
from app.services import business_slice_incremental_load as load_svc
from app.services import business_slice_service as svc


def test_active_drivers_rule_blocks_rollup():
    rule = get_omniview_kpi_rule("active_drivers")
    assert rule["aggregation_type"] == "semi_additive_distinct"
    assert rule["rebuild_from_atomic"] is True
    assert rule["allowed_rollup_from_lower_grain"] is False


def test_avg_ticket_rule_requires_canonical_components():
    rule = get_omniview_kpi_rule("avg_ticket")
    assert rule["rollup_components_required"] == [
        "ticket_sum_completed",
        "ticket_count_completed",
    ]


def test_canonical_metrics_from_components_rebuilds_ratios():
    metrics = svc._canonical_metrics_from_components(
        {
            "trips_completed": 18,
            "trips_cancelled": 2,
            "active_drivers": 6,
            "ticket_sum_completed": 270.0,
            "ticket_count_completed": 18,
            "revenue_yego_net": 81.0,
            "total_fare_completed_positive_sum": 300.0,
        }
    )
    assert metrics["avg_ticket"] == 15.0
    assert metrics["commission_pct"] == 0.27
    assert metrics["cancel_rate_pct"] == 0.1
    assert metrics["trips_per_driver"] == 3.0


def test_extract_period_comparison_ranges_uses_period_key():
    rows = [
        {
            "week_start": "2026-04-06",
            "comparison_context": {
                "previous_equivalent_range_start": "2026-03-30",
                "previous_equivalent_cutoff_date": "2026-04-02",
            },
        },
        {
            "week_start": "2026-04-06",
            "comparison_context": {
                "previous_equivalent_range_start": "2026-03-30",
                "previous_equivalent_cutoff_date": "2026-04-02",
            },
        },
    ]
    ranges = svc._extract_period_comparison_ranges(rows, "weekly")
    assert ranges == {
        "2026-04-06": (date(2026, 3, 30), date(2026, 4, 2)),
    }


def test_safe_fetch_matrix_totals_meta_contract(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_fetch_resolved_period_totals",
        lambda *args, **kwargs: {"2026-04-01": {"trips_completed": 10, "trips_cancelled": 1}},
    )
    monkeypatch.setattr(
        svc,
        "_fetch_resolved_metrics_for_range",
        lambda *args, **kwargs: {"trips_completed": 8, "trips_cancelled": 1},
    )
    rows = [
        {
            "month": "2026-04-01",
            "comparison_context": {
                "previous_equivalent_range_start": "2026-03-01",
                "previous_equivalent_cutoff_date": "2026-03-10",
            },
        }
    ]
    meta = svc._safe_fetch_matrix_totals_meta("monthly", rows, country="Peru")
    assert meta["period_totals"]["2026-04-01"]["trips_completed"] == 10
    assert meta["comparison_period_totals"]["2026-04-01"]["trips_completed"] == 8
    assert "unmapped_period_totals" in meta


def test_weekly_sql_uses_resolved_and_distinct_drivers():
    sql = load_svc._WEEK_AGG_FROM_RESOLVED.lower()
    assert "count(distinct r.driver_id)" in sql
    assert "sum(d.active_drivers)" not in sql
    assert "from {resolved} r" in sql
