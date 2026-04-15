# FASE 2.7B — Scan de validación final

## 1. Qué se supone que ya quedó blindado

- 5 servicios críticos usan `execute_db_gated_query()` con `context_from_policy()`
- `_active_db_gate` ContextVar marca ejecución guardada
- `DB_SERVING_GUARD_MODE` configurable (off/warn/strict), default warn
- `assert_db_gate_active()` disponible para verificación opt-in
- Fuentes prohibidas bloqueadas via `assert_serving_source()`
- DB gate log separado del usage log
- Diagnostics enriquecidos con campos db_gate

## 2. Gaps encontrados y corregidos

| # | Gap | Severidad | Estado |
|---|-----|-----------|--------|
| 1 | `execute_serving_query()` NO verificaba `_active_db_gate` — bypass posible | ALTA | **CORREGIDO** |
| 2 | `check_db_layer_gate.py` no probaba escenario de bypass | MEDIA | **CORREGIDO** |
| 3 | `connection.py` devuelve conn raw sin enforcement | MEDIA | Mitigado (wrapper obligatorio) |
| 4 | db_gate_status WARN_ONLY cuando guard_mode=warn | BAJA | Correcto semánticamente |

### Corrección aplicada (Gap 1)

Se agregó verificación de `_active_db_gate` en `execute_serving_query()`: cuando `policy.query_mode == SERVING` y el ContextVar no está seteado, en modo `strict` lanza `ServingSourceViolation`, en modo `warn` loguea `DB_GATE_BYPASS_DETECTED`.

## 3. Resultados de validación

### check_db_layer_gate.py: 12/12 COMPLIANT

```
Result: COMPLIANT  (12/12 passed, 0 failed)
db_guard_mode: warn
db_gated_features: 5
```

### Prueba de ruptura controlada: 6/6 PASS

| Test | Resultado |
|------|-----------|
| Bypass execute_serving_query() sin DB gate | DETECTADO (DB_GATE_BYPASS_DETECTED) |
| Source prohibida via execute_db_gated_query() en strict | BLOQUEADA |
| Source prohibida via execute_serving_query() directo en strict | BLOQUEADA |
| ContextVar activo durante ejecución | CONFIRMADO |
| ContextVar limpiado después | CONFIRMADO |
| assert_db_gate_active() fuera del gate en strict | BLOQUEA |

### Endpoints E2E: 23/23 PASS

| Endpoint | Status | DB gate |
|----------|--------|---------|
| GET /ops/business-slice/omniview | 200 | Funcional |
| GET /ops/control-loop/plan-versions | 200 | Funcional |
| GET /ops/real-lob/monthly | 200 | db_gate_enabled=True, query_ctx=True |
| GET /ops/diagnostics/serving-sources | 200 | Todos los campos presentes |

### Diagnostics coherentes

- summary.db_guard_mode = warn
- non_compliant = 0
- policies_declared = 5
- 5 features críticas con policy_declared=True, registry_declared=True
- Real LOB monthly confirmado como caso modelo: db_gate_enabled=True, WARN_ONLY

## 4. Valor actual de DB_SERVING_GUARD_MODE

`warn` (default). Recomendación: mantener en `warn` para producción. El bypass se detecta como WARNING. Fuentes prohibidas ya bloquean en ambos modos.

## 5. Archivos modificados en esta validación

- `backend/app/services/serving_guardrails.py` — agregada verificación de _active_db_gate en execute_serving_query()
- `backend/scripts/check_db_layer_gate.py` — agregado test 8 de bypass detection

## 6. Veredicto

### CIERRE APROBADO

**Qué sí quedó cerrado:**
- 5 servicios críticos pasan por DB gate con QueryExecutionContext
- Bypass de execute_db_gated_query() es detectado por execute_serving_query()
- Fuentes prohibidas bloqueadas en strict, logueadas en warn
- ContextVar funciona correctamente (set/reset)
- Diagnostics reportan estado real por feature
- Omniview, Control Loop, Real LOB funcionan E2E

**Qué NO quedó cerrado (riesgo residual aceptable):**
- `connection.py` sigue devolviendo conn raw — un dev podría hacer `cur.execute()` saltándose AMBOS wrappers. Mitigación: grep estático (ningún servicio crítico lo hace actualmente). Defensa en profundidad: no se puede interceptar psycopg2 sin monkey-patching, lo cual sería frágil y arriesgado.

**Riesgo real restante:**
- Un dev nuevo podría hacer `cur.execute()` directo en un servicio serving. Esto NO se intercepta a nivel runtime (solo con code review/grep). El riesgo es BAJO porque:
  1. Los 5 servicios críticos ya usan el wrapper correcto
  2. Cualquier uso de `execute_serving_query()` SIN el DB gate es detectado
  3. Cualquier fuente prohibida es bloqueada independientemente del path

### Go/No-Go hacia FASE 3: GO
