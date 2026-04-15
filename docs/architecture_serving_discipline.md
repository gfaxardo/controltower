# Serving Discipline — YEGO Control Tower

## Principio rector

> **Serving reads from fact/MV/cache first. Detailed resolved/raw sources are forbidden for normal serving when an equivalent serving layer exists.**

## Capas del sistema

### 1. Source (Build / Ingest)
- `public.trips_all`, `public.trips_unified`
- `ops.v_real_trips_enriched_base`
- `ops.v_real_trips_business_slice_resolved`
- Raw ingest tables (`bi.*`, `staging.*`)

**Uso permitido**: scripts de ETL, backfill, refresh de MVs/facts, reconciliación manual, auditoría de integridad.
**Uso prohibido**: endpoints de serving normal, dashboards operativos, vistas UI.

### 2. Serving (Facts / MVs / Caches)
- `ops.real_business_slice_month_fact` — mensual × tajada
- `ops.real_business_slice_week_fact` — semanal × tajada
- `ops.real_business_slice_day_fact` — diario × tajada
- `ops.real_business_slice_hour_fact` — horario × tajada
- `ops.mv_real_lob_month_v2` — mensual × LOB
- `ops.mv_real_lob_week_v2` — semanal × LOB
- `ops.mv_real_lob_day_v2` — diario × LOB
- `ops.mv_real_lob_hour_v2` — horario × LOB
- `ops.real_drill_dim_fact` — drill multidimensional
- `ops.real_rollup_day_fact` — rollup diario
- `ops.mv_real_monthly_canonical_hist` — canónico histórico
- `ops.mv_supply_*`, `ops.mv_driver_*` — supply/driver lifecycle

**Uso obligatorio**: todo endpoint de serving normal, dashboards operativos, vistas UI.

### 3. Drill excepcional
- Endpoints explícitamente marcados como drill (`/drill/`, `/audit/`, `/reconciliation/`)
- Pueden leer de resolved/enriched **solo con `query_mode=drill`**
- Deben declarar source_type y no ser la ruta por defecto

## Reglas

### R1: Fact-first para serving
Todo endpoint que muestra datos agregados (mensual, semanal, diario) DEBE leer de la fact/MV correspondiente.
No se permite recalcular agregaciones desde viajes individuales en runtime.

### R2: No silent fallback
Si la fact/MV está vacía, stale o incompleta:
- El endpoint devuelve un diagnóstico (source_status = empty/stale/degraded)
- NO recalcula silenciosamente desde la fuente cruda
- El log registra el intento de fallback

### R3: Source traceability
Todo servicio crítico declara en `SERVING_REGISTRY`:
- `preferred_source`: la fact/MV esperada
- `source_type`: fact / mv / cache / view / resolved / raw
- `query_mode`: serving / drill / audit / rebuild
- `forbidden_sources`: vistas/tablas que NO debe usar para serving

### R4: Freshness awareness
El serving layer expone metadata de frescura:
- `last_refresh_at` cuando está disponible
- `freshness_status`: ok / stale / unknown
- Criterio de stale por tipo de fact

### R5: Drill separado
- Endpoints tipo `/drill/`, `/audit/`, `/reconciliation/` pueden usar resolved/raw
- Endpoints tipo `/monthly`, `/weekly`, `/daily`, `/overview`, `/summary` NO pueden
- Si un endpoint necesita ambos modos, usar parámetro `query_mode`

## Freshness y refresh

### Cadenas de refresh

**Cadena hourly-first** (diario, post-ingesta):
```
v_trips_real_canon_120d → v_real_trip_fact_v2 → mv_real_lob_hour_v2
  → mv_real_lob_day_v2
  → mv_real_lob_week_v3
  → mv_real_lob_month_v3
  → real_drill_dim_fact (via populate_real_drill_from_hourly_chain)
```
Trigger: `POST /ops/pipeline-refresh` o `python -m scripts.run_pipeline_refresh_and_audit`

