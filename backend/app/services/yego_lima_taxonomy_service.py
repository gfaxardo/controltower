"""
YEGO Lima Growth - Driver Taxonomy Service (LG-TAX-1.0B)
Shadow mode: builds taxonomy daily, does NOT replace production programs/queue.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor, execute_values

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_STATE = "growth.yango_lima_driver_state_snapshot"
TABLE_TAXONOMY = "growth.yego_lima_driver_taxonomy_daily"
TABLE_TAXONOMY_READ = "growth.yego_lima_v2_taxonomy_daily"
TABLE_EXPLANATION = "growth.yego_lima_driver_taxonomy_explanation"
TABLE_TRANSITION = "growth.yego_lima_driver_taxonomy_transition"
TABLE_CONFIG = "growth.yego_lima_taxonomy_config"

TAXONOMY_VERSION = "v2"


def _now_utc():
    return datetime.now(timezone.utc)


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _days_since(val):
    if val is None:
        return None
    today = date.today()
    if isinstance(val, datetime):
        return (today - val.date()).days
    if isinstance(val, date):
        return (today - val).days
    return None


def _load_config(cur, layer: str) -> Dict[str, Any]:
    """Load active config for a layer, returning defaults if none found."""
    cur.execute(
        f"SELECT config_key, config_value_json FROM {TABLE_CONFIG} "
        "WHERE is_active = true AND taxonomy_version = %(v)s AND layer = %(l)s",
        {"v": TAXONOMY_VERSION, "l": layer},
    )
    cfg = {}
    for row in cur.fetchall():
        cfg[row["config_key"]] = row["config_value_json"]
    return cfg


# ── DEFAULT CONFIG (used when no DB config exists) ──

DEFAULTS = {
    "status": {
        "churn_days": 15,
        "archived_days": 90,
    },
    "segment": {
        "new_window_days": 90,
        "reactivation_gap_days": 90,
        "minimum_activation_trips": 50,
        "under_activated_window_days": 90,
        "growth_max_weekly_trips": 50,
    },
    "value": {
        "top_percentile": 90,
        "high_percentile": 70,
        "mid_percentile": 30,
        "top_min_weekly_trips": 50,
        "high_min_weekly_trips": 30,
    },
    "momentum": {
        "growth_pct": 20,
        "accelerating_pct": 40,
        "softening_pct": -10,
        "decline_pct": -25,
        "collapse_pct": -50,
        "min_volume": 3,
    },
}


def _get_config(cur, layer: str, key: str, default=None):
    """Get a config value, falling back to DB config, then DEFAULTS, then the provided default."""
    db_cfg = _load_config(cur, layer)
    if key in db_cfg:
        return db_cfg[key]
    return DEFAULTS.get(layer, {}).get(key, default)


def _compute_percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0
    idx = int(len(sorted_values) * pct / 100.0)
    return sorted_values[min(idx, len(sorted_values) - 1)]


# ================================================================
# BUILD TAXONOMY
# ================================================================


def build_driver_taxonomy(snapshot_date_str: str, taxonomy_version: str = TAXONOMY_VERSION) -> Dict[str, Any]:
    t0 = time.perf_counter()
    snapshot_date = date.fromisoformat(snapshot_date_str)

    logger.info("Building driver taxonomy: date=%s version=%s", snapshot_date, taxonomy_version)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ── 1. Load config ──
        status_cfg = {
            "churn_days": _get_config(cur, "status", "churn_days", 15),
            "archived_days": _get_config(cur, "status", "archived_days", 90),
        }
        segment_cfg = {
            "new_window_days": _get_config(cur, "segment", "new_window_days", 90),
            "reactivation_gap_days": _get_config(cur, "segment", "reactivation_gap_days", 90),
            "minimum_activation_trips": _get_config(cur, "segment", "minimum_activation_trips", 50),
            "under_activated_window_days": _get_config(cur, "segment", "under_activated_window_days", 90),
            "growth_max_weekly_trips": _get_config(cur, "segment", "growth_max_weekly_trips", 50),
        }
        value_cfg = {
            "top_percentile": _get_config(cur, "value", "top_percentile", 90),
            "high_percentile": _get_config(cur, "value", "high_percentile", 70),
            "mid_percentile": _get_config(cur, "value", "mid_percentile", 30),
            "top_min_weekly_trips": _get_config(cur, "value", "top_min_weekly_trips", 50),
            "high_min_weekly_trips": _get_config(cur, "value", "high_min_weekly_trips", 30),
        }
        momentum_cfg = {
            "growth_pct": _get_config(cur, "momentum", "growth_pct", 20),
            "accelerating_pct": _get_config(cur, "momentum", "accelerating_pct", 40),
            "softening_pct": _get_config(cur, "momentum", "softening_pct", -10),
            "decline_pct": _get_config(cur, "momentum", "decline_pct", -25),
            "collapse_pct": _get_config(cur, "momentum", "collapse_pct", -50),
            "min_volume": _get_config(cur, "momentum", "min_volume", 3),
        }

        # ── 2. Fetch driver state snapshot ──
        cur.execute(
            f"SELECT * FROM {TABLE_STATE} WHERE snapshot_date = %(d)s",
            {"d": snapshot_date},
        )
        drivers = cur.fetchall()
        if not drivers:
            return {"ok": False, "error": f"No driver_state_snapshot for {snapshot_date_str}"}

        total = len(drivers)

        # ── 3. Compute value percentiles ──
        a4_values = sorted([_safe_float(d.get("avg_orders_4w")) for d in drivers])
        p30 = _compute_percentile(a4_values, value_cfg["mid_percentile"])
        p70 = _compute_percentile(a4_values, value_cfg["high_percentile"])
        p90 = _compute_percentile(a4_values, value_cfg["top_percentile"])

        # ── 4. Get previous taxonomy for transition detection ──
        cur.execute(
            f"SELECT DISTINCT snapshot_date FROM {TABLE_TAXONOMY} ORDER BY snapshot_date DESC LIMIT 1"
        )
        prev_row = cur.fetchone()
        prev_date = str(prev_row["snapshot_date"]) if prev_row else None

        prev_taxonomy = {}
        if prev_date:
            cur.execute(
                f"SELECT driver_profile_id, operational_status, operational_segment, "
                f"operational_persona FROM {TABLE_TAXONOMY} WHERE snapshot_date = %(d)s",
                {"d": prev_date},
            )
            for row in cur.fetchall():
                prev_taxonomy[row["driver_profile_id"]] = dict(row)

        # ── 5. Clear existing data for this date (idempotent) ──
        cur.execute(
            f"DELETE FROM {TABLE_TAXONOMY} WHERE snapshot_date = %(d)s",
            {"d": snapshot_date},
        )
        cur.execute(
            f"DELETE FROM {TABLE_EXPLANATION} WHERE snapshot_date = %(d)s",
            {"d": snapshot_date},
        )
        cur.execute(
            f"DELETE FROM {TABLE_TRANSITION} WHERE curr_date = %(d)s",
            {"d": snapshot_date},
        )

        # ── 6. Classify each driver ──
        taxonomy_rows = []
        explanation_rows = []
        transition_rows = []

        status_counts = {}
        segment_counts = {}
        value_counts = {}
        momentum_counts = {}
        persona_counts = {}

        for d in drivers:
            did = d["driver_profile_id"]
            cw = _safe_int(d.get("completed_orders_week"))
            a4 = _safe_float(d.get("avg_orders_4w"))
            a12 = _safe_float(d.get("avg_orders_12w"))
            b12 = _safe_float(d.get("best_week_12w"))
            lt_days = _days_since(d.get("last_trip_at"))
            fs_days = _days_since(d.get("first_seen_at"))
            ft_days = _days_since(d.get("first_trip_at"))
            rt = d.get("retention_state", "")
            dec = d.get("declining_flag", False)
            churn = d.get("churn_risk_flag", False)
            react = d.get("reactivated_flag", False)
            recov = d.get("recoverable_flag", False)
            rtgt = d.get("reached_target_flag", False)
            hband = d.get("historical_band", "")
            new_d = d.get("new_driver_flag", False)

            signal_flags = {}

            # ── LAYER 1: OPERATIONAL STATUS ──
            status = None
            status_reason = ""
            status_matched = []
            status_failed = []

            if cw > 0:
                status = "ACTIVE"
                status_reason = "weekly_orders > 0"
                status_matched.append(
                    {"rule": "active_if_weekly_orders", "condition": "completed_orders_week > 0", "actual": cw}
                )
            elif lt_days is not None:
                if lt_days >= status_cfg["archived_days"]:
                    status = "ARCHIVED"
                    status_reason = f"no_orders_and_last_trip={lt_days}d >= {status_cfg['archived_days']}d"
                    status_matched.append(
                        {"rule": "archived_if_no_activity", "condition": f"days >= {status_cfg['archived_days']}", "actual": lt_days}
                    )
                elif lt_days >= status_cfg["churn_days"]:
                    status = "CHURN"
                    status_reason = f"no_orders_and_last_trip={lt_days}d >= {status_cfg['churn_days']}d"
                    status_matched.append(
                        {"rule": "churn_if_no_activity", "condition": f"days >= {status_cfg['churn_days']}", "actual": lt_days}
                    )
                else:
                    status = "ACTIVE"
                    status_reason = f"last_trip={lt_days}d < churn_days"
                    status_matched.append(
                        {"rule": "active_if_recent_trip", "condition": f"days < {status_cfg['churn_days']}", "actual": lt_days}
                    )
            else:
                status = "ACTIVE"
                status_reason = "fallback_no_trip_signal"
                signal_flags["status_signal"] = "DEGRADED"
                status_matched.append({"rule": "fallback_active", "condition": "no_trip_signal", "actual": None})

            status_counts[status] = status_counts.get(status, 0) + 1

            # ── LAYER 2: OPERATIONAL SEGMENT ──
            segment = None
            segment_reason = ""
            segment_matched = []
            segment_failed = []

            # Determine anchor date and type
            anchor_type = None
            anchor_date = None
            days_since_anchor = None
            trips_since_anchor = None  # Simplified: use cw as proxy

            if new_d or (fs_days is not None and fs_days <= segment_cfg["new_window_days"]):
                anchor_type = "HIRE_DATE"
                anchor_date = d.get("first_seen_at")
                days_since_anchor = fs_days if fs_days is not None else 0
            elif react and fs_days and fs_days > segment_cfg["reactivation_gap_days"]:
                anchor_type = "REACTIVATION_DATE"
                anchor_date = d.get("first_trip_at") or d.get("last_trip_at")
                days_since_anchor = min(
                    (_days_since(d.get("last_trip_at")) or 999),
                    (_days_since(d.get("first_trip_at")) or 999),
                )
            else:
                anchor_type = None
                anchor_date = d.get("first_seen_at")
                days_since_anchor = fs_days

            trips_since_anchor = cw
            weekly_trips = cw

            is_new = new_d or (fs_days is not None and fs_days <= segment_cfg["new_window_days"])
            is_reactivated = react and fs_days and fs_days > segment_cfg["reactivation_gap_days"]
            is_under_activated = ((is_new or is_reactivated) and
                                  days_since_anchor is not None and
                                  days_since_anchor <= segment_cfg["under_activated_window_days"] and
                                  trips_since_anchor < segment_cfg["minimum_activation_trips"])

            # TOP_PERFORMER check
            is_top_performer = (
                a4 >= value_cfg["top_min_weekly_trips"]
            )

            # Segment classification (exclusive)
            if status != "ACTIVE":
                segment = "INACTIVE"
                segment_reason = f"operational_status={status}"
                segment_matched.append({"rule": "inactive_if_not_active", "condition": "status != ACTIVE", "actual": status})
            elif is_new and not is_under_activated:
                segment = "NEW"
                segment_reason = f"new_driver_days_since_anchor={days_since_anchor}"
                segment_matched.append({"rule": "new_if_recent", "condition": f"days <= {segment_cfg['new_window_days']}", "actual": days_since_anchor})
            elif is_reactivated and not is_under_activated:
                segment = "REACTIVATED"
                segment_reason = f"reactivated_after_gap"
                segment_matched.append({"rule": "reactivated_if_gap", "condition": f"reactivated_gap > {segment_cfg['reactivation_gap_days']}", "actual": True})
            elif is_under_activated:
                segment = "UNDER_ACTIVATED"
                segment_reason = f"under_activated_trips={trips_since_anchor}_days={days_since_anchor}"
                segment_matched.append(
                    {"rule": "under_activated", "condition": "days <= window AND trips < minimum", "actual": f"days={days_since_anchor}_trips={trips_since_anchor}"}
                )
            elif is_top_performer:
                segment = "TOP_PERFORMER"
                segment_reason = f"avg_4w={a4:.1f}_above_threshold={value_cfg['top_min_weekly_trips']}"
                segment_matched.append({"rule": "top_performer", "condition": f"avg_4w >= {value_cfg['top_min_weekly_trips']}", "actual": a4})
            elif cw <= segment_cfg["growth_max_weekly_trips"] and cw > 0:
                segment = "ACTIVE_GROWTH"
                segment_reason = f"weekly_trips={cw}_below_growth_max={segment_cfg['growth_max_weekly_trips']}"
                segment_matched.append({"rule": "active_growth", "condition": f"weekly <= {segment_cfg['growth_max_weekly_trips']}", "actual": cw})
            else:
                segment = "STABLE"
                segment_reason = f"weekly_trips={cw}_above_growth_threshold"
                segment_matched.append({"rule": "stable_default", "condition": "no_other_segment_matched", "actual": cw})

            segment_counts[segment] = segment_counts.get(segment, 0) + 1

            # ── LAYER 3: VALUE OVERLAY ──
            value_overlay = None
            value_reason = ""
            value_matched = []
            value_failed = []

            if a4 >= value_cfg["top_min_weekly_trips"]:
                value_overlay = "TOP_VALUE"
                value_reason = f"avg_4w={a4:.1f}_>=_absolute_top={value_cfg['top_min_weekly_trips']}"
                value_matched.append({"rule": "top_absolute", "condition": f">= {value_cfg['top_min_weekly_trips']}", "actual": a4})
            elif a4 >= p70 and a4 >= value_cfg["high_min_weekly_trips"]:
                value_overlay = "HIGH_VALUE"
                value_reason = f"avg_4w={a4:.1f}_>=_p70={p70:.1f}_AND_>=_absolute={value_cfg['high_min_weekly_trips']}"
                value_matched.append({"rule": "high_hybrid", "condition": f">= p{p70} AND >= {value_cfg['high_min_weekly_trips']}", "actual": a4})
            elif a4 >= p30:
                value_overlay = "MID_VALUE"
                value_reason = f"avg_4w={a4:.1f}_>=_p30={p30:.1f}"
                value_matched.append({"rule": "mid_percentile", "condition": f">= p{value_cfg['mid_percentile']}", "actual": a4})
            elif a4 > 0:
                value_overlay = "LOW_VALUE"
                value_reason = f"avg_4w={a4:.1f}_below_p30={p30:.1f}"
                value_matched.append({"rule": "low_below_percentile", "condition": f"< p{value_cfg['mid_percentile']}", "actual": a4})
                value_failed.append({"rule": "mid_percentile", "condition": f">= p{value_cfg['mid_percentile']}", "actual": a4})
            else:
                value_overlay = "LOW_VALUE"
                value_reason = "no_orders_data"
                value_matched.append({"rule": "low_default", "condition": "no_data", "actual": 0})
                signal_flags["value_signal"] = "DEGRADED"

            value_counts[value_overlay] = value_counts.get(value_overlay, 0) + 1

            # Compute percentile for reference
            if a4_values:
                value_percentile = sum(1 for v in a4_values if v <= a4) / len(a4_values) * 100
            else:
                value_percentile = 0

            # ── LAYER 4: MOMENTUM ──
            momentum = None
            momentum_reason = ""
            momentum_matched = []
            momentum_failed = []

            vol = max(a4, cw)
            if dec and b12 >= 20:
                momentum = "COLLAPSING" if a4 == 0 else "DECLINING"
                momentum_reason = f"declining_flag_best12w={b12:.0f}_avg4w={a4:.1f}"
                momentum_matched.append({"rule": "collapsing_or_declining_flag", "condition": "declining_flag AND best_12w >= 20", "actual": f"best12w={b12:.0f}_a4={a4:.1f}"})
            elif dec and b12 >= 5:
                momentum = "SOFTENING"
                momentum_reason = f"declining_flag_best12w={b12:.0f}_avg4w={a4:.1f}"
                momentum_matched.append({"rule": "softening_declining_flag", "condition": "declining_flag AND best_12w >= 5", "actual": b12})
            elif vol < momentum_cfg["min_volume"]:
                momentum = "FLAT"
                momentum_reason = f"volume={vol:.1f}_<min={momentum_cfg['min_volume']}"
                momentum_matched.append({"rule": "flat_low_volume", "condition": f"< {momentum_cfg['min_volume']}", "actual": vol})
            elif a12 > 0 and a4 > 0:
                delta = ((a4 - a12) / a12) * 100
                if delta >= momentum_cfg["accelerating_pct"]:
                    momentum = "ACCELERATING"
                    momentum_reason = f"delta=+{delta:.0f}%_4w={a4:.1f}_12w={a12:.1f}"
                    momentum_matched.append({"rule": "accelerating", "condition": f">= +{momentum_cfg['accelerating_pct']}%", "actual": delta})
                elif delta >= momentum_cfg["growth_pct"]:
                    momentum = "GROWING"
                    momentum_reason = f"delta=+{delta:.0f}%_4w={a4:.1f}_12w={a12:.1f}"
                    momentum_matched.append({"rule": "growing", "condition": f">= +{momentum_cfg['growth_pct']}%", "actual": delta})
                elif delta >= momentum_cfg["softening_pct"]:
                    momentum = "STABLE"
                    momentum_reason = f"delta={delta:.0f}%_4w={a4:.1f}_12w={a12:.1f}"
                    momentum_matched.append({"rule": "stable", "condition": "within_bounds", "actual": delta})
                elif delta >= momentum_cfg["decline_pct"]:
                    momentum = "SOFTENING"
                    momentum_reason = f"delta={delta:.0f}%_4w={a4:.1f}_12w={a12:.1f}"
                    momentum_matched.append({"rule": "softening", "condition": f">= {momentum_cfg['softening_pct']}%", "actual": delta})
                elif delta >= momentum_cfg["collapse_pct"]:
                    momentum = "DECLINING"
                    momentum_reason = f"delta={delta:.0f}%_4w={a4:.1f}_12w={a12:.1f}"
                    momentum_matched.append({"rule": "declining", "condition": f">= {momentum_cfg['decline_pct']}%", "actual": delta})
                else:
                    momentum = "COLLAPSING"
                    momentum_reason = f"delta={delta:.0f}%_4w={a4:.1f}_12w={a12:.1f}"
                    momentum_matched.append({"rule": "collapsing", "condition": f"< {momentum_cfg['collapse_pct']}%", "actual": delta})
            else:
                momentum = "STABLE"
                momentum_reason = "no_directional_signal"
                momentum_matched.append({"rule": "stable_default", "condition": "no_signal", "actual": None})

            momentum_counts[momentum] = momentum_counts.get(momentum, 0) + 1

            # ── PERSONA ──
            persona = f"{status}_{segment}_{value_overlay}_{momentum}"
            persona_counts[persona] = persona_counts.get(persona, 0) + 1

            # ── Build taxonomy row ──
            taxonomy_rows.append({
                "snapshot_date": snapshot_date,
                "driver_profile_id": did,
                "operational_status": status,
                "operational_segment": segment,
                "value_overlay": value_overlay,
                "momentum_state": momentum,
                "operational_persona": persona,
                "anchor_type": anchor_type,
                "current_anchor_date": anchor_date.date() if hasattr(anchor_date, "date") else (
                    anchor_date if isinstance(anchor_date, date) else None
                ),
                "days_since_anchor": days_since_anchor,
                "days_since_last_trip": lt_days,
                "trips_since_anchor": trips_since_anchor,
                "weekly_trips": weekly_trips,
                "avg_orders_4w": a4,
                "avg_orders_12w": a12,
                "value_percentile": value_percentile,
                "taxonomy_version": taxonomy_version,
                "signal_quality_flags_json": json.dumps(signal_flags) if signal_flags else None,
            })

            # ── Build explanations ──
            for layer_name, state_val, matched, failed, evidence, expl_text in [
                ("operational_status", status, status_matched, status_failed,
                 {"completed_orders_week": cw, "last_trip_at": str(d.get("last_trip_at"))},
                 f"Status={status}: {status_reason}"),
                ("operational_segment", segment, segment_matched, segment_failed,
                 {"completed_orders_week": cw, "days_since_anchor": days_since_anchor, "anchor_type": anchor_type},
                 f"Segment={segment}: {segment_reason}"),
                ("value_overlay", value_overlay, value_matched, value_failed,
                 {"avg_orders_4w": a4, "avg_orders_12w": a12, "percentile": round(value_percentile, 1)},
                 f"Value={value_overlay}: {value_reason}"),
                ("momentum", momentum, momentum_matched, momentum_failed,
                 {"avg_orders_4w": a4, "avg_orders_12w": a12, "declining_flag": dec},
                 f"Momentum={momentum}: {momentum_reason}"),
            ]:
                explanation_rows.append({
                    "snapshot_date": snapshot_date,
                    "driver_profile_id": did,
                    "layer": layer_name,
                    "state_value": state_val,
                    "matched_rules_json": json.dumps(matched),
                    "failed_rules_json": json.dumps(failed) if failed else None,
                    "evidence_json": json.dumps(evidence),
                    "explanation_text": expl_text,
                    "taxonomy_version": taxonomy_version,
                })

            # ── Build transition ──
            prev = prev_taxonomy.get(did)
            if prev:
                changed = []
                if prev.get("operational_status") != status:
                    changed.append("operational_status")
                if prev.get("operational_segment") != segment:
                    changed.append("operational_segment")
                prev_persona = prev.get("operational_persona", "")
                if prev_persona != persona:
                    changed.append("operational_persona")
                    for ax in ["operational_status", "operational_segment", "value_overlay", "momentum"]:
                        if ax not in changed:
                            changed.append(ax)

                if changed:
                    transition_rows.append({
                        "driver_profile_id": did,
                        "prev_date": prev_date,
                        "curr_date": snapshot_date,
                        "previous_status": prev.get("operational_status"),
                        "current_status": status,
                        "previous_segment": prev.get("operational_segment"),
                        "current_segment": segment,
                        "previous_persona": prev_persona,
                        "current_persona": persona,
                        "changed_layers_json": json.dumps(changed),
                        "transition_reason": f"Changed axes: {', '.join(changed)}. {segment_reason}",
                        "taxonomy_version": taxonomy_version,
                    })

        # ── 7. Persist ──
        _upsert_taxonomy(cur, taxonomy_rows)
        _upsert_explanations(cur, explanation_rows)
        _upsert_transitions(cur, transition_rows)

        conn.commit()

    duration_ms = round((time.perf_counter() - t0) * 1000)

    # ── 8. Build summary ──
    status_summary = [
        {"status": k, "drivers": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(status_counts.items(), key=lambda x: -x[1])
    ]
    segment_summary = [
        {"segment": k, "drivers": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(segment_counts.items(), key=lambda x: -x[1])
    ]
    value_summary = [
        {"value": k, "drivers": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(value_counts.items(), key=lambda x: -x[1])
    ]
    momentum_summary = [
        {"momentum": k, "drivers": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(momentum_counts.items(), key=lambda x: -x[1])
    ]
    top_personas = [
        {"persona": k, "drivers": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(persona_counts.items(), key=lambda x: -x[1])[:20]
    ]

    return {
        "ok": True,
        "snapshot_date": snapshot_date_str,
        "taxonomy_version": taxonomy_version,
        "rows_built": len(taxonomy_rows),
        "explanations_built": len(explanation_rows),
        "transitions_built": len(transition_rows),
        "duration_ms": duration_ms,
        "expected_rows": total,
        "match": len(taxonomy_rows) == total,
        "distributions": {
            "operational_status": status_summary,
            "operational_segment": segment_summary,
            "value_overlay": value_summary,
            "momentum": momentum_summary,
        },
        "top_personas": top_personas,
        "total_personas": len(persona_counts),
        "config": {
            "status": status_cfg,
            "segment": segment_cfg,
            "value": value_cfg,
            "momentum": momentum_cfg,
            "value_percentiles": {"p30": p30, "p70": p70, "p90": p90},
        },
    }


# ================================================================
# UPSERT HELPERS
# ================================================================


def _upsert_taxonomy(cur, rows: list) -> None:
    if not rows:
        return

    sql = """
        INSERT INTO growth.yego_lima_driver_taxonomy_daily (
            snapshot_date, driver_profile_id,
            operational_status, operational_segment,
            value_overlay, momentum_state, operational_persona,
            anchor_type, current_anchor_date, days_since_anchor,
            days_since_last_trip, trips_since_anchor, weekly_trips,
            avg_orders_4w, avg_orders_12w, value_percentile,
            taxonomy_version, signal_quality_flags_json
        ) VALUES %s
        ON CONFLICT (snapshot_date, driver_profile_id) DO UPDATE SET
            operational_status = EXCLUDED.operational_status,
            operational_segment = EXCLUDED.operational_segment,
            value_overlay = EXCLUDED.value_overlay,
            momentum_state = EXCLUDED.momentum_state,
            operational_persona = EXCLUDED.operational_persona,
            anchor_type = EXCLUDED.anchor_type,
            current_anchor_date = EXCLUDED.current_anchor_date,
            days_since_anchor = EXCLUDED.days_since_anchor,
            days_since_last_trip = EXCLUDED.days_since_last_trip,
            trips_since_anchor = EXCLUDED.trips_since_anchor,
            weekly_trips = EXCLUDED.weekly_trips,
            avg_orders_4w = EXCLUDED.avg_orders_4w,
            avg_orders_12w = EXCLUDED.avg_orders_12w,
            value_percentile = EXCLUDED.value_percentile,
            taxonomy_version = EXCLUDED.taxonomy_version,
            signal_quality_flags_json = EXCLUDED.signal_quality_flags_json
    """

    template = """(
        %(snapshot_date)s, %(driver_profile_id)s,
        %(operational_status)s, %(operational_segment)s,
        %(value_overlay)s, %(momentum_state)s, %(operational_persona)s,
        %(anchor_type)s, %(current_anchor_date)s, %(days_since_anchor)s,
        %(days_since_last_trip)s, %(trips_since_anchor)s, %(weekly_trips)s,
        %(avg_orders_4w)s, %(avg_orders_12w)s, %(value_percentile)s,
        %(taxonomy_version)s, %(signal_quality_flags_json)s::jsonb
    )"""

    execute_values(cur, sql, rows, template=template, page_size=500)


def _upsert_explanations(cur, rows: list) -> None:
    if not rows:
        return

    sql = """
        INSERT INTO growth.yego_lima_driver_taxonomy_explanation (
            snapshot_date, driver_profile_id, layer, state_value,
            matched_rules_json, failed_rules_json, evidence_json,
            explanation_text, taxonomy_version
        ) VALUES %s
        ON CONFLICT (snapshot_date, driver_profile_id, layer) DO UPDATE SET
            state_value = EXCLUDED.state_value,
            matched_rules_json = EXCLUDED.matched_rules_json,
            failed_rules_json = EXCLUDED.failed_rules_json,
            evidence_json = EXCLUDED.evidence_json,
            explanation_text = EXCLUDED.explanation_text,
            taxonomy_version = EXCLUDED.taxonomy_version
    """

    template = """(
        %(snapshot_date)s, %(driver_profile_id)s, %(layer)s, %(state_value)s,
        %(matched_rules_json)s::jsonb, %(failed_rules_json)s::jsonb, %(evidence_json)s::jsonb,
        %(explanation_text)s, %(taxonomy_version)s
    )"""

    execute_values(cur, sql, rows, template=template, page_size=500)


def _upsert_transitions(cur, rows: list) -> None:
    if not rows:
        return

    sql = """
        INSERT INTO growth.yego_lima_driver_taxonomy_transition (
            driver_profile_id, prev_date, curr_date,
            previous_status, current_status,
            previous_segment, current_segment,
            previous_persona, current_persona,
            changed_layers_json, transition_reason, taxonomy_version
        ) VALUES %s
        ON CONFLICT DO NOTHING
    """

    template = """(
        %(driver_profile_id)s, %(prev_date)s, %(curr_date)s,
        %(previous_status)s, %(current_status)s,
        %(previous_segment)s, %(current_segment)s,
        %(previous_persona)s, %(current_persona)s,
        %(changed_layers_json)s::jsonb, %(transition_reason)s, %(taxonomy_version)s
    )"""

    execute_values(cur, sql, rows, template=template, page_size=500)


# ================================================================
# QUERY ENDPOINTS
# ================================================================


def _latest_taxonomy_date(cur) -> Optional[str]:
    cur.execute(f"SELECT MAX(target_date) FROM {TABLE_TAXONOMY_READ}")
    r = cur.fetchone()
    return str(r["max"]) if r and r["max"] else None


def get_taxonomy_summary(snapshot_date_str: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if snapshot_date_str:
            sd = snapshot_date_str
        else:
            sd = _latest_taxonomy_date(cur)
            if not sd:
                return {"error": "No taxonomy data. Run POST /taxonomy/build first."}

        cur.execute(
            f"SELECT segment AS operational_status, COUNT(*) as cnt FROM {TABLE_TAXONOMY_READ} "
            "WHERE target_date = %(d)s GROUP BY 1 ORDER BY cnt DESC",
            {"d": sd},
        )
        status = [dict(r) for r in cur.fetchall()]

        cur.execute(
            f"SELECT segment AS operational_segment, COUNT(*) as cnt FROM {TABLE_TAXONOMY_READ} "
            "WHERE target_date = %(d)s GROUP BY 1 ORDER BY cnt DESC",
            {"d": sd},
        )
        segment = [dict(r) for r in cur.fetchall()]

        cur.execute(
            f"SELECT COALESCE(elite_tier, loyalty_tier) AS value_overlay, COUNT(*) as cnt FROM {TABLE_TAXONOMY_READ} "
            "WHERE target_date = %(d)s GROUP BY 1 ORDER BY cnt DESC",
            {"d": sd},
        )
        value = [dict(r) for r in cur.fetchall()]

        momentum = []

        cur.execute(
            f"SELECT segment || '|' || COALESCE(sub_segment,'') AS operational_persona, COUNT(*) as cnt FROM {TABLE_TAXONOMY_READ} "
            "WHERE target_date = %(d)s GROUP BY 1 ORDER BY cnt DESC LIMIT 20",
            {"d": sd},
        )
        personas = [dict(r) for r in cur.fetchall()]

        cur.execute(f"SELECT COUNT(*) as total FROM {TABLE_TAXONOMY_READ} WHERE target_date = %(d)s", {"d": sd})
        total = cur.fetchone()["total"]

        has_warnings = False

    return {
        "snapshot_date": sd,
        "total_drivers": total,
        "taxonomy_version": TAXONOMY_VERSION,
        "distributions": {
            "operational_status": status,
            "operational_segment": segment,
            "value_overlay": value,
            "momentum": momentum,
        },
        "top_personas": personas,
        "signal_quality_warnings": has_warnings,
    }


def get_driver_taxonomy(driver_id: str, snapshot_date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if snapshot_date_str:
            sd = snapshot_date_str
        else:
            sd = _latest_taxonomy_date(cur)
            if not sd:
                return None

        cur.execute(
            f"SELECT target_date AS snapshot_date, driver_id AS driver_profile_id, "
            f"segment AS operational_status, sub_segment AS activity_status, "
            f"elite_tier, loyalty_tier, park_id, park_name, city, country "
            f"FROM {TABLE_TAXONOMY_READ} WHERE target_date = %(d)s AND driver_id = %(did)s",
            {"d": sd, "did": driver_id},
        )
        tax = cur.fetchone()
        if not tax:
            return None

        cur.execute(
            f"SELECT layer, state_value, explanation_text, matched_rules_json, evidence_json "
            f"FROM {TABLE_EXPLANATION} WHERE snapshot_date = %(d)s AND driver_profile_id = %(did)s "
            "ORDER BY layer",
            {"d": sd, "did": driver_id},
        )
        explanations = [dict(r) for r in cur.fetchall()]

        cur.execute(
            f"SELECT * FROM {TABLE_TRANSITION} WHERE driver_profile_id = %(did)s "
            "ORDER BY curr_date DESC LIMIT 5",
            {"did": driver_id},
        )
        transitions = [dict(r) for r in cur.fetchall()]

    return {
        "driver_profile_id": driver_id,
        "snapshot_date": sd,
        "taxonomy": dict(tax),
        "explanations": explanations,
        "recent_transitions": transitions,
    }


def get_taxonomy_transitions(snapshot_date_str: Optional[str] = None, limit: int = 100) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if snapshot_date_str:
            sd = snapshot_date_str
        else:
            sd = _latest_taxonomy_date(cur)
            if not sd:
                return []

        cur.execute(
            f"SELECT * FROM {TABLE_TRANSITION} WHERE curr_date = %(d)s "
            "ORDER BY created_at DESC LIMIT %(lim)s",
            {"d": sd, "lim": min(limit, 500)},
        )
        return [dict(r) for r in cur.fetchall()]


def seed_taxonomy_config() -> Dict[str, Any]:
    """Seed default taxonomy config into DB. Idempotent."""
    seeds = [
        ("status", "churn_days", 15),
        ("status", "archived_days", 90),
        ("segment", "new_window_days", 90),
        ("segment", "reactivation_gap_days", 90),
        ("segment", "minimum_activation_trips", 50),
        ("segment", "under_activated_window_days", 90),
        ("segment", "growth_max_weekly_trips", 50),
        ("value", "top_percentile", 90),
        ("value", "high_percentile", 70),
        ("value", "mid_percentile", 30),
        ("value", "top_min_weekly_trips", 50),
        ("value", "high_min_weekly_trips", 30),
        ("momentum", "growth_pct", 20),
        ("momentum", "accelerating_pct", 40),
        ("momentum", "softening_pct", -10),
        ("momentum", "decline_pct", -25),
        ("momentum", "collapse_pct", -50),
        ("momentum", "min_volume", 3),
    ]

    with get_db() as conn:
        cur = conn.cursor()
        inserted = 0
        for layer, key, value in seeds:
            cur.execute(
                f"SELECT id FROM {TABLE_CONFIG} WHERE config_key = %(k)s AND layer = %(l)s AND taxonomy_version = %(v)s",
                {"k": key, "l": layer, "v": TAXONOMY_VERSION},
            )
            if cur.fetchone():
                continue
            cur.execute(
                f"INSERT INTO {TABLE_CONFIG} (config_key, config_value_json, layer, taxonomy_version) "
                "VALUES (%(k)s, %(v)s::jsonb, %(l)s, %(tv)s)",
                {"k": key, "v": json.dumps(value), "l": layer, "tv": TAXONOMY_VERSION},
            )
            inserted += 1
        conn.commit()

    return {"ok": True, "seeds_inserted": inserted, "total_seeds": len(seeds)}
