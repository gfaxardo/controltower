# OV2-A — TARGET LOGICAL ARCHITECTURE (ARQUITECTURA LÓGICA OBJETIVO)

> **Fase:** OV2-A — Blindaje Lógico OV2  
> **Fecha:** 2026-06-04  
> **Estado:** SOLO DISEÑO — No implementar todavía  
> **Propósito:** Definir estructura paralela OV2 sin tocar V1 productivo

---

## 1. PRINCIPIOS ARQUITECTÓNICOS OV2

1. **Paralelo, no reemplazo** — OV2 corre en archivos nuevos, sin modificar V1
2. **Serving-first** — Todo endpoint de OV2 lee de serving facts gobernados
3. **Determinístico** — Sin AI, sin suggestions, sin decisions. Solo lógica.
4. **Trazable** — Cada celda expone su source_table, source_type, refreshed_at
5. **Backend-pesado** — Cálculos en backend. Frontend solo renderiza.
6. **Unidireccional** — Datos fluyen RAW → FACT → SERVING VIEW → API → UI. Sin ciclos.

---

## 2. DATA LAYER — SERVING FACTS OV2

```
┌─────────────────────────────────────────────────────────────┐
│                    RAW LAYER (no tocar)                       │
│  public.trips_2025/2026, public.drivers, dim.dim_park, etc.  │
└──────────────────────────┬──────────────────────────────────┘
                           │ (pipeline existente V1)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 FACT LAYER (V1 → conservar)                   │
│  ops.real_business_slice_day_fact                             │
│  ops.real_business_slice_week_fact                            │
│  ops.real_business_slice_month_fact                           │
│  ops.plan_trips_monthly                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            SERVING LAYER OV2 (NUEVO — paralelo)              │
│                                                              │
│  v2.business_slice_day_serving      ← VIEW sobre day_fact    │
│  v2.business_slice_week_serving     ← VIEW sobre week_fact   │
│  v2.business_slice_month_serving    ← VIEW sobre month_fact  │
│  v2.projection_daily_fact           ← TABLE precalculada     │
│  v2.projection_weekly_fact          ← TABLE precalculada     │
│  v2.projection_monthly_fact         ← TABLE precalculada     │
│                                                              │
│  Columnas canónicas por celda:                               │
│  - real_value, plan_value, projection_value                  │
│  - delta_value, delta_pct                                    │
│  - period_status (CLOSED/PARTIAL/CURRENT/FUTURE)             │
│  - freshness (data_date, refreshed_at, lag_hours)             │
│  - trust (source_type: real/proxy/missing, confidence)       │
│  - color_signal (green/yellow/red/gray)                       │
│  - grain (day/week/month)                                    │
│  - lineage (source_table, source_view, pipeline_version)     │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Contrato de Celda Canónica OV2

Cada celda en la matriz OV2 DEBE contener:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `real_value` | NUMERIC | Valor real (del serving fact) |
| `plan_value` | NUMERIC | Valor planificado (NULL si no hay plan) |
| `projection_value` | NUMERIC | Proyección a fin de período |
| `delta_value` | NUMERIC | real_value - previous_period_value |
| `delta_pct` | NUMERIC | (real_value / previous_period_value - 1) * 100 |
| `period_status` | ENUM | CLOSED / PARTIAL / CURRENT / FUTURE / NO_PLAN / NO_REAL |
| `data_date` | DATE | Fecha del último dato real |
| `refreshed_at` | TIMESTAMP | Momento del último refresh del serving fact |
| `lag_hours` | NUMERIC | Horas desde último dato hasta now |
| `source_type` | ENUM | real / proxy / missing / projected |
| `source_table` | TEXT | Nombre de la tabla fuente (para trazabilidad) |
| `confidence` | NUMERIC | 0.0-1.0 (según source_type y frescura) |
| `color_signal` | ENUM | green / yellow / red / gray |
| `grain` | ENUM | day / week / month |
| `attainment_pct` | NUMERIC | real / plan * 100 (solo en modo Vs Proy) |
| `gap_value` | NUMERIC | plan - real (solo en modo Vs Proy) |

---

## 3. BACKEND LAYER — SERVICIOS OV2

### 3.1 Estructura de Archivos (NUEVA, paralela a V1)

```
backend/app/
├── routers/
│   └── omnibuilder_v2.py              ← NUEVO router OV2
├── services/
│   ├── omnibuilder_v2_audit_service.py    ← NUEVO: servicio de auditoría/trazabilidad
│   ├── omnibuilder_v2_registry_service.py ← NUEVO: registro canónico de métricas
│   ├── omnibuilder_v2_serving_service.py  ← NUEVO: queries a serving layer OV2
│   └── omnibuilder_v2_projection_service.py ← NUEVO: proyección simplificada
├── repositories/
│   └── omnibuilder_v2_repository.py       ← NUEVO: queries SQL a v2.* serving layer
├── contracts/
│   └── omnibuilder_v2_cell_contract.py    ← NUEVO: contrato canónico de celda
└── sql/
    └── omnibuilder_v2/
        ├── v2_serving_views.sql           ← Vistas serving OV2
        ├── v2_projection_facts.sql        ← Facts de proyección OV2
        └── v2_lineage_audit.sql           ← Queries de auditoría de lineage
