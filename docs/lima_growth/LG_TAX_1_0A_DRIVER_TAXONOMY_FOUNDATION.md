# LG-TAX-1.0A — DRIVER TAXONOMY FOUNDATION

**Fase:** Lima Growth Foundation — TAX-1.0A  
**Motor:** Control Foundation (Lima Growth)  
**Estatus:** DESIGN ONLY — NO IMPLEMENTAR  
**Fecha:** 2026-06-10  
**Simulación:** data real 2026-06-10, N=18,545 drivers  
**Dependencia:** LG-S1.0A (Segmentación Canónica) — conocimiento previo asumido  

---

## TASK 0 — GOVERNANCE CHECK

### Fase Activa

| Motor | Fase | Estatus |
|-------|------|---------|
| Control Foundation | Omniview P0 Recovery | **REOPENED / P0** |
| Diagnostic Engine | 2A.3 | **PAUSED** |
| Lima Growth | Scheduler 5-min tick | **ACTIVE** |

### Restricciones

- **NO** activar Forecast / Suggestion / Decision / Action / AI
- **NO** modificar queue, export, control_loop, scheduler, Yango ingestion
- **NO** tocar programas legacy ni UI productiva
- LG-TAX-1.0A es **design-only**: taxonomía conceptual + simulación + diseño de persistencia. No modifica infraestructura productiva.

### Veredicto

**GO para diseño.** La taxonomía es una capa fundamental de Lima Growth Foundation (Control Foundation). No activa motores bloqueados. Es compatible con OMNI-P0 activo porque no modifica serving facts ni UI productiva.

---

## TASK 1 — TAXONOMÍA CONCEPTUAL: LOS 4 EJES CANÓNICOS

### Principio Central

NO segmentos estáticos. Taxonomía diaria multidimensional:

```
driver + date  -->  lifecycle  ×  activity  ×  value  ×  momentum  =  operational_persona
```

Cada eje es independiente. Los programas futuros consumen la persona operacional. Los ejes no son excluyentes entre sí porque miden dimensiones distintas.

---

### EJE 1: LIFECYCLE

**Definición operacional**: Dónde está el conductor en su ciclo de vida con la plataforma, medido desde su fecha ancla.

| Estado | Definición | Regla Configurable | Input Requerido |
|--------|-----------|-------------------|-----------------|
| **NEW** | Recién ingresado a la plataforma | `days_since_anchor <= new_window_days` (default: 30) | `first_seen_at`, `first_trip_at` |
| **REACTIVATED** | Volvió después de inactividad prolongada | `reactivated_flag = true` OR `days_since_anchor > reactivation_gap_days AND has_recent_activity = true` (default: 90d) | `first_seen_at`, `last_trip_at`, `reactivated_flag` |
| **MATURE** | Conductor establecido con historial | `days_since_anchor > maturity_after_days` (default: 60) | `first_seen_at`, `first_trip_at` |

**Fallback si falta input**: Si `first_seen_at` es NULL, usar `first_trip_at`. Si ambos son NULL, clasificar como MATURE con flag `anchor_date_missing=true`.

**Explicación esperada**:
- NEW: "Driver joined <N> days ago on <date>."
- REACTIVATED: "Driver was inactive for <N> days and reactivated on <date>."
- MATURE: "Driver has been active for <N> days since <date>."

**Transiciones posibles**:
- NEW → MATURE (natural, al cumplir maturity_after_days)
- NEW → REACTIVATED (si tuvo gap antes del primer viaje)
- REACTIVATED → MATURE (al estabilizarse)
- MATURE → REACTIVATED (si churned y volvió)

**Simulación 2026-06-10**:

| Estado | Drivers | % |
|--------|---------|---|
| MATURE | 17,990 | 97.0% |
| NEW | 555 | 3.0% |
| REACTIVATED | 0 | 0.0% |

**Nota**: 0% REACTIVATED porque `reactivated_flag` no está poblado en la data actual. El pipeline de reactivación requiere maduración. La regla está diseñada; el dato llegará cuando el pipeline lo genere.

---

### EJE 2: ACTIVITY

**Definición operacional**: Nivel de actividad reciente del conductor.

| Estado | Definición | Regla Configurable | Input Requerido |
|--------|-----------|-------------------|-----------------|
| **ACTIVE** | Con actividad reciente | `days_since_last_trip <= active_trip_window_days` (default: 14) OR `completed_orders_week > 0` OR `days_since_last_supply <= active_supply_window_days` (default: 14) | `last_trip_at`, `completed_orders_week`, `last_supply_at` |
| **AT_RISK** | Sin actividad reciente pero no churned | `days_since_last_trip > active_trip_window_days AND days_since_last_trip <= churned_window_days` (default: 30) | `last_trip_at` |
| **CHURNED** | Inactivo prolongado | `days_since_last_trip > churned_window_days` (default: 90) OR `completed_orders_week = 0 AND no supply in 90d` | `last_trip_at`, `completed_orders_week` |

**Señales y precedencia**:

```
1. last_trip_at (señal primaria, más confiable si está actualizada)
2. completed_orders_week (proxy semanal, cubre el caso de last_trip_at desactualizado)
3. last_supply_at (proxy de suministro, actualmente NULL para el 100% del universo)
4. retention_state (fallback: HEALTHY → ACTIVE, AT_RISK → AT_RISK, CHURN_RISK → AT_RISK)
```

**Fallback si falta input**:
- Si `last_trip_at` es NULL: usar `completed_orders_week > 0` → ACTIVE, else fallback a `retention_state`.
- Si ningún signal disponible: ACTIVE por default con flag `activity_signal_missing=true`.

**Explicación esperada**:
- ACTIVE: "Last trip <N> days ago. <M> orders this week."
- AT_RISK: "No trip in <N> days. Risk signals: <signals>."
- CHURNED: "No trip in <N> days. Last seen <date>."

