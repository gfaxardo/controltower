# ROADMAP REAL ACTUAL — CONTROL TOWER

Reconstruido: 2026-05-23

---

## 0. Weekly Bug — Status

**No bug encontrado.** API devuelve 1463 rows desde `served_from=fact`, misma estructura que daily/monthly. La tabla renderiza correctamente con los mismos datos. El reporte original de "weekly no carga" fue previo a:
- Fix de `VITE_API_URL` (apuntaba a puerto equivocado)
- Refresh de serving facts para colombia (daily/weekly estaban incompletos)
- ALTER TABLE para permitir monthly

---

## 1. Arquitectura Canónica — 9 Motores

| # | Motor | Estado Real |
|---|-------|-------------|
| 1 | **Control Foundation** | ✅ CERRADO (GO) |
| 2 | **Diagnostic Engine** | 🟡 80% — 2A.3 ACTIVE, 2B READY NEXT, 2C.1 shadow GO |
| 3 | **Reachability Engine** | ⬜ BACKLOG — no iniciado |
| 4 | **Forecast Engine** | 🔴 PROTOTYPE — código existe pero bloqueado |
| 5 | **Suggestion Engine** | 🔴 PROTOTYPE — prematuro, depende de Forecast |
| 6 | **Decision Engine** | 🔴 PROTOTYPE — solo capa de data trust |
| 7 | **Action Engine** | 🔴 PROTOTYPE — 14 acciones catalogadas, no activo |
| 8 | **AI Copilot** | ⬜ BACKLOG — no iniciado |
| 9 | **Learning Engine** | 🔴 PROTOTYPE — código existe |

---

## 2. Fases Implementadas por Completo

### 2.1 Control Foundation (Motor 1) — PHASE 1 CLOSED ✅

| Sub-fase | Qué implementa | Veredicto |
|----------|---------------|-----------|
| 1A-1E | Business Slice, mapping, refresh, closed periods, snapshots | GO |
| 1F Fraud | Bank clustering, trip behavior, autocobro, daily ops (11 services, 9 validations) | CLOSED |
| 1F Omniview | Serving integration | GO |
| 1G.1 | UI regression recovery | GO |
| 1G.2 | Control Foundation closure (43 validations) | CONDITIONAL GO |
| 1G.3 | Omniview Projection performance, frontend hardening, serving layer | GO |
| 1G.4 | Cierre formal Fase 1 (post-incidente) | GO |
| 1G.5 | Serving fact coverage reconciliation (daily+weekly+monthly) | GO |

**Lo que entrega:**
- Omniview Matrix: monthly/weekly/daily en Evolución y Vs Proyección
- Serving layer: daily (10,287 rows), weekly (1,487), monthly (338) — desde fact
- Plan vs Real: canonical monthly + weekly
- KPIs, grains, freshness, data trust, period states
- 13 endpoints activos en `/ops/`, 10+ en `/plan/`, 5+ en `/real/`
- Runtime fallback desactivado para API pública

### 2.2 Revenue (Phases 5-6) — CERRADO ✅

- Revenue Consolidation: proxy → real revenue (migration 121)
- Revenue Hardening: NaN guards, proxy monitoring (migration 122)

### 2.3 Real Canonicalization (Phases 1-2) — CERRADO ✅

- REAL desde `mv_real_monthly_canonical_hist` (no BI legacy)
- Plan vs Real canonicalizado
- Paridad MATCH global

---

## 3. Fases Parcialmente Implementadas

### 3.1 Diagnostic Engine (Motor 2) — 🟡 80%

| Sub-fase | Estado | Validación |
|----------|--------|------------|
| 2A.1 — Driver Lifecycle | GO | validate_phase2a1 |
| 2A.1.1 — Hardening | CONDITIONAL GO | validate_phase2a1_1 |
| 2A.2 — Behavior Benchmarking | GO | validate_phase2a2 |
| **2A.3 — Behavioral Pattern Diagnosis** | **ACTIVE** | validate_phase2a3 (en progreso) |
| 2B — Operational Intelligence | READY NEXT | Implementado, validado |
| 2C.1 — Recoverability Shadow | GO (shadow) | validate_phase2c1 |

**Servicios existentes:** 10 servicios (lifecycle, benchmarking, patterns, operational intelligence, recoverability)  
**Routers activos:** 5 routers (driver-lifecycle, driver-behavior, behavioral-patterns, operational-intelligence, recoverability)  
**Componentes UI:** 9 dashboards visibles en navegación

---

## 4. Fases Abiertas Prematuramente (Prototipos)

### 4.1 Forecast Engine (Motor 4) — 🔴 CÓDIGO EXISTE, BLOQUEADO

