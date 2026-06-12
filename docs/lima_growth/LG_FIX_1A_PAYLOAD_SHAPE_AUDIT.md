# LG_FIX_1A_PAYLOAD_SHAPE_AUDIT — Payload Shape Audit

**Generated:** 2026-06-12T19:36  
**Scope:** Validar si los endpoints devuelven datos pero la UI lee el shape incorrecto.

---

## Tab 1: FreshnessBanner — SHAPE OK

| Prop esperada | Key real en payload | Match |
|---------------|-------------------|-------|
| `health.system_status` | `health.system_status` | YES |
| `health.stale_assets` | `health.stale_assets` | YES |
| `health.components_healthy` | `health.components_healthy` | YES |
| `health.components_degraded` | `health.components_degraded` | YES |
| `health.components_critical` | `health.components_critical` | YES |
| `health.scheduler_status` | `health.scheduler_status` | YES |

**Veredicto:** Shape OK. Banner muestra CRITICAL real.

---

## Tab 2: Overview — **MISMATCH**

| Prop esperada | Key real en payload | Match |
|---------------|-------------------|-------|
| `overview.universe_total` | `result.universe_total` | YES |
| `overview.drivers_with_program` | **NO EXISTE** | **MISMATCH** |
| `overview.drivers_without_program` | **NO EXISTE** | **MISMATCH** |
| `overview.active_programs` | **NO EXISTE** | **MISMATCH** |
| `overview.queue_ready` | `result.queue_ready` | YES |
| `overview.queue_held` | `result.queue_held` | YES |
| `overview.program_distribution` | `result.by_program` (diferente nombre) | **MISMATCH** |
| `overview.channel_utilization` | **NO EXISTE** | **MISMATCH** |

**Fallbacks usados por OverviewTab:**
```js
const totalDrivers = driverState?.total_drivers ?? overview?.universe_total ?? truth?.total_drivers ?? 0
// ✅ Toma driverState.total_drivers = 148167 → correcto

const driversWithProgram = overview?.drivers_with_program ?? truth?.drivers_with_program ?? 0
// ❌ overview no tiene drivers_with_program → cae a truth.drivers_with_program
// ❌ truth es array de KPIs → truth.drivers_with_program = undefined → 0
// RESULTADO: 0 (equivocado)

const activePrograms = overview?.active_programs ?? truth?.active_programs?.length ?? 0
// ❌ overview no tiene active_programs → truth.active_programs = undefined → 0
// RESULTADO: 0 (equivocado. Real: 4)
```

**Veredicto:** PAYLOAD_MISMATCH. Los campos `drivers_with_program` y `active_programs` no existen en el payload. Los fallbacks tampoco funcionan porque operational-truth tiene estructura de array de KPIs, no objetos planos.

---

## Tab 3: Programs — **MISMATCH**

| Prop esperada (por programa) | Key real en payload | Match |
|------------------------------|-------------------|-------|
| `program.program_code` | `program.program_code` | YES |
| `program.eligible_drivers` | **NO EXISTE** | **MISMATCH** |
| `program.drivers` (fallback) | **NO EXISTE** | **MISMATCH** |
| `program.count` (fallback) | `program.total` (nombre != count) | **MISMATCH** |
| `program.prioritized` | **NO EXISTE** | **MISMATCH** |
| `program.prioritized_count` (fallback) | **NO EXISTE** | **MISMATCH** |
| `program.queue_count` | `program.queued_total` (nombre != queue_count) | **MISMATCH** |
| `program.queued` (fallback) | **NO EXISTE** | **MISMATCH** |
| `program.priority` | **NO EXISTE** | **MISMATCH** |

**Payload real por programa:**
```json
{
  "program_code": "PROGRAM_ACTIVE_GROWTH",
  "total": 17685,                  // ← UI espera eligible_drivers
  "eligible_total": 17685,         // ← Key correcta pero no mapeada
  "prioritized_total": 1125,       // ← Key correcta pero no mapeada
  "queued_total": 3,               // ← Key correcta pero no mapeada
  "actionable_today": 0,
  "exported_total": 0,
  ...
}
```

**Código del fallback que falla:**
```js
const eligible = program.eligible_drivers ?? program.drivers ?? program.count ?? 0
// program.eligible_drivers = undefined
// program.drivers = undefined
// program.count = undefined  (existe program.total pero no program.count!)
// RESULTADO: 0 (equivocado)

const prioritized = program.prioritized ?? program.prioritized_count ?? 0
// program.prioritized = undefined
// program.prioritized_count = undefined
// RESULTADO: 0 (equivocado)

const queueCount = program.queue_count ?? program.queued ?? 0
// program.queue_count = undefined
// program.queued = undefined
// RESULTADO: 0 (equivocado. Real: 3, 32, 15, 2)
```

**Veredicto:** PAYLOAD_MISMATCH. La UI espera nombres de campo diferentes a los que el backend devuelve. Los fallbacks no cubren los nombres reales (`eligible_total`, `prioritized_total`, `queued_total`).

---

## Tab 4: Segments — **MISMATCH**

| Prop esperada | Key real en payload | Match |
|---------------|-------------------|-------|
| `taxonomy.lifecycle_distribution` | **NO EXISTE** | **MISMATCH** |
| `taxonomy.distribution` (fallback) | **NO EXISTE** | **MISMATCH** |
| `taxonomy.segments` | **NO EXISTE** | **MISMATCH** |
| `taxonomy.value_tiers` | **NO EXISTE** | **MISMATCH** |
| `taxonomy.momentum` | **NO EXISTE** | **MISMATCH** |