**Transiciones posibles**:
- ACTIVE → AT_RISK (días sin viaje acumulándose)
- AT_RISK → ACTIVE (retomó actividad)
- AT_RISK → CHURNED (superó churned_window_days)
- CHURNED → ACTIVE (reactivación)

**Simulación 2026-06-10**:

| Estado | Drivers | % |
|--------|---------|---|
| ACTIVE | 18,545 | 100.0% |
| AT_RISK | 0 | 0.0% |
| CHURNED | 0 | 0.0% |

**Nota crítica**: 100% ACTIVE porque todos los drivers tienen `completed_orders_week > 0`. El campo `last_trip_at` muestra >90d para 10,630 drivers (57%) incluso cuando tienen órdenes esta semana — esto indica que `last_trip_at` no es confiable como señal de recencia en el pipeline actual. La simulación usa `completed_orders_week > 0` como proxy principal, que es robusto pero impide distinguir AT_RISK de ACTIVE.

**Recomendación**: Auditar y reparar el pipeline de `last_trip_at` en `driver_state_snapshot` (issue de data quality). Sin esa señal, la distinción ACTIVE/AT_RISK/CHURNED no puede implementarse correctamente.

---

### EJE 3: VALUE

**Definición operacional**: Valor productivo del conductor medido por volumen de viajes.

| Estado | Definición | Regla Configurable | Input Requerido |
|--------|-----------|-------------------|-----------------|
| **TOP** | Elite, percentil superior | `value_metric >= p90_threshold` (default: p90 del universo) | `avg_orders_4w`, `completed_orders_week` |
| **HIGH** | Alto valor | `value_metric >= p70_threshold AND < p90_threshold` | `avg_orders_4w`, `completed_orders_week` |
| **MEDIUM** | Valor medio | `value_metric >= p30_threshold AND < p70_threshold` | `avg_orders_4w`, `completed_orders_week` |
| **LOW** | Bajo valor | `value_metric < p30_threshold` | `avg_orders_4w`, `completed_orders_week` |

**Value metric**: `avg_orders_4w` (promedio de órdenes completadas en últimas 4 semanas). Fallback: `completed_orders_week` si avg_4w = 0.

**Percentiles dinámicos** (calculados sobre el universo activo del día):

| Percentil | Threshold (2026-06-10) | Etiqueta |
|-----------|------------------------|----------|
| p90 | 6.0 trips/semana | TOP |
| p70 | 3.0 trips/semana | HIGH |
| p30 | 1.0 trips/semana | MEDIUM |

**Nota**: Los thresholds de percentiles son notablemente bajos porque el 82% del universo hace 1-10 viajes/semana. Esto refleja la realidad del mercado. Los thresholds deben recalcularse diariamente sobre el universo activo.

**Fallback si falta input**: Si `avg_orders_4w = 0` y `completed_orders_week = 0`, usar `historical_band`. Si tampoco hay historical_band, clasificar como LOW con flag `value_signal_missing=true`.

**Explicación esperada**:
- TOP: "Average 4-week trips = <N>. Above p90 threshold (<T>)."
- HIGH: "Average 4-week trips = <N>. Between p70 (<T1>) and p90 (<T2>)."
- MEDIUM: "Average 4-week trips = <N>. Between p30 (<T1>) and p70 (<T2>)."
- LOW: "Average 4-week trips = <N>. Below p30 threshold (<T>)."

**Transiciones posibles**: Cualquier estado puede transicionar a cualquier otro. No hay restricciones de transición en Value.

**Simulación 2026-06-10**:

| Estado | Drivers | % |
|--------|---------|---|
| LOW | 9,417 | 50.8% |
| MEDIUM | 5,293 | 28.5% |
| HIGH | 2,211 | 11.9% |
| TOP | 1,624 | 8.8% |

---

### EJE 4: MOMENTUM

**Definición operacional**: Tendencia direccional del desempeño del conductor.

| Estado | Definición | Regla Configurable | Input Requerido |
|--------|-----------|-------------------|-----------------|
| **GROWING** | Incrementando producción | `delta_pct >= growth_pct_threshold` (default: +20%) AND `current_volume >= min_volume_for_momentum` | `avg_orders_4w`, `avg_orders_12w` |
| **STABLE** | Producción estable | `|delta_pct| < growth_pct_threshold` OR `current_volume < min_volume_for_momentum` | `avg_orders_4w`, `avg_orders_12w` |
| **DECLINING** | Cayendo producción | `delta_pct <= decline_pct_threshold` (default: -20%) AND `current_volume >= min_volume_for_momentum` | `avg_orders_4w`, `avg_orders_12w`, `declining_flag` |

**Fórmula**: `delta_pct = (avg_orders_4w - avg_orders_12w) / avg_orders_12w * 100`

**Señal adicional**: `declining_flag` (WoW decline > 30%) tiene precedencia sobre el cálculo de delta. Si `declining_flag = true`, el momentum es DECLINING independientemente del delta 4w-vs-12w.

**Min volume for momentum** (default: 4 trips/semana): Evita clasificar como GROWING/DECLINING a conductores con volumen insignificante donde +100% puede significar pasar de 1 a 2 viajes.

**Fallback si falta input**:
- Si `avg_orders_4w` y `avg_orders_12w` son 0: STABLE (sin señal suficiente).
- Si solo uno tiene datos: STABLE.
- Si `declining_flag = true`: DECLINING (señal fuerte).

**Explicación esperada**:
- GROWING: "4-week average (<N>) is <X>% above 12-week baseline (<M>)."
- STABLE: "4-week average (<N>) is within stable range of 12-week baseline (<M>). Delta: <X>%."
- DECLINING: "4-week average (<N>) is <X>% below 12-week baseline (<M>). Declining flag: <true/false>."

**Transiciones posibles**: Cualquier estado puede transicionar a cualquier otro.

**Simulación 2026-06-10**:

