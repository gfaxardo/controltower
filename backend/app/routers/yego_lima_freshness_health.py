"""
Freshness Health Endpoint — LG-UX-R2.2
"""
import logging
from fastapi import APIRouter, Query
from datetime import datetime, timezone
from app.services.freshness_service import compute_freshness, overall_status, DOMAIN_LABELS, THRESHOLDS
from app.db.connection import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/freshness",
    tags=["yego-lima-growth-freshness"],
)


@router.get("/health")
async def freshness_health():
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
        driver_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(week_start_date) FROM growth.yango_lima_driver_history_weekly")
        hist_weekly_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(generated_at) FROM growth.yango_lima_prioritized_opportunity_daily")
        opp_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(exported_at) FROM growth.yango_lima_loopcontrol_campaign_export")
        export_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(updated_at) FROM growth.yango_lima_opportunity_policy_config")
        policy_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(eligibility_date) FROM growth.yango_lima_program_eligibility_daily")
        prog_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(opportunity_date) FROM growth.yango_lima_daily_opportunity_list")
        opp_list_ts = cur.fetchone()[0]

        cur.execute("SELECT MAX(created_at) FROM growth.yego_lima_control_loop_state")
        cl_ts = cur.fetchone()[0]

    sources = [
        compute_freshness("driver_snapshot", driver_ts, "growth.yango_lima_driver_state_snapshot"),
        compute_freshness("driver_history_weekly", hist_weekly_ts, "growth.yango_lima_driver_history_weekly"),
        compute_freshness("opportunity_engine", opp_ts, "growth.yango_lima_prioritized_opportunity_daily"),
        compute_freshness("assignment_queue", None, "growth.yango_lima_assignment_queue"),
        compute_freshness("exports", export_ts, "growth.yango_lima_loopcontrol_campaign_export"),
        compute_freshness("loopcontrol", export_ts, "growth.yango_lima_loopcontrol_campaign_export"),
        compute_freshness("capacity", None, "growth.yango_lima_capacity_config"),
        compute_freshness("program_eligibility", prog_ts, "growth.yango_lima_program_eligibility_daily"),
        compute_freshness("policy_config", policy_ts, "growth.yango_lima_opportunity_policy_config"),
        compute_freshness("opportunity", opp_list_ts, "growth.yango_lima_daily_opportunity_list"),
        compute_freshness("control_loop", cl_ts, "growth.yego_lima_control_loop_state"),
    ]

    return {
        "overall_status": overall_status(sources),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
    }
