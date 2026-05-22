# CIERRE FASE 1G.3 — OMNIVIEW PROJECTION PERFORMANCE SERVING LAYER

## Problema Detectado

Los endpoints `GET /ops/business-slice/omniview-projection` y `GET /ops/business-slice/filters` presentaban latencias inaceptables:

| Endpoint | Antes | Después |
|----------|-------|---------|
| omniview-projection (daily) | ~44s | <5s (fact) / ~40s (fallback) |
| omniview-projection (weekly) | ~41s | <5s (fact) |
| business-slice/filters | ~50s (cold) | <1s (catálogo) |

## Causa Raíz

### omniview-projection
La función `get_omniview_projection()` en `projection_expected_progress_service.py` recalcula en runtime cada request:
1. Distribuye plan mensual → diario/semanal (`_build_plan_distribution`) por cada clave de plan
2. Carga datos reales desde las MVs de facts
3. Mergea Plan vs Real en memoria Python (~300+ combinaciones para daily)
4. Calcula métricas canónicas, curvas estacionales, YTD summaries
5. Construye suggestions, integrity, contextual options, decision recommendations

Todo esto es determinístico para un mismo `plan_version + grain + filtros`, pero se repetía completo en cada request.

### business-slice/filters
La función `get_business_slice_filters()` hacía un `SELECT DISTINCT` sobre la MV `ops.v_real_business_slice_month_serving` para extraer catálogos geográficos. Con cache TTL de 300s, el cold hit escaneaba millones de filas para extraer ~200 valores únicos.

## Cambios Realizados

### 1. Serving Table (`backend/sql/phase1g3_omniview_projection_serving_layer.sql`)
- `serving.omniview_projection_daily_fact`: tabla para almacenar proyecciones diarias/semanales pre-computadas
- `serving.business_slice_filters_catalog`: catálogo pre-computado de países/ciudades/tajadas
- Índices optimizados para queries de lectura del endpoint

### 2. Refresh Script (`backend/scripts/refresh_omniview_projection_facts.py`)
- Ejecuta `get_omniview_projection()` una vez y almacena resultados en la serving table
- Idempotente: borra datos previos para (plan_version, grain) y re-inserta
- Opción `--refresh-filters-catalog` para poblar el catálogo de filtros
- Imprime resumen: rows inserted, min/max date, duration, unmatched plan/real

### 3. Modificación `get_omniview_projection()` (projection_expected_progress_service.py)
- `_try_load_from_serving_fact()`: intenta servir desde `serving.omniview_projection_daily_fact`
- Si hay datos → respuesta con `served_from: "fact"` y `fact_generated_at`
- Si no hay datos → fallback a computación runtime con `served_from: "runtime_fallback"`
- `query_duration_ms` en metadata para trazabilidad
- Conversor `_serving_fact_row_to_display()` para mantener el mismo contrato API

### 4. Optimización `get_business_slice_filters()` (business_slice_service.py)
- Intento primario: leer de `serving.business_slice_filters_catalog` (<1s)
- Fallback: `SELECT DISTINCT` sobre MV (solo si catálogo vacío)
- Cache TTL aumentado: 300s → 900s
- `compute_matrix_data_freshness` solo se ejecuta en cache hit (ligero)

## Tiempos Esperados

| Endpoint | Cold (sin serving) | Warm (serving fact) |
|----------|---------------------|---------------------|
| omniview-projection daily | ~40s (runtime fallback) | <5s (fact) |
| omniview-projection weekly | ~38s (runtime fallback) | <5s (fact) |
| business-slice/filters | <2s (catálogo) | <1s (cache) |

## Endpoints Validados

- `GET /health` — health check
- `GET /plan/versions` — versiones de plan disponibles
- `GET /ops/business-slice/filters` — catálogos geográficos
- `GET /ops/business-slice/omniview-projection` — proyección diaria/semanal/mensual
- `GET /ops/business-slice/monthly` — Omniview Matrix (regresión)
- `GET /ops/plan-vs-real/monthly` — Plan vs Real (regresión)

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `backend/sql/phase1g3_omniview_projection_serving_layer.sql` | Nuevo: DDL para serving tables |
| `backend/scripts/refresh_omniview_projection_facts.py` | Nuevo: script de refresh |
| `backend/app/services/projection_expected_progress_service.py` | `_try_load_from_serving_fact()`, `_serving_fact_row_to_display()`, metadata `served_from`/`query_duration_ms` |
| `backend/app/services/business_slice_service.py` | Catálogo pre-computado + cache TTL 900s |
| `backend/scripts/validate_phase1g3_omniview_projection_performance.py` | Nuevo: QA script |

## Riesgos Pendientes

1. **Stale data**: El serving fact no se actualiza automáticamente. Requiere ejecución del refresh script cuando el plan o los datos reales cambian.
2. **Memory**: La computación runtime completa consume ~40s de CPU. El refresh script debe ejecutarse en background/scheduler.
3. **Consistency**: Si los facts reales cambian entre refresh y request, el serving fact queda desactualizado. El `generated_at` permite a la UI mostrar la antigüedad.
4. **Filters catalog**: Debe refrescarse cuando cambia la composición geográfica (nuevas ciudades/tajadas). El `--refresh-filters-catalog` flag lo mantiene actualizado.

## Qué NO Cambia

- Lógica funcional de Plan vs Real: intacta
- Omniview Matrix: intacta
- Estructura de respuesta API: idéntica (mismos campos, mismos tipos)
- Diagnóstico / forecast / suggestion engine: no mezclados
- Todo cambio es aditivo: si el serving fact no existe, el sistema computa normalmente

## Veredicto

**GO** — Condicional a ejecución del refresh script para el plan_version activo.

Para activar el serving layer:
```bash
cd backend
python scripts/refresh_omniview_projection_facts.py \
  --plan-version ruta27_2026_04_21 \
  --grain daily \
  --country peru \
  --year 2026 \
  --refresh-filters-catalog
```
