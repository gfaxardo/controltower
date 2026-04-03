# Learning Engine — Fase 9 (mejora continua basada en resultados)

## 1. Resumen ejecutivo

La fase 9 cierra el ciclo **detectar → planificar → ejecutar → medir → mejorar**. El sistema ahora:

- **mide** si una acción ejecutada produjo efecto real (before vs after),
- **acumula** efectividad histórica por acción, ciudad y país,
- **ajusta** la priorización del Action Engine y el volumen del Orchestrator usando ese historial,
- todo con **reglas explícitas** (no ML), **trazable** y **reversible**.

No se ejecutan acciones externas, no se reescribe el engine, y el multiplicador tiene caps seguros.

## 2. Qué aprende el sistema

| Pregunta | Respuesta |
|----------|-----------|
| ¿La reactivación en Lima funcionó? | Compara `active_drivers` antes vs después (ventana 7d). Si subió ≥ 5 %, `success_flag = true`. |
| ¿Qué acciones son más efectivas en Bogotá? | `ops.action_effectiveness` filtra `city = 'bogota'` y ordena por `success_rate`. |
| ¿Debo subir prioridad a CANCEL_RATE_SPIKE? | Si `success_rate ≥ 70 %` → `effectiveness_multiplier = 1.2` → sube automáticamente. |
| ¿Debo reducir volumen de una acción poco útil? | Si `success_rate ≤ 30 %` → multiplicador `0.8` → volumen baja ~20 %. |

## 3. Cómo se mide el éxito

### Tabla `ops.action_evaluation_rules`

Cada acción tiene una regla explícita:

| action_id | result_metric | expected_direction | window | threshold |
|-----------|---------------|--------------------|--------|-----------|
| DRIVER_REACTIVATION | active_drivers | up | 7d | 5 % |
| CANCEL_RATE_SPIKE | cancel_rate | down | 7d | 2 % |
| TICKET_DROP | revenue | up | 7d | 3 % |
| NAN_RAW_DATA | data_quality_issue_count | down | 7d | 10 % |
| ... | ... | ... | ... | ... |

### Proceso de evaluación

1. Toma acciones con `status = 'done'` en `action_execution_log`.
2. Busca la regla en `action_evaluation_rules`.
3. Calcula `result_value_before` = métrica en `[exec_date - window, exec_date)`.
4. Calcula `result_value_after` = métrica en `[exec_date, exec_date + window)`.
5. Si `expected_direction = 'up'`: `delta = after - before`.
   Si `expected_direction = 'down'`: `delta = before - after`.
6. `success_flag = (delta_pct >= success_threshold_pct)`.
7. Escribe todo en el mismo registro del log.

### Métricas soportadas

- `trips` — viajes completados (MV diaria)
- `revenue` — gross_revenue (MV diaria)
- `active_drivers` — conductores activos en `driver_segments`
- `trips_per_driver` — trips / active_drivers
- `cancel_rate` — cancelled / requested × 100
- `proxy_pct` — último valor de alerta de proxy
- `data_quality_issue_count` — alertas blocked/warning en la ventana

## 4. Cómo impacta la priorización

### Action Engine (`persist_action_output`)

```
priority_score_final = priority_score_base × effectiveness_multiplier
```

| success_rate | multiplier | efecto |
|-------------|------------|--------|
| ≥ 70 % | 1.20 | boost: acción probada sube en prioridad |
| 31–69 % | 1.00 | neutro |
| ≤ 30 % | 0.80 | castigo: baja en ranking sin desaparecer |
| sin historial (< 3 ejecuciones) | 1.00 | neutro (no se penaliza lo desconocido) |

Columnas nuevas en `ops.action_engine_output`: `effectiveness_score`, `effectiveness_scope`, `priority_score_base`, `priority_score_final`.

### Orchestrator (`run_action_orchestrator`)

El `suggested_volume` se multiplica por el mismo effectiveness multiplier:

- Acción con alta efectividad → volumen sube hasta +20 %.
- Acción con baja efectividad → volumen baja hasta -20 %.
- Caps duros: mínimo 10, máximo 2000.

### Lookup jerárquico

1. Busca efectividad por `(action_id, city, country)`.
2. Si < 3 ejecuciones, sube a `(action_id, country)`.
3. Si tampoco hay, usa `(action_id)` global.
4. Si no hay historial alguno, `multiplier = 1.0, scope = 'none'`.

## 5. Limitaciones honestas

- **Correlación, no causalidad**: si `active_drivers` subió tras una reactivación, no sabemos si fue *por* la reactivación o por factores externos.
- **Métricas de proxy**: `active_drivers` viene de la vista `driver_segments` que es un snapshot (no incremental). Es la mejor señal disponible sin telemetría individual.
- **Ventana fija**: la ventana de evaluación es por acción, no adaptativa. Si una acción tarda 30 días en impactar pero la ventana es 7d, dará falso negativo.
- **No ML**: no hay modelo entrenado; son reglas umbral. Suficiente para el volumen operativo actual.

