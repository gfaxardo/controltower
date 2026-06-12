"""
LG-S1.0A — DRIVER SEGMENTATION SIMULATION V3 (Final Calibration)
STABLE = healthy established active (no intervention)
ACTIVE_GROWTH = below target WITH risk/recovery signals
"""
import psycopg2, os
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

def _i(v, d=0):
    try: return int(v) if v is not None else d
    except: return d
def _f(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d
def _days(v):
    if v is None: return 9999
    try: return (date.today() - v.date()).days
    except: return 9999

segments = {}
conflict_count = {}
excluded_count = {}
reason_map = {}

PRECEDENCE = [
    "HIGH_VALUE_RECOVERY",  # 1
    "TOP_PERFORMER",         # 2
    "NEW_OR_REACTIVATED",    # 3 (includes 50_14 and 90_300 as sub-programs)
    "ACTIVE_GROWTH",         # 4
    "STABLE",                # 5
]

for d in drivers:
    cw = _i(d["co_week"])
    cd = _i(d["co_day"])
    dist = _f(d["dist_target"])
    b12 = _f(d["best_12w"])
    a4 = _f(d["avg_4w"])
    a12 = _f(d["avg_12w"])
    lt = _days(d["last_trip_at"])
    fs = _days(d["first_seen_at"])
    ft = _days(d["first_trip_at"])
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

    candidates = {}

    # ── 1. HIGH_VALUE_RECOVERY ──
    if b12 >= 80 and cw == 0 and 1 <= lt <= 14:
        candidates["HIGH_VALUE_RECOVERY"] = {"score": 1000, "reason": f"best12w={b12:.0f}_inactive={lt}d"}

    # ── 2. TOP_PERFORMER ──
    if cw >= 80:
        candidates["TOP_PERFORMER"] = {"score": 800, "reason": f"weekly={cw}"}
    elif cw >= 50 and b12 >= 60:
        candidates["TOP_PERFORMER"] = {"score": 750, "reason": f"weekly={cw}_best12w={b12:.0f}"}
    elif pf == "HIGH" and cw >= 50:
        candidates["TOP_PERFORMER"] = {"score": 700, "reason": f"HIGH_perf_weekly={cw}"}

    # ── 3. NEW_OR_REACTIVATED ──
    is_new_lc = lc in ("ACTIVATED", "EARLY_LIFE")
    is_react = react and lt <= 90
    days_since_start = min(fs, ft)
    if (is_new_lc or is_react) and not rtgt:
        if is_react:
            candidates["NEW_OR_REACTIVATED"] = {"score": 600, "reason": f"reactivated_lt={lt}d"}
        elif lc == "EARLY_LIFE":
            candidates["NEW_OR_REACTIVATED"] = {"score": 590, "reason": f"early_life_days={days_since_start}d"}
        elif lc == "ACTIVATED":
            candidates["NEW_OR_REACTIVATED"] = {"score": 580, "reason": f"activated_days={days_since_start}d"}

    # ── 4. ACTIVE_GROWTH ──
    # Underperforming drivers with intervention signals:
    # - Below target AND (declining OR churn_risk OR recoverable OR at_risk retention)
    # - Must be in active lifecycle
    can_grow_lc = lc in ("ACTIVATED", "EARLY_LIFE", "ESTABLISHED", "REACTIVATED")
    needs_intervention = (
        dec or churn or recov or (rt in ("AT_RISK", "CHURN_RISK"))
    )
    below_t = cw < WEEKLY_TARGET and dist > 0
    not_top = cw < 80
    
    if can_grow_lc and below_t and needs_intervention and not_top:
        sigs = []
        if dec: sigs.append("declining")
        if churn: sigs.append("churn_risk")
        if recov: sigs.append("recoverable")
        if rt in ("AT_RISK", "CHURN_RISK"): sigs.append(rt)
        candidates["ACTIVE_GROWTH"] = {"score": 400, "reason": f"weekly={cw}_gap={dist}_signals={'+'.join(sigs)}"}

    # ── 5. STABLE ──
    # Active healthy established drivers without intervention signals
    # OR drivers who have reached target
    if rtgt:
        candidates["STABLE"] = {"score": 300, "reason": f"reached_target_ret={rt}"}
    elif lc == "ESTABLISHED" and rt == "HEALTHY" and cw > 0 and not needs_intervention:
        candidates["STABLE"] = {"score": 250, "reason": f"stable_healthy_weekly={cw}"}
    elif can_grow_lc and not needs_intervention and cw > 0:
        candidates["STABLE"] = {"score": 200, "reason": f"active_no_signal_weekly={cw}"}

    # ── RESOLVE ──
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

print("\n" + "=" * 80)
print(f"LG-S1.0A — FINAL SEGMENTATION SIMULATION | Date={SNAP_DATE} | Target={WEEKLY_TARGET}/week | N={total}")
print("=" * 80)
print(f"{'Segment':28s} {'Drivers':>8s} {'%Univ':>7s}  {'Conflict':>10s}  Top Reason")
print("-" * 80)

for seg in ORDER:
    cnt = segments.get(seg, 0)
    pct = cnt / total * 100
    treason = ""
    if seg in reason_map:
        treason = sorted(reason_map[seg].items(), key=lambda x: -x[1])[0][0]
    # Count how many drivers in this segment had multi-candidate conflicts
    print(f"{seg:28s} {cnt:8d} {pct:6.1f}%            {treason}")

print(f"\n{'Conflict Distribution':-^80}")
for n in sorted(conflict_count):
    cnt = conflict_count[n]
    pct = cnt / total * 100
    label = "no_match" if n == 0 else f"{n}_candidates"
    print(f"  {label:18s}: {cnt:8d} ({pct:5.1f}%)")

print(f"\n{'Exclusion Impact (lost to higher priority)':-^80}")
for seg in sorted(excluded_count, key=lambda x: -excluded_count[x]):
    if excluded_count[seg] > 0:
        print(f"  {seg:28s}: {excluded_count[seg]:6d}")

classified = sum(segments.get(s, 0) for s in ORDER if s != "UNCLASSIFIED")
unc = segments.get("UNCLASSIFIED", 0)
print(f"\n{'VALIDATION':-^80}")
print(f"  Coverage:    {classified/total*100:.1f}% ({classified}/{total})")
print(f"  Unclassified: {unc} ({unc/total*100:.1f}%)")
print(f"  Duplicates:   0 (exclusive precedence)")
print(f"  SUM OK:       {classified+unc==total}")

# Cross tab: performance vs segment
print(f"\n{'Performance State × Segment':-^80}")
cur.execute("""
    SELECT s.performance_state, COUNT(*) as cnt
    FROM growth.yango_lima_driver_state_snapshot s
    WHERE s.snapshot_date = %(d)s
    GROUP BY 1 ORDER BY 2 DESC
""", {"d": SNAP_DATE})
print(f"  {'Performance':20s} {'Total':>8s}  {'%':>6s}")
for r in cur.fetchall():
    pf = r["performance_state"]
    cnt = r["cnt"]
    print(f"  {pf:20s} {cnt:8d}  {cnt/total*100:5.1f}%")

# Quick sub-program breakdown: 50_14 vs 90_300 within NEW_OR_REACTIVATED
print(f"\n{'50_14 / 90_300 SUB-PROGRAM POTENTIAL (within NEW_OR_REACTIVATED)':-^80}")
# Query: drivers in NEW_OR_REACTIVATED segment who could be 50_14 vs 90_300
cur.execute("""
    WITH nor AS (
        SELECT driver_profile_id, lifecycle_state, first_seen_at, reactivated_flag,
               COALESCE(completed_orders_week,0) as co_week
        FROM growth.yango_lima_driver_state_snapshot
        WHERE snapshot_date = %(d)s
          AND lifecycle_state IN ('ACTIVATED', 'EARLY_LIFE')
          AND reached_target_flag = false
    )
    SELECT 
        CASE 
            WHEN lifecycle_state = 'EARLY_LIFE' THEN '50_14_candidate'
            ELSE '90_300_candidate'
        END as sub_type,
        COUNT(*) as cnt
    FROM nor
    GROUP BY 1
""", {"d": SNAP_DATE})
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
print("\nDone.")
