"""
YEGO Lima Growth — Governance API (LG-OEF-2_3_4A)
Program registry, daily runs, freshness status, health.
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from app.db.connection import get_db

logger = logging.getLogger(__name__)


def get_program_registry() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT program_code, program_name, description, active, priority, policy_version, valid_from FROM growth.yego_lima_program_registry ORDER BY priority")
        programs = []
        for r in cur.fetchall():
            programs.append({
                "program_code": r[0], "program_name": r[1], "description": r[2],
                "active": r[3], "priority": r[4], "policy_version": r[5],
                "valid_from": str(r[6]) if r[6] else None,
            })
    return {"programs": programs, "total": len(programs)}


def get_daily_runs(limit: int = 10) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT operational_data_date, status, started_at, finished_at
            FROM growth.yego_lima_refresh_run_log
            ORDER BY started_at DESC LIMIT %(lim)s
        """, {"lim": limit})
        runs = []
        for r in cur.fetchall():
            runs.append({
                "date": str(r[0]) if r[0] else None,
                "status": r[1],
                "started_at": r[2].isoformat() if r[2] else None,
                "finished_at": r[3].isoformat() if r[3] else None,
            })
    return {"runs": runs, "total": len(runs)}


def get_freshness_status() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT component, last_refresh_at, freshness_status, latency_minutes, max_data_date FROM growth.yego_lima_freshness_registry ORDER BY component")
        components = []
        green = yellow = red = 0
        for r in cur.fetchall():
            status = r[2] or 'UNKNOWN'
            if status in ('FRESH', 'OK'): green += 1
            elif status in ('STALE', 'WARNING'): yellow += 1
            else: red += 1
            components.append({
                "component": r[0], "last_refresh": r[1].isoformat() if r[1] else None,
                "status": status, "latency_minutes": r[3], "max_data_date": str(r[4]) if r[4] else None,
            })

        # Health score
        if red > 0: health = "RED"
        elif yellow > 2: health = "YELLOW"
        else: health = "GREEN"

    return {"components": components, "health": health, "green": green, "yellow": yellow, "red": red}


def update_freshness(component: str, status: str, max_data_date: str = None, run_id: str = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE growth.yego_lima_freshness_registry
            SET freshness_status = %(st)s, last_refresh_at = now(),
                max_data_date = %(mdd)s::date, run_id = COALESCE(%(rid)s, run_id),
                updated_at = now()
            WHERE component = %(c)s
        """, {"st": status, "mdd": max_data_date, "rid": run_id, "c": component})
        conn.commit()
    return {"component": component, "status": status, "updated": True}


def get_health_status() -> Dict[str, Any]:
    freshness = get_freshness_status()

    # Check operational layers
    with get_db() as conn:
        cur = conn.cursor()
        checks = {}
        for table, col in [
            ("growth.yango_lima_driver_state_snapshot", "snapshot_date"),
            ("growth.yango_lima_program_eligibility_daily", "eligibility_date"),
            ("growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
            ("growth.yego_lima_assignment_queue", "assignment_date"),
        ]:
            cur.execute(f"SELECT MAX({col}) FROM {table}")
            r = cur.fetchone()
            checks[table.split('.')[-1]] = str(r[0]) if r[0] else None

    now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    today = now.date().isoformat()
    all_ok = all(v and v == today for v in checks.values() if v)

    return {
        "health": freshness["health"],
        "freshness": freshness,
        "operational_layers": checks,
        "all_operational_layers_ok": all_ok,
        "scheduler": {
            "enabled": True,
            "interval_minutes": 5,
        },
    }
