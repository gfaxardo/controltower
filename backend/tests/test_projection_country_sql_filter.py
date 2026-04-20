"""Filtro de país en proyección Omniview: variantes SQL coherentes con facts/plan."""
from __future__ import annotations

from app.services.projection_expected_progress_service import _country_sql_match_values


def test_colombia_variants_include_code_and_full_name():
    vals = set(_country_sql_match_values("COLOMBIA"))
    assert "colombia" in vals
    assert "co" in vals
    assert "col" in vals


def test_peru_variants():
    vals = set(_country_sql_match_values("Perú"))
    assert "peru" in vals
    assert "pe" in vals


def test_empty_country_returns_empty():
    assert _country_sql_match_values(None) == []
    assert _country_sql_match_values("") == []
    assert _country_sql_match_values("   ") == []
