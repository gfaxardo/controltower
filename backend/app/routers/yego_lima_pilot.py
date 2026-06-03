"""
YEGO Lima Growth — Production Pilot Router (Fase PP-0).

API map + smoke test for Miguel handoff.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yego-lima-growth/pilot", tags=["yego-lima-growth-pilot"])


class SmokeTestRequest(BaseModel):
    run_date: str = Field(..., description="Date YYYY-MM-DD")
    max_drivers: int = Field(50, ge=5, le=100)
    dry_run: bool = False


@router.get("/api-map")
async def api_map():
    return {
        "version": "Fase PP-0 — Production Pilot",
        "base_url": "/yego-lima-growth",
        "sections": [
            {
                "section": "State",
                "description": "Canonical driver states (lifecycle, performance, retention)",
                "endpoints": [
                    {"method": "POST", "path": "/state/build-driver-states", "body": {"snapshot_date": "2026-06-02"}, "description": "Build driver state snapshot for a date"},
                    {"method": "GET", "path": "/state/summary?date=YYYY-MM-DD", "description": "Get state distribution"},
                    {"method": "GET", "path": "/state/drivers?date=YYYY-MM-DD&lifecycle_state=ESTABLISHED&limit=100", "description": "List drivers by state filters"},
                    {"method": "GET", "path": "/state/driver/{driver_profile_id}?date=YYYY-MM-DD", "description": "Get single driver state"},
                ],
            },
            {
                "section": "Programs",
                "description": "Program eligibility evaluated from driver states",
                "endpoints": [
                    {"method": "POST", "path": "/programs/build-eligibility", "body": {"eligibility_date": "2026-06-02"}, "description": "Build program eligibility"},
                    {"method": "GET", "path": "/programs/summary?date=YYYY-MM-DD", "description": "Program counts"},
                    {"method": "GET", "path": "/programs/drivers?date=YYYY-MM-DD&program_code=PROGRAM_ACTIVE_GROWTH&limit=100", "description": "List eligible drivers by program"},
                ],
            },
            {
                "section": "Opportunities",
                "description": "Daily opportunity lists for agent action",
                "endpoints": [
                    {"method": "POST", "path": "/opportunities/build-daily", "body": {"opportunity_date": "2026-06-02"}, "description": "Generate daily opportunity lists"},
                    {"method": "POST", "path": "/opportunities/close-unmanaged", "body": {"opportunity_date": "2026-06-02"}, "description": "Close unmanaged from previous day"},
                    {"method": "GET", "path": "/opportunities/daily?opportunity_date=YYYY-MM-DD&opportunity_type=OPPORTUNITY_ACTIVE_GROWTH&management_status=PENDING_ACTION&limit=50", "description": "Get daily opportunities with filters"},
                    {"method": "POST", "path": "/opportunities/assign-agent", "body": {"opportunity_date": "2026-06-02", "driver_profile_id": "...", "opportunity_type": "OPPORTUNITY_ACTIVE_GROWTH", "agent": "miguel"}, "description": "Assign agent to opportunity"},
                    {"method": "POST", "path": "/opportunities/link-action", "body": {"opportunity_date": "2026-06-02", "driver_profile_id": "...", "opportunity_type": "OPPORTUNITY_ACTIVE_GROWTH", "action_id": "uuid", "management_status": "ACTION_CONFIRMED"}, "description": "Link action to opportunity"},
                ],
            },
            {
                "section": "Actions",
                "description": "Agent action registry",
                "endpoints": [
                    {"method": "POST", "path": "/control-loop/actions", "body": {"driver_profile_id": "...", "action_date": "2026-06-02", "action_type": "WHATSAPP_CALL", "source_segment_snapshot_date": "2026-06-02", "list_date": "2026-06-02", "list_type": "LEALTAD_2_ACTIVE_GROWTH", "action_channel": "WHATSAPP", "action_owner": "miguel", "action_status": "attempted", "action_confirmed": True, "confirmation_source": "WHATSAPP_REPLY", "campaign_code": "PILOT_W1"}, "description": "Register an action (legacy list_date/list_type)"},
                    {"method": "PATCH", "path": "/control-loop/actions/{action_id}/status", "body": {"action_status": "completed", "action_confirmed": True}, "description": "Update action status"},
                    {"method": "GET", "path": "/control-loop/actions?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&action_owner=miguel&limit=50", "description": "List actions with filters"},
                ],
            },
            {
                "section": "Impact",
                "description": "Daily action impact measurement",
                "endpoints": [
                    {"method": "POST", "path": "/control-loop/build-daily-impact", "body": {"impact_date": "2026-06-02"}, "description": "Build daily impact for all actions"},
                    {"method": "GET", "path": "/control-loop/agent-performance-summary?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&action_owner=miguel", "description": "Get agent performance summary"},
                    {"method": "GET", "path": "/control-loop/driver-impact-timeline/{driver_profile_id}?limit=30", "description": "Get driver impact timeline"},
                ],
            },
            {
                "section": "Executive",
                "description": "Executive metrics and freshness",
                "endpoints": [
                    {"method": "GET", "path": "/executive/summary?date=YYYY-MM-DD", "description": "Executive summary with all distributions"},
                    {"method": "GET", "path": "/executive/freshness", "description": "Data freshness across all layers"},
                    {"method": "GET", "path": "/executive/segments?date=YYYY-MM-DD", "description": "Segment distributions"},
                    {"method": "GET", "path": "/executive/actions?date=YYYY-MM-DD", "description": "Action status by list type"},
                    {"method": "GET", "path": "/executive/agents?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD", "description": "Agent performance"},
                ],
            },
            {
                "section": "Pipeline",
                "description": "Daily pipeline orchestration",
                "endpoints": [
                    {"method": "POST", "path": "/pipeline/run-daily", "body": {"run_date": "2026-06-02", "max_drivers": 250, "dry_run": False}, "description": "Run full daily pipeline"},
                    {"method": "GET", "path": "/pipeline/status?date=YYYY-MM-DD", "description": "Pipeline layer status"},
                    {"method": "GET", "path": "/pipeline/consistency-check?date=YYYY-MM-DD", "description": "Consistency validation"},
                ],
            },
            {
                "section": "Lab",
                "description": "Discovery and rebuild tools",
                "endpoints": [
                    {"method": "GET", "path": "/lab/health", "description": "Lab health check"},
                    {"method": "GET", "path": "/lab/history-source-inspection", "description": "Inspect trips_2025/2026 schema"},
                    {"method": "POST", "path": "/lab/rebuild-history-until-cutover", "body": {"cutover_date": "2026-06-01", "dry_run": True}, "description": "Rebuild history from trips tables"},
                    {"method": "GET", "path": "/lab/history-continuity-check", "description": "Check history/API continuity"},
                ],
            },
        ],
        "opportunity_types": {
            "OPPORTUNITY_14_90": "Early-life activation & acceleration (PROGRAM_14_90)",
            "OPPORTUNITY_ACTIVE_GROWTH": "Growth for underperforming drivers (PROGRAM_ACTIVE_GROWTH)",
            "OPPORTUNITY_CHURN_PREVENTION": "Retention for at-risk drivers (PROGRAM_CHURN_PREVENTION)",
        },
        "management_statuses": [
            {"status": "PENDING_ACTION", "description": "No action taken yet"},
            {"status": "ACTION_CONFIRMED", "description": "Agent action confirmed successful"},
            {"status": "ACTION_ATTEMPTED", "description": "Agent attempted but not confirmed"},
            {"status": "ACTION_NOT_CONFIRMED", "description": "Agent action explicitly not confirmed"},
            {"status": "NO_ACTION", "description": "Closed without action (end of day)"},
            {"status": "DISMISSED", "description": "Manually dismissed"},
        ],
        "daily_flow": [
            "1. Run pipeline: POST /pipeline/run-daily (or individual build steps)",
            "2. Get opportunities: GET /opportunities/daily?management_status=PENDING_ACTION",
            "3. Assign agent: POST /opportunities/assign-agent",
            "4. Contact driver, confirm action: POST /control-loop/actions",
            "5. Close unmanaged: POST /opportunities/close-unmanaged",
            "6. Build impact: POST /control-loop/build-daily-impact",
            "7. Check performance: GET /control-loop/agent-performance-summary",
            "8. Review executive: GET /executive/summary",
        ],
    }


@router.post("/smoke-test")
async def smoke_test(payload: SmokeTestRequest):
    run_date = payload.run_date
    max_drivers = payload.max_drivers
    dry_run = payload.dry_run

    results: Dict[str, Any] = {
        "run_date": run_date,
        "dry_run": dry_run,
        "overall_status": "running",
        "steps": {},
        "sample_opportunities_count": 0,
        "sample_action_created": False,
        "impact_built": False,
        "timeline_available": False,
        "agent_summary_available": False,
        "errors": [],
    }

    try:
        # 1. Pipeline dry run
        from app.services.yego_lima_daily_pipeline_service import run_daily_pipeline
        pl_result = run_daily_pipeline(run_date, max_drivers=max_drivers, dry_run=dry_run)
        results["steps"]["pipeline"] = {
            "overall_status": pl_result.get("overall_status"),
            "steps_count": len(pl_result.get("steps", [])),
            "run_id": pl_result.get("run_id"),
        }
        if pl_result.get("overall_status") != "success" and not dry_run:
            results["errors"].extend(pl_result.get("errors", []))

        # 2. Build opportunities
        from app.services.yego_lima_daily_opportunity_service import build_daily_opportunity_lists
        opp_result = build_daily_opportunity_lists(run_date)
        results["steps"]["opportunities"] = opp_result
        if opp_result.get("ok"):
            results["sample_opportunities_count"] = opp_result.get("total_opportunities", 0)

        # 3. Get 5 drivers from OPPORTUNITY_ACTIVE_GROWTH
        from app.services.yego_lima_daily_opportunity_service import get_daily_opportunities
        sample_drivers = get_daily_opportunities(
            opportunity_date=run_date,
            opportunity_type="OPPORTUNITY_ACTIVE_GROWTH",
            management_status="PENDING_ACTION",
            limit=5,
        )
        results["steps"]["sample_opportunities"] = {
            "count": len(sample_drivers),
            "drivers": [
                {
                    "driver_id_masked": d["driver_profile_id"][:8] + "****",
                    "opportunity_type": d.get("opportunity_type"),
                    "lifecycle": d.get("lifecycle_state"),
                    "performance": d.get("performance_state"),
                    "orders_week": d.get("completed_orders_week"),
                    "distance_to_target": d.get("distance_to_weekly_target"),
                }
                for d in sample_drivers
            ],
        }

        # 4. Register sample actions if we have drivers
        if sample_drivers and not dry_run:
            from app.services.yego_lima_action_registry_service import create_action
            from app.services.yego_lima_daily_opportunity_service import link_action

            # Confirmed action
            d1 = sample_drivers[0]
            a1 = create_action(
                driver_profile_id=d1["driver_profile_id"],
                action_date_str=run_date,
                action_type="SMOKE_TEST",
                source_segment_snapshot_date=run_date,
                action_channel="WHATSAPP",
                action_owner="smoke_test",
                action_status="completed",
                action_confirmed=True,
                confirmation_source="SMOKE_TEST",
                campaign_code="PILOT_SMOKE",
                notes="Smoke test - confirmed",
            )
            if a1.get("ok"):
                link_action(run_date, d1["driver_profile_id"], d1["opportunity_type"],
                           a1["action_id"], "ACTION_CONFIRMED")
            results["steps"]["action_confirmed"] = a1

            # Attempted (not confirmed) action
            if len(sample_drivers) > 1:
                d2 = sample_drivers[1]
                a2 = create_action(
                    driver_profile_id=d2["driver_profile_id"],
                    action_date_str=run_date,
                    action_type="SMOKE_TEST",
                    source_segment_snapshot_date=run_date,
                    action_channel="WHATSAPP",
                    action_owner="smoke_test",
                    action_status="attempted",
                    action_confirmed=False,
                    campaign_code="PILOT_SMOKE",
                    notes="Smoke test - attempted not confirmed",
                )
                if a2.get("ok"):
                    link_action(run_date, d2["driver_profile_id"], d2["opportunity_type"],
                               a2["action_id"], "ACTION_ATTEMPTED")
                results["steps"]["action_attempted"] = a2
                results["sample_action_created"] = True

            # 5. Close unmanaged
            from app.services.yego_lima_daily_opportunity_service import close_unmanaged_opportunities
            cr = close_unmanaged_opportunities(run_date)
            results["steps"]["close_unmanaged"] = cr

            # 6. Build daily impact
            from app.services.yego_lima_action_impact_service import build_daily_impact_for_date
            impact = build_daily_impact_for_date(run_date)
            results["steps"]["daily_impact"] = {"ok": impact.get("ok")} if isinstance(impact, dict) else {"status": "executed"}
            results["impact_built"] = True

            # 7. Build segment transitions
            from app.services.yego_lima_segment_migration_service import build_segment_transitions
            trans = build_segment_transitions(run_date)
            results["steps"]["segment_transitions"] = {"ok": trans.get("ok")} if isinstance(trans, dict) else {"status": "executed"}

            # 8. Build attribution
            from app.services.yego_lima_impact_attribution_service import build_daily_attribution
            attr = build_daily_attribution(run_date)
            results["steps"]["attribution"] = {"ok": attr.get("ok")} if isinstance(attr, dict) else {"status": "executed"}

            # 9. Driver timeline
            if sample_drivers:
                from app.services.yego_lima_action_impact_service import get_driver_impact_timeline
                timeline = get_driver_impact_timeline(sample_drivers[0]["driver_profile_id"], limit=10)
                results["timeline_available"] = len(timeline) > 0 if isinstance(timeline, list) else False
                results["steps"]["driver_timeline"] = {"available": results["timeline_available"]}

            # 10. Agent summary
            from app.services.yego_lima_action_impact_service import summarize_agent_performance
            agent_sum = summarize_agent_performance(run_date, run_date, "smoke_test")
            results["agent_summary_available"] = len(agent_sum) > 0 if isinstance(agent_sum, list) else False
            results["steps"]["agent_performance"] = {"available": results["agent_summary_available"]}

        # Final
        results["overall_status"] = "success" if not results["errors"] else "warning"

    except Exception as e:
        results["overall_status"] = "failed"
        results["errors"].append({"step": "exception", "message": str(e)[:200]})

    return results
