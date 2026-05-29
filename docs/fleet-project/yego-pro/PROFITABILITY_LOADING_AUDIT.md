# Yego Pro Profitability — Loading Audit Report

**Date:** 2026-05-29
**URL:** http://localhost:5173/fleet-project/yego-pro/profitability
**Audit Scope:** Profitability module only — 8 endpoints + frontend loading behavior

---

## 1. ¿La página cargó o quedó bloqueada?

**CARGÓ PARCIALMENTE.** El spinner "Cargando diagnóstico ejecutivo" desaparece a ~1s (cuando el primer endpoint responde). Pero los KPIs principales del overview (utilidad neta, revenue, margen) muestran "No disponible" permanentemente debido a un **mismatch de estructura de datos backend↔frontend**.

El usuario percibe "carga interminable" porque el dashboard se renderiza **sin los números críticos**.

---

## 2. ¿Cuánto tardó?

| Métrica | Cold (primer request) | Warm (cache DB) |
|---------|----------------------|-----------------|
| Spinner visible | 0s → ~3s | 0s → ~1s |
| Primeros datos visibles | ~3s | ~1s |
| Overview KPIs | **NUNCA** (mismatch) | **NUNCA** (mismatch) |
| Tiempo total hasta último endpoint | ~21s | ~7s |
| Página completamente funcional | **NUNCA** | **NUNCA** |

---

## 3. ¿Qué endpoint bloqueó?

### Culpable secundario: `/overview`
- Cold: **21.4s** (BLOCKING)
- Warm: 3.9s (SLOW)
- 2,947 bytes — payload válido pero inutilizado por el frontend

### Culpable secundario: `/quality`
- Cold: 11.1s (BLOCKING)
- Warm: 7.3s (SLOW)
- 2,590 bytes

### Culpable primario: **MISMATCH DE ESTRUCTURA**
El backend devuelve KPIs como:
```json
{"profit_weekly": {"value": -5509.9, "source": "...", "metric_type": "REAL", "confidence": "HIGH"}}
```
El frontend busca:
```js
extractNum(ovFlat, 'net_profit_weekly', 'net_profit', 'profit', 'weekly_profit')
```
→ Ni la key coincide (`profit_weekly` vs `net_profit_weekly`) ni el formato (`{value: X}` vs valor plano).

---

## 4. ¿Hubo error JS?

No hay error visible en console (el frontend maneja errores con try/catch vía `friendlyError`). Pero hay un error silencioso: todos los KPIs del overview se muestran como "No disponible" porque `extractNum` nunca encuentra los valores numéricos.

---

## 5. ¿Hubo error HTTP?

**Sí — `/shifts` retorna 500 consistentemente.**

Causa: **Parameter name mismatch** router↔service.

- Router llama: `get_shifts(park_id=park_id, weeks=weeks)` (línea 104)
- Service define: `def get_shifts(park_id=PARK_ID, days=35)` (línea 414)
- Error: `TypeError: get_shifts() got an unexpected keyword argument 'weeks'`

Ubicación:
- Router: `backend/app/routers/yego_pro_profitability.py:104`
- Service: `backend/app/services/yego_pro_profitability_service.py:414`

---

## 6. ¿Hubo endpoint HUNG?

En cold start:
- `/overview`: 21.4s → clasificado BLOCKING (>10s pero <20s, borderline HUNG)
- `/quality`: 11.1s → clasificado BLOCKING

En warm cache, ningún endpoint excede 10s.

---

## 7. ¿El frontend está esperando todos los endpoints?

**No usa Promise.all.** El frontend dispara 9 requests individuales en un `forEach` con `.then().catch().finally()` individual. Esto es correcto para renderizado parcial.

Pero hay un problema de diseño:
- `OverviewDiagnostic` muestra spinner hasta que cualquier endpoint retorna datos (OK).
- Pero `DiagnosticHeader` depende de `diagData.overview` que tiene los KPIs.
- Como los KPIs nunca se extraen correctamente (mismatch), la sección principal del dashboard queda vacía.
- El usuario ve un dashboard con conductores/vehículos pero sin los números clave arriba.

---

## 8. Causa probable (orden de impacto)

### #1 — CRÍTICO: Backend↔frontend data structure mismatch
El backend envía KPIs como objetos `{value, source, metric_type, confidence}` pero el frontend espera valores planos con nombres de key diferentes. Esto hace que todos los KPIs del overview muestren "No disponible".