**Cadena business slice** (incremental):
```
v_real_trips_enriched_base → fn_real_trips_business_slice_resolved_subset
  → real_business_slice_month_fact (mensual incremental)
  → real_business_slice_day_fact (diario incremental)
  → real_business_slice_week_fact (rollup desde day_fact)
  → real_business_slice_hour_fact (bajo demanda)
```
Trigger: `POST /ops/business-slice/backfill` o `python -m scripts.refresh_business_slice_mvs`

**Cadena supply** (semanal):
```
mv_driver_weekly_stats + dim.v_geo_park → refresh_supply_alerting_mvs()
  → mv_driver_segments_weekly
  → mv_supply_segments_weekly
  → mv_supply_segment_anomalies_weekly
  → mv_supply_alerts_weekly
```
Trigger: `POST /ops/supply/refresh` o `python -m scripts.run_supply_refresh_pipeline`

**Cadena driver lifecycle** (semanal):
```
public.trips_unified + public.drivers → refresh_driver_lifecycle_mvs()
  → mv_driver_lifecycle_base
  → mv_driver_weekly_stats / mv_driver_monthly_stats
  → mv_driver_lifecycle_weekly_kpis / mv_driver_lifecycle_monthly_kpis
```
Trigger: `python -m scripts.run_driver_lifecycle_build`

### Tabla de freshness por fact/MV

| Fact/MV | Source upstream | Script/Endpoint refresh | Frecuencia esperada | Criterio stale |
|---------|---------------|------------------------|---------------------|----------------|
| `real_business_slice_month_fact` | `v_real_trips_business_slice_resolved` | `refresh_business_slice_mvs.py` / `POST /ops/business-slice/backfill` | Diario o por demanda | >48h sin refresh |
| `real_business_slice_week_fact` | rollup desde `day_fact` | idem | Diario | >48h |
| `real_business_slice_day_fact` | `v_real_trips_business_slice_resolved` | idem | Diario | >24h |
| `real_business_slice_hour_fact` | `v_real_trips_business_slice_resolved` | idem | Por demanda | >24h |
| `mv_real_lob_hour_v2` | `v_real_trip_fact_v2` | `refresh_hourly_first_chain.py` / `POST /ops/pipeline-refresh` | Diario | >24h |
| `mv_real_lob_day_v2` | `mv_real_lob_hour_v2` | idem (encadenado) | Diario | >24h |
| `mv_real_lob_week_v3` | `mv_real_lob_hour_v2` | idem (encadenado) | Diario | >48h |
| `mv_real_lob_month_v3` | `mv_real_lob_hour_v2` | idem (encadenado) | Diario | >48h |
| `mv_real_lob_month_v2` | legacy `v_real_trips_with_lob_v2` | `refresh_real_lob_mvs_v2.py` | Diario | >48h |
| `mv_real_lob_week_v2` | idem | idem | Diario | >48h |
| `real_drill_dim_fact` | `mv_real_lob_day/week/month` | `run_pipeline_refresh_and_audit.py` | Diario (pipeline) | >48h |
| `mv_real_monthly_canonical_hist` | `v_trips_real_canon` | `refresh_real_monthly_canonical_hist.py` | Tras cargas grandes | >72h |
| `mv_supply_*` | `refresh_supply_alerting_mvs()` | `POST /ops/supply/refresh` / pipeline | Semanal | >7d |
| `mv_driver_lifecycle_*` | `refresh_driver_lifecycle_mvs()` | `run_driver_lifecycle_build.py` / pipeline | Semanal | >7d |
| `mv_driver_segments_weekly` | `refresh_supply_alerting_mvs()` | pipeline | Semanal | >7d |

## Inventario serving vs build

