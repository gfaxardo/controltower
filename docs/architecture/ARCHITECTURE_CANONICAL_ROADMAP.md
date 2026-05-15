# YEGO Control Tower — Arquitectura Canónica: Roadmap Maestro

**Versión:** 1.0.0
**Fecha:** 2026-05-15
**Propósito:** Hoja de ruta arquitectónica oficial. Reemplaza la nomenclatura de fases legacy (2A/2B/2C/2C+) como roadmap, aunque los nombres legacy permanecen en código como identificadores técnicos.

---

## A. Arquitectura Maestra Vigente (por Motores)

El sistema se organiza en **9 motores arquitectónicos**, ordenados por madurez operacional:

| # | Motor | Estado Actual | Sigla |
|---|-------|--------------|-------|
| 1 | **Control Foundation** | ACTIVE | CF |
| 2 | **Diagnostic Engine** | READY NEXT | DX |
| 3 | **Reachability Engine** | BACKLOG | RH |
| 4 | **Forecast Engine** | BACKLOG | FC |
| 5 | **Suggestion Engine** | BACKLOG | SG |
| 6 | **Decision Engine** | BACKLOG | DC |
| 7 | **Action Engine** | BACKLOG | AC |
| 8 | **AI Copilot** | BACKLOG | AI |
| 9 | **Learning Engine** | BACKLOG | LN |

---

## B. Principio de Evolución

```
CONTROL → DIAGNÓSTICO → FORECAST → SUGERENCIA → DECISIÓN → EJECUCIÓN → APRENDIZAJE
   │            │           │           │           │           │            │
   CF           DX         RH+FC       SG          DC          AC          LN+AI
```

Cada motor **depende del anterior como prerrequisito**:
- No puede haber Forecast sin Control confiable.
- No puede haber Suggestion sin Forecast validado.
- No puede haber Decision sin Suggestion trazable.
- No puede haber Action sin Decision explícita.
- No puede haber Learning sin evidencia histórica de acciones ejecutadas.

---

## C. Regla de Fase Activa

En todo momento, el proyecto opera con un **máximo de**:

| Estado | Máximo | Significado |
|--------|--------|-------------|
| **ACTIVE** | 1 motor | Desarrollo principal en curso |
| **READY NEXT** | 1 motor | Preparado para entrar (dependencias resueltas) |
| **BACKLOG** | resto | No activo hasta que el anterior cierre |

**No se permite tener más de un motor en ACTIVE simultáneamente.**

---

## D. Estado Actual Recomendado (2026-05-15)

| Motor | Estado | Justificación |
|-------|--------|---------------|
| **Control Foundation** | ACTIVE | Base operacional en construcción: Omniview, Plan vs Real, Freshness, KPIs, grains, YTD. Aún no cerrado formalmente. |
| **Diagnostic Engine** | READY NEXT | Componentes de diagnóstico ya existen parcialmente (behavior alerts, deviation, margin quality, data trust, integrity reports). Listo para formalizarse como motor. |
| **Reachability Engine** | BACKLOG | No iniciado. Depende de Control Foundation cerrado. |
| **Forecast Engine** | BACKLOG | Projection Integrity Engine existe como prototipo técnico, pero no está listo como motor Forecast completo (depende de Control Foundation estable). |
| **Suggestion Engine** | BACKLOG | Existen servicios parciales (`projection_suggestion_engine_service`, `projection_contextual_suggestion_service`) pero no deben activarse como motor hasta que Forecast esté validado. |
| **Decision Engine** | BACKLOG | Existe `decision_engine.py` como prototipo de capa de gobierno (STOP/LIMIT/MONITOR) pero no debe expandirse a decisiones operativas hasta que Suggestion esté trazable. |
| **Action Engine** | BACKLOG | Existe `action_engine_service.py` y `action_orchestrator_service.py` con `ops.action_engine_output`. **No confundir con `phase2b_actions`**. El Action Engine real solo debe activarse cuando Decision Engine esté operativo. |
| **AI Copilot** | BACKLOG | No iniciado. |
| **Learning Engine** | BACKLOG | Existe `action_learning_service.py` como prototipo. Solo debe activarse con evidencia histórica suficiente de acciones ejecutadas. |

---

## E. Criterios de Cierre de Control Foundation

Control Foundation se considera **CERRADO** cuando se cumplen TODOS los siguientes criterios:

