"""
YEGO Lima Growth — Program Capacity Policy Service (LG-UX-R2.8E)

Governed allocation policy per program.
Min/max caps, target share, allocation mode.
Read, simulate, validate. NO auto-apply.
"""
from __future__ import annotations

import logging
from datetime import date as DateType, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_POLICY = "growth.yego_lima_program_capacity_policy"

DEFAULT_POLICY = [
    {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "priority_rank": 1,
     "allocation_mode": "STRICT_PRIORITY", "policy_reason": "Default seed: strict priority for high-value drivers"},
    {"program_code": "PROGRAM_CHURN_PREVENTION", "priority_rank": 2,
     "allocation_mode": "STRICT_PRIORITY", "policy_reason": "Default seed: strict priority for churn prevention"},
    {"program_code": "PROGRAM_14_90", "priority_rank": 3,
     "allocation_mode": "STRICT_PRIORITY", "policy_reason": "Default seed: strict priority for 14/90"},
    {"program_code": "PROGRAM_ACTIVE_GROWTH", "priority_rank": 4,
     "allocation_mode": "STRICT_PRIORITY", "policy_reason": "Default seed: strict priority for active growth"},
]


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "version": row["version"],
        "policy_date_from": str(row["policy_date_from"]),
        "policy_date_to": str(row["policy_date_to"]) if row.get("policy_date_to") else None,
        "program_code": row["program_code"],
        "priority_rank": row["priority_rank"],
        "allocation_mode": row["allocation_mode"],
        "min_daily_capacity": row.get("min_daily_capacity"),
        "max_daily_capacity": row.get("max_daily_capacity"),
        "target_share_pct": float(row["target_share_pct"]) if row.get("target_share_pct") else None,
        "is_enabled": row.get("is_enabled", True),
        "policy_status": row.get("policy_status", "ACTIVE"),
        "policy_reason": row.get("policy_reason"),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "created_by": row.get("created_by", "system"),
    }


# ── READ ──

def get_active_policy(date: Optional[str] = None) -> Dict[str, Any]:
    d = date or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT * FROM {TABLE_POLICY} "
            f"WHERE is_enabled = true AND policy_date_from <= %(d)s "
            f"AND (policy_date_to IS NULL OR policy_date_to >= %(d)s) "
            f"ORDER BY program_code, version DESC",
            {"d": d}
        )
        rows = cur.fetchall()

        # Take latest version per program
        seen = set()
        programs = []
        for r in rows:
            if r["program_code"] not in seen:
                seen.add(r["program_code"])
                programs.append(_row_to_dict(r))

        if not programs:
            return {"active": False, "programs": [], "message": "No policy found. Call seed_default_policy()."}

        return {
            "active": True,
            "date": d,
            "programs": sorted(programs, key=lambda p: p["priority_rank"]),
            "total_programs": len(programs),
        }


