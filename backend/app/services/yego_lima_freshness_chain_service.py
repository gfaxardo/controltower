"""
YEGO Lima Growth — Freshness Chain Service V2 (LG-INFRA-R3.0E)
Adds effective_source_date and propagated staleness.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from app.db.connection import get_db

logger = logging.getLogger(__name__)

# Lineage: each layer's true upstream source
LINEAGE_SOURCE = {
    "norm_orders": None,
    "history_daily": "norm_orders",
    "history_weekly": "history_daily",
    "snapshot": "history_weekly",
    "eligibility": "snapshot",
    "opportunity": "eligibility",
    "exclusive_worklist": "snapshot",
    "exclusive_worklist_transition": "exclusive_worklist",
    "prioritized": "opportunity",
    "queue": "prioritized",
    "serving": "queue",
    "control_loop": "queue",
}


def get_freshness_chain_status() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        layers_meta = []
        max_dates = {}

        queries = [
            ("norm_orders", "growth", "yango_lima_orders_raw", "ended_at"),
            ("history_daily", "growth", "yango_lima_driver_history_daily", "date"),
            ("history_weekly", "growth", "yango_lima_driver_history_weekly", "week_start_date"),
            ("snapshot", "growth", "yango_lima_driver_state_snapshot", "snapshot_date"),
            ("eligibility", "growth", "yango_lima_program_eligibility_daily", "eligibility_date"),
            ("opportunity", "growth", "yango_lima_daily_opportunity_list", "opportunity_date"),
            ("exclusive_worklist", "growth", "yango_lima_exclusive_driver_worklist_daily", "generated_date"),
            ("exclusive_worklist_transition", "growth", "yango_lima_exclusive_worklist_transition_daily", "generated_date"),
            ("prioritized", "growth", "yango_lima_prioritized_opportunity_daily", "opportunity_date"),
            ("queue", "growth", "yego_lima_assignment_queue", "assignment_date"),
            ("serving", "growth", "yego_lima_serving_fact", "fact_date"),
            ("control_loop", "growth", "yego_lima_control_loop_state", "created_at"),
        ]

        for label, schema, table, col in queries:
            full = f"{schema}.{table}"
            try:
                cur.execute(f"SELECT MAX({col}), COUNT(*) FROM {full}")
                r = cur.fetchone()
                max_dates[label] = str(r[0]) if r[0] else None
                layers_meta.append({
                    "layer": label,
                    "table": full,
                    "layer_date": max_dates[label],
                    "rows": r[1] or 0,
                })
            except Exception:
                max_dates[label] = None
                layers_meta.append({"layer": label, "layer_date": None, "error": "table error"})

        # Compute effective source date by following lineage
        effective_sources = {}
        for label in max_dates:
            src = LINEAGE_SOURCE.get(label)
            if src is None:
                effective_sources[label] = max_dates.get(label)
            else:
                effective_sources[label] = effective_sources.get(src) or max_dates.get(src)

        # Build final waterfall with status
        layers = []
        first_breakpoint = None
        has_false_freshness = False

        for l in layers_meta:
            label = l["layer"]
            layer_date = l.get("layer_date")
            eff_src = effective_sources.get(label)
            source = LINEAGE_SOURCE.get(label)

            # Determine status
            if layer_date and eff_src:
                layer_d = layer_date[:10] if layer_date else ""
                eff_d = eff_src[:10] if eff_src else ""
                
                if layer_d == eff_d:
                    today_str = __import__('datetime').date.today().isoformat()
                    if layer_d >= today_str:
                        status = "FRESH"
                    else:
                        status = "STALE"
                        if first_breakpoint is None:
                            first_breakpoint = label
                elif layer_d > eff_d:
                    status = "STALE_PROPAGATED"
                    has_false_freshness = True
                    if first_breakpoint is None:
                        first_breakpoint = label
                else:
                    status = "CHECK"
            elif l.get("rows", 0) == 0:
                status = "EMPTY"
            else:
                status = "MISSING"

            layers.append({
                **l,
                "source_layer": source,
                "effective_source_date": eff_src[:10] if eff_src else None,
                "effective_freshness": status,
                "propagated": status == "STALE_PROPAGATED",
            })

        # Operability
        if has_false_freshness:
            operability = "OPERABLE_WARNING"
        else:
            operability = "OPERABLE"

    return {
        "layers": layers,
        "first_breakpoint": first_breakpoint,
        "false_freshness_detected": has_false_freshness,
        "operability": operability,
        "message": "STALE_PROPAGATED: operational layers use stale source data" if has_false_freshness else "All layers fresh",
    }
