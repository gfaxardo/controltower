"""
Ejecuta Action Engine y persiste acciones del día.
Uso: cd backend && python -m scripts.run_action_engine
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.action_engine_service import run_action_engine, persist_action_output

result = run_action_engine()
persisted = persist_action_output(result)

print("=" * 70)
print("  ACTION ENGINE — OUTPUT OPERATIVO")
print("=" * 70)
print(f"  Fecha: {result['run_date']}")
print(f"  Total acciones: {result['total_actions']}")
print(f"  Critical: {result['critical']} | High: {result['high']} | "
      f"Medium: {result['medium']} | Low: {result['low']}")
print(f"  Persistidas: {persisted}")

for i, a in enumerate(result["actions"], 1):
    sev = a["severity"].upper()
    city_label = f"{a.get('country','')}/{a.get('city','')}" if a.get("city") else "(global)"
    print(f"\n  #{i} [{sev:8}] P={a['priority_score']:>7.1f} | {city_label}")
    print(f"     {a['action_name']}")
    print(f"     {a['reason']}")
    print(f"     Metric: {a.get('metric_name')}={a.get('metric_value')} (threshold: {a.get('threshold')})")
    print(f"     Owner: {a.get('suggested_owner')}")

print(f"\n{'='*70}")
