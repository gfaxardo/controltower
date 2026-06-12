# LG_LIN_1A_CANONICAL_DATA_CONTRACT — Canonical Data Contract Certification

**Generated:** 2026-06-12T20:30  
**Scope:** Determinar la fuente canónica oficial para Taxonomy, Movement, RNA, Effectiveness  
**Veredicto:** `CANONICAL_CONTRACT_BLOCKED`

---

## 1. INVENTARIO COMPLETO DE TABLAS

### 1.1 TAXONOMY (3 tablas)

| Tabla | Rows Total | Rows/día (06-10) | Rows 06-11/12 | Max Date | Writer | Scheduler | Propósito |
|-------|-----------|-----------------|---------------|----------|--------|-----------|-----------|
| `growth.yego_lima_driver_taxonomy_daily` | 18,545 | 18,545 | **0** | 2026-06-10 | `POST /taxonomy/build` (manual) | **NINGUNO** | V1 Shadow: clasifica drivers por operational_status, segment, value_overlay, momentum |
| `growth.yego_lima_driver_taxonomy_v2_daily` | 273,908 | 68,473 | **0** | 2026-06-10 | **DESCONOCIDO** (sin INSERT en código) | **NINGUNO** | V2 Production: misma clasificación con más granularidad (68K drivers vs 18K) |
| `growth.yego_lima_v2_taxonomy_daily` | 273,908 | 68,473 | **0** | 2026-06-10 | V2 pipeline step 5 (`_build_taxonomy_v2_daily`) | `lima_growth_v2_daily_pipeline` cron 04:45 | V2 Shadow: copia shadow de lifecycle_daily con segment + sub_segment + elite_tier + loyalty_tier |

**Diferencia clave:** 
- V1 (`driver_taxonomy_daily`): 18,545 drivers/día. Se puebla vía API manual.
- V2 (`driver_taxonomy_v2_daily`): 68,473 drivers/día. Sin writer conocido en el código.
- Shadow (`v2_taxonomy_daily`): 68,473 drivers/día. Se puebla desde el V2 pipeline leyendo de `driver_lifecycle_daily`.

### 1.2 MOVEMENT (2 tablas)

| Tabla | Rows Total | Rows 06-10 | Rows 06-11/12 | Max Date | Writer | Scheduler | Propósito |
|-------|-----------|-----------|---------------|----------|--------|-----------|-----------|
| `growth.driver_movement_fact` | 68,473 | 68,473 | **0** | 2026-06-10 | **DESCONOCIDO** (sin INSERT en código) | **NINGUNO** | Producción: transiciones de segmento, lifecycle, programa con movement_score |
| `growth.yego_lima_v2_movement_fact` | **0** | 0 | 0 | NULL | V2 pipeline step 7 (`_build_movement_fact`) | `lima_growth_v2_daily_pipeline` cron 04:45 | V2 Shadow: copia de trazas con target_date + driver_id |

### 1.3 RNA (2 tablas + Yango Loyalty)

| Tabla | Rows | Existe en DB | Writer | Scheduler | Propósito |
|-------|------|-------------|--------|-----------|-----------|
| `growth.rna_priority_fact` | N/A | **NO EXISTE** | Migración 217 la crea, pero no se ejecutó en prod | `POST /rna-priority/build` (manual) | Priorización de RNA drivers con scoring |
| `growth.rna_pilot_measurement_fact` | N/A | **NO EXISTE** | Migración 218 la crea, pero no se ejecutó en prod | — | Medición de conversión de pilotos RNA |
| `ops.mv_driver_lifecycle_monthly_kpis` | ~9 cities × months | SÍ | External ingestion (read-only MV) | N/A | KPIs mensuales de AD, activaciones, etc. por ciudad |
| `ops.yango_loyalty_kpi_manual` | ~9 cities × 8 KPIs | SÍ | Manual via API | N/A | KPIs manuales de Yango Loyalty |
| `ops.yango_loyalty_targets` | Variable | SÍ | Manual via API | N/A | Targets mensuales por KPI y ciudad |

### 1.4 EFFECTIVENESS (3 tablas)

