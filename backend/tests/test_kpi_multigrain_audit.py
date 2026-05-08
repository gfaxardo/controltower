"""Tests utilidades y reglas documentadas P2 KPI multi-grain (sin I/O BD)."""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.utils.kpi_multigrain_audit import (  # noqa: E402
    active_drivers_not_sum_of_days,
    diff_pct,
    explain_iso_week_full_sum_vs_calendar_month,
    map_validation_status_to_audit,
    recompute_avg_ticket,
    trips_completed_must_exclude_cancelled,
)
from scripts.validate_kpi_grain_consistency import (  # noqa: E402
    _eval_additive,
    _eval_semi_additive,
)


def test_recompute_avg_ticket_is_sum_over_count_not_avg_of_avgs():
    assert recompute_avg_ticket(100.0, 4) == 25.0
    assert recompute_avg_ticket(0, 0) is None


def test_map_validation_status():
    assert map_validation_status_to_audit("ok") == "ok"
    assert map_validation_status_to_audit("expected_non_comparable") == "not_certified"


def test_iso_week_doc_mentions_crossing():
    t = explain_iso_week_full_sum_vs_calendar_month().lower()
    assert "iso" in t or "semana" in t or "mes" in t


def test_additive_monthly_matches_daily_sum_within_tolerance():
    status, note = _eval_additive(1000.0, 1000.0, 1200.0, 1000.0)
    assert status == "ok"
    status2, _ = _eval_additive(1000.0, 900.0, 0, 0)
    assert status2 == "fail"


def test_trips_completed_cancelled_separate_contract_doc():
    assert "trips_completed" in trips_completed_must_exclude_cancelled().lower()


def test_eval_additive_weekly_full_mismatch_daily_ok_no_fail():
    """weekly_sum_full_iso puede diverger; intersect=0 omite check secundario."""
    st, _ = _eval_additive(500.0, 500.0, 99999.0, 0.0)
    assert st == "ok"


def test_diff_pct_uses_max_base():
    assert diff_pct(100, 101) == pytest.approx(100 * (101 - 100) / max(100, 101), rel=1e-9)


def test_active_drivers_semi_additive_doc():
    assert "distinct" in active_drivers_not_sum_of_days().lower()


def test_semi_additive_fail_when_monthly_lt_daily_max():
    st, _ = _eval_semi_additive(10.0, 0.0, 5.0, 200.0, 50.0)
    assert st == "fail"
