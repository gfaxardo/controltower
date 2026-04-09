from datetime import date


def _finding(code, *, category="consistency", severity="error", evidence=None, message=None):
    return {
        "code": code,
        "category": category,
        "severity": severity,
        "evidence": evidence,
        "message": message or code,
    }


def test_compute_confidence_signals_applies_hard_cap_for_rollup_mismatch():
    from app.services.omniview_matrix_integrity_service import compute_confidence_signals

    findings = [_finding("ROLLUP_MISMATCH")]
    snap = {
        "day_fact_max": date(2026, 4, 7),
        "source_trip_max_bounded": date(2026, 4, 7),
    }
    impact_summary = {"pct_trips_affected": 0, "pct_revenue_affected": 0}

    out = compute_confidence_signals(findings, snap, impact_summary)

    assert out["consistency"] == 30.0
    assert out["score_before_caps"] > out["confidence_score"]
    assert out["confidence_score"] == 35
    assert out["hard_cap"]["code"] == "ROLLUP_MISMATCH"


def test_compute_confidence_signals_prioritizes_consistency_over_freshness():
    from app.services.omniview_matrix_integrity_service import compute_confidence_signals

    findings = [
        _finding("MONTH_REVENUE_MISMATCH"),
        _finding("DERIVED_BEHIND_SOURCE", category="freshness", severity="warn", evidence={"lag_days": 2}),
    ]
    snap = {
        "day_fact_max": date(2026, 4, 5),
        "source_trip_max_bounded": date(2026, 4, 7),
    }
    impact_summary = {"pct_trips_affected": 1, "pct_revenue_affected": 2}

    out = compute_confidence_signals(findings, snap, impact_summary)

    assert out["consistency"] < out["freshness"]
    assert out["hard_cap"]["code"] == "MONTH_REVENUE_MISMATCH"
    assert out["confidence_score"] == 40


def test_build_operational_decision_blocks_on_hard_blockers_even_with_good_pillars():
    from app.services.omniview_matrix_integrity_service import build_operational_decision

    findings = [_finding("REVENUE_WITHOUT_COMPLETED", category="revenue", severity="error")]
    snap = {
        "day_fact_max": date(2026, 4, 7),
        "source_trip_max_bounded": date(2026, 4, 7),
    }
    impact_summary = {"pct_trips_affected": 0, "pct_revenue_affected": 0}

    out = build_operational_decision(findings, snap, impact_summary, "warning")

    assert out["decision_mode"] == "BLOCKED"
    assert out["confidence"]["score"] == 45
    assert out["hard_blockers"][0]["code"] == "REVENUE_WITHOUT_COMPLETED"


def test_should_persist_omniview_trust_history_only_on_significant_change():
    from app.services.omniview_matrix_integrity_service import should_persist_omniview_trust_history

    previous = {
        "decision_mode": "CAUTION",
        "confidence_score": 72,
        "primary_issue_code": "DAY_FACT_DATE_GAPS",
    }
    decision_same = {"decision_mode": "CAUTION", "confidence": {"score": 74}}
    decision_delta = {"decision_mode": "CAUTION", "confidence": {"score": 78}}

    keep_same, reason_same = should_persist_omniview_trust_history(
        previous, decision_same, "DAY_FACT_DATE_GAPS"
    )
    keep_delta, reason_delta = should_persist_omniview_trust_history(
        previous, decision_delta, "DAY_FACT_DATE_GAPS"
    )
    keep_mode, reason_mode = should_persist_omniview_trust_history(
        previous, {"decision_mode": "BLOCKED", "confidence": {"score": 40}}, "DAY_FACT_DATE_GAPS"
    )

    assert keep_same is False
    assert reason_same == "no_significant_change"
    assert keep_delta is True
    assert reason_delta == "confidence_score_delta"
    assert keep_mode is True
    assert reason_mode == "decision_mode_changed"


def test_build_early_warnings_detects_freshness_and_gaps_deterioration():
    from app.services.omniview_matrix_integrity_service import build_early_warnings

    current_decision = {"confidence": {"freshness": 55, "coverage": 45}}
    current_issue_snapshots = [
        {
            "code": "DAY_FACT_DATE_GAPS",
            "evidence": {"gap_count": 8},
        }
    ]
    recent_history_rows = [
        {
            "payload": {
                "confidence": {"freshness": 80, "coverage": 65},
                "issue_snapshots": [
                    {"code": "DAY_FACT_DATE_GAPS", "evidence": {"gap_count": 3}}
                ],
            }
        }
    ]

    warnings = build_early_warnings(current_decision, current_issue_snapshots, recent_history_rows)
    types = {w["type"] for w in warnings}

    assert "freshness_deterioration" in types
    assert "coverage_drop" in types
    assert "gaps_increase" in types


def test_build_issue_history_and_clusters_summarize_current_issues():
    from app.services.omniview_matrix_integrity_service import build_issue_history_summary, build_issue_clusters

    current_issue_snapshots = [
        {
            "issue_key": "ROLLUP_MISMATCH|Madrid|Airport|2026-04-01|revenue_yego_net",
            "code": "ROLLUP_MISMATCH",
            "trust_status": "blocked",
            "severity_weight": 96,
            "impact_pct": 24.0,
            "cluster_key": "reconciliation",
            "cluster_label": "Reconciliación canon",
            "cluster_description": "Descuadres entre rollups/facts y el universo canon resolved.",
        }
    ]
    recent_history_rows = [
        {
            "period_key": "2026-03-01",
            "evaluated_at": "2026-04-01T09:00:00+00:00",
            "decision_mode": "CAUTION",
            "confidence_score": 61,
            "payload": {
                "issue_snapshots": [
                    {
                        "issue_key": "ROLLUP_MISMATCH|Madrid|Airport|2026-04-01|revenue_yego_net",
                        "code": "ROLLUP_MISMATCH",
                        "trust_status": "warning",
                        "impact_pct": 15.0,
                    }
                ]
            },
        },
        {
            "period_key": "2026-04-01",
            "evaluated_at": "2026-04-03T09:00:00+00:00",
            "decision_mode": "BLOCKED",
            "confidence_score": 35,
            "payload": {
                "issue_snapshots": [
                    {
                        "issue_key": "ROLLUP_MISMATCH|Madrid|Airport|2026-04-01|revenue_yego_net",
                        "code": "ROLLUP_MISMATCH",
                        "trust_status": "blocked",
                        "impact_pct": 24.0,
                    }
                ]
            },
        },
    ]

    issue_history = build_issue_history_summary(current_issue_snapshots, recent_history_rows)
    issue_clusters = build_issue_clusters(current_issue_snapshots)

    assert issue_history[current_issue_snapshots[0]["issue_key"]]["trend"] in {"stable", "worsening", "recurring"}
    assert issue_history[current_issue_snapshots[0]["issue_key"]]["occurrences"] == 3
    assert issue_clusters[0]["cluster_key"] == "reconciliation"
    assert issue_clusters[0]["combined_impact_pct"] == 24.0
