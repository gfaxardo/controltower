# FASE 2C.1 — RECOVERABILITY SHADOW IMPLEMENTATION

## Objetivo

Implementar el scoring deterministico de recoverability diseniado en `FASE2C_RECOVERABILITY_INTELLIGENCE_ARCHITECTURE.md`.
Shadow mode: diagnostico solamente, sin automatizacion ni recomendaciones.

---

## Runtime Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    FASE 2C.1 — Recoverability                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────┐  ┌──────────────────────────────┐         │
│  │ Facts 2B.2          │  │ Scoring Engine               │         │
│  │                     │  │                              │         │
│  │ trip_daily_fact ────┼──▶ C1 Historical Consistency    │         │
│  │ (309K rows)         │  │ C2 Degradation Severity      │         │
│  │                     │  │ C3 Recency & Churn Duration  │         │
│  │                     │  │ C4 Archetype Compatibility   │         │
│  │                     │  │ C5 Efficiency Legacy         │         │
│  │                     │  │ C6 Modifiers (±10 pts)       │         │
│  └────────────────────┘  └──────────────┬───────────────┘         │
│                                         │                          │
│  ┌──────────────────────────────────────┼─────────────────────┐   │
│  │ Router /recoverability               │                     │   │
│  │  GET /summary                        │                     │   │
│  │  GET /top-recoverable                │                     │   │
│  │  GET /distribution                   │                     │   │
│  │  GET /driver/{driver_id}             │                     │   │
│  │  GET /shadow-priority                │                     │   │
│  │  GET /segments                       │  (lifecycle + archetype)│
│  │  GET /explainability/{driver_id}     │  (components + evidence)│
│  │  GET /risk-distribution              │  (severity buckets)  │   │
│  └──────────────────────────────────────┼─────────────────────┘   │
│                                         │                          │
│  ┌──────────────────────────────────────┼─────────────────────┐   │
│  │ Frontend: RecoverabilityDashboard    │                     │   │
│  │  - SHADOW MODE banner                │                     │   │
│  │  - KPI Cards                         │                     │   │
│  │  - Distribution Chart                │                     │   │
│  │  - Top Recoverable Table             │                     │   │
│  │  - Shadow Priority Table             │                     │   │
│  │  - Recoverability vs Lifecycle       │  (new)              │   │
│  │  - Recoverability vs Archetype       │  (new)              │   │
│  │  - Risk Distribution Cards           │  (new)              │   │
│  │  - Driver Detail Panel               │                     │   │
│  │  - Explainability Panel              │                     │   │
│  └──────────────────────────────────────┴─────────────────────┘   │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Facts Used

Source: `ops.driver_trip_behavior_daily_fact` (materialized, 2B.2)
Period: CURRENT_DATE - period_days to CURRENT_DATE
Filters: country, city, trips > 0
Aggregation: GROUP BY driver_id, country, city

**NO se escanean VIEWs 64M+.** Solo facts materializadas.

## Scoring Model

### Formula
```
RecoverabilityScore = Σ(ComponentScore_i × Weight_i) + Modifiers
Rango: 0-100 (deterministico, sin ML/IA)
```

### Componentes y Pesos

| # | Componente | Peso | Fuente |
|---|-----------|------|--------|
| C1 | Historical Consistency | 25% | `active_days / period_days` |
| C2 | Degradation Severity | 25% | trips_change vs expected |
| C3 | Recency & Churn Duration | 20% | `days_since_last_activity` |
| C4 | Archetype Compatibility | 15% | Clasificacion 9 arquetipos |
| C5 | Efficiency Legacy | 10% | `revenue_per_hour` vs percentiles |
| C6 | Modifiers | ±10 | Prior TOP_PERFORMER, Balanced Schedule, Extreme Specialist |

### Recoverability States

| Estado | Score | Color | Severity |
|--------|-------|-------|----------|
| HIGHLY_RECOVERABLE | 80-100 | #22c55e | low |
| RECOVERABLE | 60-79 | #3b82f6 | moderate |
| LOW_RECOVERABLE | 40-59 | #eab308 | elevated |
| HARD_TO_RECOVER | 20-39 | #f97316 | high |
| NON_RECOVERABLE | 0-19 | #ef4444 | critical |

## Explainability Structure

Cada driver devuelve:

```json
{
  "total_score": 82,
  "bucket": "HIGHLY_RECOVERABLE",
  "components": [
    {"name": "historical_consistency", "score": 22, "weight": 0.25, "contribution": 5.5},
    {"name": "degradation_severity", "score": 25, "weight": 0.25, "contribution": 6.25},
    {"name": "recency", "score": 18, "weight": 0.20, "contribution": 3.6},
    {"name": "archetype_compatibility", "score": 13, "weight": 0.15, "contribution": 1.95},
    {"name": "efficiency_legacy", "score": 8, "weight": 0.10, "contribution": 0.8}
  ],
  "modifiers": [
    {"modifier": "Balanced Schedule", "points": 2, "evidence": "weekend_share=0.45, peak_share=0.52"}
  ],
  "evidence": [
    "Consistencia historica excepcional (85% dias activos).",
    "Sin seniales de degradacion.",
    "Activo esta semana (2026-05-21). Ventana optima de intervencion.",
    "Perfil FULLTIMER. Alta dependencia de la plataforma.",
    "Buena eficiencia historica (revenue/h=18)."
  ],
  "source_metrics": [
    {"metric": "active_days", "value": 24, "period_days": 28},
    {"metric": "total_trips", "value": 96},
    {"metric": "days_since_last_activity", "value": 2},
    {"metric": "revenue_per_hour", "value": 18.50, "population_p50": 12.30}
  ]
}
```

**TODO deterministico.** Sin LLM text generation.

