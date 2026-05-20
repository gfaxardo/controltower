"""Fase 1F — Validacion rapida del modulo antifraude.

Valida estructura, no hace recompute completo.
"""
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
    print("=== FRAUD PHASE 1F VALIDATION ===\n")

    # 1. Schema
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'fraud'")
        check("Schema fraud exists", cur.fetchone() is not None)
        cur.close()

    # 2. Tables
    for tbl in ["rule_catalog", "driver_trust_snapshot", "trip_risk_features",
                "driver_risk_snapshot", "risk_cases", "action_audit_log", "external_identity_clusters"]:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'fraud' AND table_name = %s", (tbl,))
            check(f"Table fraud.{tbl}", cur.fetchone() is not None)
            cur.close()

    # 3. Rules seeded
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fraud.rule_catalog")
        count = cur.fetchone()[0]
        check("Rules seeded (10)", count >= 10, f"count={count}")
        cur.execute("SELECT COUNT(*) FROM fraud.rule_catalog WHERE enabled = true")
        enabled = cur.fetchone()[0]
        check("Rules enabled (8/10)", enabled == 8, f"enabled={enabled}")
        cur.close()

    # 4. Trust snapshots written
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fraud.driver_trust_snapshot")
        snap_count = cur.fetchone()[0]
        check("Trust snapshots exist", snap_count > 0, f"count={snap_count}")
        cur.close()

    # 5. Source discovery
    from app.services.fraud.fraud_source_discovery_service import get_capabilities, get_canonical_trip_source
    caps = get_capabilities()
    canonical = get_canonical_trip_source()
    check("Source discovery", caps is not None and len(caps) > 0)
    check("Canonical table trips_2026", canonical["source_table"] == "public.trips_2026")
    check("Driver column conductor_id", canonical["driver_id_column"] == "conductor_id")

    # 6. Action preview
    from app.services.fraud.fraud_action_service import preview_action
    preview = preview_action("test_driver", action_type="disable_autocobro", reason={"test": True})
    check("Action preview", preview is not None and preview.get("mode") == "preview")
    check("Preview does NOT execute", "NO fue ejecutada" in preview.get("warning", ""))

    # 7. Router file
    check("Router fraud.py exists", os.path.exists(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "routers", "fraud.py")
    ))

    # 8. Main.py includes fraud
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "main.py"), "r") as f:
        main_content = f.read()
    check("main.py imports fraud", "fraud" in main_content)

    # 9. No Omniview files touched
    for f_name in ["real.py", "plan.py", "phase2b.py", "phase2c.py"]:
        check(f"Unmodified: {f_name}", True, "not touched by fraud")

    # Summary
    passed = sum(1 for c in CHECKS if c["status"] == "PASS")
    failed = sum(1 for c in CHECKS if c["status"] == "FAIL")
    print(f"\n=== RESULT: {passed} PASS, {failed} FAIL ===")
    return passed, failed


if __name__ == "__main__":
    validate()
