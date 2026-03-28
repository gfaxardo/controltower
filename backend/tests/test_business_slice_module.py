"""Smoke: módulo BUSINESS_SLICE importable sin BD."""


def test_business_slice_service_import():
    from app.services import business_slice_service as m

    assert m.MV_MONTHLY == "ops.real_business_slice_month_fact"
    assert callable(m.get_business_slice_filters)
