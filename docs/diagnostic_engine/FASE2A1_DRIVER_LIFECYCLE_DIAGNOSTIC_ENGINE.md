# FASE 2A.1 — DRIVER LIFECYCLE DIAGNOSTIC ENGINE

**Fecha:** 2026-05-21
**Motor:** Diagnostic Engine (#2 de 9)
**Fase:** 2A.1 — Early Leakage Detection
**Veredicto:** GO

---

## 1. OBJETIVO OPERACIONAL

Crear una primera capa para medir diariamente el leakage/fuga de conductores con reglas deterministicas. Este motor permite identificar cuales conductores entran, activan, se mantienen, caen, estan en riesgo, dormidos o fugados. Genera listas accionables para SAC / Lealtad / Call Center.

---

## 2. PROBLEMA QUE RESUELVE

**Leakage de conductores:** Conductores que dejan de hacer viajes progresivamente hasta desaparecer del sistema. Sin deteccion temprana, se pierden sin oportunidad de retencion.

Este motor diagnostica:
- Que conductores estan fugando (CHURNED, DORMANT)
- Cuales estan en riesgo inminente (AT_RISK, DECLINING)
- Cuales estan creciendo (GROWING)
- Cual retorno despues de dormancia (REACTIVATED)
- La tasa global de retencion y leakage

---

## 3. INPUTS

| Input | Fuente | Columna |
|-------|--------|---------|
| Viajes completados | `public.trips_2026` | `condicion = 'Completado'` |
| ID conductor | `trips_2026.conductor_id` | varchar |
| Fecha de viaje | `trips_2026.fecha_finalizacion` | timestamp |
| Parque | `trips_2026.park_id` | varchar |
| Pais/Ciudad | `dim.dim_park` (JOIN) | country, city |
| LOB | `trips_2026.tipo_servicio` | varchar |

**Ventana de lookback:** 60 dias (configurable).

---

## 4. OUTPUTS

### 4.1 Endpoints API

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/driver-lifecycle/summary` | Agregado: total, active_7d/28d, estados, riesgos, leak/retention rate |
| GET | `/driver-lifecycle/funnel` | 4 capas: input, retained, risk, leakage |
| GET | `/driver-lifecycle/risk-list` | Lista accionable por conductor (estado, riesgo, baseline, declive) |
| GET | `/driver-lifecycle/cohorts-basic` | Retencion agrupada por mes de primer viaje |

### 4.2 Estados de lifecycle (deterministicos)

| Estado | Regla | Precedencia |
|--------|-------|-------------|
| CHURNED | days_since_last_trip >= 30 | 1 |
| DORMANT | days_since_last_trip >= 14 | 2 |
| REACTIVATED | rolling_7d > 0 AND was dormant | 3 |
| NEW | first_trip_date dentro de 7 dias | 4 |
| AT_RISK | days_since_last >= 3 OR rolling_7d < 40% baseline | 5 |
| DECLINING | rolling_7d entre 40-70% baseline | 6 |
| GROWING | rolling_7d >= 120% baseline | 7 |
| STABLE | rolling_7d >= 70% baseline | 8 |
| ACTIVATING | first_trip 8-21d AND rolling_7d > 0 | 9 |

### 4.3 Niveles de riesgo

| Nivel | Regla |
|-------|-------|
| HIGH | CHURNED, DORMANT, AT_RISK, o decline > 60% |
| MEDIUM | DECLINING o decline 30-60% |
| LOW | STABLE, GROWING, NEW, ACTIVATING sin senales criticas |

---

## 5. REGLAS DETERMINISTICAS DE LIFECYCLE

(Ver seccion 4.2 para la tabla completa)

**Regla de precedencia:** Se aplica en orden. La primera regla que hace match asigna el estado.

**Calculo de baseline:** `baseline_trips_21d` (viajes entre dias 35 y 7 atras) dividido entre 3 para obtener el equivalente semanal (~7d).

**Reactivated detection heuristic:**
1. `total_trips > rolling_28d AND rolling_28d > 0` (tenia viajes antes de la ventana 28d)
2. O `first_trip_date` durante ventana dormida pero activo ahora

---

## 6. REGLAS DE RISK LEVEL

(Ver seccion 4.3)

`decline_pct = ((baseline_7d_equiv - rolling_7d) / baseline_7d_equiv) * 100`

---

## 7. ENDPOINTS

### 7.1 Summary Response

```json
{
  "total_drivers_seen": 10229,
  "active_7d": 3645,
  "active_28d": 5673,
  "new_drivers": 265,
  "churned_drivers": 2368,
  "dormant_drivers": 568,
  "at_risk_drivers": 847,
  "leakage_rate": 28.7,
  "retention_rate": 5.4
}
```

### 7.2 Funnel Response (4 capas)

```json
{
  "input_layer": {"new_drivers": N, "reactivated_drivers": M, ...},
  "retained_layer": {"stable_drivers": N, "growing_drivers": M, ...},
  "risk_layer": {"declining_drivers": N, "at_risk_drivers": M, ...},
  "leakage_layer": {"dormant_drivers": N, "churned_drivers": M, ...}
}
```

### 7.3 Risk List Response

Cada row contiene: `driver_id`, `country`, `city`, `lifecycle_state`, `risk_level`, `rule_reason`, `first_trip_date`, `last_trip_date`, `days_since_last_trip`, `rolling_7d_trips`, `baseline_trips_28d`, `decline_pct`.

---

## 8. VISTA FRONTEND

**Componente:** `DriverLifecycleDashboard.jsx`
**Ruta:** `/drivers/diagnostic`
**Tab:** Drivers > Diagnostico

**Secciones:**
1. Header con titulo y boton de refresh
2. Filtros: country, city, risk_level, lifecycle_state
3. KPI Cards (8): Active 7D, Active 28D, New, At Risk, Dormant, Churned, Retention, Leakage
4. Leakage Funnel: 4 columnas (Entrada, Retenidos, Riesgo, Fuga)
5. Risk List: tabla accionable ordenada por days_since_last_trip descendente
6. Cohorts Basic: tabla de retencion por mes de primer viaje

---

## 9. LIMITACIONES

1. **Solo trips_2026**: No incluye trips_2025. Conductores activos solo en 2025 no aparecen.
2. **Baseline aproximado**: `baseline_trips_21d / 3` como proxy de baseline semanal. Mejorable con baseline_28d real.
3. **Reactivated heuristic**: La deteccion de reactivacion es basica (gap detection por total_trips vs rolling_28d). No distingue reactivacion genuina de conductor intermitente.
4. **Sin revenue**: No se incluye revenue en esta fase. Backlog para 2A.2.
5. **Sin segmentacion**: No hay segmentacion FT/PT/CASUAL. Se usan solo viajes completados.
6. **Sin source/scout/origin**: Columna no existe en trips_2026. Backlog.
7. **Sin park drilldown**: El diagnostico actual no desglosa por park. Backlog.
8. **Performance**: ~3.8s por query. Aceptable para fase inicial pero necesita MV si escala.

---

## 10. BACKLOG PARA FASE 2A.2

| Item | Prioridad |
|------|-----------|
| Revenue en diagnostico (comision_empresa_asociada) | HIGH |
| Baseline_28d real (no proxy) | HIGH |
| Segmentacion FT/PT/CASUAL | MEDIUM |
| Park drilldown en todos los endpoints | MEDIUM |
| Source/scout/origin si existe en otra tabla | LOW |
| Materialized view para performance | LOW |
| Alertas automaticas (threshold breach) | BACKLOG |
| Integracion con Action Engine | BACKLOG |

---

## 11. QUE NO SE CONSTRUYO

- Forecast de churn futuro
- Recomendaciones de accion
- Automatizacion de intervenciones
- IA / ML
- Integracion con Decision Engine
- Integracion con Action Engine
- Segmentacion avanzada de conductores
- Alertas push/email

---

## 12. VEREDICTO

**GO** — 30/30 validaciones QA aprobadas.

| Metrica | Valor |
|---------|-------|
| Validaciones totales | 30 |
| PASS | 30 (100%) |
| FAIL (critical) | 0 |
| Tiempo summary | 3.8s |
| Tiempo risk-list | 3.8s |
| Omniview Matrix | No afectado |
| Plan vs Real | No afectado |

Fase 2A.1 — Driver Lifecycle Diagnostic Engine puede cerrarse.

---

*Documento generado por Fase 2A.1 — Driver Lifecycle Diagnostic Engine*
*Script QA: backend/scripts/validate_phase2a1_driver_lifecycle_diagnostic.py*
