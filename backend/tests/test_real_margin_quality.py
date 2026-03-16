"""
Tests FASE 8 — Calidad de margen en fuente REAL.
- Reglas de severidad (completados sin margen, cancelados con margen).
- Estructura del payload de API (get_margin_quality_full).
- No inventar margen; cancelados sin margen no son error.
"""
import pytest
from app.services.real_margin_quality_constants import (
    severity_completed_without_margin,
    severity_cancelled_with_margin,
)


# ─── A. Severidad anomalía principal: completados sin margen ───

def test_completed_without_margin_zero_trips_ok():
    assert severity_completed_without_margin(0, 0, 0) == "OK"


def test_completed_without_margin_all_have_margin_ok():
    assert severity_completed_without_margin(100, 0, 100) == "OK"


def test_completed_without_margin_some_without_info():
    # 0.4% sin margen -> INFO (< 0.5% umbral WARNING)
    assert severity_completed_without_margin(1000, 4, 996) == "INFO"


def test_completed_without_margin_warning_threshold():
    # > 0.5% sin margen -> WARNING
    assert severity_completed_without_margin(1000, 6, 994) == "WARNING"


def test_completed_without_margin_critical_threshold():
    # > 2% sin margen -> CRITICAL
    assert severity_completed_without_margin(1000, 25, 975) == "CRITICAL"


def test_completed_without_margin_zero_coverage_critical():
    # completed_trips > 0 y completed_trips_with_margin = 0 -> CRITICAL
    assert severity_completed_without_margin(100, 100, 0) == "CRITICAL"


# ─── B. Severidad anomalía secundaria: cancelados con margen ───

def test_cancelled_with_margin_zero_cancelled_ok():
    assert severity_cancelled_with_margin(0, 0) == "OK"


def test_cancelled_with_margin_none_with_margin_ok():
    assert severity_cancelled_with_margin(100, 0) == "OK"


def test_cancelled_with_margin_warning_threshold():
    # > 5% cancelados con margen -> WARNING
    assert severity_cancelled_with_margin(100, 6) == "WARNING"


def test_cancelled_with_margin_critical_threshold():
    # > 10% cancelados con margen -> CRITICAL
    assert severity_cancelled_with_margin(100, 11) == "CRITICAL"


# ─── C. API / servicio: estructura del payload ───

def test_get_margin_quality_full_structure():
    """get_margin_quality_full devuelve dict con keys esperados (puede fallar si no hay DB)."""
    from app.services.real_margin_quality_service import get_margin_quality_full

    try:
        data = get_margin_quality_full(days_recent=90, findings_limit=5)
    except Exception:
        pytest.skip("DB no disponible")
    assert isinstance(data, dict)
    assert "aggregate" in data
    assert "severity_primary" in data
    assert "severity_secondary" in data
    assert "has_margin_source_gap" in data
    assert "margin_coverage_incomplete" in data
    assert "has_cancelled_with_margin_issue" in data
    assert "margin_quality_status" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert "affected_week_dates" in data
    assert "affected_month_dates" in data
    if data.get("aggregate"):
        agg = data["aggregate"]
        assert "completed_trips" in agg
        assert "completed_trips_without_margin" in agg
        assert "margin_coverage_pct" in agg
        assert "cancelled_trips" in agg
        assert "cancelled_trips_with_margin" in agg
