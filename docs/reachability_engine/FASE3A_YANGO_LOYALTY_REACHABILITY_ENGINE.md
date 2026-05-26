# FASE 3A — YANGO LOYALTY REACHABILITY ENGINE

**Versión:** 1.0.0  
**Fecha:** 2026-05-22  
**Estado:** Implementado  
**Autor:** Control Tower Team  

---

## 1. Objetivo

Construir una capa que mida **Plan vs Real** de KPIs Yango Oro/Plata/Bronce y determine si YEGO va a llegar a sus metas mensuales. Tracking, gap, reachability y diagnóstico — sin recomendaciones automáticas.

---

## 2. KPIs Yango

| Código | KPI | Unidad | Fuente | Categoría umbral |
|--------|-----|--------|--------|-----------------|
| `AD` | Active Drivers | count | `ops.real_business_slice_month_fact` | Oro ≥95%, Plata ≥85%, Bronce ≥70% |
| `SH` | Supply Hours | hours | Manual input | Oro ≥95%, Plata ≥85%, Bronce ≥70% |
| `N_R` | Nuevos + Reactivados | count | `ops.mv_driver_lifecycle_weekly_kpis` | Oro ≥90%, Plata ≥80%, Bronce ≥65% |
| `CALLS` | Calls efectivas | count | Manual input | Oro ≥90%, Plata ≥80%, Bronce ≥65% |
| `CONV_NEW` | Conversión nuevos | pct | Manual input | Oro ≥25%, Plata ≥15%, Bronce ≥10% |
| `CONV_REA` | Conversión reactivados | pct | Manual input | Oro ≥15%, Plata ≥10%, Bronce ≥5% |
| `UFC` | % AD en UFC | pct | Manual input | Oro ≥70%, Plata ≥50%, Bronce ≥30% |
| `COMMS` | Fleetroom communications | score | Manual input | Oro ≥90%, Plata ≥75%, Bronce ≥60% |
| `SUPPORT` | Support MS score | score | Manual input | Oro ≥90%, Plata ≥75%, Bronce ≥60% |
| `SOCIAL` | Social Media score | score | Manual input | Oro ≥90%, Plata ≥75%, Bronce ≥60% |

---

## 3. Fórmulas

### Expected Progress (progreso esperado al día D)

```
expected_progress_pct = (today_day / total_days_in_month) × 100
expected_value_today  = target_value × (today_day / total_days_in_month)
```

### Gap

```
gap_abs = real_value - expected_value_today
gap_pct = (gap_abs / target_value) × 100
```

### Velocity Required (velocidad diaria necesaria para alcanzar la meta)

```
velocity_required = (target_value - real_value) / (total_days_in_month - today_day)
```

### Projected End (proyección lineal a fin de mes)

```
projected_end_value = real_value + (velocity_required × remaining_days)
```

### Attainment

```
attainment_pct = (real_value / target_value) × 100
projected_attainment_pct = (projected_end_value / target_value) × 100
```

### Current Category (categoría actual basada en attainment)

```
Si attainment_pct ≥ gold_threshold   → ORO
Si attainment_pct ≥ silver_threshold → PLATA
Si attainment_pct ≥ bronze_threshold → BRONCE
Sino → SIN_CATEGORIA
```

---

## 4. Fuentes de Datos

### available_now (consultados desde la DB en tiempo real)

- **AD**: `ops.real_business_slice_month_fact` — `SUM(active_drivers)` filtrado por month, country, city.
- **N_R**: `ops.mv_driver_lifecycle_weekly_kpis` — `SUM(activations) + SUM(reactivated)` para el mes.

### manual_input (tabla `ops.yango_loyalty_manual_results`)

- SH, CALLS, CONV_NEW, CONV_REA, UFC, COMMS, SUPPORT, SOCIAL

Los valores manuales se ingresan vía `POST /yango-loyalty/manual-results`.

### future_integration

Ninguno en esta fase. Todos los KPIs no automatizados usan `manual_input`.

---

## 5. Reachability Logic

| Estado | Condición |
|--------|-----------|
| `ON_TRACK` | `real_value ≥ expected_value_today` |
| `SLIGHTLY_BEHIND` | `gap_pct ≥ -10%` (recuperable sin aceleración fuerte) |
| `RECOVERABLE` | `gap_pct ≥ -25%` (necesita aceleración) |
| `HIGH_RISK` | `gap_pct < -25%` y proyección ≥ target (posible pero difícil) |
| `UNREACHABLE` | Proyección lineal < target (matemáticamente imposible a velocidad actual) |
| `DATA_MISSING` | No hay `real_value` o `target_value` |

