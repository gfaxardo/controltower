"""Registry de segmentos (FASE 4.2B)."""

from app.services.driver_segment_registry import (
    SID_LOW_ACTIVITY_0_5_7D,
    all_registered_segment_ids,
    segment_public_meta,
)


def test_all_segments_have_payload():
    ids = all_registered_segment_ids()
    assert SID_LOW_ACTIVITY_0_5_7D in ids
    for sid in ids:
        m = segment_public_meta(sid)
        assert m["segment_id"] == sid
        assert m["logic_version"]


def test_unknown_segment_meta():
    m = segment_public_meta("not_a_real_segment")
    assert m["logic_version"] == "unknown"