| Estado | Drivers | % |
|--------|---------|---|
| STABLE | 17,970 | 96.9% |
| DECLINING | 575 | 3.1% |
| GROWING | 0 | 0.0% |

**Nota**: 96.9% STABLE porque la mayoría de drivers tiene `avg_orders_4w == avg_orders_12w` (rendimiento plano en los thresholds bajos del mercado). 0% GROWING porque muy pocos conductores muestran crecimiento >20% sostenido con volumen suficiente. 3.1% DECLINING capturados por `declining_flag`.

---

### OPERATIONAL PERSONA (Combinación)

La persona operacional es la concatenación de los 4 ejes:

```
{lifecycle}_{activity}_{value}_{momentum}
```

Ejemplos reales del universo 2026-06-10:

| Persona | Drivers | % | Interpretación |
|---------|---------|---|---------------|
| `MATURE_ACTIVE_LOW_STABLE` | 9,088 | 49.0% | Conductor establecido, activo, bajo volumen, estable |
| `MATURE_ACTIVE_MEDIUM_STABLE` | 4,882 | 26.3% | Conductor establecido, activo, volumen medio, estable |
| `MATURE_ACTIVE_HIGH_STABLE` | 1,995 | 10.8% | Conductor establecido, activo, alto volumen, estable |
| `MATURE_ACTIVE_TOP_STABLE` | 1,472 | 7.9% | Top performer establecido y estable |
| `NEW_ACTIVE_LOW_STABLE` | 287 | 1.5% | Nuevo conductor, activo, bajo volumen |
| `MATURE_ACTIVE_MEDIUM_DECLINING` | 225 | 1.2% | Establecido en declive |
| `NEW_ACTIVE_MEDIUM_STABLE` | 175 | 0.9% | Nuevo conductor creciendo a medio |
| `MATURE_ACTIVE_HIGH_DECLINING` | 147 | 0.8% | Alto valor en declive — alta prioridad |
| `MATURE_ACTIVE_TOP_DECLINING` | 139 | 0.7% | Top performer en declive — máxima prioridad |

**Total combinaciones únicas**: 15 (de 3×3×4×3 = 108 posibles)

---

## TASK 2 — ANCHOR DATES

### Contrato de Fechas Ancla

Cada driver tiene una fecha ancla que determina su lifecycle:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `hire_date` | DATE | Fecha de registro en la plataforma (`first_seen_at`) |
| `first_trip_date` | DATE | Fecha del primer viaje (`first_trip_at`) |
| `last_trip_date` | DATE | Fecha del último viaje (`last_trip_at`) |
| `last_supply_date` | DATE | Fecha del último suministro (`last_supply_at`) |
| `reactivation_date` | DATE | Fecha de reactivación (primera actividad post-gap) |
| `current_anchor_date` | DATE | Fecha ancla activa para cálculo de lifecycle |
| `anchor_type` | TEXT | `HIRE_DATE`, `REACTIVATION_DATE`, `MATURITY_DATE`, `UNKNOWN` |

### Reglas de Anchor Type

| Lifecycle | anchor_type | current_anchor_date | Condición |
|-----------|-------------|---------------------|-----------|
| NEW | `HIRE_DATE` | `hire_date` | `days_since_hire <= new_window_days` |
| REACTIVATED | `REACTIVATION_DATE` | `reactivation_date` | `reactivated_flag = true` OR (gap > reactivation_gap AND has recent activity) |
| MATURE | `MATURITY_DATE` o NULL | `hire_date` | Default cuando no es NEW ni REACTIVATED |

### Resolución de Ambigüedades

| Escenario | Resolución |
|-----------|-----------|
| Supply sin trips | `anchor_type` usa `first_seen_at`. Activity usa `last_supply_at` como proxy de actividad. |
| Trip sin supply | `anchor_type` usa `first_trip_at`. Activity prioriza `last_trip_at`. |
| `last_trip_at` no confiable | Usar `completed_orders_week > 0` como proxy. Marcar `trip_signal_quality = DEGRADED`. |
| `hire_date` falta (first_seen_at IS NULL) | `anchor_type = UNKNOWN`. Lifecycle = MATURE. Flag `anchor_date_missing = true`. |

### Parámetros Configurables

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `reactivation_gap_days` | 90 | Días sin actividad para considerar "gap" |
| `new_window_days` | 30 | Días desde ancla para ser NEW |
| `maturity_after_days` | 60 | Días desde ancla para ser MATURE |

---

## TASK 3 — PARÁMETROS CONFIGURABLES

### Tabla de Configuración

```sql
CREATE TABLE growth.yego_lima_taxonomy_config (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key          TEXT NOT NULL,          -- e.g. 'lifecycle.new_window_days'
    config_value_json   JSONB NOT NULL,         -- e.g. 30 o {"p90": 6.0, "p70": 3.0, "p30": 1.0}
    axis                TEXT,                    -- 'lifecycle', 'activity', 'value', 'momentum'
    city                TEXT,                    -- NULL = global, 'lima' = city-specific
    vertical            TEXT,                    -- NULL = all, 'yango' = vertical-specific
    valid_from          DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to            DATE,
    taxonomy_version    TEXT NOT NULL DEFAULT 'v1',
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_tax_config_key_version 
    ON growth.yego_lima_taxonomy_config(config_key, taxonomy_version, city, vertical)
    WHERE is_active = true;
```

### Seed Inicial (V1)