def get_policy_versions(program_code: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if program_code:
            cur.execute(
                f"SELECT * FROM {TABLE_POLICY} WHERE program_code = %(p)s ORDER BY version DESC",
                {"p": program_code}
            )
        else:
            cur.execute(f"SELECT * FROM {TABLE_POLICY} ORDER BY program_code, version DESC")
        rows = cur.fetchall()
        return {"versions": [_row_to_dict(r) for r in rows], "count": len(rows)}


# ── SEED ──

def seed_default_policy() -> Dict[str, Any]:
    existing = get_active_policy()
    if existing.get("active") and existing.get("programs"):
        return {"seeded": False, "message": "Policy already exists", "policy": existing}

    with get_db() as conn:
        cur = conn.cursor()
        count = 0
        for p in DEFAULT_POLICY:
            cur.execute(
                f"INSERT INTO {TABLE_POLICY} "
                f"(version, policy_date_from, program_code, priority_rank, allocation_mode, policy_reason, created_by) "
                f"VALUES (1, %(pds)s, %(pc)s, %(pr)s, %(am)s, %(reason)s, 'system')",
                {"pds": "2026-01-01", "pc": p["program_code"], "pr": p["priority_rank"],
                 "am": p["allocation_mode"], "reason": p["policy_reason"]}
            )
            count += 1
        conn.commit()

    return {"seeded": True, "message": f"Seeded {count} default policies", "policy": get_active_policy()}


# ── SIMULATE ──

def simulate_policy(date: str, policy_payload: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.yego_lima_priority_allocation_service import _get_actionable_counts
    from app.services.yego_lima_capacity_service import get_capacity_config

    actionable_by_prog = _get_actionable_counts(date)
    cap = get_capacity_config(date)
    total_capacity = cap.get("total_capacity", 310)
    total_actionable = sum(actionable_by_prog.values())

    programs_payload = policy_payload.get("programs", [])
    programs_payload.sort(key=lambda p: p.get("priority_rank", 999))

    programs = []
    remaining = total_capacity

    for pp in programs_payload:
        code = pp.get("program_code", "")
        mode = pp.get("allocation_mode", "STRICT_PRIORITY")
        min_cap = pp.get("min_daily_capacity")
        max_cap = pp.get("max_daily_capacity")
        target_pct = pp.get("target_share_pct")
        enabled = pp.get("is_enabled", True)
        priority = pp.get("priority_rank", 999)

        avail = actionable_by_prog.get(code, 0)
        assigned = 0

        if not enabled:
            programs.append({"program_code": code, "actionable": avail, "assigned": 0,
                             "unmet": avail, "priority_rank": priority, "enabled": False,
                             "reason": "Program disabled"})
            continue

        if mode == "STRICT_PRIORITY":
            assigned = min(avail, remaining)
            if max_cap: assigned = min(assigned, max_cap)
            if min_cap and avail > 0: assigned = max(assigned, min(min_cap, avail))
        elif mode == "PROPORTIONAL":
            share = avail / max(1, total_actionable) if target_pct is None else target_pct / 100
            assigned = min(avail, max(1, int(total_capacity * share)))
            if max_cap: assigned = min(assigned, max_cap)
            if min_cap and avail > 0: assigned = max(assigned, min(min_cap, avail))
        elif mode == "HYBRID":
            max_from_pct = int(total_capacity * (target_pct / 100)) if target_pct else total_capacity
            if max_cap: max_from_pct = min(max_from_pct, max_cap)
            assigned = min(avail, remaining, max_from_pct)
            if min_cap and avail > 0: assigned = max(assigned, min(min_cap, avail))

        assigned = min(assigned, remaining)
        remaining -= assigned

        programs.append({
            "program_code": code,
            "actionable": avail,
            "assigned": assigned,
            "unmet": max(0, avail - assigned),
            "priority_rank": priority,
            "enabled": enabled,
            "allocation_mode": mode,
            "min_cap_applied": min_cap,
            "max_cap_applied": max_cap,
            "reason": f"{mode}: {assigned}/{avail} assigned"
        })

    return {
        "date": date,
        "total_actionable": total_actionable,
        "total_capacity": total_capacity,
        "total_assigned": sum(p["assigned"] for p in programs),
        "unassigned_total": sum(p["unmet"] for p in programs),
        "remaining_capacity": remaining,
        "programs": programs,
    }


# ── VALIDATE ──

def validate_policy(policy_payload: Dict[str, Any]) -> Dict[str, Any]:
    errors = []
    warnings = []
    programs = policy_payload.get("programs", [])

    if not programs:
        errors.append("At least one program required")

    valid_codes = {"PROGRAM_HIGH_VALUE_RECOVERY", "PROGRAM_CHURN_PREVENTION",
                   "PROGRAM_14_90", "PROGRAM_ACTIVE_GROWTH"}
    ranks = []
    shares = []
    for i, p in enumerate(programs):
        code = p.get("program_code", "")
        rank = p.get("priority_rank", 0)
        mode = p.get("allocation_mode", "STRICT_PRIORITY")
        min_cap = p.get("min_daily_capacity")
        max_cap = p.get("max_daily_capacity")
        share = p.get("target_share_pct")
        enabled = p.get("is_enabled", True)

        if not code: errors.append(f"Program [{i}]: missing program_code")
        elif code not in valid_codes:
            errors.append(f"Program {code}: not in static registry")

        if not rank: errors.append(f"Program {code}: missing priority_rank")
        if mode not in ("STRICT_PRIORITY", "PROPORTIONAL", "HYBRID"):
            errors.append(f"Program {code}: invalid allocation_mode '{mode}'")
        if rank in ranks: warnings.append(f"Program {code}: duplicate priority_rank {rank}")
        ranks.append(rank)

        if min_cap is not None and min_cap < 0:
            errors.append(f"Program {code}: min_daily_capacity must be >= 0")
        if max_cap is not None and max_cap < 0:
            errors.append(f"Program {code}: max_daily_capacity must be >= 0")
        if min_cap is not None and max_cap is not None and min_cap > max_cap:
            errors.append(f"Program {code}: min ({min_cap}) > max ({max_cap})")
        if share is not None and (share < 0 or share > 100):
            errors.append(f"Program {code}: target_share_pct must be 0-100")
        if share is not None and enabled:
            shares.append(share)

    if shares and sum(shares) > 100:
        warnings.append(f"Sum of target_share_pct ({sum(shares)}%) exceeds 100%")

    enabled_programs = [p for p in programs if p.get("is_enabled", True)]
    if len(enabled_programs) == 0:
        errors.append("At least one program must be enabled")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# ── AUDIT LOG ──

TABLE_AUDIT = "growth.yego_lima_program_capacity_policy_audit"


def _write_audit(policy_id: str, action: str, detail: Optional[Dict] = None, created_by: str = "system"):
    try:
        import json
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE_AUDIT} (policy_id, action, detail, created_by) "
                f"VALUES (%(pid)s, %(a)s, %(d)s, %(cb)s)",
                {"pid": policy_id, "a": action,
                 "d": json.dumps(detail) if detail else None, "cb": created_by}
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")


def get_audit_log(limit: int = 50) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT a.*, p.program_code FROM {TABLE_AUDIT} a "
            f"LEFT JOIN {TABLE_POLICY} p ON p.id = a.policy_id "
            f"ORDER BY a.created_at DESC LIMIT %(lim)s",
            {"lim": limit}
        )
        rows = cur.fetchall()
        return {"entries": [{**dict(r), "id": str(r["id"]), "policy_id": str(r["policy_id"]) if r.get("policy_id") else None} for r in rows], "count": len(rows)}