```

### 3.2 `omnibuilder_v2.py` (Router) — Endpoints propuestos

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/v2/matrix/{grain}` | Matriz completa OV2 (daily/weekly/monthly) con todas las columnas del contrato |
| GET | `/v2/cell/{grain}/{country}/{city}/{slice}/{period}` | Celda individual con trazabilidad completa |
| GET | `/v2/audit/lineage/{metric_id}` | Lineage completo de una métrica (RAW→FACT→SERVING→API) |
| GET | `/v2/audit/freshness` | Frescura de todos los serving facts OV2 |
| GET | `/v2/audit/coverage` | Matriz de cobertura grain × metric × country |
| GET | `/v2/audit/risk` | Riesgos activos detectados (del risk register) |
| GET | `/v2/registry/metrics` | Registro canónico de métricas OV2 |
| GET | `/v2/registry/sources` | Registro de fuentes de datos OV2 |

### 3.3 `omnibuilder_v2_audit_service.py`

Responsabilidades:
- `get_metric_lineage(metric_id)` → árbol de dependencias RAW→FACT→SERVING
- `get_freshness_matrix()` → última fecha de dato por grain × metric
- `get_coverage_matrix()` → coverage_pct por grain × metric × country
- `get_active_risks()` → riesgos del risk register con status
- `validate_cell_contract(cell_data)` → validar que una celda cumple el contrato canónico
- `trace_cell_source(country, city, slice, period, metric)` → trazabilidad completa de una celda

### 3.4 `omnibuilder_v2_registry_service.py`

Responsabilidades:
- `register_metric(metric_def)` → registrar métrica en catálogo canónico
- `get_metric_registry()` → listar todas las métricas con fuente, grain, fórmula
- `register_source(source_def)` → registrar fuente de datos
- `get_source_registry()` → listar fuentes con tipo, frescura, dependencias
- `get_metric_by_id(metric_id)` → ficha completa de métrica

### 3.5 `omnibuilder_v2_serving_service.py`

Responsabilidades:
- `get_matrix(grain, filters)` → query a `v2.business_slice_{grain}_serving`
- `get_cell(grain, country, city, slice, period)` → celda individual con contrato completo
- Columnas devueltas: todas las del contrato canónico (ver 2.1)
- SIN cálculos runtime: todo precalculado en serving facts

### 3.6 `omnibuilder_v2_projection_service.py`

Responsabilidades:
- `get_projection_matrix(grain, filters)` → proyección simplificada
- Fuente única: `v2.projection_{grain}_fact`
- Columnas: attainment_pct, gap_value, projection_value, expected_ratio, curve_confidence
- SIN sugerencias, SIN decisiones, SIN AI

### 3.7 `omnibuilder_v2_repository.py`

Queries SQL directas a la capa `v2.*`:
- `get_serving_matrix_query(grain)` → SELECT * FROM v2.business_slice_{grain}_serving
- `get_cell_query(grain)` → SELECT * WHERE country=X AND city=Y AND slice=Z AND period=P
- `get_freshness_query()` → SELECT serving_key, max_data_date, refreshed_at FROM v2.serving_freshness
- `get_lineage_query(metric_id)` → CTE recursivo de lineage

---

## 4. FRONTEND LAYER — COMPONENTES OV2 (DISEÑO, no implementar)

### 4.1 Principios Frontend OV2
- **Thin client**: Sin lógica de negocio. Solo renderizado y filtros.
- **Una sola fuente de verdad**: `GET /v2/matrix/{grain}` devuelve TODO precalculado.
- **Sin localStorage para estado de negocio**: filtros OK, pero no deltas/colores/señales.
- **Celda como contrato**: cada celda recibe el contrato canónico completo del backend.

