"""Smoke: módulo BUSINESS_SLICE importable sin BD."""

import math
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


def test_month_fact_load_uses_temp_table_not_resolved_view():
    """Evidencia: agregación mensual usa _bs_enriched_month (temp table), no la vista resolved."""
    from app.services.business_slice_incremental_load import describe_month_load_sql_contract

    c = describe_month_load_sql_contract()
    assert c["month_path_uses_temp_table"]
    assert c["month_path_avoids_global_resolved_view"]
    assert c["month_path_avoids_fn_subset"]
    assert c["hour_block_still_uses_resolved_view"]
