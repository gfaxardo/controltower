"""
Evalúa acciones ejecutadas (status = 'done') y escribe resultados en action_execution_log.
Uso: cd backend && python -m scripts.run_action_learning_evaluation

Flujo recomendado:
  1. run_action_engine  (genera acciones)
  2. run_action_orchestrator  (genera plan)
  3. equipo marca acciones como 'done' via POST /ops/action-plan/log o /ops/action-engine/log
  4. run_action_learning_evaluation  (mide before/after y escribe success_flag)
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.action_learning_service import evaluate_executions, get_effectiveness

result = evaluate_executions(min_status="done", force_re_evaluate=False, limit=500)

print("=" * 70)
print("  LEARNING ENGINE — EVALUACIÓN DE ACCIONES")
print("=" * 70)
print(f"  Evaluadas:    {result['evaluated']}")
print(f"  Omitidas:     {result['skipped']}")
print(f"  Errores:      {result['errors']}")
print(f"  Timestamp:    {result['evaluated_at']}")

eff = get_effectiveness(limit=50)
if eff:
    print(f"\n  EFECTIVIDAD HISTÓRICA (top {len(eff)} combinaciones)")
    print(f"  {'ACTION_ID':<25} {'CITY':<15} {'EXECS':>6} {'OK':>4} {'RATE':>7} {'AVG_DELTA':>10}")
    for e in eff:
        print(
            f"  {str(e.get('action_id','')):<25} "
            f"{str(e.get('city','') or '(global)'):<15} "
            f"{e.get('executions_count',0):>6} "
            f"{e.get('success_count',0):>4} "
            f"{e.get('success_rate','?'):>7} "
            f"{e.get('avg_result_delta','?'):>10}"
        )
else:
    print("\n  Sin historial de efectividad todavía (no hay acciones evaluadas).")

print(f"\n{'='*70}")