### 4.2 Componentes Propuestos (solo nombres, sin código)

```
frontend/src/components/ov2/
├── Ov2Matrix.jsx                  ← Vista principal OV2 (reemplaza BusinessSliceOmniviewMatrix)
├── Ov2MatrixHeader.jsx            ← Cabecera con periodos y badges de estado
├── Ov2MatrixCell.jsx              ← Celda individual (solo renderiza contrato)
├── Ov2CellInspector.jsx           ← Inspector con trazabilidad completa
├── Ov2KpiStrip.jsx                ← Franja KPI superior
├── Ov2FilterBar.jsx                ← Barra de filtros unificada
├── Ov2FreshnessBanner.jsx          ← Banner de frescura (max_data_date visible siempre)
├── Ov2PeriodStatusLegend.jsx       ← Leyenda CLOSED/PARTIAL/CURRENT/FUTURE
└── Ov2AuditPanel.jsx              ← Panel de auditoría (lineage, riesgos, coverage)
```

---

## 5. MIGRATION PATH OV1 → OV2

```
FASE OV2-A (ACTUAL):     Auditoría + Documentación      ← ESTAMOS AQUÍ
FASE OV2-B:              Implementar backend layer OV2
                         (routers, services, repositories, SQL)
                         Sin tocar V1. Paralelo.
                         
FASE OV2-C:              Implementar frontend layer OV2
                         Sin reemplazar V1. Ruta /v2/operacion.
                         
FASE OV2-D:              Validación cruzada OV1 vs OV2
                         Mismos datos, distinta arquitectura.
                         Comparar resultados numéricos.
                         
FASE OV2-E:              Switch controlado
                         OV2 como default. OV1 como legacy (/v1/...).
                         
FASE OV2-F:              Deprecación OV1
                         Eliminar componentes/endpoints/servicios DROP.
```

---

## 6. SQL — VISTAS SERVING OV2 (PROPUESTA)

### 6.1 `v2_serving_views.sql`

```sql
-- Vista serving diaria OV2 (paralela a day_fact, añade columnas de contrato)
CREATE OR REPLACE VIEW v2.business_slice_day_serving AS
SELECT
    d.country,
    d.city,
    d.business_slice_name,
    d.period_key AS period,
    'day' AS grain,
    -- real values
    d.trips_completed AS real_value_trips,
    d.revenue_yego_final AS real_value_revenue,
    d.active_drivers AS real_value_drivers,
    d.avg_ticket AS real_value_avg_ticket,
    d.trips_completed / NULLIF(d.active_drivers, 0) AS real_value_tpd,
    d.cancel_rate_pct AS real_value_cancel_rate,
    d.commission_pct AS real_value_commission,
    -- freshness
    d.data_date,
    d.refreshed_at,
    EXTRACT(EPOCH FROM (NOW() - d.refreshed_at)) / 3600.0 AS lag_hours,
    -- source
    'real' AS source_type,
    'ops.real_business_slice_day_fact' AS source_table,
    -- trust
    CASE WHEN d.revenue_source = 'proxy' THEN 0.7 ELSE 1.0 END AS confidence,
    -- period status
    pc.status AS period_status,
    -- deltas (DoD)
    d.trips_completed - LAG(d.trips_completed) OVER (
        PARTITION BY d.country, d.city, d.business_slice_name 
        ORDER BY d.period_key
    ) AS delta_trips,
    -- color signal
    CASE 
        WHEN pc.status = 'CLOSED' THEN 'green'
        WHEN pc.status = 'PARTIAL' THEN 'yellow'
        WHEN pc.status = 'FUTURE' THEN 'gray'
        ELSE 'red'
    END AS color_signal
FROM ops.real_business_slice_day_fact d
LEFT JOIN ops.period_closure_registry pc 
    ON d.period_key = pc.period AND d.country = pc.country;

-- (Similar para week_serving y month_serving)
```

### 6.2 `v2_projection_facts.sql`