| Tabla | Rows Total | Rows 06-10 | Rows 06-11/12 | Max Date | Writer | Scheduler | Propósito |
|-------|-----------|-----------|---------------|----------|--------|-----------|-----------|
| `growth.program_effectiveness_fact` | **10** | 10 | **0** | 2026-06-10 | V2 pipeline step 9 (`_build_effectiveness_facts`) | `lima_growth_v2_daily_pipeline` cron 04:45 | Producción: efectividad agregada por programa |
| `growth.driver_program_effectiveness_fact` | 68,473 | 68,473 | **0** | 2026-06-10 | V2 pipeline step 9 | `lima_growth_v2_daily_pipeline` cron 04:45 | Producción: efectividad por driver + programa |
| `growth.yego_lima_v2_effectiveness_fact` | **0** | 0 | 0 | NULL | V2 pipeline step 9 | `lima_growth_v2_daily_pipeline` cron 04:45 | V2 Shadow: copia de effectiveness |

---

## 2. CLASIFICACIÓN POR TABLA

### 2.1 TAXONOMY

| Tabla | Clasificación | Razón |
|-------|--------------|-------|
| `yego_lima_driver_taxonomy_daily` | **LEGACY** | V1 shadow. Solo 18K drivers. Sin scheduler. UI1A la consume pero es obsoleta. |
| `yego_lima_driver_taxonomy_v2_daily` | **CANONICAL** | V2 production. 68K drivers. Sin writer conocido (poblada por script externo). Es la fuente más completa. |
| `yego_lima_v2_taxonomy_daily` | **SHADOW** | Copia generada por V2 pipeline leyendo de `driver_lifecycle_daily`. Tiene los mismos 68K rows que la canónica. Sin consumidor en UI1A. |

### 2.2 MOVEMENT

| Tabla | Clasificación | Razón |
|-------|--------------|-------|
| `driver_movement_fact` | **CANONICAL** | Única fuente con datos reales (68K rows). Sin writer conocido (script externo). UI1A la consume vía stats/matrix. |
| `yego_lima_v2_movement_fact` | **ORPHAN** | 0 rows. NUNCA se ha poblado. V2 pipeline step 7 la escribe pero las fuentes no tienen datos frescos. Winners/losers la leen y fallan con 500. |

### 2.3 RNA

| Tabla | Clasificación | Razón |
|-------|--------------|-------|
| `rna_priority_fact` | **BLOCKED** | Migración existe (217) pero la tabla NO fue creada en producción. Sin tabla → endpoint 500. |
| `rna_pilot_measurement_fact` | **BLOCKED** | Migración existe (218) pero la tabla NO fue creada en producción. Sin tabla → endpoint 500. |
| `ops.mv_driver_lifecycle_monthly_kpis` | **LEGACY** (RNA context) | Pertenece al dominio Yango Loyalty (KPIs mensuales), no a Lima Growth RNA. |
| `ops.yango_loyalty_kpi_manual` | **WRONG_DOMAIN** | KPIs manuales de Yango Loyalty. UI1A RNA los consume por error. |

### 2.4 EFFECTIVENESS

| Tabla | Clasificación | Razón |
|-------|--------------|-------|
| `program_effectiveness_fact` | **CANONICAL** | Única fuente con datos (aunque solo 10 rows). UI1A la consume. |
| `driver_program_effectiveness_fact` | **CANONICAL** | 68K rows. Contiene datos por driver. UI1A la consume para métricas agregadas. |
| `yego_lima_v2_effectiveness_fact` | **ORPHAN** | 0 rows. NUNCA se ha poblado. Sin consumidor en UI1A. |

---

## 3. ¿QUIÉN PUEBLA LAS TABLAS CANÓNICAS?

### Taxonomy Canónica: `yego_lima_driver_taxonomy_v2_daily`

