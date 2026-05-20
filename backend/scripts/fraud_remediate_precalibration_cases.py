"""Fase 1F-5B — Remediate cases created before threshold calibration.
Marks pre-calibration cases and downgrades repeated_origin-only cases.
Dry run first, then commit.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import Json

CONFIG_VERSION = "trip_behavior_v1_calibrated"


def remediate(dry_run=True):
    with get_db() as conn:
        cur = conn.cursor()

        # Find pre-calibration cases (created May 20, no calibration_status)
        cur.execute("""
            SELECT id, driver_id, park_id, severity, case_reason, recommended_action,
                   status, created_at
            FROM fraud.risk_cases
            WHERE created_at >= '2026-05-20'
              AND calibration_status IS NULL
              AND status = 'open'
            ORDER BY created_at
        """)
        cases = cur.fetchall()

        print(f"Found {len(cases)} pre-calibration open cases")

        # Classify
        repeated_origin_only = 0
        repeated_route_only = 0
        long_trip = 0
        other = 0
        to_downgrade = []
        to_keep = []
        to_close = []

        for c in cases:
            case_id = c[0]
            driver_id = c[1]
            park_id = c[2]
            reason = c[4]
            action = c[5]

            rule_codes = []
            if isinstance(reason, dict):
                trig = reason.get('triggered_rules', [])
            elif isinstance(reason, list):
                trig = reason
            else:
                trig = []

            if isinstance(trig, list):
                rule_codes = [t.get('rule_code', '') for t in trig if isinstance(t, dict)]

            is_rep_origin = "REPEATED_ORIGIN_PATTERN" in rule_codes
            is_rep_route = "REPEATED_ROUTE_SIGNATURE" in rule_codes
            is_long_trip = "LONG_TRIP_OUTLIER_V2" in rule_codes

            # Downgrade: repeated_origin alone without strong evidence
            if is_rep_origin and len(rule_codes) == 1:
                # Check repeat_count evidence
                repeat_count = 0
                if isinstance(trig, list) and len(trig) > 0:
                    ev = trig[0].get('evidence', {}) if isinstance(trig[0], dict) else {}
                    repeat_count = ev.get('repeat_count', 0)
                if repeat_count < 5:
                    to_downgrade.append({
                        "case_id": case_id,
                        "driver_id": driver_id,
                        "reason": "repeated_origin_low_count",
                        "repeat_count": repeat_count,
                    })
                    repeated_origin_only += 1
                else:
                    to_keep.append(case_id)
                    repeated_origin_only += 1
            elif is_rep_route and len(rule_codes) == 1:
                to_downgrade.append({
                    "case_id": case_id,
                    "driver_id": driver_id,
                    "reason": "repeated_route_only",
                })
                repeated_route_only += 1
            elif is_long_trip and len(rule_codes) == 1:
                # Long trip outliers: keep but downgrade severity
                to_downgrade.append({
                    "case_id": case_id,
                    "driver_id": driver_id,
                    "reason": "long_trip_only_downgrade",
                })
                long_trip += 1
            else:
                to_keep.append(case_id)
                other += 1

        print(f"Classification:")
        print(f"  repeated_origin only: {repeated_origin_only} (downgrade if count<5)")
        print(f"  repeated_route only: {repeated_route_only}")
        print(f"  long_trip outlier only: {long_trip}")
        print(f"  other/combo: {other}")
        print(f"  to downgrade: {len(to_downgrade)}")
        print(f"  to keep: {len(to_keep)}")

        if dry_run:
            print("\n[DRY RUN] No changes written.")
            print("Sample cases to downgrade:")
            for d in to_downgrade[:5]:
                print(f"  case#{d['case_id']} driver={d['driver_id']} reason={d['reason']}")
            cur.close()
            return

        # Commit: update all pre-calibration cases
        for c in cases:
            case_id = c[0]
            cur.execute("""
                UPDATE fraud.risk_cases
                SET calibration_status = 'pre_calibration',
                    calibration_version = %s
                WHERE id = %s
            """, (CONFIG_VERSION, case_id))

        # Downgrade low-confidence cases
        for d in to_downgrade:
            cur.execute("""
                UPDATE fraud.risk_cases
                SET calibration_status = 'recalibrated_downgraded',
                    status = 'closed',
                    severity = 'low',
                    review_decision = 'rejected',
                    review_comment = %s,
                    reviewed_by = 'system_calibration_1f5b'
                WHERE id = %s
            """, (f"Downgraded by F1F-5B calibration. Pre-calibration case with insufficient evidence. {d['reason']}", d['case_id']))

        # Keep combo cases
        for case_id in to_keep:
            cur.execute("""
                UPDATE fraud.risk_cases
                SET calibration_status = 'recalibrated_kept'
                WHERE id = %s
            """, (case_id,))

        conn.commit()
        cur.close()

    print(f"\nCommitted: {len(cases)} cases marked")
    print(f"  Downgraded/closed: {len(to_downgrade)}")
    print(f"  Kept: {len(to_keep)}")


if __name__ == "__main__":
    dry_run = sys.argv[1].lower() != "false" if len(sys.argv) > 1 else True
    remediate(dry_run)
