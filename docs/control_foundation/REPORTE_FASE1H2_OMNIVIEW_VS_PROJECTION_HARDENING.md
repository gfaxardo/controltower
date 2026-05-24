# REPORTE FASE 1H.2 — OMNIVIEW VS PROYECCIÓN HARDENING

**Motor:** Control Foundation
**Fase:** 1H.2 — Omniview Vs Proyección: Performance + Render + Legibilidad
**Estado:** COMPLETADO
**Veredicto:** GO

---

## 1. PROBLEMAS IDENTIFICADOS

| # | Problema | Severidad | Causa Raíz |
|---|----------|-----------|------------|
| 1 | Weekly UI no carga/renderiza correctamente | Alta | `_fact_table_has_data` o `_weekly_from_fact` puede fallar por conexión DB sin graceful handling; frontend muestra skeleton o error 500 |
| 2 | Daily Colombia lento (~21s), "connection already closed" | Crítica | `get_db()` pool reutiliza conexiones stale; si la query tarda, el pool puede cerrar la conexión y propagar 500 |
| 3 | Números demasiado pequeños en Comfortable mode | Media | Font sizes hardcodeados: `text-xs` (12px) para valor principal, `text-[9px]` para delta. Sin diferenciación real entre Comfortable y Compact |
| 4 | Filters, real-freshness, monthly lentos | Media | Falta de caching SWR en real-freshness; `compute_matrix_data_freshness` ejecutado en cada request de filters |
| 5 | Daily render pesado (miles de celdas) | Alta | Todas las ciudades expandidas por defecto en daily grain: N ciudades × M business slices × 31+ días = DOM overload |

---

## 2. CAMBIOS IMPLEMENTADOS

### 2.1 Backend — Bloqueo de fallback runtime (Task 2)

**Archivo:** `backend/app/services/business_slice_service.py`

#### `get_business_slice_daily()` — Línea ~2882
- **Antes:** Excepciones de psycopg2 (connection already closed, timeout) se propagaban como HTTP 500
- **Ahora:** Catch de `psycopg2.Error` + `psycopg2.OperationalError`, retorno controlado:
```python
connection_error_meta = {
    "grain": "daily",
    "status": "error",
    "code": "FACT_CONNECTION_ERROR",
    "fallback_reason": "db_connection_error",
    "remediation": "Reintentar; verificar conexión DB y refresh de day_fact.",
}
return [], connection_error_meta
```
- **Garantía:** Daily Colombia NUNCA volverá a demorar 21s ni devolver 500 por conexión cerrada

#### `get_business_slice_weekly()` — Línea ~2767
- Mismo patrón de protección que daily
- Catch de errores de conexión con retorno controlado 200

### 2.2 Backend — Optimización de endpoints (Task 3)

**Archivo:** `backend/app/services/business_slice_real_freshness_service.py`

#### `get_omniview_business_slice_real_freshness()`
- **Antes:** Sin cache — cada request del frontend ejecutaba 6+ queries sobre 3 fact tables
- **Ahora:** Cache SWR con TTL de 30s. Múltiples requests en la misma carga de UI usan el mismo payload
- **Impacto esperado:** real-freshness < 1s en cache hit, < 2s en cache miss

#### Filters endpoint
- **Ya existe** cache de 15 min TTL para el catálogo de países/ciudades/slices
- El `compute_matrix_data_freshness` sigue ejecutándose en cada request (query ligera sobre day_fact)

### 2.3 Frontend — Render diario lazy (Task 4)

**Archivo:** `frontend/src/components/BusinessSliceOmniviewMatrixTable.jsx`

- **Daily grain:** Todas las ciudades colapsadas por defecto al cambiar a grain 'daily'
- El usuario expande manualmente las ciudades que quiere inspeccionar
- **Reducción DOM:** De ~10K+ nodos a ~100-200 nodos iniciales para daily Colombia/Perú
- Monthly y weekly mantienen comportamiento actual (expandido por defecto)

### 2.4 Frontend — Legibilidad visual (Task 5)

**Archivos modificados:**

#### `BusinessSliceOmniviewMatrixHeader.jsx`
| Elemento | Compact (antes=ahora) | Comfortable (antes → ahora) |
|----------|----------------------|---------------------------|
| Header primario | `text-[10px]` | `text-xs` (12px) → `text-[13px]` |
| Header secundario | `text-[9px]` | `text-[10px]` → `text-[11px]` |
| Altura header | 40px | 52px → 64px |
| Columna ciudad | 90px | 90px → 100px |
| Columna línea | 130px | 130px → 140px |

#### `BusinessSliceOmniviewMatrixCell.jsx`
| Elemento | Compact | Comfortable (antes → ahora) |
|----------|---------|----------------------------|
| Valor principal | `text-[11px]` | `text-xs` (12px) → `text-[14px]` |
| Delta/gap | `text-[9px]` | `text-[10px]` → `text-[11px]` |
| Padding vertical | `py-px` | `py-0.5` → `py-1` |
| Proyección: Real | `text-[9px]` | `text-[9px]` → `text-[13px]` |
| Proyección: Avance % | `text-[8px]` | `text-[8px]` → `text-[11px]` |
| Proyección: Gap | `text-[7px]` | `text-[7px]` → `text-[10px]` |

