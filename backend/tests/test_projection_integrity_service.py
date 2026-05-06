"""Tests FASE 3.7 / 3.8B — projection integrity status."""

from app.services.projection_integrity_service import (
    build_projection_integrity_status,
    safe_build_projection_integrity_status,
)


def _auth_peru_lima():
    return {
        "total": {
            "row_type": "total",
            "row_scope_key": "__PORTFOLIO__",
            "ytd_slice": {
            "slice_key": "__PORTFOLIO__",
            "slice_level": "total",
            "metric_trace": {"basis": "test_fixture"},
        },
        },
        "by_country": {},
        "by_city": {
            "peru::lima": {
                "row_type": "city",
                "row_scope_key": "peru::lima",
                "ytd_slice": {"slice_key": "peru::lima", "slice_level": "city"},
            },
        },
        "rows": [],
    }


def _row(with_pop: bool, with_ytd_slice: bool = True):
    r = {"country": "peru", "city": "lima", "business_slice_name": "x", "trips_completed": 1}
    if with_pop:
        r["period_over_period"] = {"comparable": False, "kind": "mom"}
    if with_ytd_slice:
        r["ytd_slice"] = {"slice_key": "peru::lima::x::0::", "slice_level": "lob"}
        r["row_type"] = "lob"
        r["row_scope_key"] = "peru::lima::x::0::"
    return r


def test_integrity_ok_full():
    rows = [_row(True), _row(True)]
    ytd = {"grain": "monthly", "year": 2026, "ytd_trend": "flat"}
    out = build_projection_integrity_status(
        display_rows=rows,
        ytd_summary=ytd,
        ytd_alerts=[{"level": "warning"}],
        had_resolved_plan=True,
        matched_count=2,
        plan_without_real_count=0,
        authoritative_ytd=_auth_peru_lima(),
    )
    assert out["status"] == "ok"
    assert out["can_make_decisions"] is True
    assert out["checks"]["period_over_period"] == "ok"
    assert out["checks"]["ytd_summary"] == "ok"
    assert out["checks"]["authoritative_aggregation"] == "ok"


def test_integrity_broken_no_ytd():
    out = build_projection_integrity_status(
        display_rows=[_row(True)],
        ytd_summary=None,
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=1,
        plan_without_real_count=0,
        authoritative_ytd=None,
    )
    assert out["status"] == "broken"
    assert out["can_make_decisions"] is False
    assert out["checks"]["ytd_summary"] == "missing"


def test_integrity_broken_ytd_error():
    out = build_projection_integrity_status(
        display_rows=[_row(True)],
        ytd_summary={"error": "x", "grain": "monthly"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=1,
        plan_without_real_count=0,
        authoritative_ytd=_auth_peru_lima(),
    )
    assert out["status"] == "broken"
    assert out["checks"]["ytd_summary"] == "error"


def test_integrity_broken_all_pop_missing():
    rows = [_row(False), _row(False)]
    out = build_projection_integrity_status(
        display_rows=rows,
        ytd_summary={"ytd_trend": "flat"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=2,
        plan_without_real_count=0,
        authoritative_ytd=_auth_peru_lima(),
    )
    assert out["status"] == "broken"
    assert out["checks"]["period_over_period"] == "missing"


def test_integrity_warning_partial_pop():
    rows = [_row(True), _row(False)]
    out = build_projection_integrity_status(
        display_rows=rows,
        ytd_summary={"ytd_trend": "flat"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=2,
        plan_without_real_count=0,
        authoritative_ytd=_auth_peru_lima(),
    )
    assert out["status"] == "warning"
    assert out["checks"]["period_over_period"] == "partial"
    assert out["can_make_decisions"] is True


def test_integrity_broken_plan_but_no_rows():
    out = build_projection_integrity_status(
        display_rows=[],
        ytd_summary={"ytd_trend": "flat"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=0,
        plan_without_real_count=0,
        authoritative_ytd=None,
    )
    assert out["status"] == "broken"
    assert out["checks"]["data_rows"] == "empty"


def test_safe_wrap_never_raises():
    out = safe_build_projection_integrity_status(
        display_rows=object(),  # type: ignore[arg-type]
        ytd_summary=None,
        ytd_alerts=[],
        had_resolved_plan=False,
        matched_count=0,
        plan_without_real_count=0,
        authoritative_ytd=None,
    )
    assert out["status"] == "warning"
    assert "No se pudo calcular integridad" in out["issues"][0]


def test_integrity_warning_partial_ytd_slice():
    rows = [_row(True, True), _row(True, False)]
    out = build_projection_integrity_status(
        display_rows=rows,
        ytd_summary={"ytd_trend": "flat"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=2,
        plan_without_real_count=0,
        authoritative_ytd=_auth_peru_lima(),
    )
    assert out["status"] == "warning"
    assert out["checks"]["ytd_slice"] == "partial"
    assert out["checks"]["authoritative_aggregation"] == "partial"
    assert out["can_make_decisions"] is True


def test_integrity_broken_all_ytd_slice_missing():
    rows = [_row(True, with_ytd_slice=False)]
    out = build_projection_integrity_status(
        display_rows=rows,
        ytd_summary={"ytd_trend": "flat"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=1,
        plan_without_real_count=0,
        authoritative_ytd=_auth_peru_lima(),
    )
    assert out["status"] == "broken"
    assert out["checks"]["ytd_slice"] == "missing"


def test_integrity_broken_authoritative_missing():
    out = build_projection_integrity_status(
        display_rows=[_row(True)],
        ytd_summary={"grain": "monthly", "ytd_trend": "flat"},
        ytd_alerts=[],
        had_resolved_plan=True,
        matched_count=1,
        plan_without_real_count=0,
        authoritative_ytd=None,
    )
    assert out["status"] == "broken"
    assert out["checks"]["authoritative_aggregation"] == "missing"
