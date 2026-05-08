"""FASE 4.1 — motor de sugerencias (sin ejecución automática)."""

from app.services.projection_suggestion_engine_service import (
    ACTION_CATALOG,
    build_projection_suggestions,
)


def _alert(level, driver, **kwargs):
    base = {
        "level": level,
        "dimension": "lob",
        "entity": "Trujillo - Delivery",
        "gap_trips": -1200.0,
        "gap_pct": -12.0,
        "principal_driver": driver,
        "pacing_vs_expected": "behind",
        "ytd_trend": "deteriorating",
    }
    base.update(kwargs)
    return base


def test_integrity_broken_disables():
    sug, st = build_projection_suggestions(
        integrity_status={"status": "broken"},
        ytd_alerts=[_alert("critical", "productivity")],
    )
    assert sug == []
    assert st == {"status": "disabled", "reason": "integrity_broken"}


def test_no_alerts_empty():
    sug, st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=[],
    )
    assert sug == []
    assert st["status"] == "empty"
    assert st["reason"] == "no_ytd_alerts"


def test_critical_productivity_two_actions():
    alerts = [_alert("critical", "productivity")]
    sug, st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    ids = [s["recommended_action_id"] for s in sug]
    assert "productivity_reactivation" in ids
    assert "productivity_incentive" in ids
    assert st["status"] == "ok"
    assert all(s["execution_enabled"] is False for s in sug)


def test_volume_onboarding_and_scouts_when_gap_large():
    alerts = [_alert("warning", "volume", gap_trips=-8000.0, gap_pct=-5.0)]
    sug, _st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    ids = [s["recommended_action_id"] for s in sug]
    assert ids == ["volume_onboarding_followup", "volume_scouts_push"]


def test_volume_only_onboarding_when_gap_small():
    alerts = [_alert("warning", "volume", gap_trips=-100.0, gap_pct=-2.0)]
    sug, _st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    ids = [s["recommended_action_id"] for s in sug]
    assert ids == ["volume_onboarding_followup"]


def test_ticket_mix_review():
    alerts = [_alert("warning", "ticket")]
    sug, _st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    assert len(sug) == 1
    assert sug[0]["recommended_action_id"] == "ticket_mix_review"


def test_opportunity_replicate():
    alerts = [
        {
            "level": "opportunity",
            "dimension": "city",
            "entity": "Lima · PE",
            "gap_trips": 500.0,
            "gap_pct": 8.0,
            "principal_driver": "volume",
            "pacing_vs_expected": "ahead",
            "ytd_trend": "improving",
        }
    ]
    sug, _st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    assert len(sug) == 1
    assert sug[0]["recommended_action_id"] == "opportunity_replicate_winner"
    assert sug[0]["principal_driver"] == "opportunity"


def test_unknown_driver_data_review():
    alerts = [_alert("warning", None, principal_driver=None)]
    sug, _st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    assert len(sug) == 1
    assert sug[0]["recommended_action_id"] == "data_review"
    assert sug[0]["confidence"] == "low"


def test_integrity_warning_partial_status():
    alerts = [_alert("critical", "productivity")]
    _sug, st = build_projection_suggestions(
        integrity_status={"status": "warning"},
        ytd_alerts=alerts,
    )
    assert st == {"status": "partial", "reason": "integrity_warning"}


def test_sort_critical_before_opportunity():
    alerts = [
        {
            "level": "opportunity",
            "dimension": "country",
            "entity": "PE",
            "gap_trips": 100.0,
            "gap_pct": 2.0,
            "principal_driver": "volume",
            "pacing_vs_expected": "ahead",
            "ytd_trend": "improving",
        },
        _alert("critical", "ticket", entity="X", gap_trips=-9000.0, gap_pct=-20.0),
    ]
    sug, _st = build_projection_suggestions(
        integrity_status={"status": "ok"},
        ytd_alerts=alerts,
    )
    assert sug[0]["level"] == "critical"
    assert any(s["level"] == "opportunity" for s in sug)
    opp_idx = next(i for i, s in enumerate(sug) if s["level"] == "opportunity")
    assert opp_idx > 0


def test_action_catalog_has_required_keys():
    for aid, row in ACTION_CATALOG.items():
        assert aid
        for k in ("name", "driver", "channel_suggested", "owner_suggested", "cost", "speed", "expected_impact", "description"):
            assert k in row
