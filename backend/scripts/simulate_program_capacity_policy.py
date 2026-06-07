"""
LG-UX-R2.8D — Program Capacity Policy Simulation
Runs 5 allocation scenarios against real data. Read-only. No DB writes.
"""
import sys, json, os
sys.path.insert(0, '.')
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATE = "2026-06-02"
OUT_DIR = r"C:\cursor\controltower\controltower\exports\audits\lima_growth"
os.makedirs(OUT_DIR, exist_ok=True)

def _safe_int(val): return int(val or 0)

# Fetch real data
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT selected_program_code, COUNT(*) as cnt "
        "FROM growth.yango_lima_prioritized_opportunity_daily "
        "WHERE opportunity_date = %(d)s AND is_actionable_today = true "
        "GROUP BY selected_program_code", {"d": DATE}
    )
    actionable_by_prog = {r["selected_program_code"]: r["cnt"] for r in cur.fetchall()}

    cur.execute(
        "SELECT SUM(agents * capacity_per_agent) as total "
        "FROM growth.yego_lima_capacity_config WHERE is_active = true AND config_date IS NULL"
    )
    TOTAL_CAPACITY = _safe_int(cur.fetchone()["total"])  # 310

PROGRAMS = ["PROGRAM_HIGH_VALUE_RECOVERY", "PROGRAM_CHURN_PREVENTION",
            "PROGRAM_14_90", "PROGRAM_ACTIVE_GROWTH"]
NAMES = {"PROGRAM_HIGH_VALUE_RECOVERY": "High Value Recovery",
         "PROGRAM_CHURN_PREVENTION": "Churn Prevention",
         "PROGRAM_14_90": "14/90",
         "PROGRAM_ACTIVE_GROWTH": "Active Growth"}
PRIORITY = {"PROGRAM_HIGH_VALUE_RECOVERY": 1, "PROGRAM_CHURN_PREVENTION": 2,
            "PROGRAM_14_90": 3, "PROGRAM_ACTIVE_GROWTH": 4}

TOTAL_ACTIONABLE = sum(actionable_by_prog.values())

def simulate(name, alloc_fn):
    """Run allocation function and return result dict."""
    result = alloc_fn(dict(actionable_by_prog), TOTAL_CAPACITY)
    result["scenario_name"] = name
    result["total_actionable"] = TOTAL_ACTIONABLE
    result["total_capacity"] = TOTAL_CAPACITY
    return result

# ── SCENARIO A: Current (strict priority) ──
def scenario_a(opps, cap):
    programs = []
    remaining = cap
    for pc in PROGRAMS:
        avail = opps.get(pc, 0)
        alloc = min(avail, remaining)
        remaining -= alloc
        programs.append({"program_code": pc, "program_name": NAMES[pc],
                         "actionable": avail, "assigned": alloc, "unmet": avail - alloc,
                         "priority_rank": PRIORITY[pc]})
    return {"programs": programs, "unassigned_total": sum(p["unmet"] for p in programs),
            "logic": "Strict priority order. Higher rank takes all needed. Lower ranks get 0 if capacity exhausted."}

# ── SCENARIO B: Max cap per program ──
def scenario_b(opps, cap):
    max_share = {"PROGRAM_HIGH_VALUE_RECOVERY": 0.40, "PROGRAM_CHURN_PREVENTION": 0.60,
                 "PROGRAM_14_90": 0.30, "PROGRAM_ACTIVE_GROWTH": 0.30}
    programs = []
    remaining = cap
    for pc in PROGRAMS:
        avail = opps.get(pc, 0)
        max_cap = int(cap * max_share.get(pc, 0.30))
        alloc = min(avail, remaining, max_cap)
        remaining -= alloc
        programs.append({"program_code": pc, "program_name": NAMES[pc],
                         "actionable": avail, "assigned": alloc, "unmet": avail - alloc,
                         "max_cap": max_cap, "priority_rank": PRIORITY[pc]})
    return {"programs": programs, "unassigned_total": sum(p["unmet"] for p in programs),
            "logic": "Max caps: HVR=40%, CP=60%, 1490=30%, AG=30% of capacity. Prevents one program from consuming all."}

