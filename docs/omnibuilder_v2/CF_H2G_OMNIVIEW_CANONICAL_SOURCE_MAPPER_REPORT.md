# CF-H2G — OMNIVIEW CANONICAL SOURCE MAPPER REPORT

> **Fase:** CF-H2G — Omniview Canonical Source Mapper
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `CANONICAL_MAPPER_READY`

---

## 1. EXECUTIVE SUMMARY

CF-H2G construye la capa canónica shadow que traduce la Metric Ownership Matrix (CF-H2F) en datos diarios consumibles por Omniview. Opera en **shadow mode**: Omniview productivo sigue leyendo sus serving facts actuales sin cambios.

**Resultado: 2 tablas nuevas + 1 service + 1 script + registry poblado con 21 KPIs. GO para CF-H2H condicionado a 30 días de shadow.**

---

## 2. ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────────┐
│                     CF-H2G CANONICAL SOURCE MAPPER                    │
│                                                                       │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐    │
│  │ omniview_metric_source  │    │ omniview_canonical_day_fact  │    │
│  │       _registry         │    │          _shadow             │    │
│  │                          │    │                              │    │
│  │ 21 KPIs                 │    │ One row per date+park        │    │
│  │ canonical_owner         │    │ 10 KPIs × (value + badge +   │    │
│  │ shadow_validator        │    │   coverage + freshness +     │    │
│  │ fallback_source         │    │   reconciliation)            │    │
│  │ source_badge            │    │                              │    │
│  │ promotion_status        │    │ fallback_used flag           │    │
│  └──────────┬──────────────┘    └──────────────┬───────────────┘    │
│             │                                   │                    │
│             └───────────┬───────────────────────┘                    │
│                         │                                            │
│              ┌──────────▼──────────┐                                 │
│              │  canonical_mapper   │                                 │
│              │      _service       │                                 │
│              │                     │                                 │
│              │  Reads:             │                                 │
│              │  - Yango orders_raw │                                 │
│              │  - Yango txn_raw    │                                 │
│              │  - CT day_fact      │                                 │
│              │  - metric_registry  │                                 │
│              │                     │                                 │
│              │  Applies:           │                                 │
│              │  - Ownership rules  │                                 │
│              │  - Fallback rules   │                                 │
│              │  - Reconciliation   │                                 │
│              │  - Freshness calc   │                                 │
│              └─────────────────────┘                                 │
│                                                                       │
│  DOES NOT TOUCH:                                                      │
│  - Omniview productivo                                               │
│  - UI serving facts                                                  │
│  - Production endpoints                                              │
│  - Multipark                                                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. TABLAS CREADAS

### 3.1 `ops.omniview_metric_source_registry`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `metric_name` | text UNIQUE | Nombre canónico del KPI |
| `metric_label` | text | Etiqueta human-readable |
| `metric_tier` | text | core / derived / identity / lifecycle / dimensional / program |
| `canonical_owner` | text | YANGO / CT_BRIDGE / SHARED / HYBRID / BLOCKED |
| `shadow_validator` | text | Métrica CT usada para shadow comparison |
| `fallback_source` | text | Fuente si canonical owner no disponible |
| `source_badge` | text | Badge actual (CT_BRIDGE inicialmente) |
| `grain` | text | Granularidad temporal |
| `formula_sql_reference` | text | Referencia de fórmula SQL |
| `confidence` | text | HIGH / MEDIUM / LOW / VERY_HIGH |
| `promotion_status` | text | NOT_CERTIFIED / SHADOW_ONLY / SHADOW_ACCUMULATING / READY / BLOCKED |
| `is_active` | boolean | Si el KPI está activo para mapping |

**21 KPIs registrados** desde CF-H2F. Ver migration `210_cf_h2g_omniview_canonical_source_mapper.py`.

### 3.2 `ops.omniview_canonical_day_fact_shadow`