# ── ACTIVATION GUARDRAILS ──

def save_draft(programs: List[Dict[str, Any]], created_by: str = "system") -> Dict[str, Any]:
    validation = validate_policy({"programs": programs})
    if not validation["valid"]:
        return {"saved": False, "error": "Validation failed", "validation": validation}

    with get_db() as conn:
        cur = conn.cursor()
        for p in programs:
            cur.execute(
                f"INSERT INTO {TABLE_POLICY} "
                f"(version, policy_date_from, program_code, priority_rank, allocation_mode, "
                f" min_daily_capacity, max_daily_capacity, target_share_pct, is_enabled, "
                f" policy_reason, policy_status, created_by) "
                f"VALUES ((SELECT COALESCE(MAX(version),0)+1 FROM {TABLE_POLICY} WHERE program_code=%(pc)s), "
                f" CURRENT_DATE, %(pc)s, %(pr)s, %(am)s, %(min)s, %(max)s, %(ts)s, %(en)s, "
                f" %(reason)s, 'DRAFT', %(cb)s) "
                f"RETURNING id",
                {"pc": p.get("program_code", ""), "pr": p.get("priority_rank", 0),
                 "am": p.get("allocation_mode", "STRICT_PRIORITY"),
                 "min": p.get("min_daily_capacity"), "max": p.get("max_daily_capacity"),
                 "ts": p.get("target_share_pct"), "en": p.get("is_enabled", True),
                 "reason": p.get("policy_reason"), "cb": created_by}
            )
            pid = str(cur.fetchone()[0])
            _write_audit(pid, "DRAFT_CREATED", {"program_code": p.get("program_code")}, created_by)
        conn.commit()

    return {"saved": True, "message": f"Draft saved for {len(programs)} programs", "validation": validation}


