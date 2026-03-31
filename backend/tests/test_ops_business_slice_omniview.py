"""Tests del endpoint GET /ops/business-slice/omniview (validación y cableado)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_PAYLOAD = {
    "granularity": "monthly",
    "comparison_rule": "MoM",
    "current_period_start": "2026-02-01",
    "current_period_end_exclusive": "2026-03-01",
    "previous_period_start": "2026-01-01",
    "previous_period_end_exclusive": "2026-02-01",
    "is_current_partial": False,
    "is_previous_partial": False,
    "mixed_currency_warning": False,
    "warnings": [],
    "meta": {
        "detail_source": "ops.real_business_slice_month_fact",
        "totals_source": "ops.v_real_trips_business_slice_resolved",
        "subtotals_source": "ops.v_real_trips_business_slice_resolved",
        "units": {},
        "coverage_level": "none_at_business_slice_grain",
        "coverage_reference": "",
        "daily_window_days": 90,
        "daily_window_note": "",
    },
    "rows": [],
    "subtotals": [],
    "totals": {
        "current": {},
        "previous": {},
        "delta": {},
        "signals": {},
        "flags": {},
    },
}


def test_omniview_weekly_without_country_422():
    r = client.get("/ops/business-slice/omniview", params={"granularity": "weekly"})
    assert r.status_code == 422
    assert "country" in r.json().get("detail", "").lower()


def test_omniview_daily_without_country_422():
    r = client.get("/ops/business-slice/omniview", params={"granularity": "daily"})
    assert r.status_code == 422


def test_omniview_daily_window_over_120_422():
    r = client.get(
        "/ops/business-slice/omniview",
        params={"granularity": "daily", "country": "peru", "daily_window_days": 121},
    )
    assert r.status_code == 422
    detail = r.json().get("detail")
    blob = detail if isinstance(detail, str) else str(detail)
    assert "120" in blob


@patch(
    "app.routers.ops.get_business_slice_omniview",
    return_value=MOCK_PAYLOAD,
)
def test_omniview_monthly_200_shape(mock_svc):
    r = client.get("/ops/business-slice/omniview", params={"granularity": "monthly"})
    assert r.status_code == 200
    body = r.json()
    mock_svc.assert_called_once()
    assert body["granularity"] == "monthly"
    assert "meta" in body
    assert body["meta"]["detail_source"]
    assert body["meta"]["totals_source"]
    assert "rows" in body
    assert "subtotals" in body
    assert "totals" in body
    assert "comparison_rule" in body
    assert "current_period_start" in body


@patch(
    "app.routers.ops.get_business_slice_omniview",
    return_value=MOCK_PAYLOAD,
)
def test_omniview_passes_fleet_subfleet(mock_svc):
    client.get(
        "/ops/business-slice/omniview",
        params={
            "granularity": "weekly",
            "country": "peru",
            "fleet": "X",
            "subfleet": "Y",
            "include_subfleets": True,
            "limit_rows": 100,
        },
    )
    kwargs = mock_svc.call_args.kwargs
    assert kwargs["fleet"] == "X"
    assert kwargs["subfleet"] == "Y"
    assert kwargs["include_subfleets"] is True
    assert kwargs["limit_rows"] == 100