### E.1 KPIs
- [ ] KPIs cuadran entre daily, weekly y monthly (sin diferencias inexplicables >1%).
- [ ] YTD (year-to-date) y comparativos interanuales funcionan sin rupturas.
- [ ] Métricas core (trips, revenue, margin, km) son trazables hasta fuente.

### E.2 Grains
- [ ] Grains consistentes: daily ↔ weekly ↔ monthly con reglas de rollup documentadas y auditables.
- [ ] No existen duplicaciones de filas por grano (PK enforcement).

### E.3 Joins Auditables
- [ ] Todos los joins Plan↔Real están documentados (homologación de parks, LOB, service_type).
- [ ] Las reglas de mapeo (regla madre LOB, B2B/B2C, city normalization) son explícitas y verificables.

### E.4 Freshness
- [ ] Data freshness funciona correctamente para todas las MVs y vistas críticas.
- [ ] Staleness se detecta y notifica (watchdog + GlobalFreshnessBanner).
- [ ] Refresh pipeline certificado (no hay MVs stale > threshold sin alerta).

### E.5 Omniview
- [ ] Omniview Matrix estable: sin celdas vacías inexplicables, sin NaN en KPIs core.
- [ ] Omniview Matrix Integrity checks pasan (trip loss, B2B, LOB mapping, duplicates, MV stale, join loss, weekly anomaly).
- [ ] Business Slice canonical aggregation consistente con fuentes.

### E.6 Plan vs Real
- [ ] Plan vs Real mensual consistente (sin diferencias de fuente entre monthly y views legacy).
- [ ] Plan vs Real semanal validado (parity con fuente canónica).
- [ ] Plan upload, validación (expansión/huecos) y versionado funcionan sin errores.

### E.7 Performance
- [ ] Tiempos de respuesta aceptables para todas las vistas principales (<5s para drill, <2s para resúmenes).
- [ ] No hay N+1 queries ni conexiones bloqueadas por consultas lentas.

---

## F. Regla Crítica de Avance

**NO avanzar a Suggestion Engine, Decision Engine, Action Engine ni Learning Engine si:**

1. La base de control no es confiable (Control Foundation no cerrado).
2. Los KPIs no cuadran entre grains.
3. Los grains no son consistentes.
4. La trazabilidad (source → view → API → UI) no está resuelta.
5. El Forecast no es confiable (para Suggestion y Decision).

**Consecuencia de violar esta regla:**
- Acciones generadas sobre datos inconsistentes → decisiones equivocadas.
- Learning Engine entrenado sobre señales rotas → recomendaciones no confiables.
- Deuda arquitectónica acumulada que requerirá refactor completo posterior.

---

## G. Notas sobre Motores Parcialmente Implementados

### G.1 Projection Integrity Engine (Forecast parcial)
- Existe como `projection_integrity_service.py` + `seasonality_curve_engine.py`.
- Debe tratarse como **piloto técnico**, no como Forecast Engine completo.
- No debe alimentar Suggestion ni Decision hasta que Control Foundation esté cerrado.

### G.2 Decision Layer (prototipo)
- Existe como `decision_engine.py` con reglas `STOP_DECISIONS` / `LIMIT_DECISIONS` / etc.
- Actualmente opera como **capa de gobierno de confianza de datos**, no como Decision Engine operacional.
- Correcto para la fase actual. No expandir a decisiones de negocio todavía.

### G.3 Action Engine (prototipo)
- Existe `ops.action_engine_output` con acciones por ciudad/día.
- El `action_engine_service.py` actual es un **prototipo de cohortes y recomendaciones**.
- **NO es el Action Engine arquitectónico completo** (que requiere Decision Engine previo).
- El `action_orchestrator_service.py` (Phase 8) y `action_learning_service.py` (Phase 9) son prototipos de fases futuras.

### G.4 phase2b_actions (registro de acciones)
- `ops.phase2b_actions` es un **registro operacional básico de seguimiento de acciones**.
- Pertenece a Control Foundation / accountability inicial.
- **NO es el Action Engine** ni debe confundirse con él.

---

## H. Referencias Cruzadas

- [LEGACY_PHASE_TRANSLATION_MAP.md](./LEGACY_PHASE_TRANSLATION_MAP.md) — Mapeo de fases legacy a motores.
- [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md) — Límites y responsabilidades de cada motor.
- [ROADMAP_GOVERNANCE_RULES.md](./ROADMAP_GOVERNANCE_RULES.md) — Reglas de gobierno para futuras implementaciones.
