# FASE 2C.1 — RECOVERABILITY SHADOW IMPLEMENTATION

## Objetivo

Implementar el scoring deterministico de recoverability diseniado en `FASE2C_RECOVERABILITY_INTELLIGENCE_ARCHITECTURE.md`. Shadow mode: diagnostico solamente, sin automatizacion ni recomendaciones.

---

## Arquitectura Implementada

```
┌─────────────────────────────────────────────────────────┐
│                 FASE 2C.1 — Recoverability               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │ Facts 2B.2        │  │ Scoring Engine              │  │
│  │                   │  │                             │  │
│  │ trip_daily_fact ──┼──▶ C1 Historical Consistency   │  │
│  │                   │  │ C2 Degradation Severity     │  │
│  │                   │  │ C3 Recency & Churn Duration │  │
│  │                   │  │ C4 Archetype Compatibility  │  │
│  │                   │  │ C5 Efficiency Legacy        │  │
│  │                   │  │ C6 Modifiers (±10 pts)      │  │
│  └──────────────────┘  └──────────────┬──────────────┘  │
│                                       │                  │
│  ┌────────────────────────────────────┼──────────────┐  │
│  │ Router /recoverability             │              │  │
│  │  GET /summary                      │              │  │
│  │  GET /top-recoverable              │              │  │
│  │  GET /distribution                 │              │  │
│  │  GET /driver/{driver_id}           │              │  │
│  │  GET /shadow-priority              │              │  │
│  └────────────────────────────────────┼──────────────┘  │
│                                       │                  │
│  ┌────────────────────────────────────┼──────────────┐  │
│  │ Frontend: RecoverabilityDashboard  │              │  │
│  │  - KPI Cards                       │              │  │
│  │  - Distribution Chart              │              │  │
│  │  - Top Recoverable Table           │              │  │
│  │  - Shadow Priority Table           │              │  │
│  │  - Driver Detail Panel             │              │  │
│  │  - Explainability Panel            │              │  │
│  │  - Shadow Mode Banner              │              │  │
│  └────────────────────────────────────┴──────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Scoring Model

### Formula
```
RecoverabilityScore = Σ(ComponentScore_i × Weight_i) + Modifiers
Rango: 0-100
```

### Componentes y Pesos

| # | Componente | Peso | Fuente |
|---|-----------|------|--------|
| C1 | Historical Consistency | 25% | `active_days / period_days` |
| C2 | Degradation Severity | 25% | trips_change vs expected |
| C3 | Recency & Churn Duration | 20% | `days_since_last_activity` |
| C4 | Archetype Compatibility | 15% | Clasificacion 9 arquetipos |
| C5 | Efficiency Legacy | 10% | `revenue_per_hour` vs percentiles |
| C6 | Modifiers | ±10 | Prior TOP_PERFORMER, Balanced Schedule, etc. |

### Recoverability States

| Estado | Score | Color | Significado |
|--------|-------|-------|------------|
| HIGHLY_RECOVERABLE | 80-100 | #22c55e | Recuperacion altamente probable |
| RECOVERABLE | 60-79 | #3b82f6 | Buen candidato para intervencion |
| LOW_RECOVERABLE | 40-59 | #eab308 | Seniales mixtas, incierto |
| HARD_TO_RECOVER | 20-39 | #f97316 | Degradacion severa, baja probabilidad |
| NON_RECOVERABLE | 0-19 | #ef4444 | Churn consolidado |

## Explainability

Cada driver incluye:
- **score_breakdown**: 5 componentes con score, weight, contribution, evidence
- **explainability_text**: Texto deterministico generado por templates (no LLM)
- **state_metadata**: label, severity, color, description
- **intervention_urgency**: HIGH/MEDIUM/LOW/NONE

Ejemplo de explainability:
> "Consistencia historica excepcional (85% dias activos). Sin seniales de degradacion. Activo esta semana (2026-05-21). Perfil FULLTIMER. Alta dependencia de la plataforma. Buena eficiencia historica (revenue/h=18). Modificadores: Balanced Schedule (+2 pts)."

## Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/recoverability/summary` | Resumen agregado + distribucion |
| GET | `/recoverability/top-recoverable` | Top N drivers por score |
| GET | `/recoverability/distribution` | Distribucion por estado + stats |
| GET | `/recoverability/driver/{id}` | Score detallado + explainability |
| GET | `/recoverability/shadow-priority` | Ranking shadow (visual only) |

