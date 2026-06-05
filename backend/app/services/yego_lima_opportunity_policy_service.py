"""
YEGO Lima Growth — Opportunity Policy Governance Service (Fase 5B.1).

Policy layer on top of program_eligibility and daily_opportunity_list.
Converts ELIGIBLE universe into ACTIONABLE TODAY list.

Principle: ELEGIBLE != ACCIONABLE
"""

from __future__ import annotations
import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_POLICY = "growth.yango_lima_opportunity_policy_config"
TABLE_PRIORITIZED = "growth.yango_lima_prioritized_opportunity_daily"
TABLE_STATE = "growth.yango_lima_driver_state_snapshot"
TABLE_PROGRAM = "growth.yango_lima_program_eligibility_daily"
TABLE_OPPORTUNITY = "growth.yango_lima_daily_opportunity_list"
TABLE_HIST_W = "growth.yango_lima_driver_history_weekly"

PROGRAM_PRIORITY = [
    "PROGRAM_HIGH_VALUE_RECOVERY",
    "PROGRAM_CHURN_PREVENTION",
    "PROGRAM_14_90",
    "PROGRAM_ACTIVE_GROWTH",
]

DEFAULT_POLICY_NAME = "default_opportunity_policy_v1"


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def _safe_float(val, default=0.0):
    if val is None: return default
    try: return float(val)
    except: return float(default)


def _now_utc():
    return datetime.now(timezone.utc)


# ==============================================================
# POLICY MANAGEMENT
# ==============================================================

def get_active_policy() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM {TABLE_POLICY} WHERE is_active = true LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {"active": False, "policy": None,
                    "message": "No active policy. Call create_default_policy_if_missing() then activate_policy()."}
        return {"active": True, "policy": _policy_to_dict(row)}


def create_default_policy_if_missing() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT policy_id FROM {TABLE_POLICY} WHERE policy_name = %(n)s",
                    {"n": DEFAULT_POLICY_NAME})
        existing = cur.fetchone()
        if existing:
            return {"policy_id": str(existing["policy_id"]),
                    "message": "Default policy already exists", "created": False}

        cur.execute(f"""
            INSERT INTO {TABLE_POLICY} (
                policy_name, is_active, effective_from,
                weekly_trips_target, critical_threshold, low_threshold, medium_threshold,
                top_performer_threshold, top_performer_percentile,
                daily_action_capacity,
                high_value_min_weekly_trips, high_value_inactive_days, high_value_critical_inactive_days,
                churn_requires_real_decline, missing_data_is_churn,
                exclude_top_performers_from_active_growth,
                allow_multi_program_eligibility,
                enforce_single_actionable_program,
                created_by, notes
            ) VALUES (
                %(n)s, false, CURRENT_DATE,
                100, 50, 70, 100,
                100, 0.80,
                500,
                80, 1, 3,
                true, false,
                true,
                true,
                true,
                'system', 'Default policy created automatically. Activate to use.'
            )
            RETURNING policy_id
        """, {"n": DEFAULT_POLICY_NAME})
        pid = str(cur.fetchone()["policy_id"])
    return {"policy_id": pid, "message": "Default policy created", "created": True}


