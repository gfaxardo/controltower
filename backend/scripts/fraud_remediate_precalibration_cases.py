"""Fase 1F-5C — Remediate cases created before threshold calibration.

Marks pre-calibration cases and downgrades repeated_origin-only cases.
Supports --dry-run, --config-version, --batch-size, --resume-from.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import Json

CONFIG_VERSION = "trip_behavior_v1_calibrated"


def remediate(dry_run=True, config_version=CONFIG_VERSION, batch_size=25, resume_from=0):
    with get_db() as conn:
        cur = conn.cursor()

        # Find pre-calibration cases (created May 20 or befor calibration, no calibration_status)
        cur.execute("""
            SELECT id, driver_id, park_id, severity, case_reason, recommended_action,
                   status, created_at
            FROM fraud.risk_cases
            WHERE calibration_status IS NULL
              AND status = 'open'
            ORDER BY created_at, id
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

        for c in cases:
            case_id = c[0]
            driver_id = c[1]
            reason = c[4]

            rule_codes = []
            if isinstance(reason, dict):
                trig = reason.get("triggered_rules", [])
            elif isinstance(reason, list):
                trig = reason
            else:
                trig = []

            if isinstance(trig, list):
                rule_codes = [t.get("rule_code", "") for t in trig if isinstance(t, dict)]

            is_rep_origin = "REPEATED_ORIGIN_PATTERN" in rule_codes
            is_rep_route = "REPEATED_ROUTE_SIGNATURE" in rule_codes
            is_long_trip = "LONG_TRIP_OUTLIER_V2" in rule_codes or "LONG_TRIP_OUTLIER" in rule_codes
            has_combo = sum(1 for rc in rule_codes if rc) > 1

            # Case: repeated_origin alone without strong evidence -> downgrade
            if is_rep_origin and not has_combo:
                repeat_count = 0
                if isinstance(trig, list) and len(trig) > 0:
                    ev = trig[0].get("evidence", {}) if isinstance(trig[0], dict) else {}
                    repeat_count = ev.get("repeat_count", ev.get("min_count", 0))
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
            elif is_rep_route and not has_combo:
                to_downgrade.append({
                    "case_id": case_id,
                    "driver_id": driver_id,
                    "reason": "repeated_route_only",
                })
                repeated_route_only += 1
            elif is_long_trip and not has_combo:
                to_downgrade.append({
                    "case_id": case_id,
                    "driver_id": driver_id,
                    "reason": "long_trip_only_downgrade",
                })
                long_trip += 1
            else:
                to_keep.append(case_id)
                other += 1

        print(f"\nClassification:")
        print(f"  repeated_origin only: {repeated_origin_only} (downgrade if count<5)")
        print(f"  repeated_route only: {repeated_route_only}")
        print(f"  long_trip outlier only: {long_trip}")
        print(f"  other/combo: {other}")
        print(f"  total to downgrade: {len(to_downgrade)}")
        print(f"  total to keep: {len(to_keep)}")

        if dry_run:
            print("\n[DRY RUN] No changes written.")
            print("Sample cases to downgrade:")
            for d in to_downgrade[:10]:
                print(f"  case#{d['case_id']} driver={d['driver_id']} reason={d['reason']}")
            if len(to_downgrade) > 10:
                print(f"  ... and {len(to_downgrade) - 10} more")
            print("\nSample cases to keep:")
            for case_id in to_keep[:10]:
                print(f"  case#{case_id}")
            if len(to_keep) > 10:
                print(f"  ... and {len(to_keep) - 10} more")
            cur.close()
            return

        # ── COMMIT: Batching ──
        total_batches = (len(cases) + batch_size - 1) // batch_size
        print(f"\nProcessing {len(cases)} cases in {total_batches} batches of {batch_size} (resume_from={resume_from})")

        processed = 0
        errors = 0

        # Batch 1: mark ALL pre-calibration cases with calibration status
        for batch_start in range(0, len(cases), batch_size):
            batch = cases[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            if batch_num < resume_from:
                continue

            print(f"\nBatch {batch_num}/{total_batches} ({batch_start + 1}-{batch_start + len(batch)})")
            try:
                for c in batch:
                    case_id = c[0]
                    cur.execute("""
                        UPDATE fraud.risk_cases
                        SET calibration_status = 'pre_calibration',
                            calibration_version = %s
                        WHERE id = %s
                    """, (config_version, case_id))
                conn.commit()
                processed += len(batch)
                print(f"  -> {len(batch)} cases marked 'pre_calibration'")
            except Exception as e:
                conn.rollback()
                errors += len(batch)
                print(f"  -> ERROR batch {batch_num}: {e}")
                print(f"  -> Try --resume-from {batch_num} --batch-size {max(5, batch_size // 3)}")

        # Batch 2: Downgrade low-confidence cases
        downgrade_batches = (len(to_downgrade) + batch_size - 1) // batch_size
        print(f"\nDowngrading {len(to_downgrade)} cases in {downgrade_batches} batches...")
        for batch_start in range(0, len(to_downgrade), batch_size):
            batch = to_downgrade[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1

            try:
                for d in batch:
                    cur.execute("""
                        UPDATE fraud.risk_cases
                        SET calibration_status = 'recalibrated_downgraded',
                            status = 'closed',
                            severity = 'low',
                            review_decision = 'rejected',
                            review_comment = %s,
                            reviewed_by = 'system_calibration_1f5c'
                        WHERE id = %s
                    """, (
                        f"Downgraded by F1F-5C calibration. Pre-calibration case with insufficient evidence. {d['reason']}. Repeat count: {d.get('repeat_count', 'N/A')}",
                        d['case_id'],
                    ))
                conn.commit()
                print(f"  Batch {batch_num}/{downgrade_batches}: {len(batch)} cases downgraded")
            except Exception as e:
                conn.rollback()
                errors += len(batch)
                print(f"  -> ERROR batch {batch_num}: {e}")

        # Batch 3: Keep combo cases
        keep_batches = (len(to_keep) + batch_size - 1) // batch_size
        print(f"\nMarking {len(to_keep)} combo cases as 'recalibrated_kept' in {keep_batches} batches...")
        for batch_start in range(0, len(to_keep), batch_size):
            batch = to_keep[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1

            try:
                for case_id in batch:
                    cur.execute("""
                        UPDATE fraud.risk_cases
                        SET calibration_status = 'recalibrated_kept'
                        WHERE id = %s
                    """, (case_id,))
                conn.commit()
                print(f"  Batch {batch_num}/{keep_batches}: {len(batch)} cases kept")
            except Exception as e:
                conn.rollback()
                errors += len(batch)
                print(f"  -> ERROR batch {batch_num}: {e}")

        cur.close()

    print(f"\n=== REMEDIATION COMPLETE ===")
    print(f"  Total cases processed: {len(cases)}")
    print(f"  Downgraded/closed: {len(to_downgrade)}")
    print(f"  Kept: {len(to_keep)}")
    print(f"  Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remediate pre-calibration fraud cases")
    parser.add_argument("--dry-run", type=str, default="true", help="true/false")
    parser.add_argument("--config-version", type=str, default=CONFIG_VERSION, help="version tag")
    parser.add_argument("--batch-size", type=int, default=25, help="cases per batch")
    parser.add_argument("--resume-from", type=int, default=0, help="batch number to resume from")
    args = parser.parse_args()

    dry = args.dry_run.lower() in ("true", "1", "yes")
    print(f"=== FASE 1F-5C PRE-CALIBRATION REMEDIATION ===")
    print(f"  dry_run: {dry}")
    print(f"  config_version: {args.config_version}")
    print(f"  batch_size: {args.batch_size}")
    print(f"  resume_from: {args.resume_from}")
    print()

    remediate(dry_run=dry, config_version=args.config_version,
              batch_size=args.batch_size, resume_from=args.resume_from)
