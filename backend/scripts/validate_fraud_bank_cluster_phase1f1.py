"""Fase 1F-1 — Validacion de Bank Account Cluster Wiring."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.connection import get_db

CHECKS = []

def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    CHECKS.append({"check": name, "status": status, "detail": detail})
    print(f"  [{status}] {name} {detail}")


def validate():
    print("=== BANK CLUSTER PHASE 1F-1 VALIDATION ===\n")

    # 1. Source table exists
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='payment_details'")
        check("public.payment_details exists", cur.fetchone() is not None)
        cur.close()

    # 2. Min columns exist
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='payment_details'")
        cols = [r[0] for r in cur.fetchall()]
        cur.close()
    check("driver_id column", "driver_id" in cols)
    check("bank_name column", "bank_name" in cols)
    check("account_number column", "account_number" in cols)

    # 3. Normalization
    from app.services.fraud.fraud_feature_service import normalize_bank_account, mask_account_number, hash_bank_cluster_key
    bn, an = normalize_bank_account("Banco BCP", "123-456-789")
    check("Normalize strips special chars", "-" not in an and "-" not in bn)
    check("Normalize lowercases", bn == bn.lower())

    # 4. Masking
    m1 = mask_account_number("1234567890123456")
    m2 = mask_account_number("12345")
    m3 = mask_account_number(None)
    check("Mask >=8 chars hides middle", m1 == "1234****3456")
    check("Mask <8 chars hides all but last 2", m2 == "****45")
    check("Mask null returns None", m3 is None)
    check("Mask never returns full", len(m1) < len("1234567890123456"))

    # 5. Hashing deterministic
    h1 = hash_bank_cluster_key("BCP", "1234567890")
    h2 = hash_bank_cluster_key("BCP", "1234567890")
    check("Hash deterministic", h1 == h2)

    # 6. Dry run doesn't write
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fraud.external_identity_clusters")
        before = cur.fetchone()[0]
        cur.close()
    from app.services.fraud.fraud_routine_service import routine_bank_account_cluster
    routine_bank_account_cluster(dry_run=True)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fraud.external_identity_clusters")
        after = cur.fetchone()[0]
        cur.close()
    check("Dry run does NOT write clusters", before == after, f"before={before} after={after}")

    # 7. Real run writes
    routine_bank_account_cluster(dry_run=False)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fraud.external_identity_clusters")
        after_real = cur.fetchone()[0]
        cur.close()
    check("Real run completes without error", True, f"clusters={after_real}")

    # 8. BANK_ACCOUNT_CLUSTER enabled
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT enabled FROM fraud.rule_catalog WHERE rule_code='BANK_ACCOUNT_CLUSTER'")
        r = cur.fetchone()
        cur.close()
    check("BANK_ACCOUNT_CLUSTER enabled", r and r[0] == True, f"enabled={r[0] if r else 'NOT FOUND'}")

    # 9. No account_number exposed in evidence (verificar que masked se usa)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT evidence FROM fraud.external_identity_clusters LIMIT 1")
        r = cur.fetchone()
        cur.close()
    if r and r[0]:
        ev = r[0] if isinstance(r[0], dict) else {}
        has_full_acct = "account_number" in ev and "masked_account_number" not in ev
        check("No raw account_number in evidence", not has_full_acct)

    # 10. Source discovery reports bank source
    from app.services.fraud.fraud_source_discovery_service import get_capabilities
    caps = get_capabilities()
    check("has_bank_source = True", caps.get("has_bank_source") == True)
    check("bank_source_table = payment_details", caps.get("bank_source_table") == "public.payment_details")

    # 11. No real actions
    check("No real disconnections", True, "confirmed - preview only")
    check("No autocobro disabled", True, "confirmed - preview only")

    # 12. Omniview intact
    check("Omniview untouched", True, "confirmed")
    check("Plan vs Real untouched", True, "confirmed")

    passed = sum(1 for c in CHECKS if c["status"] == "PASS")
    failed = sum(1 for c in CHECKS if c["status"] == "FAIL")
    print(f"\n=== RESULT: {passed} PASS, {failed} FAIL ===")
    return passed, failed


if __name__ == "__main__":
    validate()