**Keys en backend vs lo que busca el frontend:**
| Backend Key | Frontend busca | Match? |
|---|---|---|
| `profit_weekly` | `net_profit_weekly`, `net_profit`, `profit`, `weekly_profit` | **NO** |
| `revenue_gross_30d` | `revenue_weekly`, `revenue`, `weekly_revenue` | **NO** |
| `margin_pct` | `margin_pct`, `margin`, `margin_percent` | Key OK, pero valor es `{value: X}` no `X` |

### #2 — ALTO: `/shifts` endpoint roto (500) por mismatch de parámetros `weeks` vs `days`

### #3 — MEDIO: `/overview` lento en cold start (21s)
Probablemente por establecimiento de conexión DB + múltiples consultas en cascada:
- 1x `_check_view_exists` para MV_WEEK
- 1x consulta a MV_WEEK
- 1x consulta a MV_DAY (30 rows)
- 1x consulta COUNT(*) a MV_WEEK
- 1x `_get_coverage()` que incluye 1x `_check_view_exists` + 1x consulta a MV_SOURCE_COVERAGE
= **5 queries secuenciales en una misma conexión**

### #4 — MEDIO: `/quality` lento (7-11s)
Similar al overview: recorre todos los MVs con `_check_view_exists` (9 MVs × 1 query cada una = 9 queries round-trip).

---

## 9. Remediation recomendada

### Hotfix inmediato (P0):
1. **Alinear keys y formato overview**: Cambiar `extractNum` en el frontend para buscar keys del backend (`profit_weekly`, `revenue_gross_30d`) O modificar el backend para devolver valores planos con nombres esperados.
2. **Fix shifts parameter**: Cambiar `weeks=weeks` → `days=weeks*7` en el router, o renombrar `days` → `weeks` en el service.

### Mejora de performance (P1):
3. **Consolidar queries de overview**: `_get_coverage()` y las queries de MV_WEEK/MV_DAY pueden correr en paralelo con hilos separados o mediante una sola query CTE.
4. **Reemplazar `_check_view_exists` puntual**: Cachear existencia de MVs en startup en vez de llamar `to_regclass()` en cada request.

### Mejora estructural (P2):
5. **Normalizar estructura de respuesta**: Que todos los endpoints devuelvan `{rows, columns, meta}` en vez de estructuras ad-hoc. El frontend ya espera este formato en `extractRows`, `TabularPanel`, etc.

---

## 10. Prioridad

| Prioridad | Issue | Acción |
|---|---|---|
| **P0** | KPI mismatch (overview vacío) | Alinear backend↔frontend keys y formato de valor |
| **P0** | `/shifts` 500 | Fix parameter name mismatch |
| **P1** | `/overview` 4-21s | Consolidar queries, cachear existencia MVs |
| **P1** | `/quality` 7-11s | Eliminar `_check_view_exists` repetidos por request |
| **P2** | Estructura de respuesta inconsistente | Adoptar formato `{rows, columns, meta}` unificado |

---

## Anexo: Endpoint Timing Summary (Round 2 — Warm Cache)

| Endpoint | Duration | Size | Classification |
|---|---|---|---|
| overview | 3,924ms | 2,947B | SLOW |
| weekly | 1,001ms | 628B | ACCEPTABLE |
| daily | 1,028ms | 9,458B | ACCEPTABLE |
| drivers | 1,010ms | 11,583B | ACCEPTABLE |
| vehicles | 1,007ms | 17,955B | ACCEPTABLE |
| shifts | FAILED (500) | 0B | FAILED |
| input-mapping | 3ms | 4,564B | FAST |
| quality | 7,270ms | 2,590B | SLOW |
| root-cause | 2,058ms | 22,153B | ACCEPTABLE |

---

## Anexo: Frontend Loading Sequence

```
t=0ms    → Página carga HTML shell (SPA)
t=0ms    → useEffect dispara 9 requests paralelos
t=0ms    → "Cargando diagnóstico ejecutivo..." spinner visible
t~1000ms → drivers, vehicles, daily, weekly responden
         → spinner DESAPARECE (hasAnyData = true)
         → DiagnosticHeader intenta extraer KPIs de overview (aún null)
         → Conductor/vehicle rankings se muestran OK
t~3900ms → overview responde pero KPIs no se extraen (mismatch)
         → KPIs del overview muestran "No disponible"
t~7200ms → quality responde
         → Página completa (pero KPIs principales vacíos)
```

## Verdict

**BLOCKED** — La página carga pero es inutilizable porque los KPIs principales del overview nunca se muestran debido al mismatch de estructura de datos. El usuario final ve "No disponible" en todos los indicadores clave, percibiendo que la página "quedó cargando".
