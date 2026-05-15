# YEGO Control Tower — Documentación

## Arquitectura (Canónica)

La arquitectura del producto se organiza por **motores** de madurez operacional, no por fases técnicas legacy.

| Documento | Descripción |
|-----------|-------------|
| [ARCHITECTURE_CANONICAL_ROADMAP.md](architecture/ARCHITECTURE_CANONICAL_ROADMAP.md) | Roadmap maestro: 9 motores, estados, criterios de cierre. |
| [LEGACY_PHASE_TRANSLATION_MAP.md](architecture/LEGACY_PHASE_TRANSLATION_MAP.md) | Traducción de fases legacy (2A/2B/2C/2C+) a motores canónicos. |
| [ENGINE_BOUNDARIES.md](architecture/ENGINE_BOUNDARIES.md) | Responsabilidades, inputs, outputs y límites de cada motor. |
| [ROADMAP_GOVERNANCE_RULES.md](architecture/ROADMAP_GOVERNANCE_RULES.md) | Reglas vinculantes para toda implementación futura. |

## Principio de Evolución

```
CONTROL → DIAGNÓSTICO → FORECAST → SUGERENCIA → DECISIÓN → EJECUCIÓN → APRENDIZAJE
```

## Documentos Clave por Dominio

### Control Foundation
- [CONTROL_TOWER_SYSTEM_MAP.md](CONTROL_TOWER_SYSTEM_MAP.md) — Mapa completo del sistema.
- [CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md](CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md) — Auditoría de fuentes de verdad.
- [CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md](CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md) — Plan de canonicalización de datos REAL.
- [BUSINESS_SLICE_OMNIVIEW_BACKEND.md](BUSINESS_SLICE_OMNIVIEW_BACKEND.md) — Backend de Omniview.
- [DATA_TRUST_LAYER.md](DATA_TRUST_LAYER.md) — Capa de confianza de datos.
- [DECISION_LAYER.md](DECISION_LAYER.md) — Capa de decisión (gobierno de confianza).
- [observability_data_lineage.md](observability_data_lineage.md) — Linaje de datos y observabilidad.

### Diagnostic Engine (inicial)
- [REAL_RUPTURE_2026_ROOT_CAUSE_ENTREGABLE.md](REAL_RUPTURE_2026_ROOT_CAUSE_ENTREGABLE.md) — Diagnóstico de ruptura REAL 2026.
- [behavioral_alerts_architecture_scan.md](behavioral_alerts_architecture_scan.md) — Arquitectura de alertas conductuales.
- [driver_behavior_deviation_proposal.md](driver_behavior_deviation_proposal.md) — Propuesta de desviación de conductores.

### Proyección (Forecast piloto)
- [real_vs_projection_metric_dictionary.md](real_vs_projection_metric_dictionary.md) — Métricas de proyección.
- [CONFIDENCE_ENGINE.md](CONFIDENCE_ENGINE.md) — Motor de confianza.
- [FASE_CONTROL_AND_DECISION_ENGINE.md](FASE_CONTROL_AND_DECISION_ENGINE.md) — Control & Decision Engine (Omniview Proyección).

### Acciones y Aprendizaje (prototipos)
- [ACTION_ENGINE_PHASE7.md](ACTION_ENGINE_PHASE7.md) — Action Engine Phase 7.
- [ACTION_ORCHESTRATOR_PHASE8.md](ACTION_ORCHESTRATOR_PHASE8.md) — Action Orchestrator Phase 8.
- [LEARNING_ENGINE_PHASE9.md](LEARNING_ENGINE_PHASE9.md) — Learning Engine Phase 9.

### Navegación y UX
- [FASE_1_SIMPLIFICACION_NAVEGACION_NAMING.md](FASE_1_SIMPLIFICACION_NAVEGACION_NAMING.md) — Simplificación de navegación.
- [MAPEO_Y_PROPUESTA_SIMPLIFICACION_CONTROL_TOWER.md](MAPEO_Y_PROPUESTA_SIMPLIFICACION_CONTROL_TOWER.md) — Propuesta de simplificación.
- [CONTROL_TOWER_REDESIGN_PLAN.md](CONTROL_TOWER_REDESIGN_PLAN.md) — Plan de rediseño.

---

**Nota:** Las fases legacy (2A, 2B, 2C, 2C+) son identificadores técnicos en código. El roadmap de producto se rige por los **9 motores canónicos**. Ver [LEGACY_PHASE_TRANSLATION_MAP.md](architecture/LEGACY_PHASE_TRANSLATION_MAP.md) para el mapeo completo.
