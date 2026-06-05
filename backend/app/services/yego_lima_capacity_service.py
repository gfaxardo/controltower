"""
YEGO Lima Growth — Daily Capacity Service (LG-2.2B).

Persistent capacity config replacing hardcoded frontend values.
Reglas:
- config_date NULL = default global
- Si existe config para fecha especifica, overridea default
- No borrar historico
"""
from __future__ import annotations

import logging
from datetime import date as DateType, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_CAPACITY = "growth.yego_lima_capacity_config"


def get_capacity_config(config_date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if config_date:
            cur.execute(
                f"SELECT * FROM {TABLE_CAPACITY} WHERE config_date = %(d)s AND is_active = true ORDER BY channel",
                {"d": config_date},
            )
            rows = cur.fetchall()
            if rows:
                return _format_response(config_date, rows)

        cur.execute(
            f"SELECT * FROM {TABLE_CAPACITY} WHERE config_date IS NULL AND is_active = true ORDER BY channel"
        )
        rows = cur.fetchall()
        if not rows:
            return {"config_date": config_date or "default", "channels": [], "total_capacity": 0}

        return _format_response(config_date or "default", rows)


def upsert_capacity_config(config_date: Optional[str], channels: List[Dict[str, Any]]) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"UPDATE {TABLE_CAPACITY} SET is_active = false, updated_at = now() "
            f"WHERE is_active = true AND config_date IS NOT DISTINCT FROM %(d)s",
            {"d": config_date},
        )

        for ch in channels:
            cur.execute(
                f"INSERT INTO {TABLE_CAPACITY} (config_date, channel, agents, capacity_per_agent, is_active) "
                f"VALUES (%(d)s, %(ch)s, %(a)s, %(cpa)s, true)",
                {
                    "d": config_date,
                    "ch": ch["channel"],
                    "a": ch["agents"],
                    "cpa": ch["capacity_per_agent"],
                },
            )

        conn.commit()

    return get_capacity_config(config_date)


def calculate_capacity_summary(config_date: Optional[str], actionable_count: int) -> Dict[str, Any]:
    config = get_capacity_config(config_date)
    channels = config.get("channels", [])
    total_capacity = config.get("total_capacity", 0)
    capacity_gap = actionable_count - total_capacity
    coverage_rate = total_capacity / actionable_count if actionable_count > 0 else 0
    utilization_status = "green" if coverage_rate >= 1 else "yellow" if coverage_rate >= 0.7 else "red"

    return {
        "config_date": config.get("config_date"),
        "total_capacity": total_capacity,
        "actionable_count": actionable_count,
        "capacity_gap": capacity_gap,
        "coverage_rate": round(coverage_rate, 4),
        "utilization_status": utilization_status,
        "channels": channels,
    }


def seed_default_capacity_config() -> Dict[str, Any]:
    defaults = [
        {"channel": "Call Center", "agents": 2, "capacity_per_agent": 40},
        {"channel": "SAC", "agents": 1, "capacity_per_agent": 30},
        {"channel": "Bot / WhatsApp", "agents": 1, "capacity_per_agent": 200},
    ]

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT COUNT(*) as cnt FROM {TABLE_CAPACITY} WHERE config_date IS NULL AND is_active = true"
        )
        row = cur.fetchone()
        if row and row["cnt"] > 0:
            return {"seeded": False, "message": "Default config already exists", "config": get_capacity_config(None)}

    return upsert_capacity_config(None, defaults)


def _format_response(config_date: str, rows: list) -> Dict[str, Any]:
    channels = []
    total = 0
    for r in rows:
        cap = (r["agents"] or 0) * (r["capacity_per_agent"] or 0)
        total += cap
        channels.append({
            "channel": r["channel"],
            "agents": r["agents"],
            "capacity_per_agent": r["capacity_per_agent"],
            "channel_capacity": cap,
        })
    return {
        "config_date": config_date,
        "channels": channels,
        "total_capacity": total,
    }
