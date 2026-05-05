"""CT-MATCH-3: lob_base de plantilla Control Tower = literal Excel (solo espacios)."""
import pytest

from app.services.plan_template_parser_service import _normalize_lob_display_only


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("YMA", "YMA"),
        ("YMM", "YMM"),
        ("Auto regular", "Auto regular"),
        ("Delivery moto", "Delivery moto"),
        ("Taxi Moto", "Taxi Moto"),
        ("Dellivery bicicleta", "Dellivery bicicleta"),
        ("  Auto  regular  ", "Auto regular"),
        ("YMM\u00a0", "YMM"),
    ],
)
def test_normalize_lob_display_only_preserves_semantics(raw, expected):
    assert _normalize_lob_display_only(raw) == expected


def test_normalize_lob_display_only_no_ymm_to_yma():
    assert _normalize_lob_display_only("YMM") != "YMA"
    assert _normalize_lob_display_only("YMA") != "YMM"


def test_normalize_lob_display_only_no_auto_taxi_alias():
    """Regresión CT-MATCH: 'Auto regular' no debe convertirse a Auto Taxi en ingesta."""
    out = _normalize_lob_display_only("Auto regular")
    assert out == "Auto regular"
    assert out != "Auto Taxi"