```json
[
  {"config_key": "lifecycle.new_window_days",           "config_value_json": 30,       "axis": "lifecycle"},
  {"config_key": "lifecycle.reactivation_gap_days",     "config_value_json": 90,       "axis": "lifecycle"},
  {"config_key": "lifecycle.maturity_after_days",       "config_value_json": 60,       "axis": "lifecycle"},
  {"config_key": "activity.active_trip_window_days",    "config_value_json": 14,       "axis": "activity"},
  {"config_key": "activity.at_risk_window_days",        "config_value_json": 30,       "axis": "activity"},
  {"config_key": "activity.churned_window_days",        "config_value_json": 90,       "axis": "activity"},
  {"config_key": "activity.use_supply_as_proxy",        "config_value_json": true,     "axis": "activity"},
  {"config_key": "activity.use_weekly_orders_fallback", "config_value_json": true,     "axis": "activity"},
  {"config_key": "value.metric",                        "config_value_json": "avg_orders_4w", "axis": "value"},
  {"config_key": "value.top_percentile",                "config_value_json": 90,       "axis": "value"},
  {"config_key": "value.high_percentile",               "config_value_json": 70,       "axis": "value"},
  {"config_key": "value.medium_percentile",             "config_value_json": 30,       "axis": "value"},
  {"config_key": "value.use_completed_orders_week_fallback", "config_value_json": true, "axis": "value"},
  {"config_key": "momentum.current_window_weeks",       "config_value_json": 4,        "axis": "momentum"},
  {"config_key": "momentum.baseline_window_weeks",      "config_value_json": 4,        "axis": "momentum"},
  {"config_key": "momentum.baseline_offset_weeks",      "config_value_json": 4,        "axis": "momentum"},
  {"config_key": "momentum.growth_pct",                 "config_value_json": 20,       "axis": "momentum"},
  {"config_key": "momentum.decline_pct",                "config_value_json": -20,      "axis": "momentum"},
  {"config_key": "momentum.min_volume_for_momentum",    "config_value_json": 4,        "axis": "momentum"}
]
```

### Soporte para thresholds por ciudad / vertical

El campo `city` y `vertical` permiten sobreescribir thresholds globales. Ejemplo:

```json
{
  "config_key": "value.top_percentile",
  "config_value_json": 85,
  "city": "lima",
  "vertical": null,
  "taxonomy_version": "v1-lima"
}
```

**Resolución**: city-specific > vertical-specific > global. Si no hay override, se usa el valor global.

### Dependencia entre ejes

| Dependencia | Descripción |
|-------------|-------------|
| Activity depende de Lifecycle | Un driver NEW no puede ser CHURNED (lleva <30 días) |
| Momentum depende de Value | Si Value = LOW, el min_volume_for_momentum se ignora (su volumen es bajo por definición) |
| Value es independiente | No depende de ningún otro eje |
| Lifecycle es independiente | Solo depende de anchor dates |

---

## TASK 4 — PERSONA OPERACIONAL

### Regla de Combinación

```
operational_persona = CONCAT(lifecycle, '_', activity, '_', value, '_', momentum)
```

Ejemplo: `MATURE_ACTIVE_HIGH_DECLINING`

### Propiedades

- La persona es **derivada**, no asignada. Cambia si cambia cualquier eje.
- La persona es **persistida** diariamente en `driver_taxonomy_daily`.
- La persona **no es un segmento** — es una descripción. Los segmentos (LG-S1.0A) son excluyentes; las personas no.
- Múltiples drivers pueden compartir persona. Diferentes personas pueden requerir diferentes intervenciones.

### No todos requieren programa

| Persona | ¿Requiere programa? | Prioridad |
|---------|---------------------|-----------|
| `*_*_TOP_DECLINING` | SÍ — HIGH_VALUE_RECOVERY | Crítica |
| `*_*_HIGH_DECLINING` | SÍ — Churn prevention | Alta |
| `NEW_*_LOW_*` | SÍ — 50/14 onboarding | Alta |
| `NEW_*_MEDIUM_*` | SÍ — 90/300 acceleration | Media |
| `MATURE_ACTIVE_LOW_STABLE` | SÍ — Active growth (si tiene señales) | Media |
| `MATURE_ACTIVE_TOP_STABLE` | NO — Monitoreo pasivo | Baja |
| `MATURE_ACTIVE_MEDIUM_STABLE` | NO — Monitoreo pasivo | Baja |
| `*_CHURNED_*_*` | NO — Fuera de alcance operativo | Ninguna |

### Persistencia de Persona

La persona se persiste en la tabla de taxonomía diaria (ver TASK 6). Cada snapshot diario tiene la persona calculada para ese día.

---

## TASK 5 — PROGRAMAS FUTUROS COMO CONSUMIDORES

### Matriz de Mapeo: Persona → Programa

| Programa | Lifecycle | Activity | Value | Momentum | Condiciones Adicionales |
|----------|-----------|----------|-------|----------|------------------------|
| **50/14** | NEW, REACTIVATED | ACTIVE, AT_RISK | LOW, MEDIUM | STABLE, GROWING | `days_since_anchor <= 14 AND trips_since_anchor < 50` |
| **90/300** | NEW, REACTIVATED | ACTIVE | LOW, MEDIUM, HIGH | STABLE, GROWING | `days_since_anchor <= 90 AND trips_since_anchor < 300` |
| **HVR** | MATURE | ACTIVE, AT_RISK | TOP, HIGH | DECLINING | `current_weekly_orders << best_week_12w` |
| **ACTIVE_GROWTH** | MATURE | ACTIVE | LOW, MEDIUM | STABLE, GROWING, DECLINING | `weekly_trips <= configurable_threshold AND has_intervention_signal` |
| **TOP_RETENTION** | MATURE | ACTIVE | TOP | STABLE, GROWING | Sin intervención — solo monitoreo y engagement |
| **STABLE_MONITOR** | MATURE | ACTIVE | MEDIUM, HIGH | STABLE | Sin acción inmediata |
| **CHURN_WINBACK** | MATURE | CHURNED | HIGH, TOP | DECLINING | Campaña de reactivación |
| **UNMANAGED** | Cualquiera | Cualquiera | Cualquiera | Cualquiera | No califica a ningún programa activo |

### Principios

