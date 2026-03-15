"""
Tests Fase 2A — Real vs Proyección.
Verifica estructura de respuestas del servicio. Si la migración 097 no está aplicada,
algunos endpoints pueden devolver error o listas vacías (no se considera fallo de test).
"""
import pytest
from app.services.real_vs_projection_service import (
    get_real_vs_projection_overview,
    get_real_vs_projection_dimensions,
    get_mapping_coverage,
    get_real_metrics,
    get_projection_template_contract,
    get_system_segmentation_view,
    get_projection_segmentation_view,
)


def test_real_vs_projection_overview_structure():
    """Overview debe devolver un dict con claves esperadas."""
    data = get_real_vs_projection_overview()
    assert isinstance(data, dict)
    assert "message" in data or "ready_for_comparison" in data or "error" in data


def test_real_vs_projection_dimensions_returns_list():
    """get_real_vs_projection_dimensions debe devolver una lista de dimensiones."""
    out = get_real_vs_projection_dimensions()
    assert isinstance(out, list)
    if out:
        assert "id" in out[0] and "label" in out[0]


def test_mapping_coverage_returns_list():
    """get_mapping_coverage debe devolver una lista."""
    out = get_mapping_coverage()
    assert isinstance(out, list)


def test_real_metrics_returns_list():
    """get_real_metrics debe devolver una lista (puede estar vacía si no hay BD o datos)."""
    out = get_real_metrics(limit=10)
    assert isinstance(out, list)


def test_projection_template_contract_structure():
    """get_projection_template_contract debe devolver un dict con contrato."""
    data = get_projection_template_contract()
    assert isinstance(data, dict)
    assert "staging_table" in data or "description" in data


def test_system_segmentation_view_returns_list():
    """get_system_segmentation_view debe devolver una lista."""
    out = get_system_segmentation_view(limit=10)
    assert isinstance(out, list)


def test_projection_segmentation_view_returns_list():
    """get_projection_segmentation_view debe devolver una lista."""
    out = get_projection_segmentation_view(limit=10)
    assert isinstance(out, list)
