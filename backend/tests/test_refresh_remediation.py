"""
QA Tests — Refresh Remediation Control (CF-H1G)

Verifica:
- Lógica de agregación de status en freshness governance
- Estructura de respuesta del refresh job
- Startup check liviano de omniview freshness
"""
import pytest
from datetime import date


# ── Freshness Governance Service Logic ──

def test_worst_status_ordering():
    from app.services.omniview_freshness_governance_service import (
        _worst_status,
        STATUS_OK,
        STATUS_WARNING,
        STATUS_BLOCKED,
        STATUS_ERROR,
    )
    assert _worst_status(STATUS_OK, STATUS_OK) == STATUS_OK
    assert _worst_status(STATUS_OK, STATUS_WARNING) == STATUS_WARNING
    assert _worst_status(STATUS_OK, STATUS_BLOCKED) == STATUS_BLOCKED
    assert _worst_status(STATUS_WARNING, STATUS_BLOCKED) == STATUS_BLOCKED
    assert _worst_status(STATUS_BLOCKED, STATUS_BLOCKED) == STATUS_BLOCKED
    assert _worst_status(STATUS_ERROR, STATUS_OK) == STATUS_ERROR
    assert _worst_status(STATUS_ERROR, STATUS_BLOCKED) == STATUS_ERROR
    assert _worst_status(STATUS_OK, STATUS_WARNING, STATUS_BLOCKED, STATUS_ERROR) == STATUS_ERROR


def test_status_from_lag():
    from app.services.omniview_freshness_governance_service import (
        _status_from_lag,
        STATUS_OK,
        STATUS_WARNING,
        STATUS_BLOCKED,
        STATUS_ERROR,
    )
    assert _status_from_lag(0) == STATUS_OK
    assert _status_from_lag(1) == STATUS_OK
    assert _status_from_lag(2) == STATUS_WARNING
    assert _status_from_lag(3) == STATUS_WARNING
    assert _status_from_lag(4) == STATUS_BLOCKED
    assert _status_from_lag(10) == STATUS_BLOCKED
    assert _status_from_lag(None) == STATUS_ERROR


def test_freshness_governance_returns_expected_keys():
    from app.services.omniview_freshness_governance_service import get_omniview_freshness_governance

    result = get_omniview_freshness_governance()
    assert isinstance(result, dict)
    assert "status" in result
    assert "raw" in result
    assert "facts" in result
    assert "message" in result
    assert "remediation" in result
    assert result["status"] in ("ok", "warning", "blocked", "error")


def test_freshness_governance_facts_structure():
    from app.services.omniview_freshness_governance_service import get_omniview_freshness_governance

    result = get_omniview_freshness_governance()
    facts = result.get("facts", {})
    for key in ("daily", "weekly", "monthly"):
        assert key in facts, f"Missing fact layer: {key}"

    serving = result.get("serving", {})
    for key in ("daily", "weekly", "monthly"):
        assert key in serving, f"Missing serving layer: {key}"


def test_freshness_governance_blocked_has_remediation_message():
    from app.services.omniview_freshness_governance_service import get_omniview_freshness_governance

    result = get_omniview_freshness_governance()
    if result["status"] == "blocked":
        assert result["message"], "BLOCKED status should have a message"
        assert result["remediation"], "BLOCKED status should have remediation text"


def test_freshness_governance_ok_has_no_remediation():
    from app.services.omniview_freshness_governance_service import get_omniview_freshness_governance

    result = get_omniview_freshness_governance()
    if result["status"] == "ok":
        assert result["remediation"] is None
        assert "OK" in result["message"]


# ── Refresh Job Structure ──

def test_refresh_job_return_structure():
    from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job

    result = run_business_slice_real_refresh_job(force=False)
    assert isinstance(result, dict)
    assert "ok" in result
    assert "duration_seconds" in result
    assert "errors" in result
    assert "log" in result
    assert "freshness_after" in result
    assert "upstream_preflight" in result

    if result.get("skipped"):
        assert "reason" in result, "Skipped refresh should include reason"


def test_refresh_job_respects_cooldown_by_default():
    from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job

    first = run_business_slice_real_refresh_job(force=False)
    second = run_business_slice_real_refresh_job(force=False)

    if not first.get("skipped") and first.get("ok") and first.get("duration_seconds", 0) > 0:
        assert second.get("skipped") or second.get("ok"), (
            "Second call should be skipped due to cooldown or run successfully if cooldown passed in tests"
        )


