"""
Yego Pro Profitability P2.7 -- Root Cause CSV Generator
Exports root cause audit data to CSV files.
READ-ONLY.
"""
import sys, os, csv, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.yego_pro_profitability_service import get_root_cause_audit, PARK_ID

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

def write_csv(filename, rows):
    if not rows: print(f"  [SKIP] {filename} -- no rows"); return
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [OK] {filename} -- {len(rows)} rows")

print("Generating root cause CSVs...")
rc = get_root_cause_audit(park_id=PARK_ID)

write_csv("yego_pro_missing_driver_closes.csv", rc.get("missing_driver_closes", []))
write_csv("yego_pro_missing_plates.csv", rc.get("missing_plates", []))
write_csv("yego_pro_production_without_billing.csv", rc.get("production_without_billing", []))
write_csv("yego_pro_billing_without_support.csv", rc.get("billing_with_support", []))

summary_rows = rc.get("root_cause_summary", [])
if summary_rows:
    path = os.path.join(REPORTS_DIR, "yego_pro_root_cause_summary.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["finding", "severity", "impact"])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"  [OK] yego_pro_root_cause_summary.csv -- {len(summary_rows)} findings")

print("Done.")
