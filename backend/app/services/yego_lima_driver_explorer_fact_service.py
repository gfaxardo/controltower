"""
LG-EXP-1D — Driver Explorer Fact Writer

Builds growth.yego_lima_driver_explorer_fact from governed snapshot sources.
Grain: (target_date, driver_profile_id). Idempotent UPSERT.

Rules:
- Never fail on missing source tables (rna_priority_fact, impact_tracking, etc.)
- data_quality reflects source availability: COMPLETE / PARTIAL
- Movement derived from day-over-day lifecycle_state diff
- Activity trend computed from declining_flag / new_driver_flag / completed_orders_week
- NEVER reads deprecated tables (driver_movement_fact, driver_taxonomy_v2_daily)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_FACT = "growth.yego_lima_driver_explorer_fact"
TABLE_DS = "growth.yango_lima_driver_state_snapshot"
TABLE_PR = "growth.yango_lima_program_eligibility_daily"
TABLE_RNA = "growth.rna_priority_fact"
TABLE_LC = "growth.yego_lima_loopcontrol_result_sync"
TABLE_AQ = "growth.yango_lima_assignment_queue"
TABLE_LF = "growth.yego_lima_driver_lifecycle_daily"
TABLE_IMP = "growth.yego_lima_impact_tracking"
TABLE_TAX = "growth.yego_lima_v2_taxonomy_daily"
TABLE_MOV = "growth.yego_lima_v2_movement_fact"

TIMEOUT_MS = 60000


def _table_exists(cur, table_name: str) -> bool:
    parts = table_name.split(".")
    schema = parts[0] if len(parts) > 1 else "public"
    name = parts[1] if len(parts) > 1 else parts[0]
    cur.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s) AS exists_flag",
        (schema, name),
    )
    row = cur.fetchone()
    if row is None:
        return False
    if isinstance(row, dict):
        return row.get("exists_flag", False)
    return row[0]


def _col_exists(cur, table_name: str, col: str) -> bool:
    parts = table_name.split(".")
    schema = parts[0] if len(parts) > 1 else "public"
    name = parts[1] if len(parts) > 1 else parts[0]
    cur.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name=%s) AS exists_flag",
        (schema, name, col),
    )
    row = cur.fetchone()
    if row is None:
        return False
    if isinstance(row, dict):
        return row.get("exists_flag", False)
    return row[0]


def build_driver_explorer_fact(target_date: str) -> Dict[str, Any]:
    target_date = str(target_date)[:10]
    prev_date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    result: Dict[str, Any] = {
        "target_date": target_date,
        "status": "UNKNOWN",
        "rows_upserted": 0,
        "sources_available": [],
        "sources_missing": [],
        "data_quality": "PARTIAL",
        "errors": [],
    }

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET LOCAL statement_timeout = %s", (str(TIMEOUT_MS),))

        ds_ok = _table_exists(cur, TABLE_DS)
        pr_ok = _table_exists(cur, TABLE_PR)
        rna_ok = _table_exists(cur, TABLE_RNA)
        lc_ok = _table_exists(cur, TABLE_LC)
        aq_ok = _table_exists(cur, TABLE_AQ)
        lf_ok = _table_exists(cur, TABLE_LF)
        imp_ok = _table_exists(cur, TABLE_IMP)
        tax_ok = _table_exists(cur, TABLE_TAX)
        mov_ok = _table_exists(cur, TABLE_MOV)

        for name, ok in [
            ("driver_state_snapshot", ds_ok),
            ("program_eligibility_daily", pr_ok),
            ("rna_priority_fact", rna_ok),
            ("loopcontrol_result_sync", lc_ok),
            ("assignment_queue", aq_ok),
            ("driver_lifecycle_daily", lf_ok),
            ("impact_tracking", imp_ok),
            ("v2_taxonomy_daily", tax_ok),
            ("v2_movement_fact", mov_ok),
        ]:
            (result["sources_available"] if ok else result["sources_missing"]).append(name)

        if not ds_ok:
            result["status"] = "FAILED"
            result["errors"].append(f"{TABLE_DS} does not exist")
            return result

        has_driver_name = _col_exists(cur, TABLE_DS, "driver_name")
        has_phone = _col_exists(cur, TABLE_DS, "phone")
        has_segment = _col_exists(cur, TABLE_DS, "segment")

        available_count = sum([1 for x in [rna_ok, lf_ok, tax_ok, mov_ok, lc_ok, imp_ok, aq_ok] if x])
        data_quality = "COMPLETE" if available_count >= 7 else "PARTIAL"

        # Build column expressions and join clauses
        ds_name_expr = "ds.driver_name" if has_driver_name else "NULL::text"
        ds_phone_expr = "ds.phone" if has_phone else "NULL::text"
        ds_segment_expr = "ds.segment" if has_segment else "NULL::text"

        rna_join_clause = ""
        rna_trips_7d_expr = "COALESCE(ds.completed_orders_week, 0)"
        rna_trips_30d_expr = "COALESCE(lf.completed_trips_30d, 0)"
        rna_days_since_expr = "lf.days_since_last_completed_trip"
        if rna_ok:
            rna_join_clause = "LEFT JOIN growth.rna_priority_fact rna ON ds.driver_profile_id = rna.driver_profile_id"
            rna_trips_7d_expr = "COALESCE(rna.trips_7d, ds.completed_orders_week, 0)"
            rna_trips_30d_expr = "COALESCE(rna.trips_30d, lf.completed_trips_30d, 0)"
            rna_days_since_expr = "COALESCE(rna.days_since_last_trip, lf.days_since_last_completed_trip)"

        lc_join_clause = ""
        if lc_ok:
            lc_join_clause = """
                LEFT JOIN LATERAL (
                    SELECT last_call_at, disposition, agent, attempts
                    FROM growth.yego_lima_loopcontrol_result_sync
                    WHERE driver_id = ds.driver_profile_id
                    ORDER BY synced_at DESC NULLS LAST
                    LIMIT 1
                ) lc_sync ON TRUE"""

        aq_join_clause = ""
        if aq_ok:
            aq_join_clause = """
                LEFT JOIN LATERAL (
                    SELECT driver_name AS aq_name, phone AS aq_phone, campaign_id_external, status
                    FROM growth.yango_lima_assignment_queue
                    WHERE driver_profile_id = ds.driver_profile_id
                    ORDER BY queue_date DESC NULLS LAST
                    LIMIT 1
                ) aq ON TRUE"""

        lf_join_clause = ""
        if lf_ok:
            lf_join_clause = f"""
                LEFT JOIN {TABLE_LF} lf
                    ON ds.driver_profile_id = lf.driver_profile_id
                    AND lf.snapshot_date = %(target_date)s"""

        imp_join_clause = ""
        if imp_ok:
            imp_join_clause = """
                LEFT JOIN LATERAL (
                    SELECT impact_status, baseline_trips, post_contact_trips
                    FROM growth.yego_lima_impact_tracking
                    WHERE driver_id = ds.driver_profile_id
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT 1
                ) imp ON TRUE"""

        tax_join_clause = ""
        if tax_ok:
            tax_join_clause = f"""
                LEFT JOIN {TABLE_TAX} tx
                    ON ds.driver_profile_id = tx.driver_id
                    AND tx.target_date = %(target_date)s"""

        mov_join_clause = ""
        if mov_ok:
            mov_join_clause = f"""
                LEFT JOIN {TABLE_MOV} mv
                    ON ds.driver_profile_id = mv.driver_id
                    AND mv.target_date = %(target_date)s"""

        # Build the full UPSERT
        segment_expr = f"COALESCE(tx.segment, {ds_segment_expr}, ds.historical_band)" if tax_ok else f"COALESCE({ds_segment_expr}, ds.historical_band)"
        sub_segment_expr = "tx.sub_segment" if tax_ok else "NULL::text"

        rna_band_expr = "COALESCE(rna.priority_band, 'COLD')" if rna_ok else "'COLD'::text"
        rna_score_expr = "COALESCE(rna.rna_score, 0)" if rna_ok else "0::numeric(6,2)"
        contactable_expr = "COALESCE(rna.contactable, FALSE)" if rna_ok else "FALSE::boolean"
        cancelled_expr = "COALESCE(rna.cancelled_signal, FALSE)" if rna_ok else "FALSE::boolean"
        rna_valtier_expr = "rna.value_tier" if rna_ok else "NULL::text"
        rna_momentum_expr = "rna.momentum" if rna_ok else "NULL::text"

        mov_type_expr = "COALESCE(mv.movement_type, CASE WHEN prev.lifecycle_state IS NULL THEN 'NEW_ENTRY' WHEN prev.lifecycle_state = ds.lifecycle_state THEN 'STABLE' ELSE 'STATE_CHANGE' END)" if mov_ok else "CASE WHEN prev.lifecycle_state IS NULL THEN 'NEW_ENTRY' WHEN prev.lifecycle_state = ds.lifecycle_state THEN 'STABLE' ELSE 'STATE_CHANGE' END"
        mov_from_expr = "COALESCE(mv.from_state, prev.lifecycle_state)" if mov_ok else "prev.lifecycle_state"
        mov_to_expr = "COALESCE(mv.to_state, ds.lifecycle_state)" if mov_ok else "ds.lifecycle_state"
        mov_trigger_expr = "COALESCE(mv.trigger_reason, CASE WHEN prev.lifecycle_state IS NULL THEN 'First snapshot for driver' WHEN prev.lifecycle_state != ds.lifecycle_state THEN 'Lifecycle changed: ' || prev.lifecycle_state || ' -> ' || ds.lifecycle_state ELSE NULL END)" if mov_ok else "CASE WHEN prev.lifecycle_state IS NULL THEN 'First snapshot for driver' WHEN prev.lifecycle_state != ds.lifecycle_state THEN 'Lifecycle changed: ' || COALESCE(prev.lifecycle_state, 'NULL') || ' -> ' || COALESCE(ds.lifecycle_state, 'NULL') ELSE NULL END"

        contact_at_expr = "lc_sync.last_call_at" if lc_ok else "NULL::timestamptz"
        contact_disp_expr = "lc_sync.disposition" if lc_ok else "NULL::text"
        contact_agent_expr = "lc_sync.agent" if lc_ok else "NULL::text"
        contact_attempts_expr = "lc_sync.attempts" if lc_ok else "NULL::integer"

        aq_name_expr = "aq.aq_name" if aq_ok else "NULL::text"
        aq_phone_expr = "aq.aq_phone" if aq_ok else "NULL::text"
        campaign_expr = "aq.campaign_id_external" if aq_ok else "NULL::text"
        queue_status_expr = "aq.status" if aq_ok else "NULL::text"

        trips_30d_expr = "COALESCE(lf.completed_trips_30d, 0)" if lf_ok else "0::integer"
        trips_anchor_expr = "COALESCE(lf.completed_trips_since_anchor, 0)" if lf_ok else "0::integer"
        lf_days_since_expr = "lf.days_since_last_completed_trip" if lf_ok else "NULL::integer"

        imp_status_expr = "imp.impact_status" if imp_ok else "NULL::text"
        imp_baseline_expr = "COALESCE(imp.baseline_trips, 0)" if imp_ok else "0::integer"
        imp_post_expr = "COALESCE(imp.post_contact_trips, 0)" if imp_ok else "0::integer"

        upsert_sql = f"""
            WITH driver_base AS (
                SELECT DISTINCT ON (ds.driver_profile_id)
                    ds.snapshot_date::date AS target_date,
                    ds.driver_profile_id,
                COALESCE({aq_name_expr}, {ds_name_expr}) AS driver_name,
                COALESCE({aq_phone_expr}, {ds_phone_expr}) AS phone,
                NULL::text AS park_id,
                COALESCE(ds.lifecycle_state, 'UNKNOWN') AS lifecycle,
                ds.performance_state,
                ds.retention_state,
                ds.historical_band,
                {segment_expr} AS segment,
                {sub_segment_expr} AS sub_segment,
                COALESCE(pr.program_code,
                    CASE
                        WHEN ds.lifecycle_state = 'ACTIVE' THEN 'ACTIVE_GROWTH'
                        WHEN ds.lifecycle_state = 'AT_RISK' THEN 'CHURN_PREVENTION'
                        WHEN ds.lifecycle_state = 'CHURNED' THEN 'HIGH_VALUE_RECOVERY'
                        WHEN ds.new_driver_flag THEN 'NEW_DRIVER_ONBOARDING'
                        ELSE NULL
                    END
                ) AS program_code,
                pr.priority AS program_priority,
                pr.eligibility_reason,
                (pr.program_code IS NOT NULL) AS is_in_program,
                {rna_band_expr} AS rna_priority_band,
                {rna_score_expr} AS rna_score,
                {contactable_expr} AS contactable,
                {cancelled_expr} AS cancelled_signal,
                {rna_valtier_expr} AS rna_value_tier,
                {rna_momentum_expr} AS rna_momentum,
                {mov_type_expr} AS movement_type,
                {mov_from_expr} AS movement_from,
                {mov_to_expr} AS movement_to,
                {mov_trigger_expr} AS movement_trigger,
                {contact_at_expr} AS last_contact_at,
                {contact_disp_expr} AS last_contact_disposition,
                {contact_agent_expr} AS last_contact_agent,
                {contact_attempts_expr} AS contact_attempts,
                {campaign_expr} AS assigned_campaign_id,
                {queue_status_expr} AS queue_status,
                NULL::text AS opportunity_type,
                {rna_trips_7d_expr}::integer AS trips_7d,
                {trips_30d_expr}::integer AS trips_30d,
                {trips_anchor_expr}::integer AS trips_since_anchor,
                ds.first_trip_at,
                ds.last_trip_at,
                {rna_days_since_expr}::integer AS days_since_last_trip,
                CASE
                    WHEN ds.declining_flag THEN 'DECLINING'
                    WHEN ds.new_driver_flag THEN 'GROWING'
                    WHEN COALESCE(ds.completed_orders_week, 0) > 0 THEN 'STABLE'
                    WHEN ds.churn_risk_flag THEN 'INACTIVE'
                    ELSE 'UNKNOWN'
                END AS activity_trend,
                COALESCE(ds.new_driver_flag, FALSE),
                COALESCE(ds.recoverable_flag, FALSE),
                COALESCE(ds.declining_flag, FALSE),
                COALESCE(ds.churn_risk_flag, FALSE),
                {imp_status_expr} AS impact_status,
                {imp_baseline_expr}::integer AS baseline_trips,
                {imp_post_expr}::integer AS post_contact_trips,
                ({imp_post_expr}::integer - {imp_baseline_expr}::integer) AS trips_delta_after_contact,
                %(data_quality)s,
                NOW()
            FROM {TABLE_DS} ds
            LEFT JOIN {TABLE_PR} pr
                ON ds.driver_profile_id = pr.driver_profile_id
                AND pr.eligibility_date = %(target_date)s
            {rna_join_clause}
            {lf_join_clause}
            LEFT JOIN {TABLE_DS} prev
                ON ds.driver_profile_id = prev.driver_profile_id
                AND prev.snapshot_date = %(prev_date)s
            {tax_join_clause}
            {mov_join_clause}
            {lc_join_clause}
            {aq_join_clause}
            {imp_join_clause}
            WHERE ds.snapshot_date = %(target_date)s
            ORDER BY ds.driver_profile_id, pr.priority NULLS LAST
            )
            INSERT INTO {TABLE_FACT} (
                target_date, driver_profile_id,
                driver_name, phone, park_id,
                lifecycle, performance_state, retention_state, historical_band,
                segment, sub_segment,
                program_code, program_priority, eligibility_reason, is_in_program,
                rna_priority_band, rna_score, contactable, cancelled_signal,
                rna_value_tier, rna_momentum,
                movement_type, movement_from, movement_to, movement_trigger,
                last_contact_at, last_contact_disposition, last_contact_agent, contact_attempts,
                assigned_campaign_id, queue_status, opportunity_type,
                trips_7d, trips_30d, trips_since_anchor,
                first_trip_at, last_trip_at, days_since_last_trip,
                activity_trend, new_driver_flag, recoverable_flag, declining_flag, churn_risk_flag,
                impact_status, baseline_trips, post_contact_trips, trips_delta_after_contact,
                data_quality, refreshed_at
            )
            SELECT * FROM driver_base
            ON CONFLICT (target_date, driver_profile_id) DO UPDATE SET
                driver_name = EXCLUDED.driver_name,
                phone = EXCLUDED.phone,
                park_id = EXCLUDED.park_id,
                lifecycle = EXCLUDED.lifecycle,
                performance_state = EXCLUDED.performance_state,
                retention_state = EXCLUDED.retention_state,
                historical_band = EXCLUDED.historical_band,
                segment = EXCLUDED.segment,
                sub_segment = EXCLUDED.sub_segment,
                program_code = EXCLUDED.program_code,
                program_priority = EXCLUDED.program_priority,
                eligibility_reason = EXCLUDED.eligibility_reason,
                is_in_program = EXCLUDED.is_in_program,
                rna_priority_band = EXCLUDED.rna_priority_band,
                rna_score = EXCLUDED.rna_score,
                contactable = EXCLUDED.contactable,
                cancelled_signal = EXCLUDED.cancelled_signal,
                rna_value_tier = EXCLUDED.rna_value_tier,
                rna_momentum = EXCLUDED.rna_momentum,
                movement_type = EXCLUDED.movement_type,
                movement_from = EXCLUDED.movement_from,
                movement_to = EXCLUDED.movement_to,
                movement_trigger = EXCLUDED.movement_trigger,
                last_contact_at = EXCLUDED.last_contact_at,
                last_contact_disposition = EXCLUDED.last_contact_disposition,
                last_contact_agent = EXCLUDED.last_contact_agent,
                contact_attempts = EXCLUDED.contact_attempts,
                assigned_campaign_id = EXCLUDED.assigned_campaign_id,
                queue_status = EXCLUDED.queue_status,
                opportunity_type = EXCLUDED.opportunity_type,
                trips_7d = EXCLUDED.trips_7d,
                trips_30d = EXCLUDED.trips_30d,
                trips_since_anchor = EXCLUDED.trips_since_anchor,
                first_trip_at = EXCLUDED.first_trip_at,
                last_trip_at = EXCLUDED.last_trip_at,
                days_since_last_trip = EXCLUDED.days_since_last_trip,
                activity_trend = EXCLUDED.activity_trend,
                new_driver_flag = EXCLUDED.new_driver_flag,
                recoverable_flag = EXCLUDED.recoverable_flag,
                declining_flag = EXCLUDED.declining_flag,
                churn_risk_flag = EXCLUDED.churn_risk_flag,
                impact_status = EXCLUDED.impact_status,
                baseline_trips = EXCLUDED.baseline_trips,
                post_contact_trips = EXCLUDED.post_contact_trips,
                trips_delta_after_contact = EXCLUDED.trips_delta_after_contact,
                data_quality = EXCLUDED.data_quality,
                refreshed_at = EXCLUDED.refreshed_at
        """

        try:
            cur.execute(upsert_sql, {
                "target_date": target_date,
                "prev_date": prev_date,
                "data_quality": data_quality,
            })
            rowcount = cur.rowcount
            conn.commit()
            result["rows_upserted"] = rowcount
            result["data_quality"] = data_quality
            result["status"] = "SUCCESS"
            logger.info(
                "driver_explorer_fact: %s rows upserted for %s, quality=%s, sources=%d",
                rowcount, target_date, data_quality, len(result["sources_available"]),
            )
        except Exception as exc:
            conn.rollback()
            result["status"] = "FAILED"
            result["errors"].append(str(exc)[:500])
            logger.error("driver_explorer_fact build failed for %s: %s", target_date, exc)

    return result


def get_explorer_fact_stats(target_date: Optional[str] = None) -> Dict[str, Any]:
    stats = {
        "table": TABLE_FACT,
        "total_rows": 0,
        "distinct_drivers": 0,
        "min_date": None,
        "max_date": None,
        "resolved_target_date": None,
        "by_lifecycle": {},
        "by_program": {},
        "by_rna_band": {},
        "by_data_quality": {},
    }
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Resolve target_date: default to MAX(target_date) to avoid multi-date aggregation
        if target_date is None:
            cur.execute(f"SELECT MAX(target_date) AS mx FROM {TABLE_FACT}")
            row = cur.fetchone()
            if row and row.get("mx"):
                target_date = str(row["mx"])
        stats["resolved_target_date"] = target_date

        cur.execute(
            f"SELECT COUNT(*) AS c, COUNT(DISTINCT driver_profile_id) AS d, "
            f"MIN(target_date) AS mn, MAX(target_date) AS mx FROM {TABLE_FACT}"
        )
        row = cur.fetchone()
        if row:
            stats["total_rows"] = row["c"] or 0
            stats["distinct_drivers"] = row["d"] or 0
            stats["min_date"] = str(row["mn"]) if row["mn"] else None
            stats["max_date"] = str(row["mx"]) if row["mx"] else None

        date_filter = "WHERE target_date = %(d)s" if target_date else ""
        params = {"d": target_date} if target_date else {}

        if date_filter:
            for col, bucket in [
                ("lifecycle", "by_lifecycle"),
                ("program_code", "by_program"),
                ("rna_priority_band", "by_rna_band"),
                ("data_quality", "by_data_quality"),
            ]:
                cur.execute(
                    f"SELECT {col}, COUNT(*) AS c FROM {TABLE_FACT} {date_filter} GROUP BY {col} ORDER BY c DESC",
                    params,
                )
                for r in cur.fetchall():
                    stats[bucket][r[col] or "NULL"] = r["c"]

    return stats
