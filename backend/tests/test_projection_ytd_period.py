"""Tests FASE 3.5: YTD / period-over-period (sin BD cuando aplica)."""

from app.services.projection_ytd_period_service import (
    apply_period_over_period_inplace,
    _avg_ticket_ratio,
    _variation,
)


def test_period_over_period_mom_order():
    rows = [
        {
            "country": "peru",
            "city": "lima",
            "business_slice_name": "auto_taxi",
            "is_subfleet": False,
            "subfleet_name": "",
            "month": "2026-01-01",
            "trips_completed": 100,
            "revenue_yego_net": 500,
        },
        {
            "country": "peru",
            "city": "lima",
            "business_slice_name": "auto_taxi",
            "is_subfleet": False,
            "subfleet_name": "",
            "month": "2026-02-01",
            "trips_completed": 110,
            "revenue_yego_net": 550,
        },
    ]
    apply_period_over_period_inplace(rows, "monthly")
    assert rows[0]["period_over_period"]["comparable"] is False
    assert rows[1]["period_over_period"]["comparable"] is True
    assert rows[1]["period_over_period"]["kind"] == "mom"
    m = rows[1]["period_over_period"]["metrics"]["trips_completed"]
    assert m["abs"] == 10
    assert m["pct"] is not None
    at = rows[1]["period_over_period"]["metrics"]["avg_ticket"]
    assert at["basis"] == "derived_ratio"
    assert at["cur"] is not None and at["prev"] is not None


def test_avg_ticket_ratio_zero_trips():
    assert _avg_ticket_ratio(0, 100) is None
    assert _avg_ticket_ratio(10, 100) == 10.0


def test_variation_div_zero():
    ab, pc = _variation(5.0, 0.0)
    assert ab == 5.0
    assert pc is None


def test_dod_requires_distinct_lines():
    rows = [
        {
            "country": "peru",
            "city": "lima",
            "business_slice_name": "a",
            "is_subfleet": False,
            "subfleet_name": "",
            "trip_date": "2026-03-01",
            "trips_completed": 10,
        },
        {
            "country": "peru",
            "city": "lima",
            "business_slice_name": "b",
            "is_subfleet": False,
            "subfleet_name": "",
            "trip_date": "2026-03-02",
            "trips_completed": 12,
        },
    ]
    apply_period_over_period_inplace(rows, "daily")
    # Distinta tajada: no hay "período anterior" en la misma línea
    assert rows[0]["period_over_period"]["comparable"] is False
    assert rows[1]["period_over_period"]["comparable"] is False


def test_pacing_bands():
    from app.services.projection_ytd_period_service import _pacing_vs_expected

    assert _pacing_vs_expected(104.0) == "ahead"
    assert _pacing_vs_expected(100.0) == "on_track"
    assert _pacing_vs_expected(96.5) == "behind"
    assert _pacing_vs_expected(None) is None


def test_ytd_trend_slope():
    from app.services.projection_ytd_period_service import _classify_ytd_trend

    assert (
        _classify_ytd_trend(
            [
                {"attainment_pct": 90.0},
                {"attainment_pct": 92.0},
                {"attainment_pct": 94.0},
            ]
        )
        == "improving"
    )
    assert _classify_ytd_trend([{"attainment_pct": 95.0}]) == "flat"
