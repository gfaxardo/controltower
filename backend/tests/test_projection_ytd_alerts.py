"""FASE 3.6 — alertas YTD (lógica pura, sin BD)."""

from app.services.projection_ytd_alerts_service import _alert_level, _sort_alerts


def test_alert_level_rules():
    assert _alert_level("behind", "deteriorating") == "critical"
    assert _alert_level("behind", "flat") == "warning"
    assert _alert_level("behind", "improving") == "warning"
    assert _alert_level("ahead", "improving") == "opportunity"
    assert _alert_level("ahead", "flat") is None
    assert _alert_level("on_track", "deteriorating") is None


def test_sort_alerts_by_abs_gap():
    rows = [
        {"level": "warning", "gap_trips": -100, "gap_pct": -5.0},
        {"level": "critical", "gap_trips": -500, "gap_pct": -2.0},
        {"level": "warning", "gap_trips": -200, "gap_pct": -20.0},
    ]
    _sort_alerts(rows)
    assert rows[0]["gap_trips"] == -500
    assert rows[1]["gap_trips"] == -200
    assert rows[2]["gap_trips"] == -100


def test_sort_alerts_tie_breaker_gap_pct():
    rows = [
        {"gap_trips": -100, "gap_pct": -1.0},
        {"gap_trips": -100, "gap_pct": -10.0},
    ]
    _sort_alerts(rows)
    assert rows[0]["gap_pct"] == -10.0