| Feature | Endpoint | Service | Preferred serving source | Current source | Fallback detected | Risk | Action |
|---------|----------|---------|--------------------------|----------------|-------------------|------|--------|
| Omniview monthly | `GET /ops/business-slice/monthly` | `business_slice_service` | `month_fact` | `month_fact` | No | LOW | OK |
| Omniview weekly | `GET /ops/business-slice/weekly` | `business_slice_service` | `week_fact` | `week_fact` | No | LOW | OK |
| Omniview daily | `GET /ops/business-slice/daily` | `business_slice_service` | `day_fact` | `day_fact` | No | LOW | OK |
| Omniview rollups | `GET /ops/business-slice/omniview` | `business_slice_omniview_service` | facts | **`V_RESOLVED`** (rollups) | Yes (silent) | **HIGH** | Fix: compute rollups from facts |
| Omniview coverage | `GET /ops/business-slice/coverage` | `business_slice_service` | facts/summary | **`V_RESOLVED`** (2 queries) | Yes | **HIGH** | Accept for now (coverage needs trip-level); document |
| Control Loop PvR | `GET /ops/control-loop/plan-vs-real` | `control_loop_plan_vs_real_service` | `month_fact` | `month_fact` | No | LOW | OK (fixed in Fase 1) |
| Real LOB monthly | `GET /ops/real-lob/monthly-v2` | `real_lob_service_v2` | `mv_real_lob_month_v2` | `mv_real_lob_month_v2` | No | LOW | OK |
| Real LOB weekly | `GET /ops/real-lob/weekly-v2` | `real_lob_service_v2` | `mv_real_lob_week_v2` | `mv_real_lob_week_v2` | No | LOW | OK |
| Real operational | `GET /ops/real-operational/*` | `real_operational_service` | `mv_real_lob_day/hour_v2` | `mv_real_lob_day/hour_v2` | No | LOW | OK |
| Real daily | `GET /ops/real-lob/daily/*` | `real_lob_daily_service` | `real_rollup_day_fact` | `real_rollup_day_fact` | No | LOW | OK |
| Real drill | `GET /ops/real-lob/drill*` | `real_lob_drill_pro_service` | `real_drill_dim_fact` | `real_drill_dim_fact` | No | LOW | OK (drill) |
| Real margin quality | `GET /ops/real-margin-quality` | `real_margin_quality_service` | `v_real_trip_fact_v2` | `v_real_trip_fact_v2` | No | MEDIUM | Accepted: audit/quality needs trip-level |
| Revenue quality | `GET /ops/revenue-quality/*` | `revenue_quality_service` | MVs + fact | Mix: `v_real_trip_fact_v2` + MVs | Partial | MEDIUM | Accepted: quality check needs trip-level |
| Territory quality | `GET /ops/territory-quality/*` | `territory_quality_service` | aggregates | `public.trips_all` | Yes (raw) | **HIGH** | Document; needs dedicated summary MV |
| Matrix integrity | `GET /ops/business-slice/matrix-operational-trust` | `omniview_matrix_integrity_service` | facts | facts | No | LOW | OK |
| Supply dynamics | `GET /ops/supply/*` | `supply_service` | `mv_supply_*` | `mv_supply_*` | No | LOW | OK |
| Driver lifecycle | `GET /ops/driver-lifecycle/*` | `driver_lifecycle_service` | `mv_driver_*` | `mv_driver_*` | No | LOW | OK |
| Plan vs Real (legacy) | `GET /ops/plan-vs-real/monthly` | `plan_vs_real_service` | views | `v_plan_vs_real_realkey_*` | No | LOW | OK (joins, not trip scan) |

## Antipatrones prohibidos

1. **FROM `v_real_trips_business_slice_resolved`** en endpoint serving normal
2. **FROM `v_real_trips_enriched_base`** en endpoint serving normal
3. **FROM `public.trips_all`** o `public.trips_unified` en endpoint serving normal
4. **Silent fallback** a resolved cuando fact está vacía
5. **Recalcular** agregaciones en Python cuando MV SQL existe
6. **Scan completo** sin filtros en fuentes detalladas
7. **Joins pesados** por request sobre fuentes de viajes