| Atributo | Valor |
|----------|-------|
| **Propósito** | Clasificación operacional V2 de drivers: operational_status, operational_segment, value_overlay, momentum_state, persona |
| **Granularidad** | driver_id × snapshot_date |
| **Writer** | **SIN INSERT EN CÓDIGO PYTHON.** Posiblemente poblada por script SQL externo o migración no rastreada. |
| **Scheduler** | **NINGUNO.** No hay job automático. |
| **Último dato** | 2026-06-10 (68,473 rows) |
| **Consumer UI1A** | **NINGUNO.** UI1A lee `yego_lima_driver_taxonomy_daily` (V1 legacy), no esta tabla. |

**Problema estructural:** La tabla canónica (V2) existe con datos pero nadie la escribe automáticamente y la UI no la consume.

### Movement Canónica: `driver_movement_fact`

| Atributo | Valor |
|----------|-------|
| **Propósito** | Registro de transiciones de drivers entre segmentos, lifecycle states, y programas, con movement_score |
| **Granularidad** | driver_id × movement_date × movement_class |
| **Writer** | **SIN INSERT EN CÓDIGO PYTHON.** Posiblemente poblada por script SQL externo. |
| **Scheduler** | **NINGUNO.** No hay job automático. |
| **Último dato** | 2026-06-10 (68,473 rows) |
| **Consumer UI1A** | Movement stats + matrix (vía `movement-analytics/stats` y `/matrix`) |

### Effectiveness Canónica: `program_effectiveness_fact` + `driver_program_effectiveness_fact`

| Atributo | `program_effectiveness_fact` | `driver_program_effectiveness_fact` |
|----------|------------------------------|-------------------------------------|
| **Propósito** | Métricas agregadas por programa | Métricas por driver + programa |
| **Writer** | V2 pipeline step 9 | V2 pipeline step 9 |
| **Scheduler** | `lima_growth_v2_daily_pipeline` cron 04:45 | `lima_growth_v2_daily_pipeline` cron 04:45 |
| **Último dato** | 2026-06-10 (10 rows) | 2026-06-10 (68,473 rows) |
| **Consumer UI1A** | Effectiveness tab | Effectiveness tab (métricas agregadas) |

---

## 4. CONTRATO CANÓNICO POR DOMINIO

### 4.1 TAXONOMY

```
DOMAIN: Taxonomy
├─ CANONICAL TABLE: growth.yego_lima_driver_taxonomy_v2_daily (68K drivers/día)
├─ WRITER:          ❌ DESCONOCIDO (sin INSERT en código)
├─ SCHEDULER:       ❌ NINGUNO
├─ UI CONSUMER:     ❌ NINGUNO (UI1A consume tabla legacy V1)
│
├─ LEGACY TABLE:    growth.yego_lima_driver_taxonomy_daily (18K drivers/día)
│   └─ WRITER:      POST /taxonomy/build (manual)
│   └─ CONSUMER:    UI1A Segments tab ✅ (pero consume tabla equivocada)
│
└─ SHADOW TABLE:    growth.yego_lima_v2_taxonomy_daily
    └─ WRITER:      V2 pipeline step 5 (cron 04:45)
    └─ CONSUMER:    NINGUNO
```

**BREAK:** La tabla canónica (V2, 68K) no tiene writer ni consumer. La UI consume una tabla legacy (V1, 18K) que tiene la mitad de drivers y tampoco tiene scheduler.

### 4.2 MOVEMENT

```
DOMAIN: Movement
├─ CANONICAL TABLE: growth.driver_movement_fact (68K rows, max 06-10)
├─ WRITER:          ❌ DESCONOCIDO (sin INSERT en código)
├─ SCHEDULER:       ❌ NINGUNO
├─ UI CONSUMER:     ✅ Movement stats + matrix (UI1A)
│
├─ LEGACY TABLE:    growth.yego_lima_program_decision_trace
│   └─ WRITER:      autonomous_tick (cada 5 min)
│   └─ CONSUMER:    Movement summary endpoint
│
├─ LEGACY TABLE:    growth.yego_lima_state_transition_trace
│   └─ WRITER:      autonomous_tick (cada 5 min)
│   └─ CONSUMER:    Movement summary endpoint
│
└─ ORPHAN TABLE:    growth.yego_lima_v2_movement_fact (0 rows)
    └─ WRITER:      V2 pipeline step 7 (nunca exitoso)
    └─ CONSUMER:    Movement winners/losers (500)
```