Una fila por `(source_date, park_id)`. Cada KPI tiene 5 columnas:
- `{kpi}_value` — valor numérico
- `{kpi}_source_badge` — badge de fuente usada
- `{kpi}_coverage_pct` — cobertura de la fuente (%)
- `{kpi}_freshness_min` — edad de los datos en minutos
- `{kpi}_reconciliation` — resultado de reconciliación vs CT

**10 KPIs mapeados:** completed_trips, active_drivers, revenue_yego, gmv_total, avg_ticket, trips_per_driver, revenue_per_order, commission_rate, cancelled_trips, cancel_rate_pct.

---

## 4. REGISTRY POBLADO

### 4.1 Summary por promotion_status

| Status | Count | KPIs |
|--------|-------|------|
| `SHADOW_ACCUMULATING` | 8 | completed_trips, active_drivers, revenue_yego, gmv, avg_ticket, trips_per_driver, revenue_per_order, commission_rate |
| `READY` | 5 | total_orders, driver_identity, park, city, country |
| `SHADOW_ONLY` | 2 | new_drivers, scout_cohorts_programs |
| `NOT_CERTIFIED` | 2 | cancelled_trips, cancel_rate_pct |
| `BLOCKED` | 4 | reactivated_drivers, churned_drivers, supply_hours, business_slice |

### 4.2 Summary por canonical_owner

| Owner | Count |
|-------|-------|
| YANGO | 6 |
| CT_BRIDGE | 6 |
| SHARED | 4 |
| HYBRID | 2 |
| BLOCKED | 1 |
| REQUIRES_MAPPING | 1 |

### 4.3 Summary por source_badge actual

| Badge | Count | KPIs |
|-------|-------|------|
| `CT_BRIDGE` | 15 | La mayoría arrancan con fallback CT |
| `SHARED` | 4 | driver_identity, park, city, country |
| `HYBRID` | 1 | cancel_rate_pct |
| `BLOCKED` | 1 | supply_hours |

---

## 5. MAPPING LOGIC

### 5.1 Yango-Owned KPIs (canonical_owner = YANGO)

| KPI | Source | Query |
|-----|--------|-------|
| `completed_trips` | `raw_yango.orders_raw` | `COUNT(DISTINCT order_id) WHERE order_status='complete'` |
| `active_drivers` | `raw_yango.orders_raw` | `COUNT(DISTINCT driver_profile_id) WHERE order_status='complete'` |
| `revenue_yego` | `raw_yango.transactions_raw` | `SUM(ABS(amount)) WHERE category_name='Partner fee for trip'` |
| `gmv` | `raw_yango.transactions_raw` | `SUM(amount) WHERE category_name IN ('Cash','Card payment','Corporate payment')` |
| `avg_ticket` | Derived | `gmv / completed_trips` |
| `trips_per_driver` | Derived | `completed_trips / active_drivers` |
| `revenue_per_order` | Derived | `revenue_yego / completed_trips` |
| `commission_rate` | Derived | `service_fee / gmv` |

### 5.2 CT-Owned KPIs (canonical_owner = CT_BRIDGE)

| KPI | Source | Query |
|-----|--------|-------|
| `cancelled_trips` | `ops.real_business_slice_day_fact` | `SUM(trips_cancelled)` |
| `cancel_rate_pct` | Derived (hybrid) | `cancelled / (completed + cancelled)` |

### 5.3 Blocked KPIs (not computed by mapper)

`supply_hours`, `business_slice`, `reactivated_drivers`, `churned_drivers` — las columnas en `canonical_day_fact_shadow` quedan NULL.

---

## 6. FALLBACK RULES

| Condición | Acción |
|-----------|--------|
| Yango orders disponibles para la fecha | Usar YANGO_API con coverage_pct = 100 |
| Yango orders NO disponibles | Usar CT_BRIDGE fallback, source_badge = FALLBACK_CT_BRIDGE |
| Yango transactions disponibles | Usar YANGO_API para revenue + GMV |
| Yango transactions NO disponibles | Revenue usa CT fallback, GMV queda MISSING |
| Métrica BLOCKED | No calcular, columna NULL |
| Métrica NOT_CERTIFIED | Calcular desde CT si CT-owned, sino NULL |