def test_refresh_job_force_bypasses_cooldown():
    from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job

    result = run_business_slice_real_refresh_job(force=True)
    assert "ok" in result
    if result.get("skipped"):
        assert result.get("reason") in ("no_upstream_data", "lock_held_by_another_worker")


# ── Startup Check Omniview Freshness ──

def test_startup_omniview_freshness_check_injects_into_report():
    from app.startup_checks import _run_omniview_freshness_startup_check

    report: dict = {"overall": "ok", "checks": []}
    _run_omniview_freshness_startup_check(report)

    assert "omniview_freshness_startup" in report
    fs = report["omniview_freshness_startup"]
    assert "status" in fs
    assert "raw_max_date" in fs
    assert "daily_max_date" in fs
    assert "message" in fs
    assert fs["status"] in ("ok", "warning", "blocked", "error")

    checks = [c for c in report["checks"] if c["name"] == "omniview_freshness"]
    assert len(checks) == 1
    assert checks[0]["tier"] == "non_blocking"


def test_startup_check_does_not_alter_overall_when_blocked():
    from app.startup_checks import _run_omniview_freshness_startup_check

    report: dict = {"overall": "ok", "checks": []}
    _run_omniview_freshness_startup_check(report)

    assert report["overall"] == "ok", (
        "Omniview freshness check is non_blocking — should not change overall status"
    )


# ── Scheduler Settings Defaults ──

def test_ct_scheduler_disabled_by_default():
    from app.settings import settings

    assert settings.CT_SCHEDULER_ENABLED is False, (
        "CT_SCHEDULER_ENABLED debe ser False por defecto. "
        "APScheduler no debe iniciar en dev sin configuración explícita."
    )


def test_omniview_refresh_has_timeout_configured():
    from app.settings import settings

    timeout = settings.OMNIVIEW_REAL_REFRESH_TIMEOUT_MS
    assert timeout > 0
    assert timeout >= 60000, "Timeout should be at least 60s (1 minute)"


def test_omniview_refresh_has_cooldown_configured():
    from app.settings import settings

    cooldown = settings.OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES
    assert cooldown > 0
    assert cooldown <= 1440, "Cooldown should be at most 1440 minutes (1 day)"


# ── CF-H1L.2: Post-Migration Serving Integrity Guard ──

def test_post_migration_guard_returns_expected_structure():
    from app.services.omniview_serving_integrity_guard import validate_omniview_serving_integrity

    result = validate_omniview_serving_integrity()
    assert isinstance(result, dict)
    assert "status" in result
    assert result["status"] in ("ok", "warning", "blocked", "error")
    assert "message" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)
    assert "missing_periods" in result
    assert isinstance(result["missing_periods"], list)
    assert "closed_months" in result
    assert "closed_weeks" in result
    assert "remediation" in result
    assert "evaluated_at" in result


def test_post_migration_guard_passes_when_facts_present():
    from app.services.omniview_serving_integrity_guard import validate_omniview_serving_integrity

    result = validate_omniview_serving_integrity()
    assert result["status"] in ("ok", "warning", "blocked"), (
        f"Status should be ok/warning/blocked, got {result['status']}. "
        f"Message: {result.get('message')}"
    )
    assert len(result["checks"]) > 0, "Should have at least one check entry"
    if result["status"] in ("warning", "blocked"):
        assert result.get("remediation") is not None, (
            f"{result['status']} status should have remediation text"
        )
        assert len(result["missing_periods"]) > 0, (
            f"{result['status']} status should list missing periods"
        )


def test_post_migration_guard_returns_remediation_not_runtime_refresh():
    from app.services.omniview_serving_integrity_guard import validate_omniview_serving_integrity

    result = validate_omniview_serving_integrity()

    if result["status"] == "blocked":
        remediation = result.get("remediation")
        assert remediation is not None, "BLOCKED must have remediation text"
        assert "refresh_omniview_real_slice_incremental" in remediation.lower(), (
            "Remediation should point to the canonical refresh script"
        )
        assert "CT_SCHEDULER_ENABLED" in remediation, (
            "Remediation should mention scheduler status"
        )
    elif result["status"] == "ok":
        assert result.get("remediation") is None, "OK status should have no remediation"
    else:
        pass


def test_post_migration_guard_periods_are_in_past():
    from app.services.omniview_serving_integrity_guard import (
        _closed_iso_weeks,
        _closed_months,
    )
    from datetime import date

    weeks = _closed_iso_weeks(5)
    months = _closed_months(2)
    today = date.today()

    for w in weeks:
        assert w < today, f"Closed week {w} should be in the past"
    for m in months:
        assert m < date(today.year, today.month, 1), (
            f"Closed month {m} should be before current month start"
        )
