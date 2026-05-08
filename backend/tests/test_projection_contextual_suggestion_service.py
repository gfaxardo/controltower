"""FASE 4.2 — sugerencias contextualizadas auditables (sin ejecución)."""



from __future__ import annotations



from contextlib import contextmanager

from unittest.mock import MagicMock, patch



from app.services.driver_segment_registry import SID_LOW_ACTIVITY_0_5_7D

from app.services.projection_contextual_suggestion_service import (

    build_projection_contextual_suggestions,

    enrich_one_contextual_suggestion,

    merge_integrity_with_contextual_check,

    _fallback_pool_productivity,

    _volume_affected_geos_from_alerts,

    _pick_comparable_slice_labels,

    _RequestFetchCache,

)





def _base_suggestion(action_id: str, entity: str = "Trujillo - Delivery", **extra):

    alert = {

        "level": "critical",

        "dimension": "lob",

        "entity": entity,

        "country": "PE",

        "city": "Trujillo",

        "business_slice": "Delivery",

        "gap_trips": -2000.0,

        "gap_pct": -14.0,

        "principal_driver": "productivity",

        "pacing_vs_expected": "behind",

        "ytd_trend": "deteriorating",

    }

    return {

        "suggestion_id": f"sid-{action_id}",

        "recommended_action_id": action_id,

        "recommended_action_name": "Test action",

        "entity": entity,

        "confidence": "high",

        "priority_score": 80,

        "expected_impact": "medium",

        "source_alert": {**alert, **{k: v for k, v in extra.items() if k not in alert}},

    }





def test_merge_integrity_adds_check():

    i = {"status": "ok", "checks": {"ytd_summary": "ok"}}

    detail = {"segment_registry": "ok", "recovery_auditability": "ok"}

    out = merge_integrity_with_contextual_check(i, "partial", detail)

    assert out["checks"]["contextual_suggestions"] == "partial"

    assert out["checks"]["ytd_summary"] == "ok"

    assert out["checks"]["segment_registry"] == "ok"





def test_broken_integrity_missing():

    lst, chk, det = build_projection_contextual_suggestions(

        integrity_status={"status": "broken"},

        base_suggestions=[_base_suggestion("productivity_reactivation")],

        ytd_alerts=[],

        display_rows=[],

        ytd_summary=None,

        grain="monthly",

    )

    assert lst == [] and chk == "missing"

    assert det["segment_registry"] == "missing"





def test_no_base_suggestions_missing():

    lst, chk, _ = build_projection_contextual_suggestions(

        integrity_status={"status": "ok"},

        base_suggestions=[],

        ytd_alerts=[],

        display_rows=[],

        ytd_summary=None,

        grain="monthly",

    )

    assert lst == [] and chk == "missing"





def test_fallback_pool_single_registry_proxy():

    m = {"ytd_avg_active_drivers_real": 400.0}

    alert = {"gap_trips": -1000.0}

    pool = _fallback_pool_productivity(m, alert)

    ids = {s["segment_id"] for s in pool["segments_detail"]}

    assert ids == {SID_LOW_ACTIVITY_0_5_7D}

    assert pool["total_candidates"] > 0





def test_volume_affected_geos_orders_by_gap():

    alert = {"country": "PE", "principal_driver": "volume"}

    yalerts = [

        {"country": "PE", "principal_driver": "volume", "gap_trips": -100.0, "city": "A"},

        {"country": "PE", "principal_driver": "volume", "gap_trips": -900.0, "city": "B"},

        {"country": "CL", "principal_driver": "volume", "gap_trips": -5000.0, "city": "X"},

    ]

    out = _volume_affected_geos_from_alerts(alert, yalerts)

    assert out[0] == "B"

    assert "A" in out





def test_pick_comparable_slices_same_lob():

    alert = {"country": "PE", "business_slice": "Delivery", "entity": "Trujillo - Delivery"}

    rows = [

        {"country": "PE", "city": "Trujillo", "business_slice_name": "Delivery"},

        {"country": "PE", "city": "Lima", "business_slice_name": "Delivery"},

        {"country": "PE", "city": "Chiclayo", "business_slice_name": "Delivery"},

    ]

    labs = _pick_comparable_slice_labels(alert, rows, limit=5)

    assert "Lima - Delivery" in labs

    assert all(x != "Trujillo - Delivery" for x in labs)





