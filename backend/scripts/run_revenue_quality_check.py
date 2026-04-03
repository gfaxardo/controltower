"""
Ejecuta check de calidad de revenue y persiste alertas.
Uso: cd backend && python -m scripts.run_revenue_quality_check
"""
import sys, os, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.revenue_quality_service import run_revenue_quality_check, persist_alerts

result = run_revenue_quality_check()
persisted = persist_alerts(result.get("alerts", []))

print("=" * 70)
print("  REVENUE QUALITY CHECK")
print("=" * 70)
print(f"  Timestamp: {result['check_ts']}")
print(f"  Overall: {result['overall_status']}")
print(f"  Alerts: {result['alerts_count']} "
      f"(blocked={result['blocked_count']}, "
      f"warning={result['warning_count']}, "
      f"ok={result['ok_count']})")
print(f"  Persisted: {persisted}")

for a in result["alerts"]:
    icon = {"ok": "  ", "warning": "! ", "blocked": "X "}[a["severity"]]
    print(f"\n  [{a['severity'].upper():7}] {icon}{a['domain']}")
    print(f"           {a['metric']}: {a['observed_value']} (threshold: {a.get('threshold')})")
    print(f"           {a['message']}")
    if a.get("recommendation"):
        print(f"           -> {a['recommendation']}")

print(f"\n{'=' * 70}")
print(f"  Check complete. Overall: {result['overall_status']}")