def activate_policy(policy_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE {TABLE_POLICY} SET is_active = false WHERE is_active = true")
        cur.execute(f"UPDATE {TABLE_POLICY} SET is_active = true, updated_at = now() WHERE policy_id = %(pid)s",
                    {"pid": policy_id})
        if cur.rowcount == 0:
            return {"error": "Policy not found", "policy_id": policy_id}
    return {"policy_id": policy_id, "message": "Policy activated", "active": True}


def _policy_to_dict(row) -> Dict[str, Any]:
    return {
        "policy_id": str(row["policy_id"]),
        "policy_name": row["policy_name"],
        "is_active": row["is_active"],
        "effective_from": str(row["effective_from"]),
        "effective_to": str(row["effective_to"]) if row.get("effective_to") else None,
        "weekly_trips_target": _safe_int(row.get("weekly_trips_target"), 100),
        "critical_threshold": _safe_int(row.get("critical_threshold"), 50),
        "low_threshold": _safe_int(row.get("low_threshold"), 70),
        "medium_threshold": _safe_int(row.get("medium_threshold"), 100),
        "top_performer_threshold": _safe_int(row.get("top_performer_threshold"), 100),
        "top_performer_percentile": _safe_float(row.get("top_performer_percentile"), 0.80),
        "daily_action_capacity": _safe_int(row.get("daily_action_capacity"), 500),
        "max_per_program": _safe_int(row.get("max_per_program")) if row.get("max_per_program") else None,
        "high_value_min_weekly_trips": _safe_int(row.get("high_value_min_weekly_trips"), 80),
        "high_value_inactive_days": _safe_int(row.get("high_value_inactive_days"), 1),
        "high_value_critical_inactive_days": _safe_int(row.get("high_value_critical_inactive_days"), 3),
        "churn_requires_real_decline": row.get("churn_requires_real_decline", True),
        "missing_data_is_churn": row.get("missing_data_is_churn", False),
        "active_growth_max_inactive_days": _safe_int(row.get("active_growth_max_inactive_days"), 30),
        "high_value_recovery_max_inactive_days": _safe_int(row.get("high_value_recovery_max_inactive_days"), 14),
        "dormant_recovery_min_inactive_days": _safe_int(row.get("dormant_recovery_min_inactive_days"), 30),
        "dormant_recovery_enabled": row.get("dormant_recovery_enabled", False),
        "low_cost_reactivation_min_inactive_days": _safe_int(row.get("low_cost_reactivation_min_inactive_days"), 90),
        "require_recent_signal_for_active_growth": row.get("require_recent_signal_for_active_growth", True),
        "require_decline_evidence_for_churn": row.get("require_decline_evidence_for_churn", True),
        "exclude_top_performers_from_active_growth": row.get("exclude_top_performers_from_active_growth", True),
        "allow_multi_program_eligibility": row.get("allow_multi_program_eligibility", True),
        "enforce_single_actionable_program": row.get("enforce_single_actionable_program", True),
    }


# ==============================================================
# BUILD PRIORITIZED OPPORTUNITIES
# ==============================================================

def build_prioritized_opportunities(opportunity_date: str,
                                   max_drivers: Optional[int] = None) -> Dict[str, Any]:
    policy = get_active_policy()
    if not policy["active"]:
        return {"error": "No active policy. Activate one first."}
    p = policy["policy"]
    pid = p["policy_id"]
    t0 = __import__("time").perf_counter()

    # Policy params for SQL
    target = p["weekly_trips_target"]
    crit = p["critical_threshold"]
    low_t = p["low_threshold"]
    med_t = p["medium_threshold"]
    top_t = p["top_performer_threshold"]
    cap = p["daily_action_capacity"]
    excl_top = p["exclude_top_performers_from_active_growth"]
    miss_churn = p["missing_data_is_churn"]
    hv_min = p["high_value_min_weekly_trips"]
    churn_real = p["churn_requires_real_decline"]
    ag_max_inactive = p.get("active_growth_max_inactive_days", 30)
    hv_max_inactive = p.get("high_value_recovery_max_inactive_days", 14)
    dormant_min = p.get("dormant_recovery_min_inactive_days", 30)
    dormant_enabled = p.get("dormant_recovery_enabled", False)
    require_recent = p.get("require_recent_signal_for_active_growth", True)
    require_decline_ev = p.get("require_decline_evidence_for_churn", True)

    with get_db() as conn:
        cur = conn.cursor()

        # 0. Wipe existing data for this date
        cur.execute(f"DELETE FROM {TABLE_PRIORITIZED} WHERE opportunity_date = %(clean_date)s",
                    {"clean_date": opportunity_date})

        # 1. Single set-based CTE: enrich, score, rank, cap
        limit_clause = f"LIMIT {max_drivers}" if max_drivers else ""

        cur.execute(f"""
            WITH
            raw_opps AS (
                SELECT driver_profile_id, opportunity_type
                FROM {TABLE_OPPORTUNITY}
                WHERE opportunity_date = %(d)s
                {limit_clause}
            ),
            drv_state AS (
                SELECT driver_profile_id, lifecycle_state, performance_state, retention_state
                FROM {TABLE_STATE}
                WHERE snapshot_date = %(d)s
            ),
            drv_programs AS (
                SELECT driver_profile_id, program_code
                FROM {TABLE_PROGRAM}
                WHERE eligibility_date = %(d)s
            ),
            drv_eligible AS (
                SELECT r.driver_profile_id, r.opportunity_type,
                       array_agg(p.program_code) as eligible_programs
                FROM raw_opps r
                JOIN drv_programs p ON p.driver_profile_id = r.driver_profile_id
                GROUP BY 1, 2
            ),
            drv_weekly AS (
                SELECT driver_profile_id,
                       COALESCE(SUM(completed_orders_week) FILTER (
                           WHERE week_start_date = %(wcurr)s), 0) as orders_week,
                       COALESCE(MAX(best_week_12w), 0) as best_week_12w
                FROM {TABLE_HIST_W}
                WHERE week_start_date >= %(w12)s
                  AND driver_profile_id IN (SELECT driver_profile_id FROM raw_opps)
                GROUP BY 1
            ),
            drv_recency AS (
                SELECT driver_profile_id, MAX(date) as last_trip_date
                FROM {TABLE_HIST_W.replace('_weekly', '_daily')}
                WHERE completed_orders > 0
                  AND driver_profile_id IN (SELECT driver_profile_id FROM raw_opps)
                GROUP BY 1
            ),
            enriched AS (
                SELECT
                    e.driver_profile_id,
                    e.opportunity_type,
                    e.eligible_programs,
                    s.lifecycle_state,
                    s.performance_state,
                    s.retention_state,
                    COALESCE(w.orders_week, 0) as completed_orders_week,
                    COALESCE(w.best_week_12w, 0) as best_week_12w,
                    r.last_trip_date,
                    %(target)s as weekly_target,
                    %(top_t)s as top_threshold,
                    {str(excl_top).lower()} as exclude_top,
                    {str(miss_churn).lower()} as missing_is_churn,
                    %(hv_min)s as hv_min_trips,
                    {str(churn_real).lower()} as churn_real_decline,
                    {ag_max_inactive} as ag_max_inactive,
                    {hv_max_inactive} as hv_max_inactive,
                    {dormant_min} as dormant_min,
                    {str(dormant_enabled).lower()} as dormant_enabled,
                    {str(require_recent).lower()} as require_recent,
                    {str(require_decline_ev).lower()} as require_decline_ev
                FROM drv_eligible e
                JOIN drv_state s ON s.driver_profile_id = e.driver_profile_id
                LEFT JOIN drv_weekly w ON w.driver_profile_id = e.driver_profile_id
                LEFT JOIN drv_recency r ON r.driver_profile_id = e.driver_profile_id
            ),
            classified AS (
                SELECT
                    *,
                    -- Days since last trip (null = never active)
                    COALESCE(CURRENT_DATE - last_trip_date::date, 999) as last_trip_age_days,
                    -- Selected program via CASE priority with recency
                    CASE
                        -- HIGH_VALUE_RECOVERY: top historical performer, recently inactive
                        WHEN best_week_12w >= hv_min_trips
                             AND completed_orders_week = 0
                             AND last_trip_date IS NOT NULL
                             AND (CURRENT_DATE - last_trip_date::date) BETWEEN 1 AND hv_max_inactive
                        THEN 'PROGRAM_HIGH_VALUE_RECOVERY'
                        -- CHURN: evidence-based decline required
                        WHEN 'PROGRAM_CHURN_PREVENTION' = ANY(eligible_programs)
                             AND (NOT require_decline_ev
                                  OR completed_orders_week > 0
                                  OR missing_is_churn)
                        THEN 'PROGRAM_CHURN_PREVENTION'
                        -- 14_90: new/reactivated drivers
                        WHEN 'PROGRAM_14_90' = ANY(eligible_programs)
                        THEN 'PROGRAM_14_90'
                        -- ACTIVE_GROWTH: must have recent signal if required
                        WHEN 'PROGRAM_ACTIVE_GROWTH' = ANY(eligible_programs)
                             AND NOT (exclude_top AND completed_orders_week >= top_threshold)
                             AND (
                                 NOT require_recent
                                 OR (
                                     last_trip_date IS NOT NULL
                                     AND (CURRENT_DATE - last_trip_date::date) <= ag_max_inactive
                                 )
                             )
                        THEN 'PROGRAM_ACTIVE_GROWTH'
                        ELSE NULL
                    END as selected_program_code,
                    -- Exclusion reason
                    CASE
                        WHEN best_week_12w >= hv_min_trips
                             AND completed_orders_week = 0
                             AND last_trip_date IS NOT NULL
                             AND (CURRENT_DATE - last_trip_date::date) BETWEEN 1 AND hv_max_inactive
                        THEN NULL
                        WHEN 'PROGRAM_CHURN_PREVENTION' = ANY(eligible_programs)
                             AND require_decline_ev
                             AND completed_orders_week = 0
                             AND NOT missing_is_churn
                        THEN 'MISSING_DATA_NOT_CHURN'
                        WHEN 'PROGRAM_ACTIVE_GROWTH' = ANY(eligible_programs)
                             AND exclude_top
                             AND completed_orders_week >= top_threshold
                        THEN 'TOP_PERFORMER_EXCLUDED'
                        WHEN 'PROGRAM_ACTIVE_GROWTH' = ANY(eligible_programs)
                             AND require_recent
                             AND (
                                 last_trip_date IS NULL
                                 OR (CURRENT_DATE - last_trip_date::date) > ag_max_inactive
                             )
                        THEN 'STALE_DRIVER_NOT_ACTIVE_GROWTH'
                        WHEN last_trip_date IS NOT NULL
                             AND (CURRENT_DATE - last_trip_date::date) >= dormant_min
                             AND NOT dormant_enabled
                        THEN 'DORMANT_LOW_PRIORITY_CHANNEL'
                        ELSE NULL
                    END as exclusion_reason,
                    -- Productivity bucket
                    CASE
                        WHEN completed_orders_week < %(crit)s THEN 'Critical'
                        WHEN completed_orders_week < %(low_t)s THEN 'Low'
                        WHEN completed_orders_week < %(med_t)s THEN 'Medium'
                        WHEN completed_orders_week < %(target)s THEN 'NearTarget'
                        ELSE 'Target'
                    END as productivity_bucket,
                    -- Value tier
                    CASE
                        WHEN best_week_12w >= 100 THEN 'Platinum'
                        WHEN best_week_12w >= 80 THEN 'Gold'
                        WHEN best_week_12w >= 50 THEN 'Silver'
                        ELSE 'Bronze'
                    END as value_tier,
                    -- Risk tier
                    CASE
                        WHEN retention_state = 'CHURN_RISK' THEN 'High'
                        WHEN retention_state = 'AT_RISK' THEN 'Medium'
                        ELSE 'Low'
                    END as risk_tier,
                    -- Distance to target
                    GREATEST(0, %(target)s - completed_orders_week) as distance_to_target,
                    -- Impact score: gap_weighted + potential
                    LEAST(1.0,
                        GREATEST(0, %(target)s - completed_orders_week)::numeric
                            / GREATEST(1, %(target)s) * 0.6
                        + LEAST(1.0, best_week_12w::numeric / GREATEST(1, %(target)s)) * 0.4
                    ) as impact_score,
                    -- Urgency score
                    LEAST(1.0,
                        CASE WHEN retention_state = 'CHURN_RISK' THEN 0.4
                             WHEN retention_state = 'AT_RISK' THEN 0.3
                             ELSE 0.1
                        END
                        + CASE WHEN completed_orders_week = 0 THEN 0.2 ELSE 0 END
                    ) as urgency_score,
                    -- Probability score
                    LEAST(1.0,
                        0.5
                        + CASE WHEN best_week_12w >= 100 THEN 0.3
                               WHEN best_week_12w >= 50 THEN 0.15
                               ELSE 0 END
                        + CASE WHEN completed_orders_week > 0 THEN 0.2 ELSE 0 END
                        + CASE WHEN lifecycle_state = 'ESTABLISHED' THEN 0.1 ELSE 0 END
                    ) as probability_score
                FROM enriched
            ),
            scored AS (
                SELECT *,
                       ROUND(
                           COALESCE(impact_score * 0.4, 0) + COALESCE(urgency_score * 0.3, 0) + COALESCE(probability_score * 0.3, 0)
                           + CASE WHEN selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY' THEN 200
                                  WHEN selected_program_code = 'PROGRAM_CHURN_PREVENTION' THEN 100
                                  WHEN selected_program_code = 'PROGRAM_14_90' THEN 50
                                  WHEN selected_program_code = 'PROGRAM_ACTIVE_GROWTH' THEN 0
                                  ELSE -999 END,
                           4
                       ) as opportunity_score
                FROM classified
            ),
            ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY driver_profile_id ORDER BY opportunity_score DESC
                       ) as dedup_rank
                FROM scored
                WHERE selected_program_code IS NOT NULL
            ),
            deduped AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           ORDER BY opportunity_score DESC, urgency_score DESC, impact_score DESC
                       ) as final_rank
                FROM ranked WHERE dedup_rank = 1
            )
            INSERT INTO {TABLE_PRIORITIZED} (
                opportunity_date, driver_profile_id, policy_id,
                selected_program_code, eligible_programs, opportunity_type,
                lifecycle_state, performance_state, retention_state,
                completed_orders_7d, completed_orders_30d, completed_orders_week,
                supply_hours_7d, supply_hours_30d,
                distance_to_target, historical_avg_orders_12w, best_week_12w,
                productivity_bucket, value_tier, risk_tier,
                opportunity_score, impact_score, urgency_score, probability_score,
                final_rank,
                is_actionable_today, action_capacity_rank,
                exclusion_reason, management_status, generated_at
            )
            SELECT
                %(d)s::date, driver_profile_id, %(pid)s::uuid,
                selected_program_code, eligible_programs, opportunity_type,
                lifecycle_state, performance_state, retention_state,
                0, 0, completed_orders_week,
                0, 0,
                distance_to_target, 0, best_week_12w,
                productivity_bucket, value_tier, risk_tier,
                opportunity_score, impact_score, urgency_score, probability_score,
                final_rank,
                final_rank <= %(cap)s
                AND selected_program_code IS NOT NULL
                AND exclusion_reason IS NULL as is_actionable_today,
                CASE WHEN final_rank <= %(cap)s THEN final_rank ELSE NULL END as action_capacity_rank,
                CASE WHEN final_rank > %(cap)s THEN 'OUTSIDE_DAILY_CAPACITY' ELSE exclusion_reason END,
                'PENDING_ACTION', now()
            FROM deduped
            ON CONFLICT (opportunity_date, driver_profile_id) DO UPDATE SET
                policy_id = EXCLUDED.policy_id,
                selected_program_code = EXCLUDED.selected_program_code,
                eligible_programs = EXCLUDED.eligible_programs,
                opportunity_type = EXCLUDED.opportunity_type,
                lifecycle_state = EXCLUDED.lifecycle_state,
                performance_state = EXCLUDED.performance_state,
                retention_state = EXCLUDED.retention_state,
                completed_orders_7d = EXCLUDED.completed_orders_7d,
                completed_orders_30d = EXCLUDED.completed_orders_30d,
                completed_orders_week = EXCLUDED.completed_orders_week,
                distance_to_target = EXCLUDED.distance_to_target,
                best_week_12w = EXCLUDED.best_week_12w,
                productivity_bucket = EXCLUDED.productivity_bucket,
                value_tier = EXCLUDED.value_tier,
                risk_tier = EXCLUDED.risk_tier,
                opportunity_score = EXCLUDED.opportunity_score,
                impact_score = EXCLUDED.impact_score,
                urgency_score = EXCLUDED.urgency_score,
                probability_score = EXCLUDED.probability_score,
                final_rank = EXCLUDED.final_rank,
                is_actionable_today = EXCLUDED.is_actionable_today,
                action_capacity_rank = EXCLUDED.action_capacity_rank,
                exclusion_reason = EXCLUDED.exclusion_reason,
                generated_at = now()
        """, {
            "d": opportunity_date,
            "pid": pid,
            "wcurr": "2026-05-25",
            "w12": (__import__("datetime").date.fromisoformat(opportunity_date) - __import__("datetime").timedelta(days=84)).isoformat(),
            "target": target, "crit": crit, "low_t": low_t, "med_t": med_t,
            "top_t": top_t, "cap": cap, "hv_min": hv_min,
        })

        inserted = cur.rowcount

        # 2. Query stats
        cur2 = conn.cursor(cursor_factory=RealDictCursor)
        cur2.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END) as actionable,
                SUM(CASE WHEN NOT is_actionable_today THEN 1 ELSE 0 END) as excluded,
                SUM(CASE WHEN exclusion_reason = 'TOP_PERFORMER_EXCLUDED' THEN 1 ELSE 0 END) as top_excluded,
                SUM(CASE WHEN selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY' THEN 1 ELSE 0 END) as hv_count
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s
        """, {"d": opportunity_date})
        stats = cur2.fetchone()

        cur2.execute(f"""
            SELECT selected_program_code, COUNT(*) as n
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s
            GROUP BY 1 ORDER BY 2 DESC
        """, {"d": opportunity_date})
        prog_dist = {r["selected_program_code"]: r["n"] for r in cur2.fetchall()}

        cur2.execute(f"""
            SELECT productivity_bucket, COUNT(*) as n
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s
            GROUP BY 1 ORDER BY 1
        """, {"d": opportunity_date})
        bucket_dist = {r["productivity_bucket"]: r["n"] for r in cur2.fetchall()}

        elapsed = round(__import__("time").perf_counter() - t0, 2)

    logger.info("Built prioritized: %d inserted, %d actionable in %.1fs",
                inserted, stats["actionable"] if stats else 0, elapsed)

    return {
        "opportunity_date": opportunity_date,
        "policy_id": pid,
        "total_inserted": inserted,
        "total_prioritized": stats["total"] if stats else 0,
        "actionable_today": stats["actionable"] if stats else 0,
        "outside_capacity": stats["excluded"] if stats else 0,
        "top_performer_excluded": stats["top_excluded"] if stats else 0,
        "high_value_recovery_count": stats["hv_count"] if stats else 0,
        "program_distribution": prog_dist,
        "bucket_distribution": bucket_dist,
        "elapsed_seconds": elapsed,
    }


# ==============================================================
# QUERY
# ==============================================================

def get_prioritized_opportunities(opportunity_date: str,
                                   program_code: Optional[str] = None,
                                   is_actionable_today: Optional[bool] = None,
                                   productivity_bucket: Optional[str] = None,
                                   value_tier: Optional[str] = None,
                                   risk_tier: Optional[str] = None,
                                   limit: int = 200) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = ["opportunity_date = %(d)s"]
        params = {"d": opportunity_date, "lim": min(limit, 1000)}

        if program_code:
            conditions.append("selected_program_code = %(pc)s")
            params["pc"] = program_code
        if is_actionable_today is not None:
            conditions.append("is_actionable_today = %(ia)s")
            params["ia"] = is_actionable_today
        if productivity_bucket:
            conditions.append("productivity_bucket = %(pb)s")
            params["pb"] = productivity_bucket
        if value_tier:
            conditions.append("value_tier = %(vt)s")
            params["vt"] = value_tier
        if risk_tier:
            conditions.append("risk_tier = %(rt)s")
            params["rt"] = risk_tier

        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT * FROM {TABLE_PRIORITIZED}
            WHERE {where}
            ORDER BY final_rank ASC
            LIMIT %(lim)s
        """, params)
        rows = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) as total FROM {TABLE_PRIORITIZED} WHERE {where}", params)
        total = cur.fetchone()["total"]

    return {
        "opportunity_date": opportunity_date,
        "total": total,
        "returned": len(rows),
        "opportunities": [_prioritized_to_dict(r) for r in rows],
    }