@contextmanager

def _mock_conn():

    conn = MagicMock()

    cur = MagicMock()

    conn.cursor.return_value = cur

    cur.fetchone.return_value = None

    cur.fetchall.return_value = []

    yield conn





def test_enrich_productivity_reactivation_fallback():

    base = _base_suggestion("productivity_reactivation")

    with _mock_conn() as conn:

        with patch(

            "app.services.projection_contextual_suggestion_service._resolve_park_ids",

            return_value=[],

        ):

            out, pfail = enrich_one_contextual_suggestion(

                base=base,

                integrity_status={"status": "ok"},

                ytd_alerts=[],

                display_rows=[],

                ytd_summary={

                    "driver_productivity_ytd_real": 18.0,

                    "driver_productivity_ytd_expected": 25.0,

                    "ytd_avg_active_drivers_real": 400.0,

                },

                conn=conn,

                req_cache=_RequestFetchCache(),

                grain="monthly",

                filters={"year": 2026, "month": 5},

            )

    assert out["action_type"] == "productivity_reactivation"

    assert out["operational_pool"]["pool_method"] == "fallback_active_drivers_or_gap_norm_max_bound"

    assert out["estimated_recovery"]["recovery_method"] == "productivity_gap_projection_v1"

    assert isinstance(out["estimated_recovery"]["assumptions_used"], list)

    assert out["estimated_recovery"]["confidence_reason"]

    segs = out["operational_pool"]["segments"]

    assert len(segs) <= 3

    assert all("segment_id" in s for s in segs)

    assert "operational_leverage_score" in out

    assert out["next_step_preview"]["preview_enabled"] is False

    assert "contextual_reasoning" in out

    assert pfail is False





def test_enrich_opportunity_has_headline():

    base = _base_suggestion(

        "opportunity_replicate_winner",

        entity="Lima - Auto",

        ytd_attainment_pct=112.0,

    )

    base["source_alert"]["level"] = "opportunity"

    base["source_alert"]["pacing_vs_expected"] = "ahead"

    base["source_alert"]["ytd_trend"] = "improving"

    base["source_alert"]["business_slice"] = "Auto"

    dr = [

        {"country": "PE", "city": "Lima", "business_slice_name": "Auto"},

        {"country": "PE", "city": "Trujillo", "business_slice_name": "Auto"},

    ]

    with _mock_conn() as conn:

        with patch(

            "app.services.projection_contextual_suggestion_service._resolve_park_ids",

            return_value=[],

        ):

            out, _ = enrich_one_contextual_suggestion(

                base=base,

                integrity_status={"status": "ok"},

                ytd_alerts=[],

                display_rows=dr,

                ytd_summary=None,

                conn=conn,

                req_cache=_RequestFetchCache(),

                grain="monthly",

                filters={"year": 2026, "month": 5},

            )

    assert out["action_type"] == "opportunity_replicate_winner"

    opp = out["operational_context"]["opportunity"]

    assert "headline" in opp

    assert "Lima" in opp["headline"]

    assert "Trujillo - Auto" in (opp.get("comparable_slice_labels") or [])





def test_warning_integrity_yields_partial_check():

    with patch(

        "app.services.projection_contextual_suggestion_service.get_db",

    ) as mg:

        cm = MagicMock()

        conn = MagicMock()

        cur = MagicMock()

        conn.cursor.return_value = cur

        cur.fetchone.return_value = None

        cur.fetchall.return_value = []

        cm.__enter__.return_value = conn

        cm.__exit__.return_value = None

        mg.return_value = cm

        with patch(

            "app.services.projection_contextual_suggestion_service._resolve_park_ids",

            return_value=[],

        ):

            lst, chk, sub = build_projection_contextual_suggestions(

                integrity_status={"status": "warning"},

                base_suggestions=[_base_suggestion("volume_onboarding_followup")],

                ytd_alerts=[],

                display_rows=[],

                ytd_summary={"ytd_avg_active_drivers_real": 100, "ytd_avg_active_drivers_expected": 130},

                grain="monthly",

                filters={"year": 2026, "month": 5},

            )

    assert len(lst) == 1

    assert chk == "partial"

    assert "recovery_auditability" in sub