## Contrato de drill excepcional

### Clasificación de endpoints por modo

| Modo | Descripción | Source permitido | Ejemplos |
|------|-------------|------------------|----------|
| **serving** | Dashboard operativo, overview, series | Solo fact/MV/cache | `/ops/business-slice/monthly`, `/ops/real-lob/monthly-v2`, `/ops/control-loop/plan-vs-real` |
| **drill** | Exploración profunda, desglose detallado | Fact/MV preferido; resolved si necesario para granularidad viaje | `/ops/real-lob/drill*`, `/ops/real-drill/*` |
| **audit** | Calidad de datos, integridad, reconciliación | Fact + resolved para comparación cruzada | `/ops/real-margin-quality`, `/ops/business-slice/matrix-operational-trust` |
| **rebuild** | Backfill, refresh, recomputo | Resolved/raw/enriched permitido | `POST /ops/business-slice/backfill`, `POST /ops/pipeline-refresh` |

### Reglas por modo

1. **serving**: NUNCA leer de `v_real_trips_business_slice_resolved`, `v_real_trips_enriched_base`, `public.trips_all`, `public.trips_unified`. Si la fact está vacía/stale, devolver diagnóstico, no fallback.

2. **drill**: Preferir facts. Si necesita grano viaje (ej. lista de viajes no mapeados), puede usar resolved con:
   - LIMIT obligatorio
   - Filtros de tiempo obligatorios
   - Log del fallback

3. **audit**: Puede comparar facts vs resolved para detectar inconsistencias. Las queries de reconciliación son aceptables.

4. **rebuild**: Sin restricciones de fuente. Operaciones batch offline.

### Endpoints explícitos por categoría

**Serving normal** (fact-only):
- `GET /ops/business-slice/monthly` → `month_fact`
- `GET /ops/business-slice/weekly` → `week_fact`
- `GET /ops/business-slice/daily` → `day_fact`
- `GET /ops/business-slice/omniview` → facts (monthly/weekly/daily según granularity)
- `GET /ops/business-slice/filters` → `month_fact`
- `GET /ops/control-loop/plan-vs-real` → `month_fact`
- `GET /ops/real-lob/monthly-v2` → `mv_real_lob_month_v2`
- `GET /ops/real-lob/weekly-v2` → `mv_real_lob_week_v2`
- `GET /ops/real-operational/*` → `mv_real_lob_day/hour_v2`
- `GET /ops/real-lob/daily/*` → `real_rollup_day_fact`
- `GET /ops/supply/*` → `mv_supply_*`
- `GET /ops/driver-lifecycle/*` → `mv_driver_*`

**Drill** (fact-preferred, resolved-allowed):
- `GET /ops/real-lob/drill*` → `real_drill_dim_fact`
- `GET /ops/real-drill/*` → `real_drill_dim_fact` / `mv_real_rollup_day`
- `GET /ops/business-slice/unmatched` → `v_business_slice_unmatched_trips` (trip-level by design)
- `GET /ops/business-slice/conflicts` → `v_business_slice_conflict_trips` (trip-level by design)

**Audit** (fact + resolved for cross-check):
- `GET /ops/business-slice/matrix-operational-trust` → facts + trust history
- `GET /ops/real-margin-quality` → `v_real_trip_fact_v2` (quality audit)
- `GET /ops/revenue-quality/*` → mix facts + trip-level (quality)
- `GET /ops/integrity-report` → meta tables

**Rebuild** (batch, offline):
- `POST /ops/business-slice/backfill` → writes to facts from resolved
- `POST /ops/pipeline-refresh` → full refresh chain
- `POST /ops/supply/refresh` → supply MVs
- `POST /ops/real-drill/refresh` → drill MV

## Enforcement (FASE 2.5)

El enforcement duro se implementa a través de:

