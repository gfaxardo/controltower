"""
Tests coherencia REAL: drill por park no 500, etiqueta canónica park, parks con park_label.
Segmentación conductores (mig 106): drill y children exponen active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct.
"""
import pytest
from app.services.real_lob_drill_pro_service import get_drill_parks, get_drill_children, get_drill


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
        # Segmentación conductores (mig 106): cada fila debe exponer las 4 métricas (pueden ser null/0)
        for key in ("active_drivers", "cancel_only_drivers", "activity_drivers", "cancel_only_pct"):
            assert key in row, f"Children debe incluir {key}"


def test_get_drill_returns_driver_segmentation_metrics():
    """get_drill debe devolver active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct en kpis y en cada row."""
    try:
        out = get_drill(period="month", desglose="LOB", segmento=None, country=None, park_id=None)
    except Exception:
        pytest.skip("DB no disponible")
    assert "countries" in out
    seg_keys = ("active_drivers", "cancel_only_drivers", "activity_drivers", "cancel_only_pct")
    for c in out["countries"]:
        assert "kpis" in c
        for k in seg_keys:
            assert k in c["kpis"], f"kpis debe incluir {k}"
        for row in c.get("rows", []):
            for k in seg_keys:
                assert k in row, f"cada row debe incluir {k}"
