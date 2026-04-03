"""
Regenera el plan operativo diario (ops.action_plan_daily) desde el Action Engine.
Uso: cd backend && python -m scripts.run_action_orchestrator

Recomendado ejecutar después de: python -m scripts.run_action_engine
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.action_orchestrator_service import run_action_orchestrator

result = run_action_orchestrator()

print("=" * 70)
print("  ACTION ORCHESTRATOR — PLAN OPERATIVO DIARIO")
print("=" * 70)
print(f"  Fecha plan: {result['plan_date']}")
print(f"  Filas motor (action_engine_output): {result['source_rows']}")
print(f"  Planes insertados: {result['plans_inserted']}")
print(f"  Generado UTC: {result['generated_at']}")
print(f"\n{'='*70}")