**BREAK:** La tabla canónica (`driver_movement_fact`) funciona para stats/matrix (tiene 68K rows) pero su writer es desconocido. La tabla shadow (`v2_movement_fact`) para winners/losers está vacía.

### 4.3 RNA

```
DOMAIN: RNA
├─ CANONICAL TABLE: growth.rna_priority_fact
├─ EXISTE EN DB:    ❌ NO (migración 217 no ejecutada en prod)
├─ WRITER:          POST /rna-priority/build (manual, sin tabla destino)
├─ SCHEDULER:       ❌ NINGUNO
├─ UI CONSUMER:     ✅ RNA tab priority section (500 porque tabla no existe)
│
├─ BLOCKED TABLE:   growth.rna_pilot_measurement_fact
│   └─ EXISTE:      ❌ NO (migración 218 no ejecutada en prod)
│
└─ WRONG DOMAIN:    ops.yango_loyalty_* (KPIs mensuales Yango Loyalty)
    └─ CONSUMER:    UI1A RNA tab (consume endpoint equivocado)
```

**BREAK:** Las tablas canónicas de RNA NO EXISTEN en producción. Las migraciones que las crean (217, 218) nunca se ejecutaron contra la DB de prod. La UI consume datos de Yango Loyalty (otro dominio) como workaround roto.

### 4.4 EFFECTIVENESS

```
DOMAIN: Effectiveness
├─ CANONICAL TABLE: growth.program_effectiveness_fact (10 rows)
├─ WRITER:          V2 pipeline step 9
├─ SCHEDULER:       ❌ lima_growth_v2_daily_pipeline cron 04:45 (NO CORRIÓ 06-11/12)
├─ UI CONSUMER:     ✅ Effectiveness tab (500 por falta de datos)
│
├─ CANONICAL TABLE: growth.driver_program_effectiveness_fact (68K rows)
├─ WRITER:          V2 pipeline step 9
├─ SCHEDULER:       ❌ lima_growth_v2_daily_pipeline cron 04:45 (NO CORRIÓ 06-11/12)
├─ UI CONSUMER:     ✅ Effectiveness tab (métricas agregadas)
│
└─ ORPHAN TABLE:    growth.yego_lima_v2_effectiveness_fact (0 rows)
    └─ WRITER:      V2 pipeline step 9 (nunca exitoso para esta tabla)
    └─ CONSUMER:    NINGUNO
```

**BREAK:** Las tablas canónicas tienen scheduler (V2 pipeline 04:45) pero el scheduler no corrió para 06-11/12. `program_effectiveness_fact` tiene solo 10 rows — insuficiente para que el endpoint no falle.

---

## 5. PLAN KEEP / MIGRATE / DEPRECATE

### KEEP (mantener como está)

| Tabla | Razón |
|-------|-------|
| `yego_lima_driver_taxonomy_v2_daily` | Es la tabla canónica con 68K drivers. Tiene los datos correctos. |
| `driver_movement_fact` | Única fuente canónica de movement con datos reales. |
| `program_effectiveness_fact` | Tabla canónica de effectiveness agregada. |
| `driver_program_effectiveness_fact` | Tabla canónica de effectiveness por driver. |

### MIGRATE (cambiar consumer a tabla correcta)

| Desde | Hacia | Razón |
|-------|-------|-------|
| UI1A Segments ← `yego_lima_driver_taxonomy_daily` (V1, 18K) | UI1A Segments ← `yego_lima_driver_taxonomy_v2_daily` (V2, 68K) | V2 tiene 3.8x más drivers. Payload keys diferentes (`operational_status` vs `lifecycle`). |
| UI1A RNA ← `yango-loyalty/summary` (KPIs mensuales) | UI1A RNA ← `rna-priority/summary` (RNA real) | La UI consume el dominio equivocado. |
| Movement winners/losers ← `yego_lima_v2_movement_fact` (0 rows) | Movement winners/losers ← `driver_movement_fact` (68K rows) | La tabla shadow está vacía, la canónica tiene datos. |

### DEPRECATE (marcar como obsoleto/eliminar)

