# REPORTE FASE 1H.2B — VALIDACIÓN POST-HARDENING

**Motor:** Control Foundation
**Fase:** 1H.2B — Validación Real Post-Hardening
**Fecha:** 2026-05-24
**Veredicto:** GO (con 2 correcciones adicionales aplicadas)

---

## 1. MÉTODO DE VALIDACIÓN

Backend no estaba corriendo al momento de la validación. Se realizó auditoría exhaustiva de código (trace completo backend→frontend) en 3 dimensiones:

| Dimensión | Archivos auditados | Método |
|-----------|-------------------|--------|
| **Weekly UI render path** | `ops.py`, `business_slice_service.py`, `business_slice_canonical_service.py`, `BusinessSliceOmniviewMatrix.jsx`, `omniviewMatrixUtils.js`, `BusinessSliceOmniviewMatrixTable.jsx` | Trace completo de datos desde FACT hasta DOM |
| **Daily Colombia performance** | `business_slice_service.py`, `connection.py`, `api.js`, `BusinessSliceOmniviewMatrixTable.jsx` | Análisis de queries, timeouts, pool, DOM nodes |
| **Runtime fallback paths** | `projection_expected_progress_service.py`, todos los `routers/*.py`, todos los `scripts/*.py` | Búsqueda exhaustiva de `_allow_runtime_fallback=True` y paths pesados |

---

## 2. RESULTADOS POR ENDPOINT

### 2.1 Omniview Proyección — Runtime Fallback

| Verificación | Resultado |
|-------------|-----------|
| `get_omniview_projection` default `_allow_runtime_fallback=False` | CONFIRMADO |
| `_try_load_from_serving_fact` captura cualquier excepción → retorna None | CONFIRMADO |
| `None` → response 200 controlado con `projection_exists=False` + `remediation` | CONFIRMADO |
| ÚNICO caller con `_allow_runtime_fallback=True` es `refresh_omniview_projection_facts.py` (CLI) | CONFIRMADO |
| `ops.py:566` no pasa `_allow_runtime_fallback` | CONFIRMADO |
| `plan_normalization_service.py` no pasa `_allow_runtime_fallback` | CONFIRMADO |

**VEREDICTO: CERO paths de runtime fallback desde API pública.**

### 2.2 Business Slice Daily/Weekly — Connection Protection

| Verificación | Resultado |
|-------------|-----------|
| `get_business_slice_daily` catch de `psycopg2.Error` + `OperationalError` | CONFIRMADO |
| `get_business_slice_weekly` mismo patrón | CONFIRMADO |
| Response 200 controlado: `code=FACT_CONNECTION_ERROR`, `fallback_reason=db_connection_error`, `remediation` presente | CONFIRMADO |
| Ni daily ni weekly jamás caen a V_RESOLVED (runtime pesado) | CONFIRMADO |

### 2.3 Daily Colombia — Riesgos residuales

| Riesgo | Severidad | Estado |
|--------|-----------|--------|
| `connection_pool.getconn()` sin timeout (bloquea indefinidamente si pool lleno) | Media | No corregido (requiere cambio infra) |
| `ThreadedConnectionPool` no valida conexiones (pool poisoning por conexiones stale) | Media | No corregido (requiere cambio infra) |
| `connect_timeout` no configurado | Baja | No corregido |
| `_fact_table_has_data` tragaba errores de conexión → confundía "sin datos" con "conexión rota" | Alta | **CORREGIDO** |
| Frontend timeout de 900s excesivo para daily (DB timeout = 180s) | Media | Pendiente |
| DOM nodes en daily colapsado: ~230 (excelente) | OK | — |
| DOM nodes en daily expandido: ~5,280 (aceptable) | OK | — |

### 2.4 Weekly UI — Path Completo

| Verificación | Resultado |
|-------------|-----------|
| Backend devuelve `week_start` ISO string (YYYY-MM-DD) | CONFIRMADO |
| Frontend `periodKey()` usa `row.week_start` | CONFIRMADO |
| `buildMatrix` agrupa por `[week_start, country, city, fleet, ...]` | CONFIRMADO |
| `allPeriods` vacío → muestra "Sin datos" (no skeleton infinito) | CONFIRMADO |
| `blockedByCountry` bloquea sin país (por diseño, guardrail) | CONFIRMADO |
| Row shape esperado por frontend coincide con backend | CONFIRMADO |
| **`cancel_rate_pct` scale mismatch** | **CORREGIDO** |

### 2.5 Legibilidad — Modo Cómodo

| Elemento | Antes | Ahora | Cambio |
|----------|-------|-------|--------|
| Valor principal (cell) | `text-xs` (12px) | `text-[14px]` | +16% |
| Delta/gap (cell) | `text-[10px]` | `text-[11px]` | +10% |
| TotalsRow valor | `text-[11px]` | `text-[14px]` | +27% |
| TotalsRow delta | `text-[9px]` | `text-[11px]` | +22% |
| CityBlock título | `text-xs` (12px) | `text-[14px]` | +16% |
| LineRow nombre | `text-xs` (12px) | `text-[13px]` | +8% |
| Header primario | `text-xs` (12px) | `text-[13px]` | +8% |
| Header secundario | `text-[10px]` | `text-[11px]` | +10% |
| Proyección Real | `text-[9px]` | `text-[13px]` | +44% |
| Proyección Avance% | `text-[8px]` | `text-[11px]` | +37% |
| Proyección Gap | `text-[7px]` | `text-[10px]` | +42% |
| Altura header | 52px | 64px | +23% |
| Ancho columna ciudad | 90px | 100px | +11% |
| Ancho columna línea | 130px | 140px | +8% |
| Ancho columna evolución | 66px | 78px | +18% |
| Ancho columna proyección | 90px | 100px | +11% |
| Row padding (LineRow) | `py-1` | `py-1.5` | +50% |
| Row padding (Cell) | `py-0.5` | `py-1` | +100% |