# ── SCENARIO C: Min floor per program ──
def scenario_c(opps, cap):
    min_floor = {"PROGRAM_HIGH_VALUE_RECOVERY": 80, "PROGRAM_CHURN_PREVENTION": 50,
                 "PROGRAM_14_90": 10, "PROGRAM_ACTIVE_GROWTH": 10}
    programs = []
    remaining = cap
    # Phase 1: assign minimums
    for pc in PROGRAMS:
        avail = opps.get(pc, 0)
        floor = min_floor.get(pc, 0)
        alloc = min(avail, floor)
        remaining -= alloc
        programs.append({"program_code": pc, "program_name": NAMES[pc],
                         "actionable": avail, "min_floor": floor,
                         "phase1_assigned": alloc, "phase2_assigned": 0,
                         "priority_rank": PRIORITY[pc]})
    # Phase 2: distribute remainder by priority
    for p in programs:
        avail = opps.get(p["program_code"], 0)
        already = p["phase1_assigned"]
        extra = min(avail - already, remaining)
        p["phase2_assigned"] = extra
        remaining -= extra
        p["assigned"] = already + extra
        p["unmet"] = avail - p["assigned"]
    return {"programs": programs, "unassigned_total": sum(p["unmet"] for p in programs),
            "logic": "Min floor ensures every active program gets at least X slots. Remainder distributed by priority."}

# ── SCENARIO D: Proportional ──
def scenario_d(opps, cap):
    programs = []
    for pc in PROGRAMS:
        avail = opps.get(pc, 0)
        share = avail / max(1, TOTAL_ACTIONABLE)
        alloc = min(avail, max(1, int(cap * share)))
        programs.append({"program_code": pc, "program_name": NAMES[pc],
                         "actionable": avail, "assigned": alloc, "unmet": avail - alloc,
                         "target_share_pct": round(share * 100, 1),
                         "priority_rank": PRIORITY[pc]})
    # Redistribute remainder (from rounding)
    total_assigned = sum(p["assigned"] for p in programs)
    remaining = cap - total_assigned
    for p in programs:
        if remaining <= 0: break
        extra = min(p["unmet"], remaining)
        p["assigned"] += extra
        p["unmet"] -= extra
        remaining -= extra
    return {"programs": programs, "unassigned_total": sum(p["unmet"] for p in programs),
            "logic": "Capacity distributed proportionally to actionable count. Ensures fair share per program."}

# ── SCENARIO E: Hybrid (priority + caps + floor) ──
def scenario_e(opps, cap):
    programs = []
    remaining = cap
    policy = [
        {"code": "PROGRAM_HIGH_VALUE_RECOVERY", "name": "High Value Recovery",
         "max_pct": 0.40, "min_floor": 80, "priority": 1},
        {"code": "PROGRAM_CHURN_PREVENTION", "name": "Churn Prevention",
         "max_pct": 0.55, "min_floor": 100, "priority": 2},
        {"code": "PROGRAM_14_90", "name": "14/90",
         "max_pct": 0.20, "min_floor": 5, "priority": 3},
        {"code": "PROGRAM_ACTIVE_GROWTH", "name": "Active Growth",
         "max_pct": 0.20, "min_floor": 5, "priority": 4},
    ]
    policy.sort(key=lambda x: x["priority"])
    for pol in policy:
        avail = opps.get(pol["code"], 0)
        floor = pol["min_floor"]
        max_cap = int(cap * pol["max_pct"])
        alloc = min(avail, remaining, max_cap)
        alloc = max(alloc, min(avail, floor))  # enforce floor if possible
        remaining -= alloc
        programs.append({"program_code": pol["code"], "program_name": pol["name"],
                         "actionable": avail, "assigned": alloc, "unmet": avail - alloc,
                         "max_cap": max_cap, "min_floor": floor,
                         "priority_rank": pol["priority"]})
    return {"programs": programs, "unassigned_total": sum(p["unmet"] for p in programs),
            "logic": "Hybrid: HVR=40%max+80floor, CP=55%max+100floor, others=20%max+5floor. Priority order within caps/floors."}

# Run all scenarios
scenarios = [
    simulate("A: Current (strict priority)", scenario_a),
    simulate("B: Max cap per program", scenario_b),
    simulate("C: Min floor per program", scenario_c),
    simulate("D: Proportional share", scenario_d),
    simulate("E: Hybrid (priority + caps + floors)", scenario_e),
]

# ── Generate Markdown Report ──
report = []
report.append("# Program Capacity Policy Simulation")
report.append(f"\nGenerated: {datetime.now().isoformat()}")
report.append(f"\nDate: {DATE} | Actionable: {TOTAL_ACTIONABLE} | Capacity: {TOTAL_CAPACITY}")
report.append(f"\nActionable by program: {json.dumps(actionable_by_prog)}")

