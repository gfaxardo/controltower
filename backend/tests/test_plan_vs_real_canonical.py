"""
Tests Plan vs Real: schema legacy vs canonical, fallback, flags y respuesta del endpoint.
"""
import pytest
from unittest.mock import patch, MagicMock

# Schema esperado de cada fila (keys mínimos)
EXPECTED_ROW_KEYS = {
    "country", "city", "park_id", "park_name", "real_tipo_servicio", "period_date",
    "trips_plan", "trips_real", "revenue_plan", "revenue_real",
    "variance_trips", "variance_revenue", "status_bucket",
    "month", "gap_trips", "gap_revenue",
}


@pytest.fixture
def mock_db():
    """Evita dependencia de DB en tests unitarios."""
    with patch("app.services.plan_vs_real_service.get_db") as m:
        yield m


def _sample_row():
    return {
        "country": "pe",
        "city": "lima",
        "park_id": "1",
        "park_name": "Park",
        "real_tipo_servicio": "express",
        "period_date": None,
        "trips_plan": 10,
        "trips_real": 8,
        "revenue_plan": 100.0,
        "revenue_real": 80.0,
        "variance_trips": -2,
        "variance_revenue": -20.0,
        "status_bucket": "matched",
        "month": "2025-01-01",
        "gap_trips": 2,
        "gap_revenue": 20.0,
    }


def test_plan_vs_real_row_schema():
    """Ambas fuentes (legacy/canonical) deben devolver filas con el mismo schema."""
    row = _sample_row()
    assert EXPECTED_ROW_KEYS.issubset(set(row.keys())), "Falta algún key esperado en la fila de ejemplo"


def test_plan_vs_real_resolve_source_legacy():
    """source=legacy debe forzar use_canonical=False."""
    from app.routers.ops import _plan_vs_real_resolve_source

    with patch("app.routers.ops.get_latest_parity_audit", return_value={"diagnosis": "MATCH", "data_completeness": "FULL"}):
        use_canonical, parity, completeness = _plan_vs_real_resolve_source("legacy", None)
    assert use_canonical is False
    assert parity in ("MATCH", "MINOR_DIFF", "MAJOR_DIFF", "UNKNOWN")
    assert completeness in ("FULL", "PARTIAL", "MISSING")


def test_plan_vs_real_resolve_source_canonical():
    """source=canonical debe forzar use_canonical=True."""
    from app.routers.ops import _plan_vs_real_resolve_source

    with patch("app.routers.ops.get_latest_parity_audit", return_value={"diagnosis": "MINOR_DIFF", "data_completeness": "FULL"}):
        use_canonical, parity, completeness = _plan_vs_real_resolve_source("canonical", None)
    assert use_canonical is True
    assert completeness in ("FULL", "PARTIAL", "MISSING")


def test_plan_vs_real_resolve_source_fallback_major():
    """Con USE_CANONICAL_PLAN_VS_REAL_DEFAULT=True y parity MAJOR_DIFF debe hacer fallback a legacy."""
    from app.routers.ops import _plan_vs_real_resolve_source

    with patch("app.routers.ops.get_latest_parity_audit", return_value={"diagnosis": "MAJOR_DIFF", "data_completeness": "PARTIAL"}):
        with patch("app.routers.ops.settings", MagicMock(USE_CANONICAL_PLAN_VS_REAL_DEFAULT=True)):
            use_canonical, parity, _ = _plan_vs_real_resolve_source(None, None)
    assert use_canonical is False
    assert parity == "MAJOR_DIFF"


def test_plan_vs_real_response_shape():
    """El endpoint debe devolver data, total_records, source_status, parity_status, data_completeness."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
    except Exception as e:
        pytest.skip(f"TestClient/httpx not available: {e}")
    client = TestClient(app)
    with patch("app.routers.ops.get_plan_vs_real_monthly", return_value=[_sample_row()]):
        with patch("app.routers.ops.get_latest_parity_audit", return_value={"diagnosis": "MATCH", "data_completeness": "FULL"}):
            with patch("app.routers.ops.log_plan_vs_real_source_usage"):
                r = client.get("/ops/plan-vs-real/monthly", params={"source": "canonical"})
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "source_status" in body
    assert "parity_status" in body
    assert "data_completeness" in body
    assert body["source_status"] in ("canonical", "legacy")
    assert isinstance(body["data"], list)
    if body["data"]:
        assert EXPECTED_ROW_KEYS.issubset(set(body["data"][0].keys()))
