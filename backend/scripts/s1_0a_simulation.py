"""
LG-S1.0A — DRIVER SEGMENTATION SIMULATION
Classifies all drivers into exclusive segments using configurable rules.
Read-only. No DB modifications.
"""
import psycopg2
import os
import json
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import date, datetime, timedelta

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    cursor_factory=RealDictCursor,
)
cur = conn.cursor()

SNAP_DATE = "2026-06-10"

# ── Fetch ALL drivers with full metric panel ──
cur.execute(
    """
    SELECT
        s.driver_profile_id,
        s.lifecycle_state,
        s.performance_state,
        s.retention_state,
        COALESCE(s.completed_orders_week, 0) as completed_orders_week,
        COALESCE(s.completed_orders_day, 0) as completed_orders_day,
        COALESCE(s.supply_hours_week, 0) as supply_hours_week,
        COALESCE(s.supply_hours_day, 0) as supply_hours_day,
        COALESCE(s.trips_per_supply_hour_week, 0) as trips_per_supply_hour_week,
        COALESCE(s.distance_to_weekly_target, 999) as distance_to_weekly_target,
        s.reached_target_flag,
        s.declining_flag,
        s.churn_risk_flag,
        s.recoverable_flag,
        s.new_driver_flag,
        s.reactivated_flag,
        s.first_seen_at,
        s.first_trip_at,
        s.last_trip_at,
        s.last_supply_at,
        COALESCE(s.avg_orders_4w, 0) as avg_orders_4w,
        COALESCE(s.avg_orders_12w, 0) as avg_orders_12w,
        COALESCE(s.best_week_12w, 0) as best_week_12w,
        s.historical_band,
        s.weekly_trips_target
    FROM growth.yango_lima_driver_state_snapshot s
    WHERE s.snapshot_date = %(d)s
    """,
    {"d": SNAP_DATE},
)
drivers = cur.fetchall()
total = len(drivers)
print(f"Total drivers loaded: {total}")

# ── HELPER FUNCTIONS ──
def _i(v, default=0):
    if v is None: return default
    try: return int(v)
    except: return default

def _f(v, default=0.0):
    if v is None: return default
    try: return float(v)
    except: return default

def _days_since(dt_val):
    if dt_val is None: return 9999
    today = date.today()
    if isinstance(dt_val, datetime):
        return (today - dt_val.date()).days
    if isinstance(dt_val, date):
        return (today - dt_val).days
    return 9999

def _week_orders(d, offset):
    """Get orders from N weeks ago (1 = most recent)."""
    key = f"week_orders_{offset}w"
    return _i(d.get(key))

# ── SEGMENT CLASSIFICATION RULES ──
# Each segment is evaluated with configurable rules.
# Rules use a simple lambda-friendly interface.

TODAY = date.today()
WEEKLY_TARGET = 50  # Default target trips/week

