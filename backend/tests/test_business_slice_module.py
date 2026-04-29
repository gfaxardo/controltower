"""Smoke: módulo BUSINESS_SLICE importable sin BD."""

import math
from datetime import date
from decimal import Decimal


def test_business_slice_service_import():
    from app.services import business_slice_service as m

    assert m.MV_MONTHLY == "ops.real_business_slice_month_fact"
    assert callable(m.get_business_slice_filters)


def test_serialize_row_json_safe_scalars():
    from app.services.business_slice_service import _serialize_row

    row = {
        "ok": 1.5,
        "nan_f": float("nan"),
        "inf_f": float("inf"),
        "dec_nan": Decimal("NaN"),
        "dec_ok": Decimal("3.25"),
        "flag": True,
    }
    out = _serialize_row(row)
    assert out["ok"] == 1.5
    assert out["nan_f"] is None
    assert out["inf_f"] is None
    assert out["dec_nan"] is None
    assert math.isclose(out["dec_ok"], 3.25)
    assert out["flag"] is True

    try:
        import numpy as np

        n = _serialize_row({"x": np.float64("nan"), "y": np.float64(2.5)})
        assert n["x"] is None
        assert math.isclose(n["y"], 2.5)
    except ImportError:
        pass


def test_where_clauses_cross_year_monthly_full_year():
    from app.services.business_slice_service import _where_clauses

    w, p = _where_clauses(None, None, None, None, None, 2026, None, "")
    joined = " ".join(w)
    assert "EXTRACT(YEAR FROM month)" in joined
    assert "month = %s::date" in joined
    assert 2026 in p
    assert date(2025, 12, 1) in p


def test_where_clauses_january_includes_previous_december():
    from app.services.business_slice_service import _where_clauses

    w, p = _where_clauses(None, None, None, None, None, 2026, 1, "")
    assert date(2025, 12, 1) in p
    assert date(2026, 1, 1) in p


def test_business_slice_filter_expands_canonical_delivery_aliases(monkeypatch):
    from app.services import business_slice_service as svc

    monkeypatch.setattr(
        svc,
        "business_slice_filter_variants",
        lambda value: ["Delivery", "Delivery moto"] if value == "Delivery" else [],
    )

    variants = svc._business_slice_filter_values("Delivery")
    assert "Delivery" in variants
    assert "Delivery moto" in variants

    w, p = svc._where_clauses(None, None, "Delivery", None, None, 2026, None, "")
    joined = " ".join(w)
    assert "IN (" in joined
    assert "delivery" in p
    assert "delivery moto" in p


def test_calendar_year_week_bounds_spans_late_december():
    from app.services.business_slice_service import _calendar_year_week_bounds

    lo, hi = _calendar_year_week_bounds(2026)
    assert lo == date(2025, 12, 18)
    assert hi == date(2027, 1, 6)


def test_data_freshness_status_from_lag():
    from app.services.business_slice_service import _data_freshness_status_from_lag

    assert _data_freshness_status_from_lag(None) == "broken"
    assert _data_freshness_status_from_lag(0) == "ok"
    assert _data_freshness_status_from_lag(1) == "ok"
    assert _data_freshness_status_from_lag(2) == "warning"
    assert _data_freshness_status_from_lag(3) == "warning"
    assert _data_freshness_status_from_lag(4) == "stale"


def test_explicit_day_temporal_fields():
    from app.services.business_slice_service import explicit_day_temporal_fields

    o = explicit_day_temporal_fields("2026-04-27")
    assert o["date"] == "2026-04-27"
    assert o["weekday"] == "LUNES"
    assert o["day_label"] == "LUNES 27 ABR 2026"


def test_month_fact_load_uses_temp_table_not_resolved_view():
    """Evidencia: agregación mensual usa _bs_enriched_month (temp table), no la vista resolved."""
    from app.services.business_slice_incremental_load import describe_month_load_sql_contract

    c = describe_month_load_sql_contract()
    assert c["month_path_uses_temp_table"]
    assert c["month_path_avoids_global_resolved_view"]
    assert c["month_path_avoids_fn_subset"]
    assert c["hour_block_still_uses_resolved_view"]