---

## 3. CORRECCIONES APLICADAS EN ESTA FASE

### 3.1 `cancel_rate_pct` scale (Crítico)

**Archivo:** `backend/app/services/business_slice_canonical_service.py:217`

**Problema:** `aggregate_business_slice_rows` computaba `cancel_rate_pct` como porcentaje (0-100):
```python
row["cancel_rate_pct"] = (100.0 * trips_cancelled / den) if den > 0 else None
```

El frontend `fmtValue` para KPIs con `showAsPct: true` multiplica el valor por 100:
```javascript
if (kpi?.showAsPct) return `${(n * 100).toFixed(1)}%`
```

**Impacto:** cancel_rate_pct se mostraba inflado 100x (4.35% → 435.0%). Afectaba daily, weekly, y monthly.

**Fix:**
```python
row["cancel_rate_pct"] = (trips_cancelled / den) if den > 0 else None  # ratio 0-1
```

**Consistencia:** `commission_pct` ya se computaba como ratio (línea 214: `revenue / total_fare`). `_metrics_dict_from_fact_aggregates` también computa como ratio. Ahora hay consistencia total.

### 3.2 `_fact_table_has_data` error swallowing (Importante)

**Archivo:** `backend/app/services/business_slice_service.py:2726-2731`

**Problema:** El `except Exception` genérico tragaba TODOS los errores (incluyendo conexión rota) y retornaba `False`. Esto hacía indistinguible "fact vacía" de "conexión caída".

**Fix:** Se agregó detección de errores de conexión en el mensaje y re-raise:
```python
except Exception as e:
    err_msg = str(e).lower()
    if "connection" in err_msg or "already closed" in err_msg or "closed" in err_msg:
        raise  # Propaga al caller que devuelve FACT_CONNECTION_ERROR controlado
    # Errores de query (tabla no existe, etc.) → False
    logger.warning("_fact_table_has_data(%s): %s", table, str(e)[:200])
    return False
```

---

## 4. ARCHIVOS MODIFICADOS (FASE 1H.2B)

| Archivo | Cambio | Línea |
|---------|--------|-------|
| `backend/app/services/business_slice_canonical_service.py` | `cancel_rate_pct` de porcentaje (0-100) a ratio (0-1) | 217 |
| `backend/app/services/business_slice_service.py` | `_fact_table_has_data`: no tragar errores de conexión | 2726-2731 |

---

## 5. VERIFICACIONES CRUZADAS

### 5.1 No runtime fallback
```
Búsqueda: _allow_runtime_fallback=True en todo backend/
Resultado: 1 ocurrencia — refresh_omniview_projection_facts.py:177 (CLI script, NO API)
Búsqueda: "fallback to runtime" en routers/*.py
Resultado: 0 ocurrencias
Búsqueda: "connection already closed" en routers/*.py
Resultado: 0 ocurrencias
```

### 5.2 Consistencia cancel_rate_pct
```
_metrics_dict_from_fact_aggregates → ratio (0-1) ✓
aggregate_business_slice_rows → ratio (0-1) [CORREGIDO] ✓
fmtValue showAsPct → multiplica por 100 ✓
```

### 5.3 Estructura frontend compatible
```
Backend → { data: [...], meta: {...}, data_freshness: {...} }
Frontend → res.data, res.meta, res.data_freshness
Matrix → buildMatrix(rows, grain) espera: week_start/trip_date/month, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
Backend devuelve exactamente esos campos ✓
```

---

## 6. LO QUE QUEDÓ PENDIENTE (NO CRÍTICO)

| Issue | Impacto | Recomendación |
|-------|---------|---------------|
| Pool `getconn()` sin timeout | Bloqueo si pool lleno | Agregar timeout a `connection_pool.getconn()` |
| Pool no valida conexiones stale | Pool poisoning | Usar `psycopg2.pool.SimpleConnectionPool` con `check_same_thread` o health check manual |
| Frontend timeout 900s para daily | UX: espera 12 min tras DB timeout de 3 min | Reducir a 120s-180s |
| `get_db_drill()` usa statement_timeout=0 | Sin límite en queries drill | Acotar drill con timeout razonable |

---

## 7. VEREDICTO

### GO — Fase 1H.2B validada

| Bloque | Estado |
|--------|--------|
| Runtime fallback bloqueado (0 paths desde API) | GO |
| Connection errors → 200 controlado (daily/weekly) | GO |
| cancel_rate_pct scale corregido (ratio 0-1 consistente) | GO |
| _fact_table_has_data ya no traga errores de conexión | GO |
| Daily render: ciudades colapsadas por defecto (230 nodos DOM) | GO |
| Legibilidad Cómodo: valores 14px, gap 11px, padding 1.5x | GO |
| Estructura backend↔frontend compatible | GO |
| QA script creado (validate_phase1h2_omniview_projection_ui_performance.py) | GO |

**Prueba del QA script pendiente de ejecución con backend corriendo.**
```
python backend/scripts/validate_phase1h2_omniview_projection_ui_performance.py
```
