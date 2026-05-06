"""FASE 3.8 — YTD por slice (misma lógica que YTD global en granularidad weekly desde filas)."""

from datetime import date

from app.services.projection_ytd_period_service import compute_ytd_slice_by_line_key


def _base_row(
    *,
    country: str,
    city: str,
    bsn: str,
    week_start: str,
    iso_year: int,
    trips: float,
    exp: float,
    rev: float = 0.0,
    rev_exp: float = 0.0,
    is_sf: bool = False,
    sub: str = "",
):
    return {
        "country": country,
        "city": city,
        "business_slice_name": bsn,
        "is_subfleet": is_sf,
        "subfleet_name": sub,
        "week_start": week_start,
        "iso_year": iso_year,
        "trips_completed": trips,
        "trips_completed_projected_expected": exp,
        "revenue_yego_net": rev,
        "revenue_yego_net_projected_expected": rev_exp,
        "active_drivers": 10.0,
        "active_drivers_projected_expected": 10.0,
    }


def test_ytd_slice_weekly_two_slices_adds_up():
    today = date(2026, 5, 5)  # martes; semana ISO actual corta en ref_monday
    rows = [
        _base_row(
            country="peru",
            city="lima",
            bsn="auto",
            week_start="2026-05-04",
            iso_year=2026,
            trips=100,
            exp=100,
            rev=500,
            rev_exp=500,
        ),
        _base_row(
            country="peru",
            city="trujillo",
            bsn="delivery",
            week_start="2026-05-04",
            iso_year=2026,
            trips=50,
            exp=40,
            rev=200,
            rev_exp=160,
        ),
    ]
    by_key = compute_ytd_slice_by_line_key(
        None,
        grain="weekly",
        display_rows=rows,
        plan_version="pv1",
        idx=None,
        map_rows=[],
        country="peru",
        city=None,
        business_slice=None,
        year=2026,
        month=5,
        today=today,
    )
    assert len(by_key) == 2
    lima = by_key[("peru", "lima", "auto", False, "")]
    truj = by_key[("peru", "trujillo", "delivery", False, "")]
    assert lima["ytd_real_trips"] == 100
    assert lima["ytd_plan_expected_trips"] == 100
    assert lima["ytd_attainment_pct"] == 100.0
    assert truj["ytd_attainment_pct"] == 125.0
    assert truj["slice_level"] == "lob"
    assert "lima" in truj["slice_key"] or "trujillo" in truj["slice_key"]


def test_ytd_slice_subfleet_level():
    today = date(2026, 5, 5)
    rows = [
        _base_row(
            country="peru",
            city="lima",
            bsn="auto",
            week_start="2026-05-04",
            iso_year=2026,
            trips=10,
            exp=10,
            is_sf=True,
            sub="sf1",
        ),
    ]
    by_key = compute_ytd_slice_by_line_key(
        None,
        grain="weekly",
        display_rows=rows,
        plan_version="pv1",
        idx=None,
        map_rows=[],
        country="peru",
        city="lima",
        business_slice=None,
        year=2026,
        month=5,
        today=today,
    )
    k = ("peru", "lima", "auto", True, "sf1")
    assert k in by_key
    assert by_key[k]["slice_level"] == "subfleet"
    assert by_key[k]["slice_key"].endswith("::1::sf1")