---

## 6. Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/yango-loyalty/summary` | Vista consolidada: ciudades, KPIs, categorías, reachability |
| `GET` | `/yango-loyalty/kpis` | Catálogo del KPI Registry |
| `GET` | `/yango-loyalty/city-status` | Estado detallado por ciudad (`?city=Lima`) |
| `GET` | `/yango-loyalty/gaps` | KPIs con gap negativo (`?min_gap_pct=5`) |
| `GET` | `/yango-loyalty/reachability` | Distribución de estados reachability |
| `POST` | `/yango-loyalty/goals` | Registrar/actualizar metas mensuales |
| `POST` | `/yango-loyalty/manual-results` | Registrar/actualizar resultados manuales |

---

## 7. Tablas de Base de Datos

### `ops.yango_loyalty_kpi_registry`

Catálogo maestro de KPIs. Un registro por KPI con thresholds de categoría y metadata.

### `ops.yango_loyalty_monthly_goals`

Metas mensuales por ciudad y KPI. Unique key: `(month, country, city, kpi_code)`.

### `ops.yango_loyalty_manual_results`

Resultados manuales por ciudad, mes y KPI. Unique key: `(month, country, city, kpi_code)`.

---

## 8. Vista Frontend

- **Componente:** `YangoLoyaltyReachabilityDashboard.jsx`
- **Ruta:** `/performance/yango-loyalty`
- **Tab:** Performance > Yango Loyalty

### Secciones:
1. Header con mes, día actual, total KPIs
2. Data Missing Banner (si hay KPIs sin datos)
3. City Summary Cards (Lima, Trujillo, Arequipa) con categoría dominante y reachability
4. Reachability Distribution (resumen de estados)
5. Filtros por vista (Todos / Con Gap / En Riesgo / Sin Datos)
6. Tabla de KPIs con: Meta, Real, Gap%, Avance Esperado, Velocidad Requerida, Categoría Actual, Categoría Proyectada, Reachability
7. Gaps detalle (top 10)
8. Limitaciones y notas (colapsable)

---

## 9. Limitaciones

1. **Proyección lineal:** Se asume velocidad constante. No modela seasonality, aceleraciones ni frenos típicos de fin de mes.
2. **Solo 3 ciudades:** Lima, Trujillo, Arequipa (hardcodeadas). Para agregar ciudades se requiere modificar el código.
3. **AD y N+R tienen definiciones distintas:** AD usa `completed_flag` (business slice), N+R usa `activation_ts` + ventanas semanales (lifecycle). No son perfectamente comparables entre sí.
4. **8 de 10 KPIs son manual_input:** Dependen de que un operador ingrese datos vía el endpoint POST.
5. **Sin consolidado ponderado:** La categoría "dominante" usa moda simple, no ponderación por importancia de KPI.

---

## 10. Qué NO hace todavía

- NO genera recomendaciones automáticas
- NO automatiza acciones correctivas
- NO usa IA para decidir categorías o reachability
- NO integra fuentes externas (CRM, IVR, Fleetroom API, redes sociales)
- NO calcula consolidados ponderados por peso de KPI
- NO envía alertas o notificaciones
- NO tiene histórico de evolución diaria (solo foto del momento)
- NO soporta más de 3 ciudades sin cambio de código
- NO es un Suggestion Engine

---

## 11. QA

Script de validación: `backend/scripts/validate_phase3a_yango_loyalty_reachability.py`

Valida:
1. Tablas existen (vía endpoint KPI registry)
2. Endpoints responden 200
3. Omniview intacto (`/ops/business-slice/monthly`, matrix-operational-trust)
4. Plan vs Real intacto (`/ops/plan-vs-real/monthly`)
5. Fase 2 intacta (recoverability, lifecycle, supply, operational-intelligence)
6. Cálculos en rango (-200% a 200%)
7. Manual inputs funcionan (POST goals + POST manual-results + verificación en summary)
8. Sin recomendaciones automáticas (no contiene "recomendación" ni "suggestion")

---

## 12. Migración

Archivo: `backend/alembic/versions/152_yango_loyalty_reachability_engine.py`

Para aplicar:
```bash
cd backend
alembic upgrade head
```