1. **Los programas son excluyentes** (un driver en un solo programa activo). Resolución por prioridad de programa.
2. **Los ejes taxonómicos NO son excluyentes** — son dimensiones independientes. Un driver ES NEW y ES ACTIVE y ES LOW y ES GROWING simultáneamente.
3. **Los programas LEEN la taxonomía**, no la modifican. La taxonomía es la capa inferior; los programas son la capa superior.
4. **Cambiar un programa no cambia la taxonomía**. La taxonomía refleja la realidad operativa del driver; el programa refleja la decisión de intervención.

### Flujo Conceptual

```
driver_state_snapshot
       │
       ▼
driver_taxonomy_daily  (4 ejes + persona)
       │
       ▼
segment_classification  (LG-S1.0A: segmento excluyente)
       │
       ▼
program_assignment      (programa operativo: 50/14, 90/300, HVR, etc.)
       │
       ▼
prioritized_opportunity
       │
       ▼
assignment_queue
       │
       ▼
export
```

---

## TASK 6 — PERSISTENCIA

### 6.1 `growth.yego_lima_driver_taxonomy_daily`

Tabla principal. Un registro por driver por día. **NO crear todavía.**

```sql
CREATE TABLE growth.yego_lima_driver_taxonomy_daily (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date           DATE NOT NULL,
    driver_profile_id       TEXT NOT NULL,
    
    -- 4 axes
    lifecycle_state         TEXT NOT NULL,          -- NEW, REACTIVATED, MATURE
    activity_state          TEXT NOT NULL,          -- ACTIVE, AT_RISK, CHURNED
    value_tier              TEXT NOT NULL,          -- LOW, MEDIUM, HIGH, TOP
    momentum_state          TEXT NOT NULL,          -- GROWING, STABLE, DECLINING
    
    -- Derived
    operational_persona     TEXT NOT NULL,          -- {lifecycle}_{activity}_{value}_{momentum}
    
    -- Anchor dates
    current_anchor_date     DATE,
    anchor_type             TEXT,                   -- HIRE_DATE, REACTIVATION_DATE, MATURITY_DATE, UNKNOWN
    days_since_anchor       INTEGER,
    
    -- Value metrics (numeric, for threshold computation)
    value_metric            NUMERIC,                -- e.g. avg_orders_4w
    value_percentile        NUMERIC,                -- computed percentile in universe
    
    -- Momentum metrics
    momentum_delta_pct      NUMERIC,                -- (avg_4w - avg_12w) / avg_12w * 100
    momentum_current_avg    NUMERIC,                -- avg_orders_4w
    momentum_baseline_avg  NUMERIC,                -- avg_orders_12w
    
    -- Metadata
    taxonomy_version        TEXT NOT NULL DEFAULT 'v1',
    signal_quality_flags    JSONB,                  -- {"trip_signal_quality": "DEGRADED", ...}
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE(snapshot_date, driver_profile_id)
);

CREATE INDEX idx_taxonomy_date ON growth.yego_lima_driver_taxonomy_daily(snapshot_date);
CREATE INDEX idx_taxonomy_persona ON growth.yego_lima_driver_taxonomy_daily(snapshot_date, operational_persona);
CREATE INDEX idx_taxonomy_lifecycle ON growth.yego_lima_driver_taxonomy_daily(snapshot_date, lifecycle_state);
CREATE INDEX idx_taxonomy_activity ON growth.yego_lima_driver_taxonomy_daily(snapshot_date, activity_state);
CREATE INDEX idx_taxonomy_value ON growth.yego_lima_driver_taxonomy_daily(snapshot_date, value_tier);
CREATE INDEX idx_taxonomy_driver ON growth.yego_lima_driver_taxonomy_daily(driver_profile_id);
```

### 6.2 `growth.yego_lima_driver_taxonomy_explanation`

Explicación detallada por eje. Un registro por driver por día por eje. **NO crear todavía.**

```sql
CREATE TABLE growth.yego_lima_driver_taxonomy_explanation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date       DATE NOT NULL,
    driver_profile_id   TEXT NOT NULL,
    axis                TEXT NOT NULL,              -- 'lifecycle', 'activity', 'value', 'momentum'
    state_value         TEXT NOT NULL,              -- e.g. 'MATURE', 'ACTIVE', 'TOP', 'STABLE'
    matched_rules_json  JSONB NOT NULL,             -- [{"rule": "maturity_after_days", "threshold": 60, "actual": 352, "matched": true}]
    failed_rules_json   JSONB,                      -- rules that were evaluated but didn't match
    evidence_json       JSONB NOT NULL,             -- raw values used: {"first_seen_at": "2025-06-23", "days_since": 352}
    explanation_text    TEXT NOT NULL,              -- "Driver has been active for 352 days since 2025-06-23."
    taxonomy_version    TEXT NOT NULL DEFAULT 'v1',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE(snapshot_date, driver_profile_id, axis)
);

CREATE INDEX idx_tax_expl_date ON growth.yego_lima_driver_taxonomy_explanation(snapshot_date);
CREATE INDEX idx_tax_expl_driver ON growth.yego_lima_driver_taxonomy_explanation(driver_profile_id);
```

### 6.3 `growth.yego_lima_driver_taxonomy_transition`

Registro de cambios de persona día a día. **NO crear todavía.**

```sql
CREATE TABLE growth.yego_lima_driver_taxonomy_transition (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_profile_id   TEXT NOT NULL,
    previous_date       DATE NOT NULL,
    current_date        DATE NOT NULL,
    previous_persona    TEXT NOT NULL,
    current_persona     TEXT NOT NULL,
    changed_axes_json   JSONB NOT NULL,             -- ["lifecycle", "momentum"] — which axes changed
    transition_reason   TEXT,                        -- e.g. "lifecycle: NEW->MATURE (days 30->31)"
    taxonomy_version    TEXT NOT NULL DEFAULT 'v1',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tax_trans_driver ON growth.yego_lima_driver_taxonomy_transition(driver_profile_id);
CREATE INDEX idx_tax_trans_current ON growth.yego_lima_driver_taxonomy_transition(current_date);
```

---

## TASK 7 — EXPLAINABILITY CONTRACT