def classify_drivers(drivers_list):
    segments = {}
    conflicts = {}
    excluded_map = {}
    reasons = {}

    for d in drivers_list:
        did = d["driver_profile_id"]
        co_week = _i(d["completed_orders_week"])
        co_day = _i(d["completed_orders_day"])
        dist_target = _f(d["distance_to_weekly_target"])
        best_12w = _f(d["best_week_12w"])
        last_trip_days = _days_since(d["last_trip_at"])
        avg_4w = _f(d.get("avg_orders_4w"))
        avg_12w = _f(d.get("avg_orders_12w"))
        lifecycle = d.get("lifecycle_state", "")
        performance = d.get("performance_state", "")
        retention = d.get("retention_state", "")
        reached_target = d.get("reached_target_flag")
        declining = d.get("declining_flag")
        churn_risk = d.get("churn_risk_flag")
        recoverable = d.get("recoverable_flag")
        new_driver = d.get("new_driver_flag")
        reactivated = d.get("reactivated_flag")
        first_seen_days = _days_since(d.get("first_seen_at"))
        first_trip_days = _days_since(d.get("first_trip_at"))
        last_supply_days = _days_since(d.get("last_supply_at"))
        supply_hours = _f(d["supply_hours_week"])
        trips_per_hour = _f(d.get("trips_per_supply_hour_week"))
        weekly_target = _i(d.get("weekly_trips_target"), 100)
        historical_band = d.get("historical_band", "")

        # ── RULE EVALUATION ──
        candidates = {}

        # --- NEW_OR_REACTIVATED ---
        # Drivers in early lifecycle stages + recent activation or reactivation
        # AND not yet reached target
        days_since_first_seen = first_seen_days
        is_early_life = lifecycle in ("ACTIVATED", "EARLY_LIFE") and days_since_first_seen <= 90
        is_recently_reactivated = reactivated and last_trip_days <= 30
        
        is_new_or_react = (
            (is_early_life or is_recently_reactivated)
            and not reached_target
        )
        if is_new_or_react:
            if is_recently_reactivated:
                candidates["NEW_OR_REACTIVATED"] = {
                    "score": 100,
                    "reason": f"reactivated_inactive={last_trip_days}d",
                }
            elif lifecycle == "EARLY_LIFE":
                candidates["NEW_OR_REACTIVATED"] = {
                    "score": 95,
                    "reason": f"early_life_seen={days_since_first_seen}d_orders={co_week}",
                }
            elif lifecycle == "ACTIVATED":
                candidates["NEW_OR_REACTIVATED"] = {
                    "score": 90,
                    "reason": f"activated_seen={days_since_first_seen}d_orders={co_week}",
                }

        # --- HIGH_VALUE_RECOVERY ---
        # Historically high performers (>80 trips best week) who are now inactive
        if best_12w >= 80 and co_week == 0 and 1 <= last_trip_days <= 14:
            candidates["HIGH_VALUE_RECOVERY"] = {
                "score": 200,
                "reason": f"best_week={best_12w:.0f}_inactive={last_trip_days}d",
            }

        # --- TOP_PERFORMER ---
        # Top percentile by current week orders
        if co_week >= 80:
            candidates["TOP_PERFORMER"] = {
                "score": 180,
                "reason": f"weekly_trips={co_week}",
            }
        elif co_week >= 50 and supply_hours >= 20:
            candidates["TOP_PERFORMER"] = {
                "score": 170,
                "reason": f"weekly_trips={co_week}_supply={supply_hours:.0f}h",
            }

        # --- ACTIVE_GROWTH ---
        # Active drivers with below-target performance
        is_active_lifecycle = lifecycle in ("ACTIVATED", "EARLY_LIFE", "ESTABLISHED", "REACTIVATED")
        is_below_target = dist_target > 0 and co_week < WEEKLY_TARGET
        has_recent_activity = last_trip_days <= 14
        not_top = co_week < 80

        if is_active_lifecycle and is_below_target and has_recent_activity and not_top:
            candidates["ACTIVE_GROWTH"] = {
                "score": 50,
                "reason": f"weekly={co_week}_target_gap={dist_target}",
            }

        # --- STABLE ---
        # Healthy active drivers at/above target
        if reached_target and performance in ("TARGET", "HIGH") and retention == "HEALTHY":
            candidates["STABLE"] = {
                "score": 40,
                "reason": f"performance={performance}_retention={retention}",
            }
        elif co_week >= WEEKLY_TARGET and lifecycle == "ESTABLISHED" and retention in ("HEALTHY", "WATCHLIST"):
            candidates["STABLE"] = {
                "score": 35,
                "reason": f"above_target={co_week}",
            }

        # ── PRIORITY RESOLUTION (exclusive precedence) ──
        PRECEDENCE = [
            "HIGH_VALUE_RECOVERY",   # 1: Highest operational urgency
            "TOP_PERFORMER",          # 2: Recognize excellence first
            "NEW_OR_REACTIVATED",     # 3: Early-life growth programs
            "ACTIVE_GROWTH",          # 4: Growth intervention
            "STABLE",                 # 5: Default healthy state
        ]

        selected = None
        selected_reason = None
        excluded = []

        for seg in PRECEDENCE:
            if seg in candidates:
                selected = seg
                selected_reason = candidates[seg]["reason"]
                break

        if selected:
            excluded = [s for s in candidates if s != selected]
        else:
            selected = "UNCLASSIFIED"
            selected_reason = "no_segment_matched"
            excluded = list(candidates.keys())

        # Record
        if selected not in segments:
            segments[selected] = 0
        segments[selected] += 1

        if selected not in reasons:
            reasons[selected] = {}
        r = selected_reason
        if r not in reasons[selected]:
            reasons[selected][r] = 0
        reasons[selected][r] += 1

        num_candidates = len(candidates)
        if num_candidates not in conflicts:
            conflicts[num_candidates] = 0
        conflicts[num_candidates] += 1

        for exc in excluded:
            if exc not in excluded_map:
                excluded_map[exc] = 0
            excluded_map[exc] += 1

    return {
        "segments": segments,
        "conflicts": conflicts,
        "excluded_map": excluded_map,
        "reasons": reasons,
    }


