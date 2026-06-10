"""
YEGO Lima Growth — Operational Summary Service (LG-C1.4-P0).

Single endpoint that returns the full pipeline truth:
  universe_total → eligible_total → prioritized_total → actionable_today
  → capacity_total → queue → exported
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.services.freshness_service import compute_freshness
from app.services.lima_growth_explainability_service import explain_kpi

logger = logging.getLogger(__name__)


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def get_operational_summary(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Universe total: distinct drivers in state snapshot
        cur.execute(
            "SELECT COUNT(*) as cnt FROM growth.yango_lima_driver_state_snapshot "
            "WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot)"
        )
        universe_total = _safe_int(cur.fetchone()["cnt"])

        # 2. Eligible total: program_eligibility_daily for this date
        cur.execute(
            "SELECT COUNT(DISTINCT driver_profile_id) as cnt "
            "FROM growth.yango_lima_program_eligibility_daily "
            "WHERE eligibility_date = %(d)s", {"d": date}
        )
        eligible_total = _safe_int(cur.fetchone()["cnt"])

        # 3. Prioritized + actionable from policy table
        cur.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END) as actionable "
            "FROM growth.yango_lima_prioritized_opportunity_daily "
            "WHERE opportunity_date = %(d)s", {"d": date}
        )
        row = cur.fetchone()
        prioritized_total = _safe_int(row["total"])
        actionable_today = _safe_int(row["actionable"])

        # 4. Daily action capacity from active policy
        cur.execute(
            "SELECT daily_action_capacity FROM growth.yango_lima_opportunity_policy_config "
            "WHERE is_active = true LIMIT 1"
        )
        pol = cur.fetchone()
        daily_action_capacity = _safe_int(pol["daily_action_capacity"]) if pol else 0

        # 5. Capacity config
        cur.execute(
            "SELECT SUM(agents * capacity_per_agent) as total "
            "FROM growth.yego_lima_capacity_config "
            "WHERE is_active = true AND config_date = %(d)s",
            {"d": date},
        )
        row = cur.fetchone()
        capacity_total = _safe_int(row["total"]) if row else 0

        if capacity_total == 0:
            cur.execute(
                "SELECT SUM(agents * capacity_per_agent) as total "
                "FROM growth.yego_lima_capacity_config "
                "WHERE is_active = true AND config_date IS NULL"
            )
            row = cur.fetchone()
            capacity_total = _safe_int(row["total"]) if row else 0

        # 6. Queue stats
        cur.execute(
            "SELECT "
            "SUM(CASE WHEN queue_status != 'EXPORTED' THEN 1 ELSE 0 END) as total, "
            "SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready, "
            "SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held, "
            "SUM(CASE WHEN queue_status = 'EXPORTED' THEN 1 ELSE 0 END) as exported_from_queue "
            "FROM growth.yego_lima_assignment_queue "
            "WHERE assignment_date = %(d)s", {"d": date}
        )
        row = cur.fetchone()
        queue_total = _safe_int(row["total"])
        queue_ready = _safe_int(row["ready"])
        queue_held = _safe_int(row["held"])
        queue_exported_from = _safe_int(row["exported_from_queue"])

        # 7. LoopControl export stats
        cur.execute(
            "SELECT COUNT(*) as campaigns, SUM(contacts_inserted) as contacts "
            "FROM growth.yango_lima_loopcontrol_campaign_export "
            "WHERE export_status = 'exported' AND opportunity_date = %(d)s",
            {"d": date}
        )
        row = cur.fetchone()
        lc_campaigns = _safe_int(row["campaigns"])
        lc_contacts = _safe_int(row["contacts"])

        # 8. Program distribution within prioritized
        cur.execute(
            "SELECT selected_program_code, COUNT(*) as cnt "
            "FROM growth.yango_lima_prioritized_opportunity_daily "
            "WHERE opportunity_date = %(d)s "
            "GROUP BY selected_program_code ORDER BY cnt DESC", {"d": date}
        )
        by_program = [
            {"program_code": r["selected_program_code"], "prioritized": r["cnt"]}
            for r in cur.fetchall()
        ]

    queue_exported = queue_exported_from
    queue_exported_campaigns = lc_campaigns

    # Freshness metadata
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
        driver_ts = cur.fetchone()[0]
        cur.execute("SELECT MAX(generated_at) FROM growth.yango_lima_prioritized_opportunity_daily")
        opp_ts = cur.fetchone()[0]
        cur.execute("SELECT MAX(exported_at) FROM growth.yango_lima_loopcontrol_campaign_export")
        export_ts = cur.fetchone()[0]
        cur.execute("SELECT MAX(updated_at) FROM growth.yango_lima_opportunity_policy_config")
        policy_ts = cur.fetchone()[0]

    freshness = {
        "driver_snapshot": compute_freshness("driver_snapshot", driver_ts, "growth.yango_lima_driver_state_snapshot"),
        "opportunity_engine": compute_freshness("opportunity_engine", opp_ts, "growth.yango_lima_prioritized_opportunity_daily"),
        "assignment_queue": compute_freshness("assignment_queue", None, "growth.yango_lima_assignment_queue"),
        "exports": compute_freshness("exports", export_ts, "growth.yango_lima_loopcontrol_campaign_export"),
        "policy_config": compute_freshness("policy_config", policy_ts, "growth.yango_lima_opportunity_policy_config"),
    }

    context = {
        "universe_total": universe_total,
        "eligible_total": eligible_total,
        "prioritized_total": prioritized_total,
        "actionable_today": actionable_today,
        "daily_action_capacity": daily_action_capacity,
        "loopcontrol_campaigns_exported": lc_campaigns,
    }

    return {
        "date": date,
        "universe_total": universe_total,
        "eligible_total": eligible_total,
        "prioritized_total": prioritized_total,
        "actionable_today": actionable_today,
        "daily_action_capacity": daily_action_capacity,
        "capacity_total": capacity_total,
        "queue_total": queue_total,
        "queue_ready": queue_ready,
        "queue_held": queue_held,
        "queue_exported": queue_exported,
        "queue_exported_campaigns": queue_exported_campaigns,
        "loopcontrol_campaigns_exported": lc_campaigns,
        "loopcontrol_contacts_inserted": lc_contacts,
        "by_program": by_program,
        "freshness": freshness,
        "explainability": {
            "universe_total": explain_kpi("universe_total", universe_total, freshness.get("driver_snapshot"), context),
            "eligible_total": explain_kpi("eligible_total", eligible_total, freshness.get("driver_snapshot"), context),
            "prioritized_total": explain_kpi("prioritized_total", prioritized_total, freshness.get("opportunity_engine"), context),
            "actionable_today": explain_kpi("actionable_today", actionable_today, freshness.get("opportunity_engine"), context),
            "daily_action_capacity": explain_kpi("daily_action_capacity", daily_action_capacity, freshness.get("policy_config"), context),
            "capacity_total": explain_kpi("capacity_total", capacity_total, freshness.get("capacity"), context),
            "queue_total": explain_kpi("queue_total", queue_total, freshness.get("assignment_queue"), context),
            "queue_ready": explain_kpi("queue_ready", queue_ready, freshness.get("assignment_queue"), context),
            "queue_held": explain_kpi("queue_held", queue_held, freshness.get("assignment_queue"), context),
            "loopcontrol_contacts_inserted": explain_kpi("loopcontrol_contacts_inserted", lc_contacts, freshness.get("exports"), context),
            "loopcontrol_campaigns_exported": explain_kpi("loopcontrol_campaigns_exported", lc_campaigns, freshness.get("exports"), context),
        },
        "explanation": (
            f"actionable_today ({actionable_today}) esta limitado por "
            f"daily_action_capacity ({daily_action_capacity}). "
            f"Universo total: {universe_total}, elegibles: {eligible_total}, "
            f"priorizados: {prioritized_total}."
        ),
    }