1. **`serving_guardrails.py`**: `ServingPolicy`, `assert_serving_source()`, `trace_source_usage()`
2. **`SERVING_REGISTRY`** en `source_trace.py`: 18 features con `endpoint_classification` codificada
3. **`FORBIDDEN_SERVING_SOURCES`**: lista central de fuentes prohibidas
4. **Policies en servicios**: cada servicio crítico declara `_SERVING_POLICY`
5. **Diagnostics endpoint**: `GET /ops/diagnostics/serving-sources` con `compliance_status`
6. **Script de validación**: `scripts/check_serving_enforcement.py`
7. **Bloqueo hard**: `ServingSourceViolation` exception en strict_mode

## Hard Enforcement Gate (FASE 2.6)

Extiende FASE 2.5 con enforcement que no se puede evadir:

1. **`execute_serving_query()`** en `serving_guardrails.py`: wrapper central que intercepta toda query serving.
   - Valida que la feature esté en `SERVING_REGISTRY` (`assert_feature_registered`)
   - Valida que la fuente no sea prohibida (`assert_serving_source`)
   - Traza uso automáticamente (`trace_source_usage`)
   - Si `require_preferred_source_match=True`, loguea WARNING al usar fuente distinta

2. **Policy Registry**: `register_policy()` / `get_declared_policy()` / `is_policy_declared()`
   - Cada servicio llama `register_policy(_SERVING_POLICY)` al import
   - Diagnostics verifica si la policy fue declarada

3. **5 servicios migrados al wrapper**:
   - `business_slice_omniview_service.py`: `_fetch_fact_slice_rows`, `_fetch_fact_rollup_by_country`, `_fetch_monthly_fact_rows`
   - `control_loop_plan_vs_real_service.py`: `_load_real_from_fact`
   - `real_lob_service.py`: `get_real_lob_monthly`, `get_real_lob_weekly`
   - `real_lob_service_v2.py`: `get_real_lob_monthly_v2`, `get_real_lob_weekly_v2`
   - `real_lob_v2_data_service.py`: `get_real_lob_v2_data`

4. **Strict source match** en Omniview Matrix y Control Loop (`require_preferred_source_match=True`)

5. **Unguarded path detection**: `get_unguarded_features()` detecta features registradas como serving que no tienen trace runtime

6. **Diagnostics enriquecidos**: cada feature ahora reporta `policy_declared`, `guarded_query_path_used`, `preferred_source_match`, `runtime_gate_status`

7. **Script**: `scripts/check_serving_hard_enforcement.py` — validación estática y gate-test

## DB Layer Gate + Connection-Level Enforcement (FASE 2.7)

Cierra el gap final: impide que queries de serving se ejecuten fuera del sistema de guardrails.

### QueryExecutionContext

Dataclass que acompaña toda ejecución DB-gated:

```python
@dataclass
class QueryExecutionContext:
    feature_name: str
    query_mode: QueryMode
    expected_source: str
    source_type: SourceType
    strict_mode: bool = True
    allow_fallback: bool = False
    request_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
```

Se construye con `context_from_policy(policy, source_name=...)`.

### DB_SERVING_GUARD_MODE

Configurable vía variable de entorno `DB_SERVING_GUARD_MODE`:
- `off`: sin enforcement DB-level
- `warn` (default): valida pero solo loguea warnings
- `strict`: valida y bloquea violaciones

### execute_db_gated_query()

Wrapper DB-level que envuelve `execute_serving_query()`:
1. Setea `_active_db_gate` ContextVar con el QueryExecutionContext
2. Aplica enforcement según `DB_SERVING_GUARD_MODE`
3. Registra en `_DB_GATE_LOG` separado del usage_log
4. Limpia ContextVar al finalizar

### Query mode-aware enforcement

- `SERVING` + `strict`: enforcement completo, violaciones bloquean
- `SERVING` + `warn`: enforcement con logging solo
- `DRILL` / `AUDIT` / `REBUILD`: trace sin bloqueo