### Preguntas Obligatorias que la Taxonomía Debe Responder

Cada respuesta se genera desde `taxonomy_explanation` (persisted), **no recalculando**.

| Pregunta | Fuente | Ejemplo de Respuesta |
|----------|--------|---------------------|
| **WHY THIS LIFECYCLE?** | `taxonomy_explanation` WHERE axis='lifecycle' | "Driver is MATURE because first_seen_at = 2025-06-23 (352 days ago), exceeding maturity threshold of 60 days." |
| **WHY THIS ACTIVITY?** | `taxonomy_explanation` WHERE axis='activity' | "Driver is ACTIVE because completed_orders_week = 5 (>0). Note: last_trip_at signal is stale (112d), using weekly orders as proxy." |
| **WHY THIS VALUE?** | `taxonomy_explanation` WHERE axis='value' | "Driver is MEDIUM because avg_orders_4w = 5.0, between p30 (1.0) and p70 (3.0). Percentile: 55th." |
| **WHY THIS MOMENTUM?** | `taxonomy_explanation` WHERE axis='momentum' | "Driver is STABLE because avg_orders_4w (5.0) vs avg_orders_12w (5.0) shows 0% change. Below growth threshold of 20%." |
| **WHY DID I MOVE?** | `taxonomy_transition` WHERE current_date = today | "Persona changed from MATURE_ACTIVE_MEDIUM_STABLE to MATURE_ACTIVE_MEDIUM_DECLINING because momentum changed (STABLE→DECLINING). avg_orders_4w dropped from 5.0 to 2.0 (-60%)." |
| **WHAT CHANGED SINCE YESTERDAY?** | `taxonomy_transition` WHERE current_date = today AND driver_id = X | "Lifecycle unchanged (MATURE). Activity unchanged (ACTIVE). Value unchanged (MEDIUM). Momentum changed: STABLE→DECLINING (declining_flag activated)." |

### Contrato de Explainability

1. **Toda clasificación tiene explicación persistida.** No se recalcula on-the-fly para UI.
2. **Toda explicación incluye matched_rules_json** (qué reglas se cumplieron) y **failed_rules_json** (qué reglas no se cumplieron y por qué).
3. **Toda explicación incluye evidence_json** (valores raw usados para la decisión).
4. **Las transiciones incluyen changed_axes_json** (qué ejes cambiaron y por qué).
5. **El usuario puede entender la clasificación sin conocer las reglas internas.**

---

## TASK 8 — UI CONTRACT

### Diseño Mínimo Futuro (NO implementar)

**Fila de conductor en tabla**:
```
[Driver ID] [Name]  [NEW] [ACTIVE] [MEDIUM] [STABLE]  [Why?]
                    ^lifecycle  ^activity  ^value   ^momentum
```

- 4 badges de colores: Lifecycle (azul), Activity (verde/amarillo/rojo), Value (gris/plata/oro/diamante), Momentum (verde↑/gris→/rojo↓)
- Badge de Persona resumido (ej: "M-A-M-S" tooltip: "MATURE_ACTIVE_MEDIUM_STABLE")
- Botón `Why?` que abre el modal de explicación

**Modal de explicación (al hacer clic en Why?)**:
```
┌─────────────────────────────────────────────────┐
│ Driver: abc123                    Date: 2026-06-10 │
│ Persona: MATURE_ACTIVE_MEDIUM_STABLE   v1          │
├─────────────────────────────────────────────────┤
│ Lifecycle: MATURE                                │
│   First seen: 2025-06-23 (352 days ago)          │
│   Threshold: 60 days for maturity                │
│   ✅ maturity_after_days: 352 >= 60               │
│                                                   │
│ Activity: ACTIVE                                  │
│   Orders this week: 5                             │
│   Last trip: 2026-02-18 (112 days ago) [STALE]   │
│   ✅ weekly_orders_fallback: 5 > 0                │
│   ⚠️ trip_signal_quality: DEGRADED                │
│                                                   │
│ Value: MEDIUM (55th percentile)                   │
│   avg_orders_4w: 5.0                              │
│   p30 threshold: 1.0 ✅ | p70 threshold: 3.0 ✅   │
│   p90 threshold: 6.0 ❌                           │
│                                                   │
│ Momentum: STABLE                                  │
│   Current 4w avg: 5.0 | Baseline 12w avg: 5.0    │
│   Delta: 0.0% (stable range: -20% to +20%)       │
│   ✅ within_stable_range                          │
│                                                   │
│ Anchor Date: 2025-06-23 (HIRE_DATE)               │
├─────────────────────────────────────────────────┤
│ Yesterday: MATURE_ACTIVE_MEDIUM_STABLE (no change)│
│ [Close]                                           │
└─────────────────────────────────────────────────┘
```

### Requisitos de UI

1. Badges visibles en tabla de conductores (4 badges + persona resumido)
2. Modal con explicación completa por eje
3. Transición visible (cambio vs día anterior)
4. Fecha ancla visible
5. Taxonomy version visible (para auditoría)
6. Signal quality flags visibles (⚠️ para señales degradadas)

**NO implementar UI en esta fase.**

---

## TASK 9 — SIMULACIÓN READ-ONLY

### Resultados (2026-06-10, N=18,545)

**Lifecycle**:
| Estado | Drivers | % |
|--------|---------|---|
| MATURE | 17,990 | 97.0% |
| NEW | 555 | 3.0% |
| REACTIVATED | 0 | 0.0% |

**Activity**:
| Estado | Drivers | % |
|--------|---------|---|
| ACTIVE | 18,545 | 100.0% |
| AT_RISK | 0 | 0.0% |
| CHURNED | 0 | 0.0% |

**Value**:
| Estado | Drivers | % |
|--------|---------|---|
| LOW | 9,417 | 50.8% |
| MEDIUM | 5,293 | 28.5% |
| HIGH | 2,211 | 11.9% |
| TOP | 1,624 | 8.8% |