def _prioritized_to_dict(r) -> Dict[str, Any]:
    return {
        "driver_profile_id": r["driver_profile_id"][:12] + "...",
        "selected_program_code": r["selected_program_code"],
        "eligible_programs": r.get("eligible_programs"),
        "lifecycle_state": r.get("lifecycle_state"),
        "performance_state": r.get("performance_state"),
        "retention_state": r.get("retention_state"),
        "completed_orders_7d": _safe_int(r.get("completed_orders_7d")),
        "completed_orders_30d": _safe_int(r.get("completed_orders_30d")),
        "completed_orders_week": _safe_int(r.get("completed_orders_week")),
        "productivity_bucket": r.get("productivity_bucket"),
        "value_tier": r.get("value_tier"),
        "risk_tier": r.get("risk_tier"),
        "opportunity_score": _safe_float(r.get("opportunity_score")),
        "final_rank": _safe_int(r.get("final_rank")),
        "is_actionable_today": r.get("is_actionable_today"),
        "exclusion_reason": r.get("exclusion_reason"),
    }


def close_unmanaged_prioritized_opportunities(opportunity_date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_PRIORITIZED}
            SET management_status = 'NO_ACTION', closed_at = now()
            WHERE opportunity_date = %(d)s
              AND management_status = 'PENDING_ACTION'
        """, {"d": opportunity_date})
        closed = cur.rowcount
    return {"opportunity_date": opportunity_date, "closed": closed}


def get_policy_quality_summary(opportunity_date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END) as actionable,
                SUM(CASE WHEN NOT is_actionable_today THEN 1 ELSE 0 END) as excluded,
                SUM(CASE WHEN selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY' THEN 1 ELSE 0 END) as high_value
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s
        """, {"d": opportunity_date})
        r = cur.fetchone()

        cur.execute(f"""
            SELECT selected_program_code, COUNT(*) as n,
                   SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END) as actionable
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s
            GROUP BY 1 ORDER BY 2 DESC
        """, {"d": opportunity_date})
        by_program = [dict(row) for row in cur.fetchall()]

        cur.execute(f"""
            SELECT exclusion_reason, COUNT(*) as n
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s AND exclusion_reason IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC
        """, {"d": opportunity_date})
        exclusions = [dict(row) for row in cur.fetchall()]

    return {
        "opportunity_date": opportunity_date,
        "total_prioritized": _safe_int(r["total"]) if r else 0,
        "actionable_today": _safe_int(r["actionable"]) if r else 0,
        "excluded": _safe_int(r["excluded"]) if r else 0,
        "high_value_recovery": _safe_int(r["high_value"]) if r else 0,
        "by_program": by_program,
        "exclusion_reasons": exclusions,
    }