**Payload real:**
```json
{
  "snapshot_date": "2026-06-11",
  "total_drivers": 0,
  "taxonomy_version": "v2",
  "distributions": {           // ← KEY REAL: distributions (plural)
    "operational_status": [],  // ← SUB-KEY: operational_status
    "operational_segment": [], // ← SUB-KEY: operational_segment
    "value_overlay": [],       // ← SUB-KEY: value_overlay
    "momentum": []             // ← SUB-KEY: momentum
  },
  "top_personas": [],
  "signal_quality_warnings": false
}
```

**Código del fallback que falla:**
```js
const lifecycleDistribution = taxonomy?.lifecycle_distribution || taxonomy?.distribution || []
// taxonomy.lifecycle_distribution = undefined
// taxonomy.distribution = undefined
// RESULTADO: [] (equivocado)
```

**Veredicto:** DOBLE MISMATCH: (1) Payload shape: la key real es `distributions` (no `lifecycle_distribution`/`distribution`), y dentro hay sub-keys por capa (`operational_status`, `operational_segment`, etc.), no arrays planos. (2) Data: `total_drivers: 0` porque no hay datos para 2026-06-11.

---

## Tab 5: Movement — **MIXED (OK parcial + MISMATCH + TIMEOUT)**

| Prop esperada | Key real | Match | Nota |
|---------------|----------|-------|------|
| `summary.entries` | `result.entries` | YES | Pero valor = 0 |
| `summary.exits` | `result.exits` | YES | Pero valor = 0 |
| `stats.positive_transitions` | `result.positive_transitions` | YES | Valor = 421 ✓ |
| `stats.negative_transitions` | `result.negative_transitions` | YES | Valor = 54 ✓ |
| `stats.total_transitions` | `result.total_transitions` | YES | Valor = 68473 ✓ |
| `stats.net_movement` | `result.net_movement` | YES | Valor = 3565 ✓ |
| `stats.movement_classes` | `result.movement_classes` | YES | Data OK |
| `records.records` | N/A (404) | N/A | Endpoint inexistente |

**Shape OK para movement-analytics/stats y matrix.** Pero movement/summary devuelve ceros (date mismatch) y movement/records es 404.

---

## Tab 6: RNA — **MISMATCH (WRONG DOMAIN)**

| Prop esperada | Key real en loyalty/summary | Match |
|---------------|---------------------------|-------|
| `loyalty.total_rna` | **NO EXISTE** | **MISMATCH** |
| `loyalty.rna_total` (fallback) | **NO EXISTE** | **MISMATCH** |
| `loyalty.rna_new` | **NO EXISTE** | **MISMATCH** |
| `loyalty.rna_reactivable` | **NO EXISTE** | **MISMATCH** |
| `loyalty.with_phone` | **NO EXISTE** | **MISMATCH** |
| `loyalty.cancelled_signals` | **NO EXISTE** | **MISMATCH** |

**Payload real de `/yango-loyalty/summary`:**
```json
{
  "month": "2026-06",
  "day_of_month": 12,
  "total_days": 30,
  "cities": ["arequipa", "barranquilla", ...],
  "kpis": [ /* KPIs mensuales de AD, Supply Hours, Calls, UFC, etc. */ ],
  "city_categories": { /* Bronze/Silver/Gold per city */ },
  "rules": { /* Scoring rules */ }
}
```

**Este endpoint NO es de RNA — es el dashboard de Yango Loyalty (KPIs mensuales por ciudad).** El RNA Tab está consumiendo un endpoint del dominio equivocado.

El endpoint correcto para RNA sería `/yego-lima-growth/rna-priority/summary`, pero este devuelve **500** porque la tabla `rna_priority_fact` no existe en la DB.

**Veredicto:** WRONG_ENDPOINT + ENDPOINT_FAILING. La UI lee datos de Yango Loyalty (otro dominio) esperando campos de RNA que no existen. El endpoint real de RNA (rna-priority/summary) está caído (500).

---

## Tab 7: Driver Explorer — **SHAPE OK (con fallbacks amplios)**

| Prop esperada | Key real | Match |
|---------------|----------|-------|
| `driverData.drivers` | `result.drivers` | YES |
| `driverData.data` (fallback) | — | — |
| `driverData.records` (fallback) | — | — |
| `driverData.total` | `result.total` | YES |
| Per driver: `d.driver_id` | `d.driver_id` | YES |

**Veredicto:** Shape OK. Funciona cuando el usuario filtra.

---

## Tab 8: Effectiveness — **500, NO SHAPE**

El endpoint `/yego-lima-growth/effectiveness/summary` retorna **500 Internal Server Error**. No hay payload que auditar.

---

## Resumen de Mismatches

| Tab | Mismatch Type | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| FreshnessBanner | OK | — | Sin mismatch |
| Overview | PAYLOAD_MISMATCH | HIGH | `drivers_with_program`, `active_programs`, `program_distribution` no existen. Fallbacks rotos. |
| Programs | PAYLOAD_MISMATCH | HIGH | `eligible_drivers` → debería ser `eligible_total`. `prioritized` → `prioritized_total`. `queue_count` → `queued_total`. |
| Segments | PAYLOAD_MISMATCH | HIGH | `lifecycle_distribution` → debería ser `distributions.operational_segment`. |
| Movement | MIXED | MEDIUM | Stats/Matrix OK. Summary 0s (date). Records 404. Winners/Losers 500. |
| RNA | WRONG_ENDPOINT | CRITICAL | Lee de `/yango-loyalty/summary` (KPIs mensuales) esperando campos RNA. Endpoint real (rna-priority) caído. |
| Driver Explorer | OK | LOW | Shape correcto. |
| Effectiveness | 500 | CRITICAL | No hay payload que auditar. |