**Momentum**:
| Estado | Drivers | % |
|--------|---------|---|
| STABLE | 17,970 | 96.9% |
| DECLINING | 575 | 3.1% |
| GROWING | 0 | 0.0% |

**Top 10 Personas**:
| Persona | Drivers | % |
|---------|---------|---|
| MATURE_ACTIVE_LOW_STABLE | 9,088 | 49.0% |
| MATURE_ACTIVE_MEDIUM_STABLE | 4,882 | 26.3% |
| MATURE_ACTIVE_HIGH_STABLE | 1,995 | 10.8% |
| MATURE_ACTIVE_TOP_STABLE | 1,472 | 7.9% |
| NEW_ACTIVE_LOW_STABLE | 287 | 1.5% |
| MATURE_ACTIVE_MEDIUM_DECLINING | 225 | 1.2% |
| NEW_ACTIVE_MEDIUM_STABLE | 175 | 0.9% |
| MATURE_ACTIVE_HIGH_DECLINING | 147 | 0.8% |
| MATURE_ACTIVE_TOP_DECLINING | 139 | 0.7% |
| NEW_ACTIVE_HIGH_STABLE | 60 | 0.3% |

### Variables Faltantes / Poco Confiables

| Variable | Calidad | Impacto |
|----------|---------|---------|
| `last_trip_at` | **DEGRADED** — muestra >90d para 57% de drivers incluso con `completed_orders_week > 0` | Impide distinguir ACTIVE de AT_RISK/CHURNED por recencia de viaje |
| `last_supply_at` | **NULL 100%** | No se puede usar como proxy de actividad |
| `supply_hours_week` | **0 para 100%** | No refleja horas reales de suministro |
| `reactivated_flag` | **No poblado** | 0% REACTIVATED en simulación. Requiere pipeline de detección de reactivación |
| `avg_orders_4w` | **CONFIABLE** | Buen proxy para value tier |
| `avg_orders_12w` | **CONFIABLE** | Buen baseline para momentum |
| `declining_flag` | **CONFIABLE** | 575 drivers con señal de declive |
| `completed_orders_week` | **CONFIABLE** | Señal más robusta para actividad actual |
| `first_seen_at` | **CONFIABLE** | 100% poblado, útil para lifecycle |
| `historical_band` | **CONFIABLE** | Buen fallback para value |

### Proxies Usados

| Eje | Señal Ideal | Proxy Actual | Razón |
|-----|------------|-------------|-------|
| Activity | `last_trip_at` (recencia real) | `completed_orders_week > 0` | `last_trip_at` no es confiable |
| Activity | `last_supply_at` | No disponible | 100% NULL |
| Lifecycle | `reactivation_date` | `first_seen_at` vs `reactivation_gap_days` | `reactivated_flag` no poblado |
| Momentum | `avg_orders_4w` vs `avg_orders_12w` delta | Mismo + `declining_flag` | Sin datos de suministro para enriquecer |

### Calidad de Señal

- **ALTA**: Value (avg_orders_4w), Momentum baseline (avg_orders_12w), Lifecycle (first_seen_at)
- **MEDIA**: Activity (completed_orders_week como proxy), Momentum current (depende de avg_orders_4w)
- **BAJA**: Activity (last_trip_at degradado), Activity (last_supply_at NULL), Lifecycle (reactivation no detectable)

---

## TASK 10 — RIESGOS Y DEPRECACIÓN

### Riesgos Identificados

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| `last_trip_at` no confiable (57% de drivers con >90d pero activos) | **HIGH** | Usar `completed_orders_week > 0` como proxy primario. Plan: auditar pipeline de `last_trip_at` en `driver_state_snapshot`. Sin esta señal, AT_RISK y CHURNED no son distinguibles. |
| `last_supply_at` NULL para 100% del universo | **HIGH** | No usar en V1. Plan: investigar pipeline de suministro. Esencial para distinguir "activo sin viajes" de "totalmente inactivo". |
| `reactivated_flag` no poblado | **MEDIUM** | 0 conductores clasificados como REACTIVATED. Plan: implementar detección de reactivación en el pipeline de driver_state. |
| Distribución de ACTIVITY colapsada a 100% ACTIVE | **MEDIUM** | Con los datos actuales, Activity = binary (ACTIVE si cw>0). El eje no aporta poder discriminante hasta que `last_trip_at` se repare. |
| Distribución de MOMENTUM colapsada a 96.9% STABLE | **MEDIUM** | Con el umbral `min_volume_for_momentum = 4`, la mayoría no califica para GROWING/DECLINING. Bajar el umbral podría aumentar falsos positivos (pasar de 1 a 2 viajes = +100% growth). |
| `supply_hours_week` = 0 para todo el universo | **LOW** | No se usa en V1. Requiere investigación de pipeline. |

### Plan de Deprecación (NO ejecutar)

#### Componentes Legacy que quedan obsoletos

| Componente Legacy | Estado Futuro | Razón |
|-------------------|--------------|-------|
| `PROGRAM_CHURN_PREVENTION` (programa independiente) | **DEPRECATE** | La lógica de churn se absorbe en los ejes Activity (AT_RISK) y Momentum (DECLINING). El programa CP desaparece. |
| `PROGRAM_14_90` (programa específico) | **REDEFINE** | Se convierte en consumidor de la taxonomía: filtra por Lifecycle=NEW/REACTIVATED + Value=LOW/MEDIUM + ancla. |
| `PROGRAM_ACTIVE_GROWTH` (catch-all) | **REDEFINE** | Deja de ser catch-all. Se convierte en programa que filtra: Lifecycle=MATURE + Activity=ACTIVE + Value=LOW/MEDIUM + Momentum=DECLINING/STABLE. |
| `PROGRAM_HIGH_VALUE_RECOVERY` | **REDEFINE** | Consume taxonomía: Value=TOP/HIGH + Momentum=DECLINING. |
| `program_eligibility_daily` (hardcoded) | **DEPRECATE** | Reemplazado por `driver_taxonomy_daily`. Las reglas de eligibility migran a reglas de taxonomía. |
| `prioritized_opportunity_daily` (basado solo en programa) | **REDISEÑAR** | La priorización futura usará persona operacional + señales de riesgo, no solo programa code. |
| `opportunity_policy_service.py` (priority engine hardcoded) | **REDISEÑAR** | El motor de prioridad leerá de la taxonomía, no de program_code. |
| `yego_lima_program_registry` (seed estático) | **MANTENER** | Migrar a `segment_registry` (LG-S1.0A). Los programas legacy permanecen con `active=false`. |

