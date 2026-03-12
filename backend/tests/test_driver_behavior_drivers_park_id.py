"""
Regresión: GET /ops/driver-behavior/drivers con park_id no debe devolver 500.
Bug: missing FROM-clause entry for table "ra" cuando el WHERE usaba alias ra
en el SELECT final FROM with_action. Fix: usar where_sql_main con columnas sin prefijo.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Import app after env so settings/DB can be configured if needed
from app.main import app

client = TestClient(app)


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; driver-behavior/drivers requires DB",
)
def test_driver_behavior_drivers_with_park_id_returns_200():
    """Con park_id el endpoint debe responder 200 y estructura { data, total, limit, offset }."""
    params = {
        "recent_weeks": 4,
        "baseline_weeks": 16,
        "park_id": "00000000-0000-0000-0000-000000000000",
        "limit": 10,
        "offset": 0,
    }
    response = client.get("/ops/driver-behavior/drivers", params=params)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Body: {response.text[:500]}. "
        "If 500 with 'ra' or 'FROM-clause', alias fix may have regressed."
    )
    body = response.json()
    assert "data" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)
def test_driver_behavior_drivers_with_country_city_segment_returns_200():
    """Filtros country, city, segment_current no deben provocar 500 por alias."""
    params = {
        "recent_weeks": 4,
        "baseline_weeks": 16,
        "country": "Spain",
        "city": "Madrid",
        "segment_current": "ELITE",
        "limit": 5,
        "offset": 0,
    }
    response = client.get("/ops/driver-behavior/drivers", params=params)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text[:500]}"
    )
    body = response.json()
    assert "data" in body and "total" in body
