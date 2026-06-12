"""
LG-RNA-2A — RNA Priority Scoring Engine
Deterministic. Rule-based. Traceable. NO AI. NO ML.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_PRIORITY = "growth.rna_priority_fact"
TABLE_DS = "growth.yango_lima_driver_state_snapshot"
TABLE_LC = "growth.yego_lima_driver_lifecycle_daily"
TABLE_TAX = "growth.yego_lima_v2_taxonomy_daily"
TABLE_MOV = "growth.yego_lima_v2_movement_fact"
TABLE_PR = "growth.yango_lima_program_eligibility_daily"

SCORING = [
    ("contactable", 20, "Driver has phone — can be contacted"),
    ("cancelled_signal", 15, "Previously cancelled — high re-engagement potential"),
    ("recent_activity", 15, "Had trips in last 7 days"),
    ("high_value", 10, "Driver is in top 20% value tier"),
    ("positive_momentum", 10, "Momentum is rising"),
    ("has_program", 10, "Already assigned to a program"),
    ("positive_movement", 5, "Recent positive movement score"),
    ("trips_30d", 5, "Had trips in last 30 days (not 7)"),
    ("dormant_30d", -10, "No trips in 30+ days"),
    ("churned_lifecycle", -15, "Lifecycle is CHURNED or DECLINING"),
]


def build_rna_priority() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT ds.driver_profile_id, ds.contactability, ds.cancelled_signal,
                   ds.is_rna, lc.lifecycle_status, lc.completed_trips_7d,
                   lc.completed_trips_30d, lc.days_since_last_completed_trip,
                   tx.elite_tier, tx.loyalty_tier, 0 AS movement_score,
                   pr.program_code
            FROM {TABLE_DS} ds
            LEFT JOIN {TABLE_LC} lc ON ds.driver_profile_id = lc.driver_profile_id
            LEFT JOIN {TABLE_TAX} tx ON ds.driver_profile_id = tx.driver_id
            LEFT JOIN {TABLE_MOV} mv ON ds.driver_profile_id = mv.driver_id
            LEFT JOIN {TABLE_PR} pr ON ds.driver_profile_id = pr.driver_profile_id
            WHERE ds.is_rna = true
        """)
        rows = cur.fetchall()

        scored = []
        for r in rows:
            driver_id = r[0]
            contactable = bool(r[1])
            cancelled = bool(r[2])
            lifecycle = r[4] or "UNKNOWN"
            trips_7d = r[5] or 0
            trips_30d = r[6] or 0
            days_since = r[7]
            value_tier = r[8] or r[9] or "mid_60"
            momentum = "stable"
            movement_score = r[10] or 0
            program = r[11]

            score = 0
            signals = {}

            if contactable:
                score += 20; signals["contactable"] = 20
            if cancelled:
                score += 15; signals["cancelled_signal"] = 15
            if trips_7d > 0:
                score += 15; signals["recent_activity"] = 15
            if value_tier and value_tier in ("top_20", "top_20_pct"):
                score += 10; signals["high_value"] = 10
            if momentum and momentum == "rising":
                score += 10; signals["positive_momentum"] = 10
            if program:
                score += 10; signals["has_program"] = 10
            if movement_score > 0:
                score += 5; signals["positive_movement"] = 5
            if trips_30d > 0 and trips_7d == 0:
                score += 5; signals["trips_30d"] = 5
            if days_since and days_since > 30:
                score -= 10; signals["dormant_30d"] = -10
            if lifecycle in ("CHURNED", "DECLINING"):
                score -= 15; signals["churned_lifecycle"] = -15

            band = "COLD"
            if score >= 35:
                band = "HOT"
            elif score >= 15:
                band = "WARM"

            cur.execute(f"""
                INSERT INTO {TABLE_PRIORITY} (driver_profile_id, rna_score, priority_band,
                    contactable, cancelled_signal, lifecycle, value_tier, momentum,
                    trips_7d, trips_30d, days_since_last_trip, movement_score,
                    program_code, signal_breakdown_json, scored_at)
                VALUES (%(did)s, %(sc)s, %(band)s, %(con)s, %(can)s, %(lc)s, %(vt)s,
                        %(mom)s, %(t7)s, %(t30)s, %(ds)s, %(ms)s, %(pr)s, %(sig)s, now())
                ON CONFLICT (driver_profile_id) DO UPDATE SET
                    rna_score = EXCLUDED.rna_score,
                    priority_band = EXCLUDED.priority_band,
                    contactable = EXCLUDED.contactable,
                    cancelled_signal = EXCLUDED.cancelled_signal,
                    lifecycle = EXCLUDED.lifecycle,
                    value_tier = EXCLUDED.value_tier,
                    momentum = EXCLUDED.momentum,
                    trips_7d = EXCLUDED.trips_7d,
                    trips_30d = EXCLUDED.trips_30d,
                    days_since_last_trip = EXCLUDED.days_since_last_trip,
                    movement_score = EXCLUDED.movement_score,
                    program_code = EXCLUDED.program_code,
                    signal_breakdown_json = EXCLUDED.signal_breakdown_json,
                    scored_at = EXCLUDED.scored_at
            """, {
                "did": driver_id, "sc": score, "band": band,
                "con": contactable, "can": cancelled,
                "lc": lifecycle, "vt": value_tier, "mom": momentum,
                "t7": trips_7d, "t30": trips_30d, "ds": days_since,
                "ms": movement_score, "pr": program,
                "sig": json.dumps(signals),
            })

            scored.append({"driver_id": driver_id, "score": score, "band": band})

        hot = sum(1 for s in scored if s["band"] == "HOT")
        warm = sum(1 for s in scored if s["band"] == "WARM")
        cold = sum(1 for s in scored if s["band"] == "COLD")

        return {"total_scored": len(scored), "hot": hot, "warm": warm, "cold": cold}