### Detección de ejecución sin contexto

- `is_db_gate_active()`: True si hay gate activo en el thread/async context
- `assert_db_gate_active(hint)`: valida que haya gate; en strict lanza excepción
- `get_db_gate_log()` / `get_db_gate_summary()`: diagnostics del gate log

### Cómo ejecutar queries en una feature serving nueva

```python
from app.services.serving_guardrails import (
    ServingPolicy, QueryMode, SourceType,
    context_from_policy, execute_db_gated_query, register_policy,
)

_POLICY = ServingPolicy(
    feature_name="Mi Feature",
    query_mode=QueryMode.SERVING,
    preferred_source="ops.mi_fact_table",
    preferred_source_type=SourceType.FACT,
    strict_mode=True,
)
register_policy(_POLICY)

def mi_query(conn, params):
    ctx = context_from_policy(_POLICY, source_name="ops.mi_fact_table")
    return execute_db_gated_query(
        ctx, _POLICY, conn, sql, params,
        source_name="ops.mi_fact_table", source_type="fact",
    )
```

### Qué pasa si se ejecuta sin contexto

Si un servicio hace `cur.execute(...)` directo (sin pasar por `execute_db_gated_query`), el ContextVar `_active_db_gate` no estará seteado. `is_db_gate_active()` retorna False, y `assert_db_gate_active()` loguea warning (modo warn) o lanza excepción (modo strict).

### Diferencia service-level vs DB-level gate

| Aspecto | Service-level (2.6) | DB-level (2.7) |
|---------|---------------------|----------------|
| Wrapper | `execute_serving_query()` | `execute_db_gated_query()` |
| Contexto | Solo policy + source_name | `QueryExecutionContext` completo |
| Tracking | Usage log | Usage log + DB gate log |
| ContextVar | No | `_active_db_gate` |
| Modo configurable | No (strict per policy) | `DB_SERVING_GUARD_MODE` (off/warn/strict) |
| Detección sin contexto | No | `is_db_gate_active()` / `assert_db_gate_active()` |

### 5 servicios migrados al DB gate

Todos usan `context_from_policy(_SERVING_POLICY, ...)` + `execute_db_gated_query(...)`:
- `business_slice_omniview_service.py` (4 call sites)
- `control_loop_plan_vs_real_service.py` (1 call site)
- `real_lob_service.py` (2 call sites)
- `real_lob_service_v2.py` (2 call sites)
- `real_lob_v2_data_service.py` (1 call site)

### Diagnostics DB-gate (por feature)

Cada feature en el endpoint `/ops/diagnostics/serving-sources` ahora incluye:
- `db_gate_enabled`: True si la feature tiene entradas en DB gate log
- `db_guard_mode`: modo global actual
- `query_context_present`: True si hay ejecuciones con QueryExecutionContext
- `db_gate_status`: READY / WARN_ONLY / DEGRADED / UNKNOWN
- `ungated_db_path_detected`: True si la feature es serving sin DB gate

### Script de validación

`scripts/check_db_layer_gate.py` verifica:
1. Imports de servicios críticos
2. `DB_SERVING_GUARD_MODE` es válido
3. Policies declaradas para los 5 servicios
4. `QueryExecutionContext` se crea correctamente
5. Detección de ejecución sin gate
6. Forbidden source sigue bloqueándose
7. Estructura del DB gate summary

## Deudas pendientes

| Deuda | Descripción | Prioridad |
|-------|-------------|-----------|
| Territory quality MV | `territory_quality_service` lee `public.trips_all`; necesita MV/summary dedicada | Media |
| Coverage summary MV | `get_business_slice_coverage` lee `V_RESOLVED` para conteos por status; necesita summary materializado | Media |
| Omniview rollups from facts | Rollups por país y totales calculados desde facts en vez de `V_RESOLVED` | **Alta** (implementada en esta fase) |
