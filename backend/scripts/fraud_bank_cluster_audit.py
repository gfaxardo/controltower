"""Fase 1F-1 — Auditoria de public.payment_details.
Genera docs/fraud/AUDITORIA_FASE1F1_PAYMENT_DETAILS_SOURCE.md
NUNCA muestra account_number completo.
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.db.connection import get_db
from datetime import datetime

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "docs", "fraud", "AUDITORIA_FASE1F1_PAYMENT_DETAILS_SOURCE.md",
)

def mask_account(acct):
    if not acct:
        return None
    s = str(acct).strip()
    if not s:
        return None
    if len(s) >= 8:
        return s[:4] + "****" + s[-4:]
    return "****" + s[-2:]

def norm_key(bank_name, acct):
    bn = str(bank_name or "").strip().lower()
    an = str(acct or "").strip()
    import re
    bn = re.sub(r'[^a-z0-9]', '', bn)
    an = re.sub(r'[^a-z0-9]', '', an)
    return bn + "|" + an

def main():
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'payment_details'
            ORDER BY ordinal_position
        """)
        cols = [(r[0], r[1]) for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM public.payment_details")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT driver_id) FROM public.payment_details")
        distinct_drivers = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT account_number) FROM public.payment_details")
        distinct_accts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM public.payment_details WHERE account_number IS NULL OR TRIM(account_number) = ''")
        null_accts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM public.payment_details WHERE bank_name IS NULL OR TRIM(bank_name) = ''")
        null_banks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM public.payment_details WHERE driver_id IS NULL OR TRIM(driver_id) = ''")
        null_drivers = cur.fetchone()[0]

        # Cluster analysis
        cur.execute("""
            SELECT normalized_key, COUNT(DISTINCT driver_id) AS dc,
                   MIN(account_number) AS min_acct,
                   MIN(bank_name) AS min_bank
            FROM (
                SELECT driver_id, account_number, bank_name,
                       LOWER(REGEXP_REPLACE(COALESCE(bank_name,''), '[^a-z0-9]','','g')) || '|' ||
                       REGEXP_REPLACE(COALESCE(account_number,''), '[^a-z0-9]','','g') AS normalized_key
                FROM public.payment_details
                WHERE account_number IS NOT NULL AND TRIM(account_number) <> ''
                  AND driver_id IS NOT NULL AND TRIM(driver_id) <> ''
            ) sub GROUP BY normalized_key HAVING COUNT(DISTINCT driver_id) >= 2
            ORDER BY dc DESC
        """)
        clusters = [{"key": r[0], "driver_count": r[1], "masked": mask_account(r[2]), "bank": r[3]} for r in cur.fetchall()]

        cur.close()

    clusters_2 = len(clusters)
    clusters_3 = sum(1 for c in clusters if c["driver_count"] >= 3)
    clusters_5 = sum(1 for c in clusters if c["driver_count"] >= 5)
    drivers_affected = sum(c["driver_count"] for c in clusters)

    lines = []
    lines.append("# AUDITORIA FASE 1F-1 — PAYMENT DETAILS SOURCE\n")
    lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    lines.append("## Columnas\n")
    for name, dtype in cols:
        lines.append(f"- `{name}` ({dtype})")
    lines.append(f"\n## Estadisticas\n")
    lines.append(f"- Total rows: {total}")
    lines.append(f"- Distinct driver_id: {distinct_drivers}")
    lines.append(f"- Distinct account_number: {distinct_accts}")
    lines.append(f"- Null/empty account_number: {null_accts}")
    lines.append(f"- Null/empty bank_name: {null_banks}")
    lines.append(f"- Null/empty driver_id: {null_drivers}")

    lines.append(f"\n## Clusters bancarios\n")
    lines.append(f"- Cuentas compartidas por 2+ drivers: {clusters_2}")
    lines.append(f"- Cuentas compartidas por 3+ drivers: {clusters_3}")
    lines.append(f"- Cuentas compartidas por 5+ drivers: {clusters_5}")
    lines.append(f"- Total drivers en clusters: {drivers_affected}")

    lines.append(f"\n## Top 10 clusters (masked)\n")
    lines.append("| Bank | Masked Account | Drivers |")
    lines.append("|---|---|---|")
    for c in clusters[:10]:
        lines.append(f"| {c['bank']} | {c['masked']} | {c['driver_count']} |")

    lines.append("\n## Capacidades\n")
    has_min_cols = "driver_id" in [c[0] for c in cols] and "bank_name" in [c[0] for c in cols] and "account_number" in [c[0] for c in cols]
    lines.append(f"- Columnas minimas (driver_id, bank_name, account_number): {'SI' if has_min_cols else 'NO'}")
    lines.append(f"- Bank source listo para wiring: {'SI' if has_min_cols else 'NO'}")

    lines.append("\n## Decision\n")
    lines.append(f"**{'GO' if has_min_cols and clusters_2 > 0 else 'NO-GO'}** — "
                 f"columnas minimas={'OK' if has_min_cols else 'FALTA'}, clusters_2={clusters_2}")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Reporte: {OUTPUT}")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