| Tabla | Razón |
|-------|-------|
| `yego_lima_driver_taxonomy_daily` | V1 shadow. Solo 18K drivers. Sin scheduler. Reemplazada por V2. |
| `yego_lima_v2_movement_fact` | 0 rows. Nunca poblada. Sin consumidor viable. |
| `yego_lima_v2_effectiveness_fact` | 0 rows. Nunca poblada. Sin consumidor. |
| `yego_lima_v2_taxonomy_daily` | V2 shadow sin consumidor UI1A. Redundante con `driver_taxonomy_v2_daily`. |
| `yego_lima_v2_lifecycle_daily` | V2 shadow sin consumidor UI1A. Redundante con `driver_lifecycle_daily`. |

### CREATE (crear lo que falta)

| Tabla | Razón |
|-------|-------|
| `growth.rna_priority_fact` | **EJECUTAR MIGRACIÓN 217 en prod.** La tabla no existe. |
| `growth.rna_pilot_measurement_fact` | **EJECUTAR MIGRACIÓN 218 en prod.** La tabla no existe. |

### ADD TO SCHEDULER (agregar al scheduler automático)

| Builder | Tabla destino | Ubicación en autonomous_tick |
|---------|--------------|------------------------------|
| `build_lifecycle_daily()` | `yego_lima_driver_lifecycle_daily` | Agregar al cascade (después de driver_state) |
| `build_driver_taxonomy()` (V2 mode) | `yego_lima_driver_taxonomy_v2_daily` | Agregar al cascade (después de lifecycle) |
| `_build_movement_fact()` (usando `driver_movement_fact`, no V2 shadow) | `driver_movement_fact` | Agregar al cascade (después de taxonomy) |
| `build_rna_priority()` | `rna_priority_fact` | Agregar al cascade (después de movement) |
| `_build_effectiveness_facts()` | `program_effectiveness_fact` + `driver_program_effectiveness_fact` | Ya existe en V2 pipeline pero debe correr después del cascade |

---

## 6. ESTADO ACTUAL DEL CONTRATO

```
CANONICAL_CONTRACT_BLOCKED
```

**Razones del bloqueo:**

1. **RNA:** Las tablas canónicas (`rna_priority_fact`, `rna_pilot_measurement_fact`) no existen en producción. Migraciones 217 y 218 pendientes de ejecutar.

2. **Taxonomy:** La UI consume la tabla equivocada (V1 legacy de 18K en vez de V2 canónica de 68K). La canónica no tiene writer conocido en el código Python.

3. **Movement:** La tabla canónica (`driver_movement_fact`) funciona pero su writer es externo/desconocido. El scheduler no la regenera.

4. **Effectiveness:** Las tablas canónicas tienen scheduler (V2 pipeline) pero el scheduler no ha corrido para las fechas 06-11/12. `program_effectiveness_fact` tiene solo 10 rows — efectivamente vacía.

5. **V2 Shadow Pipeline:** 7 de 9 tablas V2 shadow no son consumidas por UI1A. Recursos desperdiciados produciendo datos huérfanos.

---

## 7. RESUMEN GRÁFICO DEL CONTRATO

```
DOMAIN       CANONICAL TABLE                    WRITER              SCHEDULER    UI CONSUMER
──────       ────────────────                    ──────              ─────────    ───────────
Taxonomy     driver_taxonomy_v2_daily           ❌ DESCONOCIDO       ❌ NINGUNO    ❌ NINGUNO
Movement     driver_movement_fact               ❌ DESCONOCIDO       ❌ NINGUNO    ✅ stats/matrix
RNA          rna_priority_fact                  ❌ TABLA NO EXISTE   ❌ NINGUNO    ❌ 500
Effectiven.  program_effectiveness_fact         ✅ V2 pipeline       ❌ NO CORRIÓ  ❌ 500 (10 rows)
             driver_program_effectiveness_fact  ✅ V2 pipeline       ❌ NO CORRIÓ  ✅ (68K staled)
```

**4 de 4 dominios tienen el contrato canónico roto.** Ninguno cumple con: tabla existe → writer automático → scheduler activo → UI consume correctamente.