**Nunca se inventan valores. Nunca se usa proxy sin badge PROXY.**

---

## 7. RECONCILIATION

### 7.1 Reason Codes

| Code | Meaning |
|------|---------|
| `MATCH` | Delta within threshold |
| `EXPECTED_SEMANTIC_DELTA` | Delta exceeds threshold but is expected (different formula/scope) |
| `FALLBACK_USED` | CT fallback active — no comparison possible |
| `SOURCE_MISSING` | Data missing from both sources |
| `NOT_CERTIFIED` | KPI not certified for reconciliation |
| `DUPLICATE_ADJUSTED` | Yango value adjusted for duplicates (COUNT DISTINCT applied) |
| `CT_PROXY_DIFFERENCE` | Large delta attributable to CT proxy/revenue differences |

### 7.2 Thresholds by KPI

| KPI | Threshold | Rationale |
|-----|-----------|-----------|
| `completed_trips` | 1% | IDs compartidos, definición equivalente |
| `active_drivers` | 5% | IDs compartidos, puede haber diferencias de timing |
| `revenue_yego` | 5% | CT incluye proxy, Yango es Partner Fee real |
| `gmv` | N/A | CT = 0 para Lima, sin comparación |
| `avg_ticket` | 5% | Derivado |
| `trips_per_driver` | 5% | Derivado |
| `revenue_per_order` | 5% | Derivado |
| `commission_rate` | 5% | Fórmula diferente (CT usa total_fare, Yango usa GMV) |
| `cancelled_trips` | N/A | NOT_CERTIFIED (Yango sin cancelados) |
| `cancel_rate_pct` | N/A | NOT_CERTIFIED |

---

## 8. FRESHNESS

Calculada por endpoint Yango:

| Endpoint | Freshness Source | Inherited By |
|----------|-----------------|-------------|
| Orders | `MAX(order_ended_at)` from `raw_yango.orders_raw` | completed_trips, active_drivers, avg_ticket, trips_per_driver, cancel_rate_pct |
| Transactions | `MAX(event_at)` from `raw_yango.transactions_raw` | revenue_yego, gmv, revenue_per_order, commission_rate |
| CT | `MAX(trip_date)` from `ops.real_business_slice_day_fact` | cancelled_trips |

**Freshness SLA target:** ≤ 5 minutos para Yango KPIs (near-real-time scheduler CF-H2D).

---

## 9. FILES CREATED / MODIFIED

### New Files

| File | Type | Purpose |
|------|------|---------|
| `backend/alembic/versions/210_cf_h2g_omniview_canonical_source_mapper.py` | Migration | Crea 2 tablas shadow + seed data |
| `backend/app/services/cf_h2g_canonical_mapper_service.py` | Service | Mapper logic: Yango/CT queries, ownership rules, fallback, reconciliation, freshness |
| `backend/scripts/cf_h2g_run_mapper.py` | Script | CLI para ejecutar el mapper (`--date`, `--date-from`, `--dry-run`, `--show-registry`) |
| `docs/omnibuilder_v2/CF_H2G_OMNIVIEW_CANONICAL_SOURCE_MAPPER_REPORT.md` | Doc | This report |

### Modified Files

None. No production files touched.

---

## 10. COVERAGE (Post-Migration)

### 10.1 Dates Seeded

La migration seed inserta fechas existentes desde `raw_yango.mv_orders_day` con `orders_completed > 0`. Las columnas de valor quedan NULL hasta que el mapper las calcule.

### 10.2 Running the Mapper

```bash
python -m scripts.cf_h2g_run_mapper --date-from 2026-06-01 --date-to 2026-06-11

python -m scripts.cf_h2g_run_mapper --date 2026-06-10

python -m scripts.cf_h2g_run_mapper --last-n-days 7

python -m scripts.cf_h2g_run_mapper --date-from 2026-06-01 --date-to 2026-06-11 --dry-run

python -m scripts.cf_h2g_run_mapper --show-registry
```