## 6. Cómo operar el ciclo completo

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. GENERAR ACCIONES                                                │
│    python -m scripts.run_action_engine                             │
│    o POST /ops/action-engine/run                                   │
├─────────────────────────────────────────────────────────────────────┤
│ 2. GENERAR PLAN DIARIO                                             │
│    python -m scripts.run_action_orchestrator                       │
│    o POST /ops/action-plan/run                                     │
├─────────────────────────────────────────────────────────────────────┤
│ 3. EJECUTAR (humano)                                               │
│    → equipo trabaja el plan                                        │
│    → marca acciones como done:                                     │
│      POST /ops/action-plan/log?action_plan_id=&action_id=&owner=   │
│           &status=done                                             │
├─────────────────────────────────────────────────────────────────────┤
│ 4. EVALUAR                                                         │
│    python -m scripts.run_action_learning_evaluation                │
│    o POST /ops/action-learning/evaluate                            │
│    (solo evalúa acciones cuya ventana ya cerró)                    │
├─────────────────────────────────────────────────────────────────────┤
│ 5. APRENDER (automático)                                           │
│    En la próxima corrida del engine (paso 1), persist_action_output│
│    busca effectiveness_multiplier y ajusta priority_score_final.   │
│    En la próxima corrida del orchestrator (paso 2), ajusta volumen.│
└─────────────────────────────────────────────────────────────────────┘
```

## 7. Extensión del `action_execution_log`

Columnas nuevas (todas nullable, compatibles con filas existentes):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `result_metric` | TEXT | Qué se midió (active_drivers, trips, cancel_rate, …) |
| `result_value_before` | NUMERIC | Valor en ventana pre-ejecución |
| `result_value_after` | NUMERIC | Valor en ventana post-ejecución |
| `result_delta` | NUMERIC | Diferencia ajustada por dirección |
| `success_flag` | BOOLEAN | ¿Cumplió umbral de éxito? |
| `evaluation_window_days` | INTEGER | Días de la ventana usada |
| `evaluated_at` | TIMESTAMPTZ | Cuándo se evaluó |

## 8. Vista `ops.action_effectiveness`

Agrega evaluaciones por `(action_id, city, country)`:

- `executions_count`
- `success_count`
- `success_rate` (%)
- `avg_result_delta`
- `last_execution_at`
- `last_evaluated_at`

Permite filtrar por ciudad, país o acción. Alimenta el multiplier.

## 9. Ejemplo real de aprendizaje

Supongamos:

1. Engine detecta `CANCEL_RATE_SPIKE` en Lima (cancel rate subió 8 pp WoW).
2. Orchestrator genera plan: "Auditar cancelaciones elevadas", volumen=30, segment=active.
3. Equipo ejecuta y marca `done` el 2026-03-20.
4. Evaluador corre el 2026-03-28 (ventana 7d cerrada):
   - `cancel_rate` antes (13–20 mar): 22.5 %
   - `cancel_rate` después (20–27 mar): 19.1 %
   - `delta = 22.5 - 19.1 = 3.4` (direction=down)
   - `delta_pct = 3.4 / 22.5 × 100 = 15.1 %` (> threshold 2 %)
   - `success_flag = true`
5. Próximo engine run:
   - `CANCEL_RATE_SPIKE` tiene `success_rate = 80 %` en Lima
   - `effectiveness_multiplier = 1.20`
   - `priority_score_final = base × 1.20` → sube en ranking
6. Orchestrator: `suggested_volume = 30 × 1.20 = 36`

## 10. Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ops/action-learning/effectiveness` | Efectividad agregada (action_id, city, country) |
| GET | `/ops/action-learning/executions` | Log de acciones evaluadas con before/after |
| GET | `/ops/action-learning/evaluation-rules` | Reglas de evaluación (métrica, dirección, umbral) |
| POST | `/ops/action-learning/evaluate` | Ejecutar evaluación de acciones `done` |

## 11. Archivos modificados / añadidos

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/125_learning_engine_phase9.py` | DDL: extend log, evaluation_rules, effectiveness view, engine_output cols |
| `backend/app/services/action_learning_service.py` | Evaluador, efectividad, multiplier lookup |
| `backend/app/services/action_engine_service.py` | `persist_action_output` aplica effectiveness multiplier |
| `backend/app/services/action_orchestrator_service.py` | Volumen ajustado por effectiveness; caps min/max |
| `backend/app/routers/ops.py` | 4 endpoints `/ops/action-learning/*` |
| `backend/scripts/run_action_learning_evaluation.py` | CLI para evaluación |
| `docs/LEARNING_ENGINE_PHASE9.md` | Este documento |

## 12. GO / NO-GO

| Criterio | Estado |
|----------|--------|
| Mide antes/después de cada acción | GO |
| Efectividad histórica por acción/ciudad | GO |
| Engine ajusta prioridad con feedback | GO |
| Orchestrator ajusta volumen prudentemente | GO |
| No rompe engine ni orchestrator existentes | GO — se añade capa aditiva |
| Trazable (scope, base, final en output) | GO |
| No ML complejo | GO — reglas umbral + fallback jerárquico |
| Auditable | GO — todo queda en BD |

**GO** para producción tras aplicar migración 125.

## 13. Siguiente paso propuesto

1. `cd backend && alembic upgrade head`
2. `python -m scripts.run_action_engine` (para tener output del día)
3. Marcar algunas acciones como `done` (manual o via API)
4. Esperar ventana de evaluación (≥ 7 días)
5. `python -m scripts.run_action_learning_evaluation`
6. Verificar `GET /ops/action-learning/effectiveness`
7. Próximo ciclo: el engine y el orchestrator ya usarán el feedback

Opcional: programar `run_action_learning_evaluation` en cron semanal.