| Servicio | Estado |
|----------|--------|
| `projection_integrity_service.py` | Pilot |
| `projection_expected_progress_service.py` | Serving layer (parte de CF) |
| `seasonality_curve_engine.py` | Pilot |
| `real_vs_projection_service.py` | Pilot |

**Endpoint oculto:** `/ops/real-vs-projection/*` — HIDE_FROM_NAV

**Problema:** Forecast se empezó antes de cerrar Control Foundation. La dependencia correcta es CF → Diagnostic → Reachability → Forecast.

### 4.2 Suggestion Engine (Motor 5) — 🔴 PREMATURO

| Servicio | Estado |
|----------|--------|
| `projection_suggestion_engine_service.py` | Prematuro |
| `projection_contextual_suggestion_service.py` | Prematuro |

**Depende de:** Forecast Engine (no validado) → NO ACTIVAR

### 4.3 Decision Engine (Motor 6) — 🔴 PROTOTYPE

| Servicio | Estado |
|----------|--------|
| `decision_engine.py` | Solo capa data trust (STOP/LIMIT/MONITOR) |
| `projection_decision_policy_engine.py` | Policy prototype |
| `global_decision_intelligence_service.py` | Prototype |

### 4.4 Action Engine (Motor 7) — 🔴 PROTOTYPE

| Servicio | Estado |
|----------|--------|
| `action_engine_service.py` | 14 acciones catalogadas |
| `action_orchestrator_service.py` | Orchestrator (Phase 8) |
| `action_learning_service.py` | Learning (Phase 9) |

**UI:** HIDE_FROM_NAV — no visible en producción

---

## 5. Qué Está ACTIVE Ahora

**Motor 2 — Diagnostic Engine, sub-fase 2A.3: Behavioral Pattern Diagnosis**

Archivos activos:
- `backend/app/services/behavioral_pattern_diagnosis_service.py`
- `backend/app/routers/behavioral_pattern_diagnosis.py`
- `backend/scripts/validate_phase2a3_behavioral_pattern_diagnosis.py`
- `frontend/src/components/behavioralPatterns/BehavioralPatternDiagnosisDashboard.jsx`
- `docs/diagnostic_engine/FASE2A3_BEHAVIORAL_PATTERN_DIAGNOSIS.md`

---

## 6. Qué Está READY NEXT

**2B — Operational Behavioral Intelligence**

Ya implementado y validado. Listo para ser marcado ACTIVE cuando 2A.3 cierre.

---

## 7. Qué Queda en BACKLOG

| Motor | Dependencia | Estado |
|-------|-------------|--------|
| 3 — Reachability Engine | Diagnostic cerrado | No iniciado |
| 4 — Forecast Engine | Reachability cerrado | Prototype existe |
| 5 — Suggestion Engine | Forecast validado | Prematuro |
| 6 — Decision Engine | Suggestion validado | Prototype existe |
| 7 — Action Engine | Decision validado | Prototype existe |
| 8 — AI Copilot | Action validado | No iniciado |
| 9 — Learning Engine | AI Copilot validado | Prototype existe |

---

## 8. Diferencia: Fase Ideal vs Fase Real

| Aspecto | Fase Ideal (canónica) | Fase Real (repo) |
|---------|----------------------|------------------|
| Orden de motores | 1→2→3→4→5→6→7→8→9 | 1 cerrado. 4,5,6,7,9 con código prototipo prematuro |
| Servicios prematuros | No deberían existir | Existen 8+ servicios de Forecast/Suggestion/Decision/Action/Learning |
| Nombres legacy | No deberían usarse | "phase2a/2b/2c" persisten en código como identificadores técnicos |
| UI oculta | Solo BACKLOG | Action Engine, Real vs Proyección, etc. ocultos |
| Control Foundation | Cerrado | Cerrado con serving layer completa |
| Diagnostic Engine | ACTIVE (2A.3) | ACTIVE (2A.3) — correcto |

---

## 9. Recomendación de Continuidad

1. **Terminar 2A.3** (Behavioral Pattern Diagnosis) — ACTIVE actual
2. **Activar 2B** (Operational Intelligence) — ya implementado y validado
3. **Evaluar 2C.1 → activación** (Recoverability de shadow a production)
4. **NO activar Forecast/Suggestion/Decision/Action/Learning** hasta que sus dependencias estén cerradas
5. **Mantener prototipos existentes como referencia** pero no activarlos en producción
6. **Seguir el orden canónico:** Diagnostic → Reachability → Forecast → Suggestion → Decision → Action → AI Copilot → Learning
7. **No abrir motores nuevos** sin cerrar el anterior (regla de gobierno: máximo 1 ACTIVE, 1 READY NEXT)
