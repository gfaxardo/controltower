"""Tests del Period State Engine (Matrix)."""
from datetime import date

from app.services.period_state_engine import (
    build_period_states_payload,
    compute_period_state_record,
    extract_period_keys_from_rows,
)


def test_monthly_past_closed_when_max_covers_month():
    ref = date(2026, 4, 8)
    pk = "2026-01-01"
    am = date(2026, 4, 7)
    r = compute_period_state_record("monthly", pk, am, ref_date=ref)
    assert r["period_status"] == "CLOSED"
    assert r["is_comparable"] is True


def test_monthly_past_stale_when_max_before_month_end():
    ref = date(2026, 4, 8)
    pk = "2026-01-01"
    am = date(2025, 12, 15)
    r = compute_period_state_record("monthly", pk, am, ref_date=ref)
    assert r["period_status"] == "STALE"
    assert r["is_comparable"] is False


def test_extract_period_keys_skips_unmapped_bucket():
    rows = [
        {"month": "2026-01-01", "city": "Lima"},
        {"month": "2026-01-01", "city": "UNMAPPED", "is_unmapped_bucket": True},
    ]
    keys = extract_period_keys_from_rows("monthly", rows)
    assert keys == ["2026-01-01"]


def test_build_period_states_payload_shape():
    rows = [{"month": "2026-01-01", "city": "Lima"}]
    payload = build_period_states_payload("monthly", rows, "2026-04-07")
    assert len(payload) == 1
    assert payload[0]["period_key"] == "2026-01-01"
    assert "period_status" in payload[0]
    assert payload[0].get("actual_max_date_in_period") == payload[0].get("actual_max_date")


def test_per_period_max_avoids_false_stale_when_global_max_is_high():
    """Con max global abril, enero histórico podría cerrar mal; con max en período (ene) se respeta."""
    ref = date(2026, 4, 8)
    pk = "2025-01-01"
    global_am = date(2026, 4, 7)
    period_am = date(2025, 1, 28)
    bad = compute_period_state_record("monthly", pk, global_am, ref_date=ref)
    good = compute_period_state_record("monthly", pk, period_am, ref_date=ref)
    assert bad["period_status"] == "CLOSED"
    assert good["period_status"] == "STALE"
    assert good["is_comparable"] is False


def test_build_period_states_payload_uses_per_period_map():
    rows = [{"month": "2025-01-01", "city": "Lima"}]
    ppm = {"2025-01-01": "2025-01-28"}
    payload = build_period_states_payload(
        "monthly", rows, "2026-04-07", per_period_max_dates=ppm
    )
    assert payload[0]["period_status"] == "STALE"
    assert payload[0]["actual_max_date_in_period"] == "2025-01-28"
