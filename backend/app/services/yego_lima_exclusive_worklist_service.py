"""
YEGO Lima Growth — Exclusive Driver Worklist Daily Service (LG-PROG-EXCL-1B)

Builds growth.yango_lima_exclusive_driver_worklist_daily from canonical sources.
Implements V1 universe contract: 9 universes, deterministic priority order,
1 driver = 1 assigned_universe_v1 per generated_date.

Idempotent UPSERT. Advisory lock protected. No DELETEs.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from app.db.connection import _get_connection_params, get_db

logger = logging.getLogger(__name__)

TABLE_OUT = "growth.yango_lima_exclusive_driver_worklist_daily"
TABLE_SNAPSHOT = "growth.yango_lima_driver_state_snapshot"
TABLE_EXPLORER = "growth.yego_lima_driver_explorer_fact"
TABLE_HISTORY_DAILY = "growth.yango_lima_driver_history_daily"

WORKLIST_LOCK_ID = 9010
SOURCE_VERSION = "exclusive_lists_v1"

UNIVERSE_CEMETERY = "CEMETERY_LONG_CHURNED"
UNIVERSE_RECOVERY_HIGH = "RECOVERY_RECENT_INACTIVE_HIGH_VALUE"
UNIVERSE_RECOVERY_LOW = "RECOVERY_RECENT_INACTIVE_LOW_VALUE"
UNIVERSE_NEW = "NEW_REACTIVATED_0_14_TO_50"
UNIVERSE_RAMP_UP = "RAMP_UP_15_45_TO_100W"
UNIVERSE_CONSOLIDATION = "CONSOLIDATION_46_90_TO_100W"
UNIVERSE_ACTIVE_GROWTH = "ACTIVE_GROWTH_90_PLUS_BAND_UP"
UNIVERSE_PROTECTED = "PROTECTED_ALREADY_MEETING_GOAL"
UNIVERSE_NO_DATA = "NO_DATA_OR_NO_ACTION"

RECOMMENDED_ACTION_CATEGORY = {
    "NEW_REACTIVATED_0_14_TO_50": "ONBOARDING_PUSH",
    "RAMP_UP_15_45_TO_100W": "PRODUCTIVITY_RAMP",
    "CONSOLIDATION_46_90_TO_100W": "CONSOLIDATION_PUSH",
    "ACTIVE_GROWTH_90_PLUS_BAND_UP": "BAND_GROWTH",
    "RECOVERY_RECENT_INACTIVE_HIGH_VALUE": "HIGH_VALUE_RECOVERY",
    "RECOVERY_RECENT_INACTIVE_LOW_VALUE": "LOW_VALUE_RECOVERY",
    "CEMETERY_LONG_CHURNED": "DO_NOT_EXPORT",
    "PROTECTED_ALREADY_MEETING_GOAL": "DO_NOT_EXPORT",
    "NO_DATA_OR_NO_ACTION": "DO_NOT_EXPORT",
}

BAND_ORDER = ["0", "1-10", "11-20", "21-30", "31-40", "41-50", "51-75", "76-99", "100+"]


def _compute_next_band(current_band: str) -> str:
    try:
        idx = BAND_ORDER.index(current_band)
        if idx < len(BAND_ORDER) - 1:
            return BAND_ORDER[idx + 1]
    except ValueError:
        pass
    return "100+"


def _band_min_trips(band: str) -> int:
    if band.endswith("+"):
        return int(band.replace("+", ""))
    parts = band.split("-")
    return int(parts[0]) if parts else 0


def _acquire_worklist_lock(conn) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT pg_try_advisory_lock(%(id)s)", {"id": WORKLIST_LOCK_ID})
    return cur.fetchone()[0]


def _release_worklist_lock(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_unlock(%(id)s)", {"id": WORKLIST_LOCK_ID})
    except Exception:
        pass


def _compute_productivity_band(weekly_trips: int) -> str:
    if weekly_trips >= 100:
        return "100+"
    if weekly_trips >= 76:
        return "76-99"
    if weekly_trips >= 51:
        return "51-75"
    if weekly_trips >= 41:
        return "41-50"
    if weekly_trips >= 31:
        return "31-40"
    if weekly_trips >= 21:
        return "21-30"
    if weekly_trips >= 11:
        return "11-20"
    if weekly_trips >= 1:
        return "1-10"
    return "0"


def _compute_weekly_trips(snapshot: Optional[Dict], explorer: Optional[Dict]) -> int:
    from_snap = (snapshot or {}).get("completed_orders_week") or 0
    from_expl = (explorer or {}).get("trips_7d") or 0
    return max(int(from_snap), int(from_expl), 0)


def _compute_inactivity_days(explorer: Optional[Dict], snapshot: Optional[Dict], target_date: date) -> int:
    dsl = (explorer or {}).get("days_since_last_trip")
    if dsl is not None:
        return int(dsl)

    lt = (snapshot or {}).get("last_trip_at")
    if lt:
        if isinstance(lt, datetime):
            return (target_date - lt.date()).days
        if isinstance(lt, date):
            return (target_date - lt).days

    return 9999


def _compute_value_tier(snapshot: Optional[Dict], explorer: Optional[Dict]) -> str:
    snap = snapshot or {}
    expl = explorer or {}
    hb = snap.get("historical_band", "") or ""
    bw = snap.get("best_week_12w") or 0
    rna_vt = expl.get("rna_value_tier", "") or ""

    if hb.startswith("HISTORICAL_50") or int(bw) >= 50 or "HIGH" in str(rna_vt).upper():
        return "HIGH"
    if hb in ("HISTORICAL_00_09", "NO_HISTORY") or int(bw) < 10:
        return "LOW"
    return "DEFAULT"


def refresh_exclusive_driver_worklist_daily(target_date: Optional[str] = None, config_version_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds exclusive worklist daily.
    If config_version_code is not provided, looks up ACTIVE config for Lima scope.
    Falls back to V1 hardcoded rules if no ACTIVE config exists.
    """
    if target_date is None:
        target_date = date.today().isoformat()
    target_d = date.fromisoformat(target_date[:10])

    # LG-UNIVERSE-ACTIVE-DEFAULT-1J.2: Auto-detect ACTIVE config
    if config_version_code is None:
        try:
            c = psycopg2.connect(**_get_connection_params())
            cur = c.cursor()
            cur.execute("SELECT version_code FROM growth.universe_config_version WHERE status='ACTIVE' AND scope='lima' LIMIT 1")
            row = cur.fetchone()
            cur.close(); c.close()
            if row:
                config_version_code = row[0]
                logger.info("Using ACTIVE config: %s", config_version_code)
        except Exception as e:
            logger.warning("Could not detect ACTIVE config, falling back to V1: %s", e)

    params = _get_connection_params()
    params["options"] = "-c statement_timeout=300000"
    conn = psycopg2.connect(**params)
    conn.autocommit = False

    if not _acquire_worklist_lock(conn):
        conn.close()
        return {"ok": False, "status": "SKIPPED_LOCKED", "reason": "Another worklist refresh is in progress"}

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ── Fetch latest snapshot ──
        cur.execute(
            f"SELECT * FROM {TABLE_SNAPSHOT} WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM {TABLE_SNAPSHOT})"
        )
        snapshot_rows = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        max_snap_date = None
        cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_SNAPSHOT}")
        row = cur.fetchone()
        if row:
            max_snap_date = row["max"]

        # ── Fetch latest explorer fact ──
        cur.execute(
            f"SELECT * FROM {TABLE_EXPLORER} WHERE target_date = (SELECT MAX(target_date) FROM {TABLE_EXPLORER})"
        )
        explorer_rows = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        max_expl_date = None
        cur.execute(f"SELECT MAX(target_date) FROM {TABLE_EXPLORER}")
        row = cur.fetchone()
        if row:
            max_expl_date = row["max"]

        # ── Fetch first_active_date from history_daily ──
        cur.execute(
            f"SELECT driver_profile_id, MIN(date) AS first_active_date "
            f"FROM {TABLE_HISTORY_DAILY} GROUP BY driver_profile_id"
        )
        first_active = {r["driver_profile_id"]: r["first_active_date"] for r in cur.fetchall()}

        cur.close()

        # ── LG-UNIVERSE-ACTIVATE-1J.1: V2 Config classification ──
        if config_version_code:
            return _build_worklist_v2(snapshot_rows, explorer_rows, first_active, target_d, max_snap_date, max_expl_date, config_version_code)

        # ── Build worklist rows V1 ──
        all_driver_ids = set(snapshot_rows.keys()) | set(explorer_rows.keys())
        rows: List[Dict[str, Any]] = []
        universe_counts: Dict[str, int] = {}

        for did in sorted(all_driver_ids):
            snap = snapshot_rows.get(did)
            expl = explorer_rows.get(did)
            fad = first_active.get(did)

            weekly_trips = _compute_weekly_trips(snap, expl)
            inactivity_days = _compute_inactivity_days(expl, snap, target_d)
            value_tier = _compute_value_tier(snap, expl)

            operational_age_days = None
            if fad:
                operational_age_days = (target_d - fad).days

            activation_window_trips = int((expl or {}).get("trips_30d") or 0)
            productivity_band = _compute_productivity_band(weekly_trips)
            trend = (expl or {}).get("activity_trend") or "UNKNOWN"

            # ── Priority-ordered assignment ──
            assigned_universe = UNIVERSE_NO_DATA
            objective = "insufficient_data_or_no_daily_action"
            reason_code = "NO_DATA_FALLBACK"
            priority_rank = 999
            export_to_cl = False
            target_metric = None
            baseline_metric = None

            # 1. CEMETERY
            if inactivity_days > 60:
                assigned_universe = UNIVERSE_CEMETERY
                objective = "separate_from_daily_ops"
                reason_code = "INACTIVITY_GT_60_DAYS"
                priority_rank = 900
                export_to_cl = False

            # 2. RECOVERY HIGH
            elif 7 <= inactivity_days <= 60 and value_tier == "HIGH":
                assigned_universe = UNIVERSE_RECOVERY_HIGH
                objective = "reactivate_high_value_driver"
                reason_code = "INACTIVE_7_60_HIGH_VALUE"
                priority_rank = 100
                export_to_cl = True

            # 3. RECOVERY LOW
            elif 7 <= inactivity_days <= 60:
                assigned_universe = UNIVERSE_RECOVERY_LOW
                objective = "reactivate_low_value_driver"
                reason_code = "INACTIVE_7_60_LOW_VALUE"
                priority_rank = 200
                export_to_cl = True

            # 4. NEW/REACTIVATED 0-14
            elif (operational_age_days is not None and 0 <= operational_age_days <= 14
                  and activation_window_trips < 50 and inactivity_days < 7):
                assigned_universe = UNIVERSE_NEW
                objective = "reach_50_trips_in_first_14_days"
                reason_code = "AGE_0_14_TRIPS_BELOW_50"
                priority_rank = 300
                export_to_cl = True
                target_metric = "50_trips_activation_window"
                baseline_metric = str(activation_window_trips)

            # 5. RAMP-UP 15-45
            elif (operational_age_days is not None and 15 <= operational_age_days <= 45
                  and weekly_trips < 100 and inactivity_days < 7):
                assigned_universe = UNIVERSE_RAMP_UP
                objective = "reach_100_trips_per_week"
                reason_code = "AGE_15_45_WEEKLY_BELOW_100"
                priority_rank = 400
                export_to_cl = True
                target_metric = "100_trips_weekly"
                baseline_metric = str(weekly_trips)

            # 6. CONSOLIDATION 46-90
            elif (operational_age_days is not None and 46 <= operational_age_days <= 90
                  and weekly_trips < 100 and inactivity_days < 7):
                assigned_universe = UNIVERSE_CONSOLIDATION
                objective = "sustain_or_reach_100_trips_per_week"
                reason_code = "AGE_46_90_WEEKLY_BELOW_100"
                priority_rank = 500
                export_to_cl = True
                target_metric = "100_trips_weekly"
                baseline_metric = str(weekly_trips)

            # 7. ACTIVE GROWTH 90+
            elif (operational_age_days is not None and operational_age_days > 90
                  and 1 <= weekly_trips < 100 and inactivity_days < 7):
                assigned_universe = UNIVERSE_ACTIVE_GROWTH
                objective = "move_up_one_weekly_trip_band"
                reason_code = "AGE_90_PLUS_BELOW_GOAL"
                priority_rank = 600
                export_to_cl = True
                target_metric = f"next_band_above_{productivity_band}"
                baseline_metric = productivity_band

            # 8. PROTECTED
            elif weekly_trips >= 100 or (
                operational_age_days is not None and 0 <= operational_age_days <= 14 and activation_window_trips >= 50
            ):
                assigned_universe = UNIVERSE_PROTECTED
                objective = "no_daily_action_already_meeting_goal"
                reason_code = "MEETING_WEEKLY_OR_ACTIVATION_GOAL"
                priority_rank = 800
                export_to_cl = False

            # 9. NO_DATA (default already set)

            # ── LG-PROG-EXCL-1E: Explainability Fields ──
            RECOVERED_THRESHOLD_DAYS = 45
            reason_text = ""
            gap_value = None
            exit_cond = ""
            move_hint = ""
            rec_action = RECOMMENDED_ACTION_CATEGORY.get(assigned_universe, "UNKNOWN")

            if assigned_universe == UNIVERSE_NEW:
                gap_value = max(0, 50 - int(activation_window_trips))
                reason_text = (
                    f"Driver on day {operational_age_days or '?'} since first activity. "
                    f"Has {activation_window_trips} trips in the activation window and has not reached the 50-trip target."
                )
                exit_cond = "Reaches 50 trips OR exceeds 14 days since activation."
                move_hint = f"If reaches 50 trips moves to Protected. If exceeds 14 days without reaching target moves to Ramp-Up. Gap: {gap_value} trips."

            elif assigned_universe == UNIVERSE_RAMP_UP:
                gap_value = max(0, 100 - int(weekly_trips))
                reason_text = (
                    f"Driver on day {operational_age_days or '?'}. "
                    f"Has {weekly_trips} weekly trips and is below the 100 trips/week objective."
                )
                exit_cond = "Reaches 100 trips/week OR exceeds 45 days OR becomes inactive."
                move_hint = f"If reaches 100 trips/week moves to Protected. If exceeds 45 days without reaching target moves to Consolidation. Gap: {gap_value} trips/week."

            elif assigned_universe == UNIVERSE_CONSOLIDATION:
                gap_value = max(0, 100 - int(weekly_trips))
                reason_text = (
                    f"Driver on day {operational_age_days or '?'}. "
                    f"Has {weekly_trips} weekly trips and is below the 100 trips/week objective during consolidation."
                )
                exit_cond = "Reaches 100 trips/week OR exceeds 90 days OR becomes inactive."
                move_hint = f"If exceeds 90 days active and below 100 trips/week moves to Active Growth. Gap: {gap_value} trips/week."

            elif assigned_universe == UNIVERSE_ACTIVE_GROWTH:
                next_band = _compute_next_band(productivity_band) if productivity_band != "100+" else None
                if next_band and productivity_band != "100+":
                    gap_value = max(0, _band_min_trips(next_band) - int(weekly_trips))
                else:
                    gap_value = 0
                reason_text = (
                    f"Driver active 90+ days. "
                    f"Has {weekly_trips} weekly trips, in band {productivity_band}. "
                    f"Target: move to band {next_band or 'higher'}."
                )
                exit_cond = f"Moves up a band OR reaches 100+ trips/week OR becomes inactive."
                move_hint = f"Target next band: {next_band}. Delta required: {gap_value} trips/week to reach minimum of next band."

            elif assigned_universe == UNIVERSE_RECOVERY_HIGH:
                gap_value = 1
                reason_text = (
                    f"High-value driver with {inactivity_days} days without trips. "
                    f"Value tier: HIGH (best_week_12w >= 50 or high historical band). Must be recovered."
                )
                exit_cond = "Returns to active driving OR exceeds 60 days inactive (Cemetery)."
                move_hint = f"If reactivates after {RECOVERED_THRESHOLD_DAYS}+ days inactive, register as recovered."

            elif assigned_universe == UNIVERSE_RECOVERY_LOW:
                gap_value = 1
                reason_text = (
                    f"Driver with {inactivity_days} days without trips. "
                    f"Value tier: {value_tier}. Recovery treatment at low/default intensity."
                )
                exit_cond = "Returns to active driving OR exceeds 60 days inactive (Cemetery)."
                move_hint = f"If reactivates after {RECOVERED_THRESHOLD_DAYS}+ days inactive, register as recovered."

            elif assigned_universe == UNIVERSE_CEMETERY:
                gap_value = None
                reason_text = (
                    f"Driver with {inactivity_days} days without trips. "
                    f"Outside daily operations. Not exported to Control Loop by default."
                )
                exit_cond = "Returns to active driving."
                move_hint = f"If returns to active after {RECOVERED_THRESHOLD_DAYS}+ days inactive, register as recovered and reclassify."

            elif assigned_universe == UNIVERSE_PROTECTED:
                gap_value = 0
                reason_text = (
                    f"Driver already meeting operational target. "
                    f"Has {weekly_trips} weekly trips or reached the activation goal."
                )
                exit_cond = "Drops below target OR becomes inactive."
                move_hint = "No daily action required. Monitor for decline."

            else:
                gap_value = None
                reason_text = "Insufficient data to classify. No daily action."
                exit_cond = "Data becomes available."
                move_hint = "Awaiting classification data."

            evidence_json = {
                "generated_date": str(target_d),
                "assigned_universe_v1": assigned_universe,
                "operational_age_days": operational_age_days,
                "weekly_trips": weekly_trips,
                "activation_window_trips": activation_window_trips,
                "inactivity_days": inactivity_days,
                "value_tier": value_tier,
                "productivity_band": productivity_band,
                "target_metric": target_metric,
                "baseline_metric": baseline_metric,
                "gap_to_target": gap_value,
                "export_to_control_loop": export_to_cl,
                "first_active_date_source": "driver_history_daily.MIN(date)",
                "recovered_threshold_days": RECOVERED_THRESHOLD_DAYS,
                "classification_version": SOURCE_VERSION,
            }

            row = {
                "generated_date": target_d,
                "driver_profile_id": did,
                "driver_id": (expl or {}).get("driver_name") or did,
                "assigned_universe_v1": assigned_universe,
                "assigned_program_v1": assigned_universe,
                "subsegment": "high_value" if value_tier == "HIGH" else ("low_value" if value_tier == "LOW" else None),
                "objective": objective,
                "reason_code": reason_code,
                "priority_rank": priority_rank,
                "operational_age_days": operational_age_days,
                "weekly_trips": weekly_trips,
                "activation_window_trips": activation_window_trips,
                "inactivity_days": inactivity_days,
                "value_tier": value_tier,
                "productivity_band": productivity_band,
                "trend": trend,
                "target_metric": target_metric,
                "baseline_metric": baseline_metric,
                "export_to_control_loop": export_to_cl,
                "source_snapshot_date": max_snap_date,
                "source_explorer_target_date": max_expl_date,
                "source_version": SOURCE_VERSION,
                "reason_text": reason_text,
                "evidence_json": evidence_json,
                "gap_to_target": gap_value,
                "exit_condition": exit_cond,
                "movement_hint": move_hint,
                "recommended_action_category": rec_action,
            }
            rows.append(row)
            universe_counts[assigned_universe] = universe_counts.get(assigned_universe, 0) + 1

        # ── UPSERT all rows in bulk ──
        from psycopg2.extras import execute_values
        import json as _json

        cur2 = conn.cursor()
        columns = [
            "generated_date", "driver_profile_id", "driver_id", "assigned_universe_v1", "assigned_program_v1",
            "subsegment", "objective", "reason_code", "priority_rank", "operational_age_days", "weekly_trips",
            "activation_window_trips", "inactivity_days", "value_tier", "productivity_band", "trend",
            "target_metric", "baseline_metric", "export_to_control_loop",
            "source_snapshot_date", "source_explorer_target_date", "source_version",
            "reason_text", "evidence_json", "gap_to_target", "exit_condition", "movement_hint", "recommended_action_category",
        ]
        values = [
            (
                r["generated_date"], r["driver_profile_id"], r["driver_id"], r["assigned_universe_v1"], r["assigned_program_v1"],
                r["subsegment"], r["objective"], r["reason_code"], r["priority_rank"], r["operational_age_days"], r["weekly_trips"],
                r["activation_window_trips"], r["inactivity_days"], r["value_tier"], r["productivity_band"], r["trend"],
                r["target_metric"], r["baseline_metric"], r["export_to_control_loop"],
                r["source_snapshot_date"], r["source_explorer_target_date"], r["source_version"],
                r.get("reason_text"), _json.dumps(r.get("evidence_json", {})),
                r.get("gap_to_target"), r.get("exit_condition"), r.get("movement_hint"), r.get("recommended_action_category"),
            )
            for r in rows
        ]
        col_list = ", ".join(columns)
        set_clause = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in columns[2:]  # skip generated_date, driver_profile_id (PK)
        ) + ", updated_at = now()"

        execute_values(
            cur2,
            f"INSERT INTO {TABLE_OUT} ({col_list}) VALUES %s "
            f"ON CONFLICT (generated_date, driver_profile_id) DO UPDATE SET {set_clause}",
            values,
            page_size=5000,
        )
        cur2.close()
        conn.commit()

        exportable = sum(1 for r in rows if r["export_to_control_loop"])

        return {
            "ok": True,
            "status": "SUCCESS",
            "generated_date": target_date,
            "total_drivers": len(rows),
            "exportable_drivers": exportable,
            "universe_counts": universe_counts,
            "source_snapshot_date": str(max_snap_date) if max_snap_date else None,
            "source_explorer_target_date": str(max_expl_date) if max_expl_date else None,
        }

    except Exception as e:
        conn.rollback()
        logger.error("Exclusive worklist refresh failed: %s", e)
        return {"ok": False, "status": "FAILED", "error": str(e)[:500]}
    finally:
        _release_worklist_lock(conn)
        try:
            conn.close()
        except Exception:
            pass