```sql
-- Proyección diaria OV2 (simplificada, sin suggestion/decision/AI)
CREATE TABLE IF NOT EXISTS v2.projection_daily_fact (
    country TEXT,
    city TEXT,
    business_slice_name TEXT,
    period_key DATE,
    grain TEXT DEFAULT 'day',
    -- real values
    real_trips NUMERIC,
    real_revenue NUMERIC,
    real_drivers NUMERIC,
    -- plan/projection values
    plan_trips NUMERIC,
    plan_revenue NUMERIC,
    plan_drivers NUMERIC,
    expected_trips NUMERIC,   -- proyección a fin de mes
    expected_revenue NUMERIC,
    -- attainment
    attainment_trips_pct NUMERIC,
    attainment_revenue_pct NUMERIC,
    attainment_drivers_pct NUMERIC,
    gap_trips NUMERIC,
    gap_revenue NUMERIC,
    -- meta
    plan_version TEXT,
    curve_method TEXT,
    curve_confidence NUMERIC,
    refreshed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (country, city, business_slice_name, period_key, grain, plan_version)
);
```

---

## 7. CONTRATO DE API OV2

### `GET /v2/matrix/{grain}`

**Query params:** `country`, `city`, `business_slice`, `year`, `month`, `week`, `perspective` (oper/owner)

**Response:**
```json
{
  "grain": "monthly",
  "periods": ["2026-01", "2026-02", ...],
  "countries": ["Colombia", "Peru"],
  "metrics": ["trips_completed", "revenue_yego_net", "active_drivers", ...],
  "cells": [
    {
      "country": "Colombia",
      "city": "Bogota",
      "slice": "YEGO",
      "period": "2026-01",
      "metrics": {
        "trips_completed": {
          "real_value": 12345,
          "delta_value": 567,
          "delta_pct": 4.8,
          "period_status": "CLOSED",
          "source_type": "real",
          "source_table": "v2.business_slice_month_serving",
          "confidence": 1.0,
          "color_signal": "green",
          "data_date": "2026-01-31",
          "refreshed_at": "2026-06-04T05:00:00Z",
          "lag_hours": 0
        }
      }
    }
  ],
  "freshness": {
    "max_data_date": "2026-01-31",
    "overall_lag_hours": 0,
    "warnings": []
  }
}
```

### `GET /v2/audit/lineage/{metric_id}`

**Response:**
```json
{
  "metric_id": "trips_completed",
  "lineage": [
    {"layer": "RAW", "source": "public.trips_2026", "grain": "trip"},
    {"layer": "ENRICHED", "source": "ops.v_real_trips_enriched_base", "grain": "trip"},
    {"layer": "FACT_DAY", "source": "ops.real_business_slice_day_fact", "grain": "day"},
    {"layer": "FACT_WEEK", "source": "ops.real_business_slice_week_fact", "grain": "week"},
    {"layer": "FACT_MONTH", "source": "ops.real_business_slice_month_fact", "grain": "month"},
    {"layer": "SERVING", "source": "v2.business_slice_month_serving", "grain": "month"},
    {"layer": "API", "source": "GET /v2/matrix/monthly", "grain": "month"},
    {"layer": "UI", "source": "Ov2MatrixCell", "grain": "month"}
  ]
}
```

---

## 8. REGLAS DE NO-IMPLEMENTACIÓN (FASE OV2-A)

- **NO** crear tablas/vistas en DB
- **NO** crear endpoints activos en router
- **NO** modificar `main.py` para incluir nuevos routers
- **NO** crear componentes React nuevos
- **NO** modificar `App.jsx` para añadir rutas
- **NO** modificar `api.js` para añadir funciones

**SÍ permitido en OV2-A:**
- Crear archivos de documentación (`.md`)
- Crear archivos de código vacíos o con docstrings (placeholders)
- Crear scripts de solo-lectura para auditoría
- Ejecutar queries de exploración (SELECT only)

---

## 9. GO / NO-GO CHECKLIST PARA OV2-B

OV2-B solo puede iniciar si:

- [x] Existe inventario completo (OV2_A_FORENSIC_INVENTORY.md)
- [x] Están clasificadas las métricas principales (OV2_A_METRIC_CLASSIFICATION.md)
- [x] Están identificadas las fuentes confiables (KEEP en clasificación)
- [x] Se detectaron fallbacks/riesgos (OV2_A_RISK_REGISTER.md)
- [x] No se tocó producción (validar con git status)
- [ ] OMNI-P0 cerrado con GO real (requisito de ai_current_phase.md)
- [ ] Revenue serving completo cross-grain
- [ ] Vs Proy como vista canónica default
- [ ] Evolution completamente oculto (no toggle)
