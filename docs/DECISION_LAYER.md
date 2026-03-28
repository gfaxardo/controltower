# Decision Layer + Action Engine

Convierte **Data Trust** y **Confidence Engine** en decisiones operativas accionables.

## Componentes

- **view_criticality** (`backend/app/config/view_criticality.py`): criticidad por vista (`critical` | `high` | `medium` | `low`).
- **decision_engine** (`backend/app/services/decision_engine.py`): señal de decisión por vista (action, priority, message, reason). Fuente única de verdad: Confidence Engine.

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ops/decision-signal?view=<vista>` | Señal completa: view, trust_status, confidence_score, criticality, action, priority, message, reason, last_update, details. |
| GET | `/ops/decision-signal/summary` | Lista `[{ view, action, priority }, ...]` para todas las vistas. |

## Reglas de gobierno

1. **Ninguna vista crítica puede estar en OK si confidence < 80.** El engine fuerza `trust_status` a warning cuando aplica.
2. **Si decision = STOP_DECISIONS** → no debe mostrarse como OK en UI (reason explícito; indicador 🔴 STOP).
3. **Las decisiones son explicables:** todo resultado incluye `reason` (ej. `completeness_missing`, `consistency_major_diff`, `ok`).
4. **No hay lógica oculta:** toda la matriz y forzados viven en `decision_engine.py`.

## Matriz (trust_status × criticality)

| trust_status | critical | high | medium | low |
|--------------|----------|------|--------|-----|
| blocked      | STOP_DECISIONS P0 | LIMIT_DECISIONS P1 | MONITOR P2 | MONITOR P2 |
| warning      | USE_WITH_CAUTION P1 | MONITOR_CLOSELY P2 | MONITOR P2 | MONITOR P2 |
| ok           | OPERATE_NORMAL P3 | OPERATE_NORMAL P3 | OPERATE_NORMAL P3 | OPERATE_NORMAL P3 |

## Forzados

- `completeness == missing` y vista **critical** → **STOP_DECISIONS** P0.
- `consistency == major_diff` → **STOP_DECISIONS** P0.
- `confidence_score < 40` → **STOP_DECISIONS** P0.

## Logging

Solo se logra cuando la acción es relevante:

```
[DECISION_ENGINE] view=real_lob action=STOP_DECISIONS priority=P0 reason=completeness_missing
```

Acciones logueadas: `STOP_DECISIONS`, `LIMIT_DECISIONS`, `USE_WITH_CAUTION`.

## Integración UI (resumen)

En el header de **Resumen** (ExecutiveSnapshotView) se muestra un indicador mínimo:

- 🔴 **STOP** — STOP_DECISIONS o LIMIT_DECISIONS
- 🟡 **CAUTION** — USE_WITH_CAUTION, MONITOR_CLOSELY, MONITOR
- 🟢 **OK** — OPERATE_NORMAL

Tooltip: mensaje + prioridad. Sin rediseño; sin tablas ni gráficos nuevos.

## Validación

Tests en `backend/tests/test_decision_engine.py`:

- real_lob incompleto → STOP_DECISIONS P0
- supply warning → MONITOR_CLOSELY
- behavioral_alerts warning → MONITOR
- sistema OK → OPERATE_NORMAL
- consistency major_diff → STOP_DECISIONS
- confidence < 40 → P0
- Estructura de respuesta y summary

Veredicto: **DECISION_LAYER_APPLIED**, **ACTION_ENGINE_BASIC**.
