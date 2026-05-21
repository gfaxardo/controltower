"""Fase 1F-6 — Recompute Case Confidence Scores.

Recalcula case_confidence_score y confidence_reason para todos los casos
abiertos que tienen NULL o 0 en confidence.

Soporta dry_run y commit. No borra casos.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import Json
from app.services.fraud.fraud_confidence_scoring import compute_case_confidence, build_signal_bundle


def recompute_confidence(dry_run=True):
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, case_code, driver_id, severity, status, risk_score,
                   case_reason, case_confidence_score, confidence_reason,
                   calibration_status
            FROM fraud.risk_cases
            WHERE status = 'open'
              AND (case_confidence_score IS NULL OR case_confidence_score = 0)
            ORDER BY created_at
        """)
        cases = cur.fetchall()

        print(f"Found {len(cases)} open cases with NULL/0 confidence")

        updated = 0
        stay_zero = 0
        errors = 0
        samples = []

        for c in cases:
            case_id = c[0]
            driver_id = c[2]
            reason_raw = c[6]
            current_conf = c[7]
            calibration = c[9]

            try:
                triggered = []
                if isinstance(reason_raw, dict):
                    triggered = reason_raw.get("triggered_rules", [])
                elif isinstance(reason_raw, list):
                    triggered = reason_raw
                if not isinstance(triggered, list):
                    triggered = []

                bundle = build_signal_bundle(triggered)
                conf_score, conf_reason = compute_case_confidence(bundle)

                if conf_score is None:
                    conf_score = 0.0

                if not dry_run:
                    cur.execute("""
                        UPDATE fraud.risk_cases
                        SET case_confidence_score = %s,
                            confidence_reason = %s,
                            updated_at = now()
                        WHERE id = %s
                    """, (conf_score, Json(conf_reason) if conf_reason else None, case_id))

                updated += 1
                if conf_score == 0:
                    stay_zero += 1

                if len(samples) < 5:
                    samples.append({
                        "case_id": case_id,
                        "driver_id": driver_id[:20],
                        "triggered_count": len(triggered),
                        "rule_codes": [t.get("rule_code", "?") if isinstance(t, dict) else "?" for t in triggered[:2]],
                        "confidence": conf_score,
                        "calibration": calibration,
                    })
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  ERROR case#{case_id}: {e}")

        if not dry_run:
            conn.commit()

        cur.close()

    print(f"\n=== CONFIDENCE RECOMPUTE ===")
    print(f"  dry_run: {dry_run}")
    print(f"  cases processed: {updated}")
    print(f"  confidence=0 after recompute: {stay_zero}")
    print(f"  errors: {errors}")
    print(f"\nSample results:")
    for s in samples:
        print(f"  #{s['case_id']} driver={s['driver_id']} rules={s['rule_codes']} conf={s['confidence']} calib={s['calibration']}")

    if stay_zero > 0:
        print(f"\nNote: {stay_zero} cases remain at confidence=0. These are single-rule weak cases.")
        print("Recommendation: review for potential close/downgrade if evidence is insufficient.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recompute case confidence scores")
    parser.add_argument("--dry-run", type=str, default="true")
    args = parser.parse_args()

    dry = args.dry_run.lower() in ("true", "1", "yes")
    recompute_confidence(dry_run=dry)
