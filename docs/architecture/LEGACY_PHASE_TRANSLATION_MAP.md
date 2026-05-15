# YEGO Control Tower — Mapa de Traducción de Fases Legacy a Arquitectura Canónica

**Versión:** 1.0.0
**Fecha:** 2026-05-15
**Propósito:** Traducir las fases técnicas legacy (2A, 2B, 2C, 2C+) a la arquitectura maestra por motores. Los nombres legacy **se mantienen en código** como identificadores técnicos, pero **no deben usarse como roadmap de producto**.

---

## Regla General

> Los identificadores `phase2a`, `phase2b`, `phase2c` en nombres de archivos, routers, endpoints, tablas y vistas SQL son **nombres técnicos legacy** que permanecen inalterados en el código. La arquitectura del producto se rige por los **9 motores canónicos** definidos en [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md).

---

## Phase 2A

### Traducción Arquitectónica
**Pertenece a: Control Foundation**

### Alcance Legacy
- Plan vs Real mensual (vistas `v_plan_vs_real_realkey_final`, `v_plan_trips_monthly_latest`).
- Universo operativo (mapeo Plan→Real, realkey).
- Deltas mensuales y `comparison_status`.
- Real vs Proyección (fundación analítica, no Forecast Engine).
- Eliminación de proxies de revenue (uso de revenue real).
- `GET /ops/plan-vs-real/monthly`, `GET /ops/compare/overlap-monthly`.

### Artefactos Legacy Detectados
| Capa | Artefacto | Tipo |
|------|-----------|------|
| Backend main | `"message": "YEGO Control Tower API - Fase 2A"` en `main.py:193` | String raíz |
| Backend router | `backend/app/routers/ops.py` (referencias Phase 2A en docstrings) | Router |
| Backend service | `backend/app/services/core_service.py` (reglas de comparación FASE 2A) | Service |
| Backend service | `backend/app/services/plan_vs_real_service.py` (monthly Plan vs Real) | Service |
| Backend scripts | `backend/scripts/validate_phase2a_no_proxy.py` | Validación |
| Backend migrations | `008_consolidate_real_monthly_phase2a.py` | Migración |
| Frontend | `MonthlySplitView.jsx` (etiqueta "Fase 2A" en UI) | Componente |
| Frontend | `RealVsProjectionView.jsx` (comentario "Fase 2A — Real vs Proyección") | Componente |
| Frontend api | `api.js:736` (comentario "Fase 2A — Real vs Proyección") | API client |
| Docs | `docs/fase2a_salida_ejecutiva.md`, `docs/fase2a_real_vs_projection_foundation.md` | Documentación |

### Nota Importante
El endpoint raíz `GET /` retorna `"message": "YEGO Control Tower API - Fase 2A"`. Esto es un string legacy que refleja el momento en que se creó. La API está en versión `2.0.0` y el producto está en **Control Foundation ACTIVE**.

---

## Phase 2B

### Traducción Arquitectónica
**Pertenece parcialmente a: Control Foundation + Diagnostic Engine inicial**

### Alcance Legacy
- Plan vs Real semanal (`v_plan_vs_real_weekly`, `mv_real_trips_weekly`).
- Alertas semanales (`v_alerts_2b_weekly`).
- **Registro básico de acciones** (`ops.phase2b_actions`): tracking manual de acciones operativas.
- Baselines semanales por país (weights de Plan Semanal).
- `GET /phase2b/weekly/plan-vs-real`, `GET /phase2b/weekly/alerts`.
- `POST/GET/PATCH /phase2b/actions`.

### Artefactos Legacy Detectados
| Capa | Artefacto | Tipo |
|------|-----------|------|
| Backend router | `backend/app/routers/phase2b.py` (router completo, prefijo `/phase2b`) | Router |
| Backend service | `backend/app/services/phase2b_weekly_service.py` | Service |
| Backend service | `backend/app/services/phase2b_actions_service.py` | Service |
| Backend migrations | `014_create_phase2b_weekly_views.py` | Migración |
| Backend migrations | `015_create_phase2b_actions_table.py` | Migración |
| Backend migrations | `016_enhance_phase2b_weekly_views_margin.py` | Migración |
| Backend migrations | `017_create_plan_weekly_baselines.py` | Migración |
| Backend sql | `backend/sql/phase2b_weekly_checks.sql` | SQL |
| Backend scripts | `backend/scripts/validate_phase2b_weekly.py` | Validación |
| Frontend | `WeeklyPlanVsRealView.jsx` (etiqueta "Fase 2B - Semanal") | Componente |
| Frontend | `Phase2BActionsTrackingView.jsx` (tracking de acciones 2B) | Componente |
| Frontend | `RegisterActionModal.jsx` (crear acción 2B) | Componente |
| Frontend api | `api.js` (funciones `getPlanVsRealWeekly`, `getWeeklyAlerts`, `createPhase2BAction`, `getPhase2BActions`, `updatePhase2BAction`) | API client |
| Frontend App | `App.jsx:14,494-495` (import y render de Phase2BActionsTrackingView) | App shell |
| PowerShell | `scripts/phase2b_closeout.ps1`, `scripts/orchestrate_phase2b_closeout.ps1` | Scripts |
| Docs | `docs/PHASE_2B_CLOSEOUT.md` y ~20 docs más con referencias | Documentación |
| DB | `ops.phase2b_actions`, `ops.phase2b_alert_audit`, `ops.phase2b_sla_status` | Tablas |
| DB | `ops.v_plan_vs_real_weekly`, `ops.v_alerts_2b_weekly` | Vistas |

