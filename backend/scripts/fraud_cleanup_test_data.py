"""Fase 1F-3 — Test data cleanup script.

Identifica y aisla/limpia datos de prueba en tablas fraud.
Soporta dry_run. NO borra data productiva.

Uso:
  python backend/scripts/fraud_cleanup_test_data.py --dry-run true
  python backend/scripts/fraud_cleanup_test_data.py --dry-run false --source-name test_data
"""
import sys, os, argparse
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.db.connection import get_db

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "docs", "fraud",
)


def detect_test_data():
    """Busca filas candidatas a test data."""
    findings = {
        "payment_identity_source": [],
        "external_identity_clusters": [],
        "risk_cases": [],
        "action_audit_log": [],
    }

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id, driver_id, source_name, source_batch_id FROM fraud.payment_identity_source WHERE source_name = %s", ("test_data",))
        for r in cur.fetchall():
            findings["payment_identity_source"].append({"id": r[0], "driver_id": r[1], "source_name": r[2], "batch": r[3]})

        cur.execute("SELECT id, driver_id, source_name FROM fraud.payment_identity_source WHERE driver_id LIKE %s", ("driver00%",))
        for r in cur.fetchall():
            if r[0] not in [f["id"] for f in findings["payment_identity_source"]]:
                findings["payment_identity_source"].append({"id": r[0], "driver_id": r[1], "source_name": r[2], "batch": None})

        cur.execute("SELECT id, cluster_type, evidence FROM fraud.external_identity_clusters")
        for r in cur.fetchall():
            ev = r[2] or {}
            if ev.get("source_name") == "test_data":
                findings["external_identity_clusters"].append({"id": r[0], "cluster_type": r[1]})

        cur.execute("SELECT id, case_code, driver_id FROM fraud.risk_cases WHERE driver_id LIKE %s", ("driver00%",))
        for r in cur.fetchall():
            findings["risk_cases"].append({"id": r[0], "case_code": r[1], "driver_id": r[2]})

        cur.execute("SELECT id, driver_id, action_type FROM fraud.action_audit_log WHERE driver_id LIKE %s", ("driver00%",))
        for r in cur.fetchall():
            findings["action_audit_log"].append({"id": r[0], "driver_id": r[1], "action_type": r[2]})

        cur.close()

    return findings


def cleanup(dry_run=True, source_name=None):
    findings = detect_test_data()
    total_affected = sum(len(v) for v in findings.values())

    print(f"\n{'[DRY RUN] ' if dry_run else '[COMMIT] '}Test Data Cleanup")
    print(f"  payment_identity_source: {len(findings['payment_identity_source'])} rows")
    print(f"  external_identity_clusters: {len(findings['external_identity_clusters'])} rows")
    print(f"  risk_cases: {len(findings['risk_cases'])} rows")
    print(f"  action_audit_log: {len(findings['action_audit_log'])} rows")
    print(f"  TOTAL affected: {total_affected}")

    if total_affected == 0:
        print("  No test data detected. Nothing to clean.")
        return

    if dry_run:
        print("\n  Dry run: no data modified. Run with --dry-run false to commit.")
        # Generate report
        lines = [
            "# AUDITORIA FASE 1F-3 — TEST DATA CLEANUP\n",
            f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
            f"## Data de prueba detectada\n",
            f"- payment_identity_source: {len(findings['payment_identity_source'])} (source_name=test_data, driver_id=driver00x)",
            f"- external_identity_clusters: {len(findings['external_identity_clusters'])}",
            f"- risk_cases: {len(findings['risk_cases'])} (driver00x)",
            f"- action_audit_log: {len(findings['action_audit_log'])} (driver00x)",
            f"\n## Accion propuesta\n",
            f"- Marcar payment_identity_source.is_active = false para {len(findings['payment_identity_source'])} filas",
            f"- Eliminar {len(findings['external_identity_clusters'])} clusters de prueba",
            f"- Cerrar {len(findings['risk_cases'])} casos de prueba",
            f"\n## Confirmacion\n",
            f"- NO se tocara data productiva",
            f"- Solo filas con driver_id driver00x o source_name test_data",
        ]
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, "AUDITORIA_FASE1F3_TEST_DATA_CLEANUP.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n  Reporte generado: {path}")
        return

    # Real cleanup
    with get_db() as conn:
        cur = conn.cursor()
        affected = 0

        if findings["payment_identity_source"]:
            cur.execute("""
                UPDATE fraud.payment_identity_source
                SET is_active = false, updated_at = now()
                WHERE source_name = %s OR driver_id LIKE %s
            """, ("test_data", "driver00%"))
            affected += cur.rowcount

        if findings["external_identity_clusters"]:
            ids = [f["id"] for f in findings["external_identity_clusters"]]
            cur.execute("DELETE FROM fraud.external_identity_clusters WHERE id = ANY(%s)", (ids,))
            affected += cur.rowcount

        if findings["risk_cases"]:
            ids = [f["id"] for f in findings["risk_cases"]]
            cur.execute("UPDATE fraud.risk_cases SET status = 'closed', updated_at = now() WHERE id = ANY(%s)", (ids,))
            affected += cur.rowcount

        conn.commit()
        cur.close()

    print(f"\n  COMMIT: {affected} rows cleaned/deactivated.")
    print(f"  Accion completada. Test data isolated.")


def main():
    parser = argparse.ArgumentParser(description="Cleanup test data from fraud tables")
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--source-name", default=None)
    args = parser.parse_args()
    dry_run = args.dry_run.lower() in ("true", "1", "yes")
    cleanup(dry_run, args.source_name)


if __name__ == "__main__":
    main()
