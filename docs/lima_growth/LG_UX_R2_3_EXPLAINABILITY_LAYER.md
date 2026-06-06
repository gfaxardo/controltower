# LG-UX-R2.3 — Explainability Layer

**Date:** 2026-06-05
**Phase:** LG-UX-R2.3 Explainability Layer E2E

---

## 1. Explainability Contract

```json
{
  "title": "Universo Total",
  "definition": "Total de conductores activos en el state snapshot mas reciente.",
  "calculation": "COUNT(DISTINCT driver_profile_id) FROM driver_state_snapshot",
  "current_value": 18475,
  "reason": "State snapshot contiene 18475 conductores.",
  "operational_meaning": "Metrifica operacional del pipeline Lima Growth.",
  "dependencies": [],
  "freshness_status": "FRESH",
  "remediation": null
}
```

## 2. KPIs Covered (11 of 58)

| KPI | Endpoint | Deterministic Rules |
|-----|----------|---------------------|
| universe_total | operational-summary | Zero check + freshness |
| eligible_total | operational-summary | Zero check + universe dependency |
| prioritized_total | operational-summary | Zero check + eligible dependency |
| actionable_today | operational-summary | Capacity limit explanation |
| daily_action_capacity | operational-summary | Policy source |
| capacity_total | operational-summary | Zero = unconfigured |
| queue_total | operational-summary | Zero = exported / no actionable / not built |
| queue_ready | operational-summary | Zero = check HELD |
| queue_held | operational-summary | Zero = all good |
| loopcontrol_contacts_inserted | operational-summary | Zero = no exports yet |
| total_drivers | driver-state/summary | Zero = pipeline stopped |

## 3. Deterministic Rules Applied

### Zero Value Resolution

| Scenario | Reason Generated |
|----------|-----------------|
| Eligible = 0, Universe = 0 | "No hay universo disponible (driver state snapshot vacio)." |
| Eligible = 0, Universe > 0 | "Ningun conductor cumple los criterios de elegibilidad actuales." |
| Queue = 0, Exported > 0 | "La cola esta vacia porque los registros ya fueron exportados." |
| Queue = 0, Actionable = 0 | "No hay conductores accionables hoy." |
| Queue = 0, neither | "Usa Construir Cola para generarla." |
| Capacity = 0 | "No hay capacidad configurada. Configura agentes en Configuracion." |

### Freshness Integration

| Freshness Status | Effect on Reason |
|-----------------|-----------------|
| UNKNOWN | "No puede certificarse completamente porque la fuente no tiene timestamp." |
| STALE | "Puede estar desactualizado. La fuente tiene Xmin de antiguedad." |
| WARNING | "Los datos tienen mas de Xmin de antiguedad." |

## 4. Frontend Components

**New:** `ExplainabilityTooltip.jsx` — icono (i) que muestra tooltip con definition, calculation, reason, operational_meaning, dependencies, freshness_status, remediation.

**Modified:** `MetricCard` now accepts `explainability` prop and renders info icon.

**Wired into:** 6 MetricCards in Command Center (Universo, Priorizados, Accionables, Capacidad, Cola, Exportados).

## 5. Files Created/Modified

| File | Action |
|------|--------|
| `backend/app/services/lima_growth_explainability_service.py` | NEW — explain_kpi(), EXPLAINABILITY_REGISTRY, deterministic rules |
| `backend/app/services/yego_lima_operational_summary_service.py` | MODIFIED — + explainability block (11 KPIs) |
| `backend/app/services/yego_lima_driver_state_summary_service.py` | MODIFIED — + explainability (total_drivers) |
| `frontend/.../components/ExplainabilityTooltip.jsx` | NEW — tooltip component |
| `frontend/.../components/SharedComponents.jsx` | MODIFIED — MetricCard accepts explainability |
| `frontend/.../sections/CommandCenterSection.jsx` | MODIFIED — wired explainability to 6 MetricCards |

## 6. Example Explanations

### Eligible = 0 (hypothetical)
```json
{
  "title": "Elegibles",
  "definition": "Conductores que cumplen criterios para al menos un programa...",
  "reason": "Eligible es 0 porque no hay universo disponible (driver state snapshot vacio).",
  "operational_meaning": "Metrica operacional del pipeline Lima Growth.",
  "remediation": "Verificar que el pipeline de program eligibility se haya ejecutado hoy."
}
```

### Queue = 0 (con exported > 0)
```json
{
  "title": "En Cola",
  "reason": "La cola esta vacia porque los registros disponibles ya fueron exportados.",
  "operational_meaning": "La cola representa el trabajo pendiente de exportacion...",
  "remediation": "Ejecutar 'Construir Cola' desde la seccion Execution Queue."
}
```

## 7. KPIs Pending

47 of 58 KPIs pending explainability. Architecture is extensible — add entries to `EXPLAINABILITY_REGISTRY` and wire into endpoint responses.

## 8. Build

- Backend: compile OK
- Frontend: build PASS (35.35 kB, gzip 8.75 kB)

## 9. GO / NO-GO for R2.4

**GO** — Explainability layer operational for critical KPIs. Users can click info icons to understand what each KPI means, how it's calculated, why it has its current value, what dependencies it has, and what to do if there's a problem. Zero values are properly contextualized. Freshness status is integrated into explanations.
