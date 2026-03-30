"""Smoke: módulo BUSINESS_SLICE importable sin BD."""


def test_business_slice_service_import():
    from app.services import business_slice_service as m

    assert m.MV_MONTHLY == "ops.real_business_slice_month_fact"
    assert callable(m.get_business_slice_filters)


def test_month_fact_load_sql_filters_enriched_via_fn_not_resolved_view():
    """Evidencia: agregación mensual no usa FROM ops.v_real_trips_business_slice_resolved."""
    from app.services.business_slice_incremental_load import describe_month_load_sql_contract

    c = describe_month_load_sql_contract()
    assert c["month_path_uses_fn_subset"]
    assert c["month_path_avoids_global_resolved_view"]
    assert c["hour_block_still_uses_resolved_view"]