def get_rna_priority_summary() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_PRIORITY}")
        total = (cur.fetchone() or [0])[0]
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_PRIORITY} WHERE priority_band = 'HOT'")
        hot = (cur.fetchone() or [0])[0]
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_PRIORITY} WHERE priority_band = 'WARM'")
        warm = (cur.fetchone() or [0])[0]
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_PRIORITY} WHERE priority_band = 'COLD'")
        cold = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT priority_band, ROUND(AVG(rna_score),1) as avg_score, COUNT(*) as cnt
            FROM {TABLE_PRIORITY} GROUP BY priority_band ORDER BY avg_score DESC
        """)
        bands = [{"band": r[0], "avg_score": float(r[1]), "count": r[2]} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT signal_key, SUM(CASE WHEN val::numeric > 0 THEN 1 ELSE 0 END) as pos,
                   SUM(CASE WHEN val::numeric < 0 THEN 1 ELSE 0 END) as neg
            FROM {TABLE_PRIORITY}, jsonb_each(signal_breakdown_json) as sig(signal_key, val)
            GROUP BY signal_key ORDER BY pos DESC
        """)
        signal_dist = [{"signal": r[0], "positive": r[1], "negative": r[2]} for r in cur.fetchall()]

        return {"total": total, "hot": hot, "warm": warm, "cold": cold, "bands": bands, "signal_distribution": signal_dist}


def get_rna_drivers(band: str = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cond = ""
        params = {"lim": limit, "off": offset}
        if band and band in ("HOT", "WARM", "COLD"):
            cond = "WHERE priority_band = %(band)s"
            params["band"] = band
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_PRIORITY} {cond}", params)
        total = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT driver_profile_id, rna_score, priority_band, contactable,
                   cancelled_signal, lifecycle, value_tier, momentum,
                   trips_7d, trips_30d, days_since_last_trip, movement_score,
                   program_code, signal_breakdown_json, scored_at
            FROM {TABLE_PRIORITY} {cond}
            ORDER BY rna_score DESC LIMIT %(lim)s OFFSET %(off)s
        """, params)

        drivers = []
        for r in cur.fetchall():
            drivers.append({
                "driver_id": r[0], "score": float(r[1]), "band": r[2],
                "contactable": r[3], "cancelled_signal": r[4],
                "lifecycle": r[5], "value_tier": r[6], "momentum": r[7],
                "trips_7d": r[8], "trips_30d": r[9],
                "days_since_last_trip": r[10], "movement_score": r[11],
                "program": r[12], "signals": r[13] if isinstance(r[13], dict) else {},
                "scored_at": str(r[14]) if r[14] else None,
            })
        return {"total": total, "drivers": drivers, "limit": limit, "offset": offset}


def get_rna_driver_detail(driver_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT driver_profile_id, rna_score, priority_band, contactable,
                   cancelled_signal, lifecycle, value_tier, momentum,
                   trips_7d, trips_30d, days_since_last_trip, movement_score,
                   program_code, signal_breakdown_json, scored_at
            FROM {TABLE_PRIORITY} WHERE driver_profile_id = %(did)s
        """, {"did": driver_id})
        r = cur.fetchone()
        if not r:
            return {"driver_id": driver_id, "found": False}

        signals = r[13] if isinstance(r[13], dict) else {}
        reasons = []
        for sig, val in signals.items():
            if val > 0:
                reasons.append(f"+{val}: {sig}")
            else:
                reasons.append(f"{val}: {sig}")

        return {
            "driver_id": r[0], "score": float(r[1]), "band": r[2],
            "contactable": r[3], "cancelled_signal": r[4],
            "lifecycle": r[5], "value_tier": r[6], "momentum": r[7],
            "trips_7d": r[8], "trips_30d": r[9],
            "days_since_last_trip": r[10], "movement_score": r[11],
            "program": r[12], "signals": signals, "reasons": reasons,
            "scored_at": str(r[14]) if r[14] else None,
        }
