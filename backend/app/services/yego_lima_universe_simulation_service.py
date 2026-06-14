"""
YEGO Lima Growth — Universe Config Simulation Engine (LG-UNIVERSE-SIM-1G)

Reads DRAFT config rules, evaluates against latest worklist data,
writes simulation_run + simulation_result. Does NOT modify production tables.
"""
from __future__ import annotations

import json as _json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

from app.db.connection import _get_connection_params, get_db

logger = logging.getLogger(__name__)

TABLE_WORKLIST = "growth.yango_lima_exclusive_driver_worklist_daily"
TABLE_HISTORY_DAILY = "growth.yango_lima_driver_history_daily"
TABLE_CONFIG_VERSION = "growth.universe_config_version"
TABLE_DEFINITION = "growth.universe_definition_config"
TABLE_RULES = "growth.universe_rule_config"
TABLE_SIM_RUN = "growth.universe_simulation_run"
TABLE_SIM_RESULT = "growth.universe_simulation_result"

SIM_LOCK_ID = 9030

OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "BETWEEN", "IN", "NOT_IN", "IS_NULL", "IS_NOT_NULL"}
ALLOWED_FIELDS = {"age_days", "anchor_age_days", "weekly_trips", "trips_since_anchor", "inactivity_days", "value_tier", "best_week_12w", "productivity_band", "has_reactivation_anchor", "export_to_control_loop"}


def _acquire_lock(conn) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT pg_try_advisory_lock(%(id)s)", {"id": SIM_LOCK_ID})
    return cur.fetchone()[0]