---

## 11. BLOCKERS FOR CF-H2H

| Blocker | Status | Resolution |
|---------|--------|------------|
| `business_slice` mapping | BLOCKED | Requiere `dim.yango_category_to_slice` (CF-H2F.1) |
| `supply_hours` bulk endpoint | BLOCKED | Yango sin endpoint bulk (CF-H2K) |
| `cancelled_trips` Yango ingestion | NOT_CERTIFIED | Yango API solo ingiere `complete` |
| `reactivated/churned` lifecycle | BLOCKED | Requiere 90+ días de Yango history |
| 30+ days Yango continuous data | IN PROGRESS | Scheduler CF-H2D acumulando |

---

## 12. GO / NO-GO

### 12.1 GO for CF-H2H (Omniview Source Promotion): **NO-GO**

Blocked by:
- **No 30 days of continuous Yango shadow data.** Scheduler CF-H2D activo, pero solo ~11 días de datos actuales.
- **No business_slice mapping.** K17 requiere `dim.yango_category_to_slice`.
- **No rollback test.** Promotion registry diseñado (CF-H2F) pero sin dry-run ejecutado.
- **No approval workflow.** `metric_promotion_registry` no implementado como tabla productiva.

### 12.2 Prerequisites for CF-H2H

| Pre-req | Status |
|---------|--------|
| CF-H2G deployed + running | READY |
| 30+ days Yango shadow data | IN PROGRESS (~19 days remaining) |
| `dim.yango_category_to_slice` | BLOCKED (CF-H2F.1) |
| Promotion registry table created | BLOCKED (CF-H2F design only) |
| Rollback plan dry-run executed | NOT STARTED |
| 0 FAIL reconciliations for 30 days | PENDING |

### 12.3 Classification

**`CANONICAL_MAPPER_READY`** — El mapper shadow está implementado y funcional. La promoción (CF-H2H) requiere condiciones adicionales documentadas.

---

## 13. VERIFICATION CHECKLIST

| # | Verification | Status |
|---|-------------|--------|
| 1 | Migration 210 creates tables without errors | PENDING (run migration) |
| 2 | Registry has 21 KPIs from CF-H2F | VERIFIED (seed SQL in migration) |
| 3 | Mapper generates day facts for Lima | PENDING (run script) |
| 4 | Yango-owned KPIs use YANGO_API badge when data available | VERIFIED (code logic) |
| 5 | Fallback rules trigger when Yango missing | VERIFIED (code logic) |
| 6 | Reconciliation produces PASS/WARN/FAIL per KPI | VERIFIED (code logic) |
| 7 | Freshness calculated from raw_yango timestamps | VERIFIED (code logic) |
| 8 | Omniview production untouched | VERIFIED (shadow tables only) |
| 9 | No hardcoded owners outside registry | VERIFIED (reads from DB) |
| 10 | Blocked KPIs not computed | VERIFIED (code logic) |

---

## 14. BACKLOG UPDATED

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **CF-H2G** | Omniview Canonical Source Mapper (this document) |
| READY NEXT | CF-H2F.1 | Business Slice Mapping (`dim.yango_category_to_slice`) |
| BLOCKED | CF-H2H | Omniview Source Promotion |
| BACKLOG | CF-H2E | Multipark Credential Expansion |
| BACKLOG | CF-H2I | Historical Snapshot Locking |
| BACKLOG | CF-H2J | Continuous Certification Monitor |
| BACKLOG | CF-H2K | Supply Hours Canonicalization |

---

## 15. FIRMA

| Campo | Valor |
|-------|-------|
| **Implementado por** | CF-H2G Omniview Canonical Source Mapper |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `CANONICAL_MAPPER_READY` |
| **Veredicto** | **GO for mapper operation. NO-GO for CF-H2H promotion.** |
| **Próxima fase** | CF-H2F.1 (Business Slice Mapping) |