def compare_policy_vs_raw_opportunities(opportunity_date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT COUNT(*) as n FROM {TABLE_OPPORTUNITY} WHERE opportunity_date = %(d)s",
                    {"d": opportunity_date})
        raw_total = cur.fetchone()["n"]

        cur.execute(f"""
            SELECT opportunity_type, COUNT(*) as n
            FROM {TABLE_OPPORTUNITY}
            WHERE opportunity_date = %(d)s
            GROUP BY 1 ORDER BY 2 DESC
        """, {"d": opportunity_date})
        raw_by_program = {}
        for r in cur.fetchall():
            prog = r["opportunity_type"].replace("OPPORTUNITY_", "PROGRAM_")
            raw_by_program[prog] = r["n"]

        cur.execute(f"""
            SELECT selected_program_code, COUNT(*) as n,
                   SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END) as actionable
            FROM {TABLE_PRIORITIZED}
            WHERE opportunity_date = %(d)s
            GROUP BY 1 ORDER BY 2 DESC
        """, {"d": opportunity_date})
        prio_by_program = {r["selected_program_code"]: {"total": r["n"], "actionable": r["actionable"]}
                           for r in cur.fetchall()}

        cur.execute(f"SELECT COUNT(*) as n FROM {TABLE_PRIORITIZED} WHERE opportunity_date = %(d)s",
                    {"d": opportunity_date})
        prio_total = cur.fetchone()["n"]

    comparison = {}
    for prog in ["PROGRAM_ACTIVE_GROWTH", "PROGRAM_CHURN_PREVENTION", "PROGRAM_14_90", "PROGRAM_HIGH_VALUE_RECOVERY"]:
        raw = raw_by_program.get(prog, 0)
        prio = prio_by_program.get(prog, {})
        comparison[prog] = {
            "raw_opportunities": raw,
            "prioritized_total": prio.get("total", 0),
            "actionable_today": prio.get("actionable", 0),
            "reduction_pct": round((1 - prio.get("total", 0) / max(raw, 1)) * 100, 1) if raw > 0 else 0,
        }

    return {
        "opportunity_date": opportunity_date,
        "raw_total_opportunities": raw_total,
        "prioritized_total": prio_total,
        "overall_reduction_pct": round((1 - prio_total / max(raw_total, 1)) * 100, 1),
        "by_program": comparison,
    }
