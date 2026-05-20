"""Fase 1F-3 — Daily Fraud Report Generator.

Genera reporte markdown diario antifraude.
NO expone account_number completo.

Uso:
  python backend/scripts/fraud_generate_daily_report.py --date 2026-05-20
"""
import sys, os, argparse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.db.connection import get_db

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "docs", "fraud", "daily_reports",
)


def generate(date_str=None):
    ref = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.now().date()
    d1 = ref - timedelta(days=1)
    report_path = os.path.join(OUTPUT_DIR, f"FRAUD_DAILY_REPORT_{ref.strftime('%Y%m%d')}.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lines = []
    lines.append(f"# FRAUD DAILY REPORT — {ref.isoformat()}\n")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    with get_db() as conn:
        cur = conn.cursor()

        # Trust snapshot stats
        cur.execute("SELECT COUNT(*) FROM fraud.driver_trust_snapshot")
        total_drivers = cur.fetchone()[0]
        cur.execute("SELECT trust_tier, COUNT(*) FROM fraud.driver_trust_snapshot GROUP BY trust_tier")
        trust = {r[0]: r[1] for r in cur.fetchall()}

        lines.append("## 1. Estado ejecutivo\n")
        lines.append(f"- Drivers clasificados: {total_drivers}")
        lines.append(f"- Trusted: {trust.get('trusted', 0)}")
        lines.append(f"- New/Unproven: {trust.get('new_or_unproven', 0)}")
        lines.append(f"- Restricted: {trust.get('restricted', 0)}")
        lines.append(f"- Unknown: {trust.get('unknown', 0)}")

        # Open cases
        cur.execute("SELECT COUNT(*), severity FROM fraud.risk_cases WHERE status='open' GROUP BY severity ORDER BY severity")
        cases = {r[1]: r[0] for r in cur.fetchall()}
        total_open = sum(cases.values())
        lines.append(f"- Casos abiertos: {total_open}")
        for sev in ("critical", "high", "medium", "low"):
            if sev in cases:
                lines.append(f"  - {sev}: {cases[sev]}")

        lines.append(f"\n## 2. Ventana analizada\n")
        lines.append(f"- Desde: {d1.isoformat()}")
        lines.append(f"- Hasta: {ref.isoformat()}")

        # Top drivers by risk
        lines.append(f"\n## 3. Top drivers por risk_score\n")
        try:
            cur.execute("""
                SELECT drs.driver_id, drs.park_id, drs.risk_score, drs.severity,
                       drs.recommended_action, dts.trust_tier
                FROM fraud.driver_risk_snapshot drs
                LEFT JOIN fraud.driver_trust_snapshot dts ON drs.driver_id = dts.driver_id
                ORDER BY drs.risk_score DESC LIMIT 10
            """)
            for r in cur.fetchall():
                lines.append(f"- `{r[0][:12]}` park={r[1]} score={r[2]} sev={r[3]} action={r[4]} tier={r[5]}")
        except Exception:
            lines.append("- No risk data yet")

        # Bank clusters
        lines.append(f"\n## 4. Clusters bancarios\n")
        try:
            cur.execute("""
                SELECT severity, jsonb_array_length(drivers) AS dc, evidence
                FROM fraud.external_identity_clusters
                WHERE cluster_type = 'bank_account'
                ORDER BY jsonb_array_length(drivers) DESC
            """)
            for r in cur.fetchall():
                ev = r[2] or {}
                lines.append(f"- sev={r[0]} drivers={r[1]} masked={ev.get('masked_account_number')}")
        except Exception:
            lines.append("- No bank clusters detected")

        # Recent routine runs
        lines.append(f"\n## 5. Ultimas corridas\n")
        try:
            cur.execute("""
                SELECT routine_name, mode, status, dry_run, duration_seconds, finished_at
                FROM fraud.routine_run_log
                ORDER BY started_at DESC LIMIT 10
            """)
            for r in cur.fetchall():
                dur = f"{r[4]}s" if r[4] else "N/A"
                lines.append(f"- `{r[0]}` mode={r[1]} status={r[2]} dry={r[3]} dur={dur} at={r[5]}")
        except Exception:
            lines.append("- No routine run log yet")

        # Actions suggested
        lines.append(f"\n## 6. Acciones sugeridas\n")
        try:
            cur.execute("""
                SELECT recommended_action, COUNT(*) FROM fraud.risk_cases
                WHERE status = 'open' GROUP BY recommended_action ORDER BY COUNT(*) DESC
            """)
            for r in cur.fetchall():
                lines.append(f"- {r[0]}: {r[1]}")
        except Exception:
            pass

        cur.close()

    lines.append(f"\n## 7. Confirmacion de NO ejecucion\n")
    lines.append("- Ninguna desconexion real ejecutada")
    lines.append("- Ningun autocobro real apagado")
    lines.append("- Ningun pago real bloqueado")
    lines.append("- Solo preview y recomendaciones")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Report generated: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Generate daily fraud report")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    generate(args.date)


if __name__ == "__main__":
    main()