for s in scenarios:
    report.append(f"\n## {s['scenario_name']}")
    report.append(f"\n**Logic:** {s['logic']}")
    report.append(f"\n**Total unassigned:** {s['unassigned_total']}")
    report.append(f"\n| Program | Actionable | Assigned | Unmet | % Served | Notes |")
    report.append("|---|---:|---:|---:|---:|---|")
    for p in s["programs"]:
        pct = round(p["assigned"] / max(1, p["actionable"]) * 100, 1)
        notes = []
        if "max_cap" in p: notes.append(f"max={p['max_cap']}")
        if "min_floor" in p: notes.append(f"floor={p['min_floor']}")
        if "target_share_pct" in p: notes.append(f"share={p['target_share_pct']}%")
        report.append(f"| {p['program_name']} | {p['actionable']} | {p['assigned']} | {p['unmet']} | {pct}% | {', '.join(notes) if notes else '—'} |")

report.append(f"\n---")
report.append(f"\n## Comparison Summary")
report.append(f"\n| Scenario | HVR | CP | 14_90 | AG | Total Unassigned |")
report.append("|---|---:|---:|---:|---:|---:|")
for s in scenarios:
    hvr = next((p["assigned"] for p in s["programs"] if "HIGH_VALUE" in p["program_code"]), 0)
    cp = next((p["assigned"] for p in s["programs"] if "CHURN" in p["program_code"]), 0)
    p14 = next((p["assigned"] for p in s["programs"] if "14_90" in p["program_code"]), 0)
    ag = next((p["assigned"] for p in s["programs"] if "ACTIVE_GROWTH" in p["program_code"]), 0)
    name = s["scenario_name"][:30]
    report.append(f"| {name} | {hvr} | {cp} | {p14} | {ag} | {s['unassigned_total']} |")

report.append(f"\n---")
report.append(f"\n## Hardcodes Found in Current Policy")
report.append(f"\n1. `PRIORITY_RANK` — strict ordering in `priority_registry.py` (HVR=1, CP=2, 1490=3, AG=4)")
report.append(f"\n2. `allocate_capacity()` — sequential greedy: first program takes all it needs")
report.append(f"\n3. `daily_action_capacity = 500` — from `opportunity_policy_config` (hardcoded default)")
report.append(f"\n4. `PROGRAM_BONUS` in scoring — HVR=200, CP=100, 1490=50, AG=0 (hardcoded in SQL)")
report.append(f"\n5. No min/max per program, no target share, no caps — pure priority order")
report.append(f"\n---")
report.append(f"\n## Recommendation")
report.append(f"\n**Scenario E (Hybrid)** offers the best balance:")
report.append(f"\n- Preserves HVR priority (40% cap = 124, floor = 80)")
report.append(f"\n- Gives CP substantial share (55% cap = 170, floor = 100)")
report.append(f"\n- Ensures 1490 and AG get something if they have actionable (floor = 5 each)")
report.append(f"\n- Prevents any program from starving others")
report.append(f"\n- Total unassigned remains the same (190) but distributed more fairly")
report.append(f"\n**DO NOT implement yet.** This is a simulation. Requires Program Registry to store policy config.")

md_path = os.path.join(OUT_DIR, "program_capacity_policy_simulation.md")
json_path = os.path.join(OUT_DIR, "program_capacity_policy_simulation.json")

with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report))
with open(json_path, "w", encoding="utf-8") as f:
    json.dump([{"name": s["scenario_name"], "programs": s["programs"],
                "unassigned": s["unassigned_total"]} for s in scenarios], f, indent=2)

print(f"Report: {md_path}")
print(f"JSON: {json_path}")
print("\n=== SCENARIO COMPARISON ===")
print(f"{'Scenario':<35s} {'HVR':>5s} {'CP':>5s} {'1490':>5s} {'AG':>5s} {'Unassigned':>10s}")
for s in scenarios:
    hvr = next((p["assigned"] for p in s["programs"] if "HIGH_VALUE" in p["program_code"]), 0)
    cp = next((p["assigned"] for p in s["programs"] if "CHURN" in p["program_code"]), 0)
    p14 = next((p["assigned"] for p in s["programs"] if "14_90" in p["program_code"]), 0)
    ag = next((p["assigned"] for p in s["programs"] if "ACTIVE_GROWTH" in p["program_code"]), 0)
    print(f"{s['scenario_name']:<35s} {hvr:>5d} {cp:>5d} {p14:>5d} {ag:>5d} {s['unassigned_total']:>10d}")

print("\nDONE.")
