"""
Tests Fase 1 — Observabilidad E2E.
Verifica que los servicios de observabilidad devuelvan estructura esperada.
No requiere migración 092 aplicada: si las tablas no existen, el servicio devuelve listas vacías.
"""
import pytest
from app.services.observability_service import (
    get_observability_overview,
    get_observability_modules,
    get_observability_artifacts,
    get_observability_lineage,
    get_observability_freshness,
)


def test_observability_overview_structure():
    """Overview debe devolver un dict con clave modules (lista)."""
    data = get_observability_overview()
    assert isinstance(data, dict)
    assert "modules" in data
    assert isinstance(data["modules"], list)


def test_observability_modules_returns_list():
    """get_observability_modules debe devolver una lista."""
    out = get_observability_modules()
    assert isinstance(out, list)


def test_observability_artifacts_returns_list():
    """get_observability_artifacts debe devolver una lista."""
    out = get_observability_artifacts()
    assert isinstance(out, list)


def test_observability_lineage_returns_list():
    """get_observability_lineage debe devolver una lista."""
    out = get_observability_lineage()
    assert isinstance(out, list)


def test_observability_freshness_returns_list():
    """get_observability_freshness debe devolver una lista."""
    out = get_observability_freshness()
    assert isinstance(out, list)