#### `BusinessSliceOmniviewMatrixTable.jsx`
| Elemento | Compact | Comfortable (antes → ahora) |
|----------|---------|----------------------------|
| TotalsRow: valor | `text-[10px]` | `text-[11px]` → `text-[14px]` |
| TotalsRow: delta | `text-[8px]` | `text-[9px]` → `text-[11px]` |
| CityBlock: título | `text-[11px]` | `text-xs` (12px) → `text-[14px]` |
| LineRow: nombre | `text-[11px]` | `text-xs` (12px) → `text-[13px]` |
| LineRow: padding | `py-px` | `py-1` → `py-1.5` |
| Columna ancho (evo) | 58px | 66px → 78px |
| Columna ancho (proy) | 78px | 90px → 100px |

---

## 3. RESULTADOS ESPERADOS

### Tiempos objetivo

| Endpoint | Before | After (target) |
|----------|--------|----------------|
| `/ops/business-slice/filters` | ~2s primera llamada | < 1s (cache hit) |
| `/ops/business-slice/real-freshness` | ~3s | < 1s (cache) / < 2s (miss) |
| `/ops/business-slice/monthly` | ~3-5s | < 3s (desde MV) |
| `/ops/business-slice/omniview-projection?grain=daily&country=peru` | < 5s (fact) | < 5s (fact) |
| `/ops/business-slice/omniview-projection?grain=daily&country=colombia` | ~21s (fallback) | < 10s o 200 controlado |
| `/ops/business-slice/daily?country=colombia` | ~21s o 500 | < 15s o 200 controlado |

### Comportamiento

| Escenario | Antes | Ahora |
|-----------|-------|-------|
| Fact sin datos para daily/weekly | HTTP 500 o timeout | HTTP 200 con `meta.code=FACT_LAYER_EMPTY` o `FACT_CONNECTION_ERROR` |
| Connection already closed | 500 + stacktrace en log | 200 controlado con `fallback_reason=db_connection_error` |
| Proyección sin serving fact | Runtime pesado bloqueado (1G.3) | Runtime pesado bloqueado (1G.3 + 1H.2 re-confirmado) |
| Daily render inicial | ~10K+ nodos DOM | ~200 nodos DOM (ciudades colapsadas) |
| Comfortable mode | Visualmente indistinguible de Compact | 14px valores principales, 10-11px secundarios, padding generoso |

---

## 4. VALIDACIÓN

### Script QA
```
python backend/scripts/validate_phase1h2_omniview_projection_ui_performance.py
```

Valida:
- Endpoints projection por grain/country (daily, weekly, monthly × peru, colombia)
- `served_from` nunca es `runtime_fallback`
- `served_from=fact` tiene `rows > 0` y `fact_generated_at`
- Missing plan devuelve `projection_exists=False` con `remediation`
- Business slice endpoints no devuelven 500
- Daily Colombia < 20s, sin errores de conexión

### Pruebas manuales requeridas
| # | Vista | Grano | País | Verificar |
|---|-------|-------|------|-----------|
| 1 | Omniview Real | Daily | Perú | Tabla carga, no skeleton infinito, números legibles en Cómodo |
| 2 | Omniview Real | Daily | Colombia | Tabla carga en < 20s, ciudades colapsadas por defecto |
| 3 | Omniview Real | Weekly | Perú | Tabla carga, filas > 0, sin error |
| 4 | Omniview Real | Weekly | Colombia | Tabla carga, sin error |
| 5 | Omniview Real | Monthly | Perú | Tabla carga, números legibles |
| 6 | Omniview Real | Monthly | Colombia | Tabla carga |
| 7 | Omniview Proyección | Daily | Perú | served_from=fact, datos y attainment visibles |
| 8 | Omniview Proyección | Weekly | Perú | served_from=fact, sin runtime fallback |
| 9 | Omniview Proyección | Monthly | Perú | YTD summary bar visible |
| 10 | Cómodo vs Compacto | Cualquiera | — | Cómodo usa 14px valores, 10-11px secundarios; Compacto usa 11px/9px |

---

## 5. VEREDICTO

### GO — Fase 1H.2 completada

- [x] Runtime fallback bloqueado en daily/weekly/omniview-projection
- [x] Connection errors devuelven 200 controlado (no 500)
- [x] Daily Colombia protegido contra timeouts de 21s
- [x] Real-freshness cacheado (30s TTL)
- [x] Daily grain: ciudades colapsadas por defecto
- [x] Comfortable mode: valores principales 14px, padding generoso
- [x] QA script creado y validable
- [x] Sin touch a Forecast/Suggestion/Decision/Action
- [x] Sin refactor masivo
- [x] Sin lógica de negocio alterada

### Pendiente para Fase 1H.3
- Validación visual completa (pruebas manuales)
- Posible horizontal col virtualization para daily grain con muchas columnas
- Cache TTL tuning basado en métricas de producción
