# FASE 3.3 — Alerting + Action Engine: escaneo y límites

## 1. Señales ya existentes

| Fuente | Señales |
|--------|---------|
| Endpoint `GET /ops/business-slice/omniview-projection` | Por KPI: `actual`, `projected_expected`, `projected_total`, `attainment_pct`, `gap_to_expected`, `signal` (green/warning/danger), `curve_method`, `curve_confidence`, `fallback_level`, `expected_ratio` |
| `buildProjectionMatrix` + `computeProjectionDeltas` (frontend) | Misma información por celda en `periodDeltas` |
| Root Cause Engine (FASE 3.2) | `main_driver.key`, factores, `recommendation` |
| Matrix trust (Omniview REAL) | `priority_score`, `action`, `trust_recommendations` en banner ejecutivo (independiente del modo proyección) |

## 2. Componentes que ya muestran información crítica

- `BusinessSliceOmniviewMatrix.jsx` — modo proyección, carga de plan, `ProjectionContextBar`
- `OmniviewTopDeviations.jsx` — top 5 peor/mejor por **attainment** (reemplazado en FASE 3.3 por panel de prioridad)
- `OmniviewProjectionDrill.jsx` — gap, curva, breakdown, root cause, Control Loop history
- `BusinessSliceOmniviewMatrixCell.jsx` — semáforo proyección, confianza de curva (`?`)
- `MatrixExecutiveBanner.jsx` — trust operativo (evolución / matriz general)

## 3. Qué se reutiliza (FASE 3.3)

- `rootCauseEngine.js` → `computeRootCause()` para driver principal y contexto
- `projectionMatrixUtils.js` → `computeProjectionDeltas`, `PROJECTION_KPIS`, `fmtAttainment`, `fmtGap`, `SIGNAL_DOT`, `projectionSignalColor`
- `decisionColors.js` — disponible para alinear semántica de severidad si hace falta en el futuro
- Datos ya en memoria: **sin nuevos endpoints**

## 4. Acciones operativas que ya existen en el repo (referencia, no integradas aquí)

| Módulo | Rol |
|--------|-----|
| `backend/.../action_engine_service.py` | Motor de acciones por cohortes (otro dominio) |
| `backend/.../phase2b_actions_service.py` | Persistencia de acciones Phase2B |
| `POST /ops/business-slice/matrix-issue-action` | Log de issue sobre matriz |
| `ActionEngineView.jsx`, `BehavioralAlertsView.jsx` | Pantallas dedicadas (no usadas por FASE 3.3) |

FASE 3.3 **no** conecta a estos servicios; solo deja `buildActionHandoff()` para FASE 3.4+.

## 5. Qué NO se toca

- Backend: ningún router, servicio ni migración
- Tablas de base de datos: ninguna
- `BusinessSliceOmniviewMatrixTable.jsx` — sin cambios (solo celda vía `BusinessSliceOmniviewMatrixCell.jsx`)
- Modo evolución Omniview (sin proyección)
- `projection_expected_progress_service.py` y contratos de API existentes
- `OmniviewTopDeviations.jsx` — archivo conservado; el montaje usa `OmniviewPriorityPanel.jsx`

## 6. Implementación FASE 3.3 (resumen)

- Motor puro frontend: `frontend/src/components/omniview/alertingEngine.js`
- UI: `OmniviewPriorityPanel.jsx`, sección `ActionSection` en drill, badge en celda proyección
- Multigrano: factor `GRAIN_FACTOR` (monthly 1.0, weekly 0.85, daily 0.70) sobre el score para no sobrerreaccionar en diario

## 7. Deudas / límites

- **Persistencia:** alertas solo en runtime (no historial)
- **Persistencia temporal:** no hay serie de períodos anteriores en el panel sin cargar más datos
- **Action Engine backend:** no unificado con Phase2B en esta fase

## 8. Go/No-Go (FASE 3.3)

- [ ] Modo proyección muestra panel de prioridades
- [ ] Drill muestra acción sugerida, equipo, urgencia, razón y breakdown opcional
- [ ] Celdas críticas (danger + attainment &lt; 75%) muestran marca
- [ ] Modo evolución intacto
- [ ] Build frontend OK
- [ ] Sin migraciones DB (N/A)

## 9. Ejemplos de QA (ilustrativos)

| Caso | priority_band | Main driver | Acción típica |
|------|-----------------|-------------|----------------|
| Brecha grande + semáforo rojo + trips KPI | CRITICAL | Volumen (trips) | Demanda / asignación (ops) |
| Revenue gap, driver ticket | HIGH | Ticket promedio | Pricing / mix (pricing) |
| Supply vs trips | MEDIUM / HIGH | Conductores activos | Activación supply |
| Cumplimiento ≥ 100% | WATCH | — | Monitoreo / capacidad |
| Sin root cause completo | LOW–MEDIUM | — | Acción genérica operativa |

## 10. Evidencia sin migraciones DB

FASE 3.3 solo añade archivos frontend bajo `frontend/src/components/` y `docs/`. No hay cambios en `backend/` ni en `alembic/`.
