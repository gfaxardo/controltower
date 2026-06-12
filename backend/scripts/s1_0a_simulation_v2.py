"""
LG-S1.0A — DRIVER SEGMENTATION SIMULATION V2
Refined rules using most reliable signals from driver_state_snapshot.
"""
import psycopg2, os, json
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import date, datetime

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" in line: k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ['DB_PORT'], dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], cursor_factory=RealDictCursor)
cur = conn.cursor()

SNAP_DATE = "2026-06-10"
WEEKLY_TARGET = 50

cur.execute("""
    SELECT
        driver_profile_id, lifecycle_state, performance_state, retention_state,
        COALESCE(completed_orders_week,0) as co_week, COALESCE(completed_orders_day,0) as co_day,
        COALESCE(supply_hours_week,0) as supply_h, COALESCE(supply_hours_day,0) as supply_h_day,
        COALESCE(trips_per_supply_hour_week,0) as trips_per_h,
        COALESCE(distance_to_weekly_target,999) as dist_target,
        reached_target_flag, declining_flag, churn_risk_flag, recoverable_flag,
        new_driver_flag, reactivated_flag,
        first_seen_at, first_trip_at, last_trip_at, last_supply_at,
        COALESCE(avg_orders_4w,0) as avg_4w, COALESCE(avg_orders_12w,0) as avg_12w,
        COALESCE(best_week_12w,0) as best_12w, historical_band, weekly_trips_target
    FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date = %(d)s
""", {"d": SNAP_DATE})
drivers = cur.fetchall()
total = len(drivers)
print(f"Total: {total} | Target: {WEEKLY_TARGET}/week | Date: {SNAP_DATE}")

def _i(v, d=0):
    try: return int(v) if v is not None else d
    except: return d