## Endpoints

| Metodo | Endpoint | Descripcion | Parametros |
|--------|----------|-------------|------------|
| GET | `/recoverability/summary` | Resumen agregado + distribucion | country, city, period_days |
| GET | `/recoverability/top-recoverable` | Top N drivers por score | country, city, period_days, limit |
| GET | `/recoverability/distribution` | Distribucion por estado + stats | country, city, period_days |
| GET | `/recoverability/driver/{id}` | Score detallado + explainability | period_days |
| GET | `/recoverability/shadow-priority` | Ranking shadow (visual only) | country, city, period_days, limit |
| GET | `/recoverability/segments` | Segmentos por lifecycle y archetype | country, city, period_days |
| GET | `/recoverability/explainability/{id}` | Explainability completa (components+evidence+source_metrics) | period_days |
| GET | `/recoverability/risk-distribution` | Distribucion de riesgo por severity | country, city, period_days |

Todos: read-only, diagnostic-only, sin acciones.

## Performance

| Endpoint | Latencia objetivo | Fuente |
|----------|-------------------|--------|
| /recoverability/summary | <5s | trip_daily_fact |
| /recoverability/top-recoverable | <5s | trip_daily_fact |
| /recoverability/distribution | <5s | trip_daily_fact |
| /recoverability/driver/{id} | <2s | trip_daily_fact (single driver) |
| /recoverability/shadow-priority | <5s | trip_daily_fact |
| /recoverability/segments | <5s | trip_daily_fact |
| /recoverability/explainability/{id} | <2s | trip_daily_fact (single driver) |
| /recoverability/risk-distribution | <5s | trip_daily_fact |

**NO scans 64M+.** Exclusivamente facts materializadas 2B.2.

## Shadow Limitations

- `shadow_mode: true` en todas las responses
- Sin automatizacion de acciones
- Sin generacion de recomendaciones
- Sin routing a cola SAC
- Sin Decision Engine, Suggestion Engine, ni Action Engine
- Priorizacion visual unicamente (TIER_1/TIER_2/TIER_3)

### Banner obligatorio en frontend

> "Recoverability Intelligence is running in SHADOW MODE. No operational actions are executed automatically."

## Que NO Hace

- NO genera recomendaciones operativas
- NO automatiza intervenciones
- NO asigna conductores a colas SAC
- NO usa ML/IA
- NO genera texto libre (solo templates deterministicos)
- NO predice recuperacion futura (Forecast Engine)
- NO sugiere canales de contacto (Reachability Engine)
- NO ejecuta acciones, campañas, ni workflows

## Limitaciones

1. **Calibracion conceptual**: Los thresholds y pesos son de disenio, no calibrados empiricamente.
2. **Sin datos de intervencion previa**: No se sabe si drivers con score alto realmente vuelven.
3. **Sin seasonality**: No ajusta por patrones estacionales.
4. **Sin tenure**: No considera antiguedad del conductor.
5. **Sin mercado local**: No ajusta por demanda de zona/mercado.
6. **C2 degradation**: Basado en trips_change vs expected (no seniales de degradacion conductual).

## Riesgos

1. **Falsos positivos**: Clasificar RECOVERABLE a quien no vuelve.
2. **Falsos negativos**: Clasificar NON_RECOVERABLE a quien si volveria.
3. **Tautologia operacional**: El score penaliza lo que predice.
4. **Sesgo hacia FULLTIMERs**: Los pesos favorecen perfiles de alta frecuencia.

## Archivos

| Archivo | Proposito |
|---------|-----------|
| `backend/app/services/recoverability_intelligence_service.py` | Scoring engine + estados + explainability + 8 provider functions |
| `backend/app/routers/recoverability_intelligence.py` | 8 endpoints API (prefijo /recoverability) |
| `backend/app/main.py` | Registro del router en app |
| `frontend/src/components/recoverability/RecoverabilityIntelligenceDashboard.jsx` | Dashboard completo con 8 vistas |
| `frontend/src/services/api.js` | 8 funciones API (getRecoverability*) |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Entrada de navegacion (8 endpoints) |
| `frontend/src/App.jsx` | Ruta mapeada a /drivers/recoverability |
| `backend/scripts/validate_phase2c1_recoverability_shadow.py` | QA Script runtime (30+ checks) |

## QA Validation Criteria

| # | Check | Status |
|---|-------|--------|
| A | All 8 endpoints HTTP 200 | ✓ |
| B | Scores 0-100 deterministicos | ✓ |
| C | 5 estados validos presentes | ✓ |
| D | explainability_text + components[] + evidence[] + source_metrics[] | ✓ |
| E | No recommendations | ✓ |
| F | shadow_mode=true en todas las responses | ✓ |
| G | Omniview intacto | ✓ |
| H | Plan vs Real intacto | ✓ |
| I | Lifecycle intacto | ✓ |
| J | Benchmarking intacto | ✓ |
| K | Patterns intactos | ✓ |
| L | Performance <8s | ✓ |
| M | Materialized facts usados, no VIEWs 64M+ | ✓ |

## Veredicto

**GO**

Fase 2C.1 cerrada. Recoverability Intelligence operativo en shadow mode runtime.
- 8 endpoints HTTP 200
- Score deterministico C1-C6 con explainability completa
- components[], evidence[], source_metrics[] estructurados
- Segments por lifecycle y archetype
- Risk distribution por severity
- Shadow mode banner en frontend
- QA script con 30+ validaciones
- Sin automatizacion, sin recomendaciones, sin ML/IA
- Facts materializadas 2B.2 (sin VIEWs 64M+)

Listo para 2C.2 cuando se requiera calibracion empirica o integracion con Suggestion Engine (Fase 4+).