### Nota Crítica
**`ops.phase2b_actions` NO equivale al futuro Action Engine.** Es un registro operacional simple de seguimiento de acciones (tracking table). Pertenece a Control Foundation / accountability operacional básico. El Action Engine arquitectónico es un motor de priorización y recomendación automática que requiere Decision Engine previo.

---

## Phase 2C

### Traducción Arquitectónica
**Pertenece a: Control Foundation / Accountability operacional básico**

### Alcance Legacy
- Scoreboard semanal de ejecución (`v_phase2c_weekly_scoreboard`).
- Backlog de acciones por owner (`v_phase2c_backlog_by_owner`).
- Breaches de SLA (`v_phase2c_sla_breaches`).
- Snapshot de alertas y evaluación de SLA.
- `GET /phase2c/scoreboard`, `GET /phase2c/backlog`, `GET /phase2c/breaches`.
- `POST /phase2c/run-snapshot`.

### Artefactos Legacy Detectados
| Capa | Artefacto | Tipo |
|------|-----------|------|
| Backend router | `backend/app/routers/phase2c.py` (router completo, prefijo `/phase2c`, endpoints scoreboard/backlog/breaches/snapshot) | Router |
| Backend service | `backend/app/services/phase2c_accountability_service.py` | Service |
| Backend migrations | `018_create_phase2c_accountability.py` | Migración |
| Backend scripts | `backend/scripts/phase2c_snapshot_and_sla.py` | Script |
| Frontend | `Phase2CAccountabilityView.jsx` | Componente |
| Frontend api | `api.js` (`getPhase2CScoreboard`, `getPhase2CBacklog`, `getPhase2CBreaches`, `runPhase2CSnapshot`) | API client |
| Frontend App | `App.jsx:15,496` (import y render de Phase2CAccountabilityView) | App shell |
| DB | `ops.phase2b_sla_status` (referenciada en contexto 2C), `ops.v_phase2c_*` | Tablas/Vistas |

### Nota Crítica
**Scoreboard, backlog y breaches de SLA NO equivalen a Decision Engine ni Action Engine.** Son mecanismos de accountability operacional (seguimiento de disciplina de ejecución). Pertenecen a Control Foundation. No toman decisiones automáticas, solo miden ejecución humana.

---

## Phase 2C+

### Traducción Arquitectónica
**Pertenece a: Control Foundation**

### Alcance Legacy
- Universo LOB: Plan vs Real con mapeo LOB (`v_phase2c_lob_universe`).
- Viajes reales sin mapeo a LOB del plan (unmatched trips).
- Regla madre LOB = tipo_servicio, con B2B override y city normalization.
- LOB Homologation system.
- `GET /phase2c/lob-universe`, `GET /phase2c/lob-universe/unmatched`.

### Artefactos Legacy Detectados
| Capa | Artefacto | Tipo |
|------|-----------|------|
| Backend router | `backend/app/routers/phase2c.py` (endpoints lob-universe, unmatched bajo prefijo `/phase2c`) | Router |
| Backend service | `backend/app/services/lob_universe_service.py` | Service |
| Backend adapter | `backend/app/adapters/lob_universe_repo.py` | Repository |
| Backend migrations | `019_create_phase2c_lob_universe_mapping.py` | Migración |
| Backend migrations | `020_enhance_phase2c_lob_with_mother_rule.py` | Migración |
| Backend migrations | `021_create_lob_homologation_system.py` | Migración |
| Frontend | `LobUniverseView.jsx` | Componente |
| Frontend | `RealLOBDrillView.jsx` (comentario "Fase 2C+") | Componente |
| Frontend api | `api.js:375-383` (`getLobUniverse`, `getUnmatchedTrips`) | API client |
| Frontend App | `App.jsx:16,499` (import y render de LobUniverseView) | App shell |

---

## Resumen de Traducción

| Fase Legacy | Motor Canónico | Rol en Arquitectura Nueva |
|-------------|---------------|--------------------------|
| **Phase 2A** | Control Foundation | Plan vs Real mensual, universo operativo, real vs proyección fundacional |
| **Phase 2B** | Control Foundation + Diagnostic inicial | Plan vs Real semanal, alertas, registro básico de acciones |
| **Phase 2C** | Control Foundation (accountability) | Scoreboard, backlog, breaches de SLA |
| **Phase 2C+** | Control Foundation | Universo LOB, mapeo Plan→Real, viajes sin mapeo |

---

## Reglas de Convivencia

1. **Los nombres legacy (phase2a, phase2b, phase2c) en archivos, endpoints, tablas y vistas NO se renombran.** Son identificadores técnicos estables.
2. **Los nombres legacy en strings visibles al usuario** (etiquetas UI como "Fase 2B - Semanal", "Fase 2C – Ejecución y Accountability") pueden mantenerse temporalmente pero deberían migrarse a nomenclatura funcional (ej. "Plan vs Real Semanal", "Accountability").
3. **Toda nueva documentación usa la nomenclatura de motores canónicos**, no fases legacy.
4. **Los scripts de closeout** (`phase2b_closeout.ps1`, etc.) son herramientas operativas legacy. Su lógica puede reutilizarse bajo nombres de motor cuando corresponda.
5. **Las migraciones de Alembic** con nombres phase2* son históricas y no se modifican.

---

## Referencias Cruzadas

- [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md) — Roadmap maestro.
- [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md) — Límites de cada motor.
- [ROADMAP_GOVERNANCE_RULES.md](./ROADMAP_GOVERNANCE_RULES.md) — Reglas de gobierno.