result = classify_drivers(drivers)

# ── OUTPUT ──
print("\n" + "=" * 70)
print("LG-S1.0A — SEGMENTATION SIMULATION RESULTS")
print(f"Date: {SNAP_DATE}  |  Drivers analyzed: {total}")
print("=" * 70)

PRECEDENCE_ORDER = ["HIGH_VALUE_RECOVERY", "TOP_PERFORMER", "NEW_OR_REACTIVATED",
                    "ACTIVE_GROWTH", "STABLE", "UNCLASSIFIED"]

print("\n--- Segment Distribution (exclusive) ---")
print(f"{'Segment':30s} {'Drivers':>8s} {'%Universe':>10s}  {'Key Reason'}")
print("-" * 80)
for seg in PRECEDENCE_ORDER:
    cnt = result["segments"].get(seg, 0)
    pct = round(cnt / total * 100, 1)
    top_reason = ""
    if seg in result["reasons"]:
        top_reason = sorted(result["reasons"][seg].items(), key=lambda x: -x[1])[0][0]
    print(f"{seg:30s} {cnt:8d} {pct:9.1f}%  {top_reason}")

print("\n--- Multi-Candidate Conflict Breakdown ---")
for n in sorted(result["conflicts"]):
    cnt = result["conflicts"][n]
    pct = round(cnt / total * 100, 1)
    label = "no match" if n == 0 else f"{n} candidates"
    print(f"  {label:15s}: {cnt:8d} ({pct}%)")

print("\n--- Excluded Candidates by Segment ---")
for seg in sorted(result["excluded_map"], key=lambda x: -result["excluded_map"][x]):
    cnt = result["excluded_map"][seg]
    print(f"  {seg:30s}: {cnt:8d} drivers excluded from this segment (lost to higher priority)")

# ── Coverage validation ──
print("\n--- Coverage Validation ---")
assigned = sum(cnt for seg, cnt in result["segments"].items() if seg != "UNCLASSIFIED")
unclassified = result["segments"].get("UNCLASSIFIED", 0)
print(f"  Total assigned (classified): {assigned} ({round(assigned/total*100,1)}%)")
print(f"  Unclassified:               {unclassified} ({round(unclassified/total*100,1)}%)")
print(f"  Coverage:                   {round(assigned/total*100,1)}%")
print(f"  Duplicate final segments:    0 (exclusive by design)")
print(f"  SUM check:                  {assigned + unclassified} == {total} ? {'OK' if assigned + unclassified == total else 'FAIL'}")

# ── Distribution detail per segment ──
print("\n--- UNCLASSIFIED Reason Breakdown ---")
unclassified_reasons = result["reasons"].get("UNCLASSIFIED", {})
for reason, cnt in sorted(unclassified_reasons.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {cnt}")

# ── ACTIVE_GROWTH detail ──
print("\n--- ACTIVE_GROWTH Reason Breakdown ---")
ag_reasons = result["reasons"].get("ACTIVE_GROWTH", {})
for reason, cnt in sorted(ag_reasons.items(), key=lambda x: -x[1])[:10]:
    print(f"  {reason}: {cnt}")

# ── STABLE detail ──
print("\n--- STABLE Reason Breakdown ---")
st_reasons = result["reasons"].get("STABLE", {})
for reason, cnt in sorted(st_reasons.items(), key=lambda x: -x[1])[:10]:
    print(f"  {reason}: {cnt}")

# ── TOP_PERFORMER detail ──
print("\n--- TOP_PERFORMER Reason Breakdown ---")
tp_reasons = result["reasons"].get("TOP_PERFORMER", {})
for reason, cnt in sorted(tp_reasons.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {cnt}")

# ── High value recovery detail ──
print("\n--- HIGH_VALUE_RECOVERY Reason Breakdown ---")
hvr_reasons = result["reasons"].get("HIGH_VALUE_RECOVERY", {})
for reason, cnt in sorted(hvr_reasons.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {cnt}")

print("\nDone.")
conn.close()
