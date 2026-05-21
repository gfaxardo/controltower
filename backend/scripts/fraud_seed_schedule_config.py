"""Fase 1F-7 — Seed routine schedule config.

Define daily/weekly/monthly plan for all 12 behavioral routines.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db

SCHEDULE = [
    # DAILY — fast routines, D-1 window
    {"routine_name": "repeated_origin_pattern", "frequency": "daily", "enabled": True, "max_runtime_seconds": 30},
    {"routine_name": "low_avg_distance_pattern", "frequency": "daily", "enabled": True, "max_runtime_seconds": 15},
    {"routine_name": "low_avg_duration_pattern", "frequency": "daily", "enabled": True, "max_runtime_seconds": 15},
    {"routine_name": "extreme_short_trip_ratio", "frequency": "daily", "enabled": True, "max_runtime_seconds": 15},
    {"routine_name": "low_variance_pattern", "frequency": "daily", "enabled": True, "max_runtime_seconds": 15},
    {"routine_name": "short_trip_farming", "frequency": "daily", "enabled": True, "max_runtime_seconds": 15},
    {"routine_name": "park_behavior_concentration", "frequency": "daily", "enabled": True, "max_runtime_seconds": 15},

    # WEEKLY — medium/slow routines, D-7 window
    {"routine_name": "repeated_route_signature", "frequency": "weekly", "enabled": True, "max_runtime_seconds": 120},
    {"routine_name": "route_loop_pattern", "frequency": "weekly", "enabled": True, "max_runtime_seconds": 30},
    {"routine_name": "coordinated_origin_pattern", "frequency": "weekly", "enabled": True, "max_runtime_seconds": 600},
    {"routine_name": "long_trip_outlier_v2", "frequency": "weekly", "enabled": True, "max_runtime_seconds": 120},

    # MONTHLY — heavy routines, D-30 window
    {"routine_name": "behavioral_driver_profile", "frequency": "monthly", "enabled": True, "max_runtime_seconds": 600},
    {"routine_name": "park_behavior_concentration", "frequency": "monthly", "enabled": True, "max_runtime_seconds": 120},
]

CONFIG_VERSION = "trip_behavior_v1_calibrated"


def seed():
    with get_db() as conn:
        cur = conn.cursor()
        for s in SCHEDULE:
            cur.execute("""
                INSERT INTO fraud.routine_schedule_config
                    (routine_name, frequency, enabled, max_runtime_seconds, config_version)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (routine_name, frequency) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    max_runtime_seconds = EXCLUDED.max_runtime_seconds,
                    config_version = EXCLUDED.config_version,
                    updated_at = now()
            """, (s["routine_name"], s["frequency"], s["enabled"],
                  s["max_runtime_seconds"], CONFIG_VERSION))
        conn.commit()
        cur.close()
    print(f"Seeded {len(SCHEDULE)} routine schedule configs")


if __name__ == "__main__":
    seed()