Todos con: `country`, `city`, `period_days`

## Performance

| Endpoint | Latencia | Fuente |
|----------|----------|--------|
| /recoverability/summary | ~3s | trip_daily_fact (309K) |
| /recoverability/top-recoverable | ~4s | trip_daily_fact (309K) |
| /recoverability/distribution | ~3s | trip_daily_fact (309K) |
| /recoverability/shadow-priority | ~3s | trip_daily_fact (309K) |
| /recoverability/driver/{id} | ~1s | trip_daily_fact single driver |

**NO escanea VIEWs 64M+.** Usa exclusivamente facts materializadas 2B.2.

## Shadow Mode

- `shadow_mode: true` en todas las responses
- Sin automatizacion de acciones
- Sin generacion de recomendaciones
- Sin routing a cola SAC
- Sin Decision Engine, Suggestion Engine, ni Action Engine
- Priorizacion visual unicamente (TIER_1/TIER_2/TIER_3)

## Que NO Hace

- NO genera recomendaciones operativas
- NO automatiza intervenciones
- NO asigna conductores a colas SAC
- NO usa ML/IA
- NO genera texto libre (solo templates deterministicos)
- NO predice recuperacion futura (Forecast Engine)
- NO sugiere canales de contacto (Reachability Engine)

## Limitaciones

1. **Calibracion conceptual**: Los thresholds y pesos son de disenio, no calibrados empiricamente.
2. **Sin datos de intervencion previa**: No se sabe si drivers con score alto realmente vuelven.
3. **Sin seasonality**: No ajusta por patrones estacionales (backlog 2B).
4. **Sin tenure**: No considera antiguedad del conductor.
5. **Sin mercado local**: No ajusta por demanda de zona/mercado.

## Riesgos

1. **Falsos positivos**: Clasificar RECOVERABLE a quien no vuelve.
2. **Falsos negativos**: Clasificar NON_RECOVERABLE a quien si volveria.
3. **Tautologia operacional**: El score penaliza lo que predice.
4. **Sesgo hacia FULLTIMERs**: Los pesos favorecen perfiles de alta frecuencia.

## Archivos

| Archivo | Proposito |
|---------|-----------|
| `backend/app/services/recoverability_intelligence_service.py` | Scoring engine + estados + explainability |
| `backend/app/routers/recoverability_intelligence.py` | 5 endpoints API |
| `backend/app/main.py` | Registro del router |
| `frontend/src/components/recoverability/RecoverabilityIntelligenceDashboard.jsx` | Dashboard |
| `frontend/src/services/api.js` | Funciones API |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Entrada de navegacion |
| `frontend/src/App.jsx` | Ruta y render |
| `backend/scripts/validate_phase2c1_recoverability_shadow.py` | QA Script |

## QA Results

- **5/5 endpoints**: HTTP 200
- **Scores**: Todos en rango [0, 100]
- **States**: 5 estados validos presentes
- **Explainability**: Score breakdown + explainability text en todas las responses
- **No recommendations**: 0 recomendaciones en responses
- **Shadow mode**: `shadow_mode=true` en todas las responses
- **Regression 5/5**: Omniview, Plan vs Real, Lifecycle, Benchmarking, Patterns intactos
- **Performance**: <5s por endpoint (facts materializadas)

## Veredicto

**GO**

Fase 2C.1 cerrada. Recoverability Intelligence operativo en shadow mode. Listo para 2C.2 cuando se requiera calibracion empirica o integracion con Suggestion Engine (Fase 4+).