def _release_lock(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_unlock(%(id)s)", {"id": SIM_LOCK_ID})
    except Exception:
        pass


def _eval_rule(field_value, operator: str, rule_value: str, value_type: str, null_behavior: str = "FAIL") -> Tuple[bool, Optional[str]]:
    if field_value is None:
        if null_behavior == "PASS":
            return True, None
        if null_behavior == "IGNORE":
            return False, None
        return False, f"field is NULL, null_behavior=FAIL"

    fv = field_value
    rv = rule_value

    try:
        if operator == "=":
            return str(fv).lower() == str(rv).lower(), None
        if operator == "!=":
            return str(fv).lower() != str(rv).lower(), None
        if operator == "IS_NULL":
            return field_value is None, None
        if operator == "IS_NOT_NULL":
            return field_value is not None, None

        # Numeric operators
        nfv = float(fv)
        if operator == ">":
            return nfv > float(rv), None
        if operator == ">=":
            return nfv >= float(rv), None
        if operator == "<":
            return nfv < float(rv), None
        if operator == "<=":
            return nfv <= float(rv), None

        if operator == "BETWEEN":
            parts = rv.split("|")
            lo, hi = float(parts[0]), float(parts[1])
            return lo <= nfv <= hi, None
        if operator == "IN":
            vals = [v.strip().lower() for v in rv.split(",")]
            return str(fv).lower() in vals, None
        if operator == "NOT_IN":
            vals = [v.strip().lower() for v in rv.split(",")]
            return str(fv).lower() not in vals, None
    except (ValueError, TypeError) as e:
        return False, f"eval error: {e}"

    return False, f"unknown operator: {operator}"


def run_universe_config_simulation(
    version_code: str = "UNIVERSE_V2_DRAFT_001",
    source_generated_date: Optional[str] = None,
    dry_run: bool = False,
    run_by: Optional[str] = None,
) -> Dict[str, Any]:
    params = _get_connection_params()
    c = psycopg2.connect(**params)
    cur = c.cursor(cursor_factory=RealDictCursor)

    try:
        # Get config version
        cur.execute(f"SELECT * FROM {TABLE_CONFIG_VERSION} WHERE version_code = %s", (version_code,))
        ver = cur.fetchone()
        if not ver:
            return {"ok": False, "error": f"Config version '{version_code}' not found"}
        if ver["status"] not in ("DRAFT", "SIMULATED", "APPROVED"):
            return {"ok": False, "error": f"Version status is {ver['status']}, not eligible for simulation"}
        version_id = ver["version_id"]

        # Get definitions
        cur.execute(f"SELECT * FROM {TABLE_DEFINITION} WHERE version_id = %s AND active_flag = true ORDER BY priority_order", (version_id,))
        defs = {r["universe_code"]: dict(r) for r in cur.fetchall()}

        # Get rules grouped by universe
        cur.execute(f"SELECT * FROM {TABLE_RULES} WHERE version_id = %s ORDER BY universe_code, priority", (version_id,))
        rules_by_universe: Dict[str, List[Dict]] = {}
        for r in cur.fetchall():
            uni = r["universe_code"]
            if uni not in rules_by_universe:
                rules_by_universe[uni] = []
            rules_by_universe[uni].append(dict(r))

        # Default source date
        if source_generated_date is None:
            cur.execute(f"SELECT MAX(generated_date) FROM {TABLE_WORKLIST}")
            row = cur.fetchone()
            source_generated_date = str(row["max"]) if row and row["max"] else None
        if not source_generated_date:
            return {"ok": False, "error": "No worklist data available"}
        src_d = date.fromisoformat(source_generated_date[:10])

        # Get current worklist
        cur.execute(f"SELECT * FROM {TABLE_WORKLIST} WHERE generated_date = %s", (src_d,))
        worklist = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        if not worklist:
            return {"ok": False, "error": f"No worklist data for {src_d}"}

        # Get anchor dates (first_active from history_daily)
        cur.execute(f"SELECT driver_profile_id, MIN(date) AS anchor, MAX(date) AS last_date FROM {TABLE_HISTORY_DAILY} GROUP BY 1")
        anchors = {}
        for r in cur.fetchall():
            anchors[r["driver_profile_id"]] = {"anchor": r["anchor"], "last_date": r["last_date"]}

        cur.close()
        c.close()

        # Build driver features
        results: List[Dict] = []
        current_counts: Dict[str, int] = {}
        simulated_counts: Dict[str, int] = {}
        changed = 0
        moves: Dict[str, int] = {}

        for did, wl in worklist.items():
            cur_uni = wl.get("assigned_universe_v1", "NO_DATA")
            current_counts[cur_uni] = current_counts.get(cur_uni, 0) + 1

            anc = anchors.get(did)
            features = {
                "age_days": wl.get("operational_age_days"),
                "anchor_age_days": (src_d - anc["anchor"]).days if anc and anc["anchor"] else None,
                "weekly_trips": wl.get("weekly_trips") if wl.get("weekly_trips") is not None else 0,
                "trips_since_anchor": wl.get("activation_window_trips") if wl.get("activation_window_trips") is not None else 0,
                "inactivity_days": wl.get("inactivity_days") if wl.get("inactivity_days") is not None else 9999,
                "value_tier": wl.get("value_tier") or "DEFAULT",
                "best_week_12w": wl.get("best_week_12w"),
                "productivity_band": wl.get("productivity_band"),
                "has_reactivation_anchor": "false",
                "export_to_control_loop": wl.get("export_to_control_loop"),
            }

            # Evaluate rules in priority order
            sim_uni = "NO_DATA"
            sim_export = False
            reason_sim = "Fallback: no rules matched"
            evidence_sim = features.copy()

            for uni in [d["universe_code"] for d in sorted(defs.values(), key=lambda x: x["priority_order"])]:
                rules = rules_by_universe.get(uni, [])
                if not rules:
                    continue

                # Group rules by rule_group
                groups: Dict[str, List[Dict]] = {}
                for r in rules:
                    grp = r["rule_group"]
                    if grp not in groups:
                        groups[grp] = []
                    groups[grp].append(r)

                # AND within groups, OR across groups
                matched = False
                for grp, grp_rules in groups.items():
                    grp_match = True
                    for rule in grp_rules:
                        fv = features.get(rule["field_name"])
                        if rule["field_name"] not in ALLOWED_FIELDS:
                            grp_match = False
                            break
                        ok, _ = _eval_rule(fv, rule["operator"], rule["value"], rule["value_type"], rule["null_behavior"])
                        if not ok:
                            grp_match = False
                            break
                    if grp_match:
                        matched = True
                        break

                if matched:
                    defn = defs.get(uni, {})
                    sim_uni = uni
                    sim_export = defn.get("export_to_control_loop", False)
                    reason_sim = f"Matched config rules: {list(groups.keys())}"
                    evidence_sim["config_version"] = version_code
                    break

            simulated_counts[sim_uni] = simulated_counts.get(sim_uni, 0) + 1

            is_changed = sim_uni != cur_uni
            if is_changed:
                changed += 1
                move_key = f"{cur_uni}→{sim_uni}"
                moves[move_key] = moves.get(move_key, 0) + 1

            results.append({
                "driver_profile_id": did,
                "current_universe": cur_uni,
                "simulated_universe": sim_uni,
                "changed_flag": is_changed,
                "current_export_to_control_loop": wl.get("export_to_control_loop"),
                "simulated_export_to_control_loop": sim_export,
                "reason_current": wl.get("reason_text") or wl.get("reason_code"),
                "reason_simulated": reason_sim,
                "evidence_current": wl.get("evidence_json"),
                "evidence_simulated": evidence_sim,
                "source_generated_date": src_d,
            })

        # Compute impact report
        current_exp = sum(1 for r in results if r["current_export_to_control_loop"])
        sim_exp = sum(1 for r in results if r["simulated_export_to_control_loop"])
        exp_delta = sim_exp - current_exp

        # Risk flags
        risk_flags = []
        if abs(exp_delta) > 500:
            risk_flags.append("LARGE_EXPORTABLE_DELTA")
        if changed > 5000:
            risk_flags.append("LARGE_UNIVERSE_SHIFT")
        no_data_sim = simulated_counts.get("NO_DATA", 0)
        if no_data_sim > 500:
            risk_flags.append("MANY_NO_DATA")
        prot_count = simulated_counts.get("PROTECTED_TOP", 0)
        if prot_count < 15:
            risk_flags.append("PROTECTED_TOO_LOW")

        summary = {
            "version_code": version_code,
            "source_generated_date": str(src_d),
            "total_drivers": len(results),
            "exportable_delta": exp_delta,
            "changed_drivers": changed,
            "current_counts": current_counts,
            "simulated_counts": simulated_counts,
            "moves": dict(sorted(moves.items(), key=lambda x: -x[1])[:10]),
            "risk_flags": risk_flags,
            "sample_changed": [
                {"driver": r["driver_profile_id"][:16] + "...",
                 "from": r["current_universe"], "to": r["simulated_universe"]}
                for r in results if r["changed_flag"]
            ][:20],
        }

        if dry_run:
            return {"dry_run": True, **summary, "status": "COMPLETED"}

        # Write to simulation tables
        sim_id = str(uuid4())
        now = datetime.now(timezone.utc)
        wc = psycopg2.connect(**params)
        wc.autocommit = False
        if not _acquire_lock(wc):
            wc.close()
            return {"ok": False, "status": "SKIPPED_LOCKED"}

        try:
            cur2 = wc.cursor()
            cur2.execute(
                f"INSERT INTO {TABLE_SIM_RUN} (simulation_id, version_id, source_generated_date, run_at, run_by, status, total_drivers, exportable_drivers, non_exportable_drivers, changed_drivers, diff_vs_current, summary_json, risk_flags_json) VALUES (%s,%s,%s,%s,%s,'COMPLETED',%s,%s,%s,%s,%s,%s,%s)",
                (sim_id, version_id, src_d, now, run_by, len(results), sim_exp, len(results) - sim_exp, changed, _json.dumps(summary.get("moves", {})), _json.dumps(summary), _json.dumps(risk_flags)),
            )

            from psycopg2.extras import execute_values
            vals = [
                (sim_id, r["driver_profile_id"], r["current_universe"], r["simulated_universe"], r["changed_flag"],
                 r["current_export_to_control_loop"], r["simulated_export_to_control_loop"], r["reason_current"],
                 r["reason_simulated"], _json.dumps(r["evidence_current"]) if r["evidence_current"] else None,
                 _json.dumps(r["evidence_simulated"]), r["source_generated_date"])
                for r in results
            ]
            execute_values(cur2, f"INSERT INTO {TABLE_SIM_RESULT} (simulation_id, driver_profile_id, current_universe, simulated_universe, changed_flag, current_export_to_control_loop, simulated_export_to_control_loop, reason_current, reason_simulated, evidence_current, evidence_simulated, source_generated_date) VALUES %s", vals, page_size=5000)
            cur2.close()
            wc.commit()
        except Exception as e:
            wc.rollback()
            logger.error("Simulation write failed: %s", e)
            return {"ok": False, "status": "FAILED", "error": str(e)[:500]}
        finally:
            _release_lock(wc)
            try: wc.close()
            except: pass

        return {"ok": True, "simulation_id": sim_id, "status": "COMPLETED", "dry_run": False, **summary}

    except Exception as e:
        logger.error("Simulation failed: %s", e)
        return {"ok": False, "status": "FAILED", "error": str(e)[:500]}
    finally:
        try: cur.close()
        except: pass
        try: c.close()
        except: pass