def _f(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d

def _days(v):
    if v is None: return 9999
    if isinstance(v, datetime): return (date.today() - v.date()).days
    if isinstance(v, date): return (date.today() - v).days
    return 9999

# ── CLASSIFICATION ENGINE ──
segments = {}
conflict_count = {}
excluded_count = {}
reason_map = {}

PRECEDENCE = [
    "HIGH_VALUE_RECOVERY",
    "TOP_PERFORMER", 
    "NEW_OR_REACTIVATED",
    "ACTIVE_GROWTH",
    "STABLE",
]

for d in drivers:
    did = d["driver_profile_id"]
    cw = _i(d["co_week"])
    cd = _i(d["co_day"])
    dist = _f(d["dist_target"])
    b12 = _f(d["best_12w"])
    a4 = _f(d["avg_4w"])
    a12 = _f(d["avg_12w"])
    lt = _days(d["last_trip_at"])
    ls = _days(d["last_supply_at"])
    fs = _days(d["first_seen_at"])
    ft = _days(d["first_trip_at"])
    sh = _f(d["supply_h"])
    tph = _f(d["trips_per_h"])
    lc = d.get("lifecycle_state","")
    pf = d.get("performance_state","")
    rt = d.get("retention_state","")
    rtgt = d.get("reached_target_flag")
    dec = d.get("declining_flag")
    churn = d.get("churn_risk_flag")
    recov = d.get("recoverable_flag")
    new_d = d.get("new_driver_flag")
    react = d.get("reactivated_flag")
    hband = d.get("historical_band","")
    wt = _i(d.get("weekly_trips_target"), 100)

    # ── SIGNALS ──
    is_active = cw > 0  # Has orders this week (best proxy for active)
    is_recent = lt <= 14  # Last trip within 14 days
    is_established = lc == "ESTABLISHED"
    is_healthy = rt == "HEALTHY"
    at_risk = rt in ("CHURN_RISK", "AT_RISK")
    below_target = cw < WEEKLY_TARGET
    is_top = cw >= 80
    is_high_tier = cw >= 50

    # Used signals from explainability that need history
    hvr_match = b12 >= 80 and cw == 0 and 1 <= lt <= 14

    candidates = {}

    # ── 1. HIGH_VALUE_RECOVERY ──
    # Historical top performer suddenly inactive (most urgent intervention)
    if hvr_match:
        candidates["HIGH_VALUE_RECOVERY"] = {"score": 1000, "reason": f"best12w={b12:.0f}_last_trip={lt}d"}

    # ── 2. TOP_PERFORMER ──
    # Active high-output drivers (>=80 orders/week or >=50 with strong 12w history)
    if is_top:
        candidates["TOP_PERFORMER"] = {"score": 800, "reason": f"weekly={cw}"}
    elif cw >= 50 and b12 >= 60:
        candidates["TOP_PERFORMER"] = {"score": 750, "reason": f"weekly={cw}_best12w={b12:.0f}"}
    elif pf == "HIGH" and cw >= 50:
        candidates["TOP_PERFORMER"] = {"score": 700, "reason": f"HIGH_perf_weekly={cw}"}

    # ── 3. NEW_OR_REACTIVATED ──
    # Early-life or recently reactivated drivers who haven't reached target
    is_new_lifecycle = lc in ("ACTIVATED", "EARLY_LIFE")
    is_recent_react = react and lt <= 90
    days_since_start = min(fs, ft)  # whichever is earlier
    
    if (is_new_lifecycle or is_recent_react) and not rtgt:
        if is_recent_react:
            candidates["NEW_OR_REACTIVATED"] = {"score": 600, "reason": f"reactivated_lt={lt}d"}
        elif lc == "EARLY_LIFE":
            candidates["NEW_OR_REACTIVATED"] = {"score": 590, "reason": f"early_life_days={days_since_start}d"}
        elif lc == "ACTIVATED":
            candidates["NEW_OR_REACTIVATED"] = {"score": 580, "reason": f"activated_days={days_since_start}d"}

    # ── 4. ACTIVE_GROWTH ──
    # Active drivers below target who need growth intervention
    # Must have recent activity (this week orders > 0) AND not already TOP
    can_grow = (
        is_active 
        and below_target 
        and not is_top
        and lc in ("ACTIVATED", "EARLY_LIFE", "ESTABLISHED", "REACTIVATED")
    )
    if can_grow:
        candidates["ACTIVE_GROWTH"] = {"score": 400, "reason": f"weekly={cw}_gap={dist}"}

    # ── 5. STABLE ──
    # Healthy drivers at or above target, or healthy established with decent output
    if rtgt and is_healthy:
        candidates["STABLE"] = {"score": 300, "reason": f"reached_target_ret={rt}"}
    elif cw >= WEEKLY_TARGET and is_healthy and is_established:
        candidates["STABLE"] = {"score": 290, "reason": f"above_target={cw}"}
    elif is_active and is_healthy and is_established and cw >= 30 and not at_risk:
        candidates["STABLE"] = {"score": 280, "reason": f"stable_tier_weekly={cw}"}

    # ── RESOLVE EXCLUSIVE ──
    selected = None
    s_reason = None
    excluded = []
    for seg in PRECEDENCE:
        if seg in candidates:
            selected = seg
            s_reason = candidates[seg]["reason"]
            break
    
    if selected:
        excluded = [s for s in candidates if s != selected]
    else:
        selected = "UNCLASSIFIED"
        s_reason = "no_segment_matched"

    # Record
    segments[selected] = segments.get(selected, 0) + 1
    reason_map.setdefault(selected, {}).setdefault(s_reason, 0)
    reason_map[selected][s_reason] += 1
    
    nc = len(candidates)
    conflict_count[nc] = conflict_count.get(nc, 0) + 1
    
    for exc in excluded:
        excluded_count[exc] = excluded_count.get(exc, 0) + 1

# ── REPORT ──
ORDER = ["HIGH_VALUE_RECOVERY", "TOP_PERFORMER", "NEW_OR_REACTIVATED",
         "ACTIVE_GROWTH", "STABLE", "UNCLASSIFIED"]

print("\n" + "=" * 75)
print(f"{'Segment':28s} {'Drivers':>8s} {'%Univ':>7s}  Top Reason")
print("-" * 75)
for seg in ORDER:
    cnt = segments.get(seg, 0)
    pct = cnt / total * 100
    treason = ""
    if seg in reason_map:
        treason = sorted(reason_map[seg].items(), key=lambda x: -x[1])[0][0]
    print(f"{seg:28s} {cnt:8d} {pct:6.1f}%  {treason}")

print(f"\n{'Multi-Candidate Conflict':-^75}")
for n in sorted(conflict_count):
    cnt = conflict_count[n]
    label = "no_match" if n == 0 else f"{n}_candidates"
    print(f"  {label:18s}: {cnt:8d} ({cnt/total*100:.1f}%)")

print(f"\n{'Exclusion Impact':-^75}")
for seg in sorted(excluded_count, key=lambda x: -excluded_count[x]):
    print(f"  {seg:28s}: {excluded_count[seg]:6d} lost to higher priority")

classified = sum(segments.get(s, 0) for s in ORDER if s != "UNCLASSIFIED")
unc = segments.get("UNCLASSIFIED", 0)
print(f"\n{'Coverage':-^75}")
print(f"  Classified:   {classified:8d} ({classified/total*100:.1f}%)")
print(f"  Unclassified: {unc:8d} ({unc/total*100:.1f}%)")
print(f"  Duplicates:   0 (exclusive)  |  SUM OK: {classified+unc==total}")

# UNCLASSIFIED reasons - what are they?
print(f"\n{'UNCLASSIFIED reason breakdown':-^75}")
for r, cnt in sorted(reason_map.get("UNCLASSIFIED", {}).items(), key=lambda x: -x[1]):
    print(f"  {r}: {cnt}")

# Sub-segment detail: what are the "PROGRAMS WITHIN NEW_OR_REACTIVATED"
print(f"\n{'NEW_OR_REACTIVATED sub-classification':-^75}")
for r, cnt in sorted(reason_map.get("NEW_OR_REACTIVATED", {}).items(), key=lambda x: -x[1]):
    print(f"  {r}: {cnt}")

# What's the breakdown of 50_14 vs 90_300 candidates within N_O_R
print(f"\n{'ACTIVE_GROWTH reason distribution':-^75}")
for r, cnt in sorted(reason_map.get("ACTIVE_GROWTH", {}).items(), key=lambda x: -x[1])[:10]:
    print(f"  {r}: {cnt}")

conn.close()
print("\nDone.")