def validate_draft(date: str) -> Dict[str, Any]:
    policy = get_active_policy(date)
    if not policy.get("active"):
        return {"valid": False, "errors": ["No active policy found to validate against"]}

    simulation = simulate_policy(date, policy)
    validation = validate_policy(policy)

    errors = list(validation.get("errors", []))
    warnings = list(validation.get("warnings", []))

    if simulation["total_assigned"] == 0:
        errors.append("Simulation produced 0 assigned slots — policy may be misconfigured")

    for prog in simulation.get("programs", []):
        if prog.get("actionable", 0) > 0 and prog.get("assigned", 0) == 0 and prog.get("enabled", True):
            warnings.append(f"{prog['program_code']}: has actionable ({prog['actionable']}) but gets 0 assigned")
        if prog.get("assigned", 0) > simulation["total_capacity"] * 0.8:
            warnings.append(f"{prog['program_code']}: consumes >80% of total capacity")

    risk_level = "low"
    if errors: risk_level = "high"
    elif len(warnings) > 2: risk_level = "medium"

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "risk_level": risk_level,
        "simulation_snapshot": simulation,
    }


def activate_policy(date: str, created_by: str = "system") -> Dict[str, Any]:
    current = get_active_policy(date)
    if not current.get("active") or not current.get("programs"):
        return {"activated": False, "error": "No DRAFT/VALIDATED policy to activate"}

    validation = validate_draft(date)
    if not validation.get("valid"):
        return {"activated": False, "error": "Policy failed validation", "validation": validation}

    with get_db() as conn:
        cur = conn.cursor()
        for p in current["programs"]:
            pid = p.get("id")
            if not pid:
                continue
            # Retire current ACTIVE
            cur.execute(
                f"UPDATE {TABLE_POLICY} SET policy_status = 'RETIRED', policy_date_to = %(d)s, updated_at = now() "
                f"WHERE program_code = %(pc)s AND policy_status = 'ACTIVE'",
                {"d": date, "pc": p["program_code"]}
            )
            # Activate the draft
            cur.execute(
                f"UPDATE {TABLE_POLICY} SET policy_status = 'ACTIVE', policy_date_from = %(d)s, "
                f"policy_date_to = NULL, updated_at = now() "
                f"WHERE id = %(pid)s AND policy_status IN ('DRAFT', 'VALIDATED')",
                {"d": date, "pid": pid}
            )
            if cur.rowcount > 0:
                _write_audit(pid, "ACTIVATED",
                             {"program_code": p["program_code"], "effective_date": date}, created_by)
        conn.commit()

    return {"activated": True, "message": f"Policy activated for {len(current['programs'])} programs",
            "validation": validation}


def retire_policy(program_code: str, created_by: str = "system") -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {TABLE_POLICY} SET policy_status = 'RETIRED', policy_date_to = CURRENT_DATE, "
            f"updated_at = now() WHERE program_code = %(pc)s AND policy_status = 'ACTIVE' "
            f"RETURNING id",
            {"pc": program_code}
        )
        rows = cur.fetchall()
        for r in rows:
            _write_audit(str(r[0]), "RETIRED", {"program_code": program_code}, created_by)
        conn.commit()
        return {"retired": len(rows) > 0, "count": len(rows),
                "message": f"Retired {len(rows)} active policies for {program_code}"}

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