def get_exclusive_worklist_summary(generated_date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if generated_date is None:
            cur.execute(f"SELECT MAX(generated_date) FROM {TABLE_OUT}")
            row = cur.fetchone()
            generated_date = str(row["max"]) if row and row["max"] else None

        if not generated_date:
            return {"ok": True, "resolved_generated_date": None, "total_drivers": 0, "by_universe": []}

        cur.execute(
            f"SELECT assigned_universe_v1, COUNT(*) AS drivers FROM {TABLE_OUT} "
            f"WHERE generated_date = %(d)s GROUP BY assigned_universe_v1 ORDER BY MIN(priority_rank)",
            {"d": generated_date},
        )
        by_universe = [dict(r) for r in cur.fetchall()]

        cur.execute(f"SELECT COUNT(*) AS total FROM {TABLE_OUT} WHERE generated_date = %(d)s", {"d": generated_date})
        total = cur.fetchone()["total"]

        cur.execute(
            f"SELECT COUNT(*) AS exp FROM {TABLE_OUT} WHERE generated_date = %(d)s AND export_to_control_loop = true",
            {"d": generated_date},
        )
        exportable = cur.fetchone()["exp"]

        return {
            "ok": True,
            "resolved_generated_date": generated_date,
            "total_drivers": total,
            "exportable_drivers": exportable,
            "by_universe": by_universe,
        }


def get_exclusive_worklist_rows(
    generated_date: Optional[str] = None,
    assigned_universe: Optional[str] = None,
    exportable_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if generated_date is None:
            cur.execute(f"SELECT MAX(generated_date) FROM {TABLE_OUT}")
            row = cur.fetchone()
            generated_date = str(row["max"]) if row and row["max"] else None

        if not generated_date:
            return {"ok": True, "rows": [], "total": 0}

        where = ["generated_date = %(d)s"]
        params = {"d": generated_date}
        if assigned_universe:
            where.append("assigned_universe_v1 = %(u)s")
            params["u"] = assigned_universe
        if exportable_only:
            where.append("export_to_control_loop = true")

        where_clause = " AND ".join(where)

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_OUT} WHERE {where_clause}", params)
        total = cur.fetchone()["count"]

        params["lim"] = limit
        params["off"] = offset
        cur.execute(
            f"SELECT * FROM {TABLE_OUT} WHERE {where_clause} "
            f"ORDER BY priority_rank, driver_profile_id LIMIT %(lim)s OFFSET %(off)s",
            params,
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            for k in ("generated_date", "created_at", "updated_at", "source_snapshot_date", "source_explorer_target_date"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
                elif d.get(k):
                    d[k] = str(d[k])
            rows.append(d)

        return {"ok": True, "rows": rows, "total": total}


def _build_worklist_v2(snapshot_rows, explorer_rows, first_active, target_d, max_snap_date, max_expl_date, config_version_code):
    """LG-UNIVERSE-WRITER-INTEGRATION-1J.1: Build worklist using Universe Config V2 rules."""
    from app.services.yego_lima_universe_simulation_service import _eval_rule
    from psycopg2.extras import execute_values
    import json as _json

    params = _get_connection_params()
    params["options"] = "-c statement_timeout=300000"
    conn = psycopg2.connect(**params)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Lookup config version
        cur.execute("SELECT * FROM growth.universe_config_version WHERE version_code = %s", (config_version_code,))
        ver = cur.fetchone()
        if not ver:
            return {"ok": False, "error": f"Config version '{config_version_code}' not found"}
        if ver["status"] not in ("DRAFT", "SIMULATED", "APPROVED", "ACTIVE"):
            return {"ok": False, "error": f"Config status is {ver['status']}"}
        version_id = ver["version_id"]

        cur.execute("SELECT * FROM growth.universe_definition_config WHERE version_id = %s AND active_flag = true ORDER BY priority_order", (version_id,))
        defs = {r["universe_code"]: dict(r) for r in cur.fetchall()}

        cur.execute("SELECT * FROM growth.universe_rule_config WHERE version_id = %s ORDER BY universe_code, priority", (version_id,))
        rules_by_universe = {}
        for r in cur.fetchall():
            uni = r["universe_code"]
            rules_by_universe.setdefault(uni, []).append(dict(r))
        cur.close()

        # Derive anchors
        cur2 = conn.cursor(cursor_factory=RealDictCursor)
        cur2.execute("SELECT driver_profile_id, MIN(date) AS first_date, MAX(date) AS last_date FROM growth.yango_lima_driver_history_daily GROUP BY 1")
        anchors = {r["driver_profile_id"]: {"first_date": r["first_date"], "last_date": r["last_date"]} for r in cur2.fetchall()}
        cur2.close()

        rows = []
        counts = {}
        src_d = target_d
        all_dids = set(snapshot_rows.keys()) | set(explorer_rows.keys())

        for did in sorted(all_dids):
            snap = snapshot_rows.get(did, {})
            expl = explorer_rows.get(did, {})
            anc = anchors.get(did)

            # Build features (simulation-compatible)
            anchor_age = (src_d - anc["first_date"]).days if anc and anc["first_date"] else None
            features = {
                "anchor_age_days": anchor_age,
                "anchor_type": "EXISTING",
                "weekly_trips": max(snap.get("completed_orders_week") or 0, expl.get("trips_7d") or 0),
                "trips_since_lifecycle_anchor": expl.get("trips_30d") or 0,
                "inactivity_days": expl.get("days_since_last_trip", 9999),
                "value_tier": _compute_value_tier(snap, expl),
                "reactivation_anchor_age_days": None,
                "has_reactivation_anchor": "false",
            }
            if anchor_age is not None and anchor_age <= 14:
                features["anchor_type"] = "NEW"

            # Evaluate rules in priority order
            sim_uni = "NO_DATA"
            sim_export = False
            sim_reason = "Fallback: no rules matched"

            for uni in [d["universe_code"] for d in sorted(defs.values(), key=lambda x: x["priority_order"])]:
                rules = rules_by_universe.get(uni, [])
                if not rules: continue
                groups = {}
                for r in rules:
                    groups.setdefault(r["rule_group"], []).append(r)
                matched = False
                for grp, grp_rules in groups.items():
                    grp_match = True
                    for rule in grp_rules:
                        fv = features.get(rule["field_name"])
                        ok2, _ = _eval_rule(fv, rule["operator"], rule["value"], rule["value_type"], rule["null_behavior"])
                        if not ok2:
                            grp_match = False
                            break
                    if grp_match:
                        matched = True
                        break
                if matched:
                    defn = defs.get(uni, {})
                    sim_uni = uni
                    sim_export = defn.get("export_to_control_loop", False)
                    sim_reason = f"V2 config: {list(groups.keys())}"
                    break

            counts[sim_uni] = counts.get(sim_uni, 0) + 1
            wt = features["weekly_trips"]
            pb = _compute_productivity_band(wt)

            row = {
                "generated_date": src_d,
                "driver_profile_id": did,
                "driver_id": expl.get("driver_name") or did,
                "assigned_universe_v1": sim_uni,
                "assigned_program_v1": sim_uni,
                "reason_code": sim_reason[:50],
                "reason_text": sim_reason,
                "objective": defs.get(sim_uni, {}).get("universe_label", sim_uni),
                "priority_rank": defs.get(sim_uni, {}).get("priority_order", 999),
                "operational_age_days": features["anchor_age_days"],
                "weekly_trips": wt,
                "activation_window_trips": features["trips_since_lifecycle_anchor"],
                "inactivity_days": features["inactivity_days"],
                "value_tier": features["value_tier"],
                "productivity_band": pb,
                "trend": expl.get("activity_trend") or "UNKNOWN",
                "target_metric": defs.get(sim_uni, {}).get("target_metric"),
                "baseline_metric": str(wt),
                "export_to_control_loop": sim_export,
                "gap_to_target": None,
                "exit_condition": None,
                "movement_hint": None,
                "recommended_action_category": defs.get(sim_uni, {}).get("recommended_action_category", "UNKNOWN"),
                "subsegment": None,
                "evidence_json": _json.dumps(features),
                "source_snapshot_date": max_snap_date,
                "source_explorer_target_date": max_expl_date,
                "source_version": f"universe_config_v2_{config_version_code}",
            }
            rows.append(row)

        # UPSERT
        from psycopg2.extras import execute_values
        cur3 = conn.cursor()
        cols = [
            "generated_date", "driver_profile_id", "driver_id", "assigned_universe_v1", "assigned_program_v1",
            "subsegment", "objective", "reason_code", "priority_rank", "operational_age_days", "weekly_trips",
            "activation_window_trips", "inactivity_days", "value_tier", "productivity_band", "trend",
            "target_metric", "baseline_metric", "export_to_control_loop",
            "source_snapshot_date", "source_explorer_target_date", "source_version",
            "reason_text", "evidence_json", "gap_to_target", "exit_condition", "movement_hint", "recommended_action_category",
        ]
        vals = [
            (r["generated_date"], r["driver_profile_id"], r["driver_id"], r["assigned_universe_v1"], r["assigned_program_v1"],
             r["subsegment"], r["objective"], r["reason_code"], r["priority_rank"], r["operational_age_days"], r["weekly_trips"],
             r["activation_window_trips"], r["inactivity_days"], r["value_tier"], r["productivity_band"], r["trend"],
             r["target_metric"], r["baseline_metric"], r["export_to_control_loop"],
             r["source_snapshot_date"], r["source_explorer_target_date"], r["source_version"],
             r["reason_text"], r["evidence_json"], r["gap_to_target"], r["exit_condition"], r["movement_hint"], r["recommended_action_category"])
            for r in rows
        ]
        col_list = ", ".join(cols)
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("generated_date", "driver_profile_id")) + ", updated_at = now()"
        execute_values(cur3, f"INSERT INTO {TABLE_OUT} ({col_list}) VALUES %s ON CONFLICT (generated_date, driver_profile_id) DO UPDATE SET {set_clause}", vals, page_size=5000)
        cur3.close()
        conn.commit()

        exportable = sum(1 for r in rows if r["export_to_control_loop"])
        return {
            "ok": True, "status": "SUCCESS", "generated_date": str(src_d),
            "total_drivers": len(rows), "exportable_drivers": exportable,
            "universe_counts": counts, "config_version_code": config_version_code,
        }
    except Exception as e:
        conn.rollback()
        logger.error("V2 worklist failed: %s", e)
        return {"ok": False, "status": "FAILED", "error": str(e)[:500]}
    finally:
        try: conn.close()
        except: pass
