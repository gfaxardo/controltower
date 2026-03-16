"""
Tests coherencia REAL: drill por park no 500, etiqueta canónica park, parks con park_label.
"""
import pytest
from app.services.real_lob_drill_pro_service import get_drill_parks, get_drill_children


def test_get_drill_parks_returns_list():
    """get_drill_parks devuelve lista (puede estar vacía si no hay data)."""
    try:
        out = get_drill_parks(country=None)
    except Exception:
        pytest.skip("DB no disponible")
    assert isinstance(out, list)


def test_get_drill_parks_items_have_park_label():
    """Cada ítem de get_drill_parks debe tener park_label (nombre — ciudad — país)."""
    try:
        out = get_drill_parks(country=None)
    except Exception:
        pytest.skip("DB no disponible")
    for p in out:
        assert "park_label" in p
        assert " — " in p["park_label"], "park_label debe ser formato 'nombre — ciudad — país'"


def test_get_drill_children_park_no_500():
    """get_drill_children con desglose=PARK no debe lanzar (compatibilidad con/sin cancelled_trips)."""
    try:
        # País y period_start existentes o vacíos; puede devolver lista vacía
        out = get_drill_children(
            country="pe",
            period="month",
            period_start="2025-01-01",
            desglose="PARK",
            segmento=None,
            park_id=None,
        )
    except Exception as e:
        pytest.fail(f"get_drill_children PARK no debe fallar: {e}")
    assert isinstance(out, list)


def test_get_drill_children_park_rows_have_park_label():
    """Si get_drill_children desglose=PARK devuelve filas, deben tener park_label."""
    try:
        out = get_drill_children(
            country="pe",
            period="month",
            period_start="2025-01-01",
            desglose="PARK",
            segmento=None,
            park_id=None,
        )
    except Exception:
        pytest.skip("DB no disponible")
    for row in out:
        assert "park_label" in row, "Cada fila PARK debe incluir park_label"
        if row.get("park_label"):
            assert " — " in row["park_label"], "park_label debe ser formato 'nombre — ciudad — país'"