#### Cronograma de Deprecación (referencia, no vinculante)

| Fase | Acción |
|------|--------|
| **TAX-1.0A** (AHORA) | Diseño y simulación. No tocar producción. |
| **TAX-1.0B** (FUTURO) | Crear tablas de taxonomía. Build diario de `driver_taxonomy_daily`. |
| **TAX-1.0C** (FUTURO) | Migrar servicios a leer taxonomía. Shadow mode: taxonomía + legacy en paralelo. |
| **TAX-1.0D** (FUTURO) | Cutover: programas leen de taxonomía. Legacy tables marcadas como deprecated. |
| **TAX-1.0E** (FUTURO) | Remover código legacy (solo después de validar GO en producción). |

---

## TASK 11 — DOCUMENTACIÓN FINAL

### GO / NO-GO

### Veredicto: **A) TAXONOMY FOUNDATION READY**

### Evidencia

| Criterio | Resultado | Estado |
|----------|-----------|--------|
| 4 ejes definidos con reglas operacionales | Lifecycle, Activity, Value, Momentum — cada uno con definición, reglas, fallbacks | **PASS** |
| Parámetros 100% configurables | 19 parámetros en `taxonomy_config`, sin hardcode | **PASS** |
| Persistencia diseñada | 3 tablas: daily, explanation, transition | **PASS** |
| Explainability diseñada | 6 preguntas obligatorias respondidas desde persisted data | **PASS** |
| Transición diaria diseñada | `taxonomy_transition` con changed_axes_json | **PASS** |
| Programas futuros consumen taxonomía | Matriz de mapeo persona → programa documentada | **PASS** |
| Simulación read-only ejecutada | 18,545 drivers, 15 personas únicas, 100% coverage | **PASS** |
| No se tocó producción | 0 cambios en queue, export, control_loop, UI, scheduler | **PASS** |
| No se tocaron programas legacy | Solo plan de deprecación, sin ejecución | **PASS** |
| Anchor dates definidas | 7 campos, reglas de anchor_type, resolución de ambigüedades | **PASS** |
| UI contract definido | Badges, modal, transiciones — diseño solamente | **PASS** |
| Señales de calidad documentadas | 4 variables DEGRADED/NULL identificadas con mitigación | **PASS** |

### Limitaciones Conocidas (no bloqueantes)

1. **Activity colapsado a 100% ACTIVE** — requiere reparar `last_trip_at` y `last_supply_at` para que el eje tenga poder discriminante.
2. **0% REACTIVATED** — requiere pipeline de detección de reactivación.
3. **Momentum colapsado a 96.9% STABLE** — umbral `min_volume_for_momentum` debe calibrarse con datos de suministro.
4. **15 personas de 108 posibles** — la baja cardinalidad refleja datos limitados, no diseño incorrecto.

### Prerrequisitos para TAX-1.0B (Implementación)

1. Reparar pipeline de `last_trip_at` en `driver_state_snapshot`
2. Poblar `last_supply_at` desde fuente de suministro
3. Implementar detección de `reactivated_flag`
4. Validar `supply_hours_week` desde fuente canónica
5. Cerrar OMNI-P0 con GO real (Control Foundation)

---

## APPENDIX A — Script de Simulación

`backend/scripts/tax_1_0a_simulation.py` — Read-only. Clasifica 18,545 drivers en 4 ejes + persona. Reproducible.

---

## APPENDIX B — Referencias Cruzadas

| Documento | Relación |
|-----------|----------|
| `LG_S1_0A_DRIVER_SEGMENTATION_CANONICAL_CONFIG_DESIGN.md` | Segmentación excluyente (capa superior). La taxonomía es la capa inferior que alimenta los segmentos. |
| `ai_operating_system.md` | Motor canónico: Control Foundation. LG-TAX-1.0A pertenece a CF → Lima Growth Foundation. |
| `ai_current_phase.md` | OMNI-P0 activo. Diagnostic PAUSED. Diseño compatible. |

---

## APPENDIX C — Glosario

| Término | Definición |
|---------|-----------|
| **Taxonomía** | Clasificación multidimensional diaria del conductor (4 ejes independientes) |
| **Eje** | Dimensión de clasificación: Lifecycle, Activity, Value, Momentum |
| **Persona Operacional** | Combinación de los 4 ejes: `{L}_{A}_{V}_{M}` |
| **Fecha Ancla** | Fecha de referencia para calcular Lifecycle |
| **Segmento** | Categoría excluyente (LG-S1.0A). Un driver pertenece a 1 segmento. |
| **Programa** | Intervención operativa (50/14, 90/300, HVR, etc.). Un driver puede estar en 0-1 programas. |
| **Señal** | Dato observado usado para clasificar (last_trip_at, avg_orders_4w, etc.) |
| **Proxy** | Señal sustituta cuando la señal ideal no está disponible |

---

**LG-TAX-1.0A — FIN DEL DISEÑO**

*No se ha tocado queue, export, control_loop, scheduler, Yango ingestion, programas legacy, ni UI productiva.*
*No se han creado tablas, migraciones, ni seeds.*
*Taxonomía canónica diseñada y simulada sobre data real 2026-06-10.*
*Veredicto: TAXONOMY FOUNDATION READY.*
