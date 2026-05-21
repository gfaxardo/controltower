"""F1F-9 - Exception Distribution Audit Script.

Analiza el snapshot actual de elegibilidad y descompone cada categoria
en sub-razones con counts detallados, samples y recomendaciones.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db

POLICY = "autocobro_v1_preview"

print("=" * 60)
print("F1F-9 - EXCEPTION DISTRIBUTION AUDIT")
print("=" * 60)

with get_db() as conn:
    cur = conn.cursor()

    # GLOBAL DISTRIBUTION
    print("\n--- 1. GLOBAL DISTRIBUTION (v1) ---")
    cur.execute("""
        SELECT eligibility_status, COUNT(*) AS cnt,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s
        GROUP BY eligibility_status
        ORDER BY cnt DESC
    """, (POLICY,))
    for r in cur.fetchall():
        print(f"  {r[0]:<20} {r[1]:>6}  ({r[2]}%)")

    # REVIEW_REQUIRED BREAKDOWN
    print("\n--- 2. REVIEW_REQUIRED BREAKDOWN ---")

    cur.execute("SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot WHERE policy_version = %s AND eligibility_status = 'review_required'", (POLICY,))
    actual_rr = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND trust_tier = 'new_or_unproven' AND total_completed_trips >= 30
    """, (POLICY,))
    r1 = cur.fetchone()[0]
    print(f"  R1 (new_or_unproven >=30 trips):          {r1:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND behavioral_profile_class = 'suspicious'
    """, (POLICY,))
    r2 = cur.fetchone()[0]
    print(f"  R2 (suspicious profile):                  {r2:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND trust_tier = 'trusted' AND total_completed_trips >= 50
          AND behavioral_profile_class IS NULL
    """, (POLICY,))
    r5 = cur.fetchone()[0]
    print(f"  R5 (trusted 50+ without profile):         {r5:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND max_case_confidence_score IS NOT NULL
          AND max_case_confidence_score > 0
          AND max_case_confidence_score <= 59
    """, (POLICY,))
    r3 = cur.fetchone()[0]
    print(f"  R3 (medium confidence cases):             {r3:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND behavioral_confidence_score IS NOT NULL
          AND behavioral_confidence_score >= 50
          AND high_case_count = 0 AND critical_case_count = 0
    """, (POLICY,))
    r4 = cur.fetchone()[0]
    print(f"  R4 (fraud candidate, no high cases):      {r4:>6}")

    # Count drivers NOT matching any of R1-R5
    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND NOT (
              (trust_tier = 'new_or_unproven' AND total_completed_trips >= 30)
              OR behavioral_profile_class = 'suspicious'
              OR (trust_tier = 'trusted' AND total_completed_trips >= 50 AND behavioral_profile_class IS NULL)
              OR (max_case_confidence_score IS NOT NULL AND max_case_confidence_score > 0 AND max_case_confidence_score <= 59)
              OR (behavioral_confidence_score IS NOT NULL AND behavioral_confidence_score >= 50 AND high_case_count = 0 AND critical_case_count = 0)
          )
    """, (POLICY,))
    other_rr = cur.fetchone()[0]
    print(f"  Other/combined:                            {other_rr:>6}")
    print(f"  ----------------------------------------------")
    print(f"  TOTAL review_required:                     {actual_rr:>6}")

    # R5 SUB-BREAKDOWN
    print("\n--- 3. R5 DETAIL: TRUSTED 50+ WITHOUT BEHAVIORAL PROFILE ---")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot aes
        WHERE aes.policy_version = %s AND aes.eligibility_status = 'review_required'
          AND aes.trust_tier = 'trusted' AND aes.total_completed_trips >= 50
          AND aes.behavioral_profile_class IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM fraud.driver_risk_snapshot drs
              WHERE drs.driver_id = aes.driver_id
          )
    """, (POLICY,))
    r5a = cur.fetchone()[0]
    print(f"  R5A (trusted, no risk snapshot at all):    {r5a:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot aes
        WHERE aes.policy_version = %s AND aes.eligibility_status = 'review_required'
          AND aes.trust_tier = 'trusted' AND aes.total_completed_trips >= 50
          AND aes.behavioral_profile_class IS NULL
          AND EXISTS (
              SELECT 1 FROM fraud.driver_risk_snapshot drs
              WHERE drs.driver_id = aes.driver_id
          )
    """, (POLICY,))
    r5b = cur.fetchone()[0]
    print(f"  R5B (trusted, in risk snapshot, no prof):  {r5b:>6}")

    # UNKNOWN BREAKDOWN
    print("\n--- 4. UNKNOWN BREAKDOWN ---")

    cur.execute("SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot WHERE policy_version = %s AND eligibility_status = 'unknown'", (POLICY,))
    actual_unknown = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'unknown'
          AND total_completed_trips < 3
    """, (POLICY,))
    u3 = cur.fetchone()[0]
    print(f"  U3 (< 3 trips):                              {u3:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'unknown'
          AND trust_tier IS NULL
    """, (POLICY,))
    u1 = cur.fetchone()[0]
    print(f"  U1 (missing trust_tier):                     {u1:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'unknown'
          AND trust_tier = 'unknown'
    """, (POLICY,))
    u2 = cur.fetchone()[0]
    print(f"  U2 (trust_tier = unknown):                   {u2:>6}")

    cur.execute("""
        SELECT COUNT(*) FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'unknown'
          AND total_completed_trips >= 3 AND trust_tier IS NOT NULL
          AND trust_tier != 'unknown'
    """, (POLICY,))
    u_other = cur.fetchone()[0]
    print(f"  U_other (>=3 trips, has trust, unknown):     {u_other:>6}")
    print(f"  ----------------------------------------------")
    print(f"  TOTAL unknown:                               {actual_unknown:>6}")

    # RESTRICTED DETAIL
    print("\n--- 5. RESTRICTED DETAIL (all 34) ---")

    cur.execute("""
        SELECT driver_id, park_id, trust_tier, total_completed_trips,
               behavioral_profile_class, max_case_confidence_score,
               open_case_count, high_case_count, critical_case_count,
               recommended_action, eligibility_reason
        FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'restricted'
        ORDER BY high_case_count DESC, critical_case_count DESC
    """, (POLICY,))
    restricted = cur.fetchall()

    print(f"  Total restricted: {len(restricted)}")
    for drv in restricted:
        reason = drv[10] or {}
        rules = reason.get("matched_rules", []) if isinstance(reason, dict) else []
        print(f"  driver={str(drv[0])[:16]}... park={str(drv[1] or 'N/A')[:8]} "
              f"trust={drv[2]} trips={drv[3]} profile={drv[4]} "
              f"conf={drv[5]} open={drv[6]} high={drv[7]} crit={drv[8]} "
              f"action={drv[9]} rules={rules}")

    # R1 BREAKDOWN
    print("\n--- 6. R1 DETAIL: NEW_OR_UNPROVEN >=30 TRIPS ---")

    cur.execute("""
        SELECT
            CASE
                WHEN total_completed_trips BETWEEN 30 AND 39 THEN '30-39'
                WHEN total_completed_trips BETWEEN 40 AND 49 THEN '40-49'
                ELSE '50+'
            END AS trip_bucket,
            COALESCE(behavioral_profile_class, 'no_profile') AS profile_class,
            CASE WHEN open_case_count > 0 THEN 'has_cases' ELSE 'no_cases' END AS case_status,
            COUNT(*) AS cnt
        FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'review_required'
          AND trust_tier = 'new_or_unproven' AND total_completed_trips >= 30
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """, (POLICY,))
    for r in cur.fetchall():
        print(f"  trips={r[0]:<8} profile={r[1]:<15} cases={r[2]:<12} count={r[3]}")

    # U3 SUB-BREAKDOWN
    print("\n--- 7. U3 DETAIL: < 3 TRIPS ---")

    cur.execute("""
        SELECT
            total_completed_trips AS trips,
            COALESCE(trust_tier, 'null') AS trust_tier,
            COUNT(*) AS cnt
        FROM fraud.autocobro_eligibility_snapshot
        WHERE policy_version = %s AND eligibility_status = 'unknown'
          AND total_completed_trips < 3
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, (POLICY,))
    for r in cur.fetchall():
        print(f"  trips={r[0]} trust={r[1]:<18} count={r[2]}")

    # SAMPLES
    print("\n--- 8. SAMPLES (3 per category, driver_id truncated) ---")

    for status in ["eligible", "review_required", "restricted", "unknown"]:
        cur.execute("""
            SELECT driver_id, park_id, trust_tier, total_completed_trips,
                   behavioral_profile_class, eligibility_reason, open_case_count,
                   recommended_action, max_case_confidence_score
            FROM fraud.autocobro_eligibility_snapshot
            WHERE policy_version = %s AND eligibility_status = %s
            LIMIT 3
        """, (POLICY, status))
        rows = cur.fetchall()
        print(f"\n  [{status}]")
        for r in rows:
            reason = r[5] or {}
            rules = reason.get("matched_rules", []) if isinstance(reason, dict) else []
            print(f"  id={str(r[0])[:14]}... park={str(r[1] or '')[:6]} "
                  f"trust={r[2]} trips={r[3]} profile={r[4]} "
                  f"cases={r[6]} action={r[7]} conf={r[8]} rules={rules[:3]}")

    cur.close()

print("\n" + "=" * 60)
print("AUDIT COMPLETE")
print("=" * 60)
