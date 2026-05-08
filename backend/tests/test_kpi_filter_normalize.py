"""Normalización de filtros KPI facts (alias pe/co, case-insensitive en SQL params)."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.utils.kpi_filter_normalize import (  # noqa: E402
    normalize_business_slice_token,
    normalize_city_token,
    normalize_country_token,
)


def test_pe_co_aliases():
    assert normalize_country_token("pe") == "peru"
    assert normalize_country_token("PE") == "peru"
    assert normalize_country_token("co") == "colombia"
    assert normalize_country_token("peru") == "peru"


def test_city_strip():
    assert normalize_city_token(" Lima ") == "Lima"


def test_slice_strip():
    assert normalize_business_slice_token(" Auto regular ") == "Auto regular"
