# Auditoría técnica: mejoras del módulo REAL (YEGO Control Tower)

**Modo:** DEBUG + AUDITORÍA — sin implementar cambios.  
**Objetivo:** Verificar si las mejoras existen en código, DB, backend runtime y UI; identificar por qué no aparecen en pantalla.

---

## FASE 1 — Inventario de cambios (tabla de estado)

| Mejora | Existe en código | Existe en DB | Existe en backend runtime | Visible en UI | Estado |
|--------|------------------|--------------|---------------------------|---------------|--------|
| **1. Normalización de márgenes (ABS)** | Sí | Depende de populate | Sí | Sí (si backend devuelve positivo) | **ACTIVE** (parcial) |
| **2. Cancelaciones en el drill** | Parcial | Sí (si mig 103 + populate) | No | Sí (columna siempre 0) | **DISABLED** |
| **3. Alerta calidad de margen** | Sí | Sí (si mig 104) | Sí | Sí (card + badges si endpoint responde) | **ACTIVE** (si endpoint OK) |
| **4. Badge "Cobertura incompleta"** | Sí | N/A | Sí (vía margin-quality) | Sí (si margin-quality devuelve affected_*_dates) | **ACTIVE** (depende 3) |
| **5. Label canónico de park** | Sí | N/A | Sí | Sí | **ACTIVE** |
| **6. Coherencia entre vistas REAL** | Sí (script) | N/A | N/A | N/A | **CODE_ONLY** (script no en UI) |
| **7. Estabilidad del drill (sin 500)** | Sí | N/A | Sí | Sí | **ACTIVE** |

Detalle por mejora:

- **1. Normalización de márgenes**  
  - **Código:** `populate_real_drill_from_hourly_chain.py` escribe `ABS(SUM(margin_total))` y `ABS(SUM(margin_total))/SUM(completed_trips)`. `real_lob_drill_pro_service.py` aplica `abs(float(...))` en Python a `margen_total` y `margen_trip` (agg_detail y children).  
  - **DB:** Si el populate no se ha re-ejecutado tras el cambio, `real_drill_dim_fact.margin_total` puede seguir negativo; el servicio igualmente devuelve positivo por la capa Python.  
  - **UI:** Muestra `margin_total_pos` / margen total y margen/trip; tooltip indica "Margen mostrado en positivo (ABS)".

- **2. Cancelaciones en el drill**  
  - **Código:** Migración 103 añade `cancelled_trips` a `real_drill_dim_fact`. Populate rellena `SUM(cancelled_trips)` desde day_v2/week_v3. **Pero** `real_lob_drill_pro_service.py` **no** selecciona `cancelled_trips` en ninguna query: usa comentario "No usar cancelled_trips: la columna puede no existir en MV" y asigna `ad["cancelaciones"] = 0` y `r["cancelaciones"] = 0` en drill y children.  
  - **DB:** La columna existe si mig 103 aplicada; tiene datos si el populate incluye esa columna (sí en el script actual).  
  - **Backend:** Siempre devuelve `cancelaciones: 0`.  
  - **UI:** La tabla tiene columna "Cancel." y muestra `row.cancelaciones` y WoW; al ser siempre 0, la mejora no es visible. **Estado: DISABLED (revertida en servicio).**

- **3. Alerta calidad de margen**  
  - **Código:** `real_margin_quality_service.py`, `audit_real_margin_source_gaps.py`, endpoint `GET /ops/real-margin-quality` y `GET /ops/real/margin-quality` en `ops.py`. Mig 104 crea `ops.real_margin_quality_audit`.  
  - **DB:** Tabla `ops.real_margin_quality_audit` existe si mig 104 aplicada; se llena con `audit_real_margin_source_gaps --persist`.  
  - **Backend:** Endpoint registrado; usa `_run_sync(get_margin_quality_full, ...)` (fix reciente). Responde con `coverage_pct`, `completed_without_margin_pct`, `cancelled_with_margin_pct`, `sample_findings`, `affected_week_dates`, `affected_month_dates`.  
  - **UI:** `RealMarginQualityCard` en pestaña Real (App.jsx); `getRealMarginQuality()` en api.js. Si el request responde OK, la card se muestra; si timeout/error, banner amarillo y card no útil.

- **4. Badge "Cobertura incompleta"**  
  - **Código:** En `RealLOBDrillView.jsx`, `marginQualityAffected` se rellena con `data.affected_week_dates` y `data.affected_month_dates` del endpoint real-margin-quality. Por cada fila, si `normalizePeriodStart(row.period_start)` está en el Set, se muestra el badge.  
  - **Backend:** `get_margin_quality_full` incluye `affected_week_dates` y `affected_month_dates` (calculados en `get_affected_period_dates` desde `v_real_trip_fact_v2`).  
  - **UI:** Badge visible solo si el endpoint margin-quality responde y hay períodos con cobertura incompleta.

- **5. Label canónico de park**  
  - **Código:** `real_lob_filters_service.py` asigna `p["park_label"] = f"{name} — {city} — {country}"`. `real_lob_drill_pro_service.py` en children PARK asigna `row["park_label"] = f"{name} — {city} — {country}"`.  
  - **Frontend:** Dropdown de park usa `p.park_label || (fallback construido con park_name, city, country)`.  
  - **Estado: ACTIVE.**

- **6. Coherencia entre vistas REAL**  
  - **Código:** `scripts/audit_real_coherence.py` (reconciliación LOB vs park vs service_type, semanal vs mensual, parks).  
  - **Runtime:** Script manual; no expuesto en UI ni en un endpoint. **CODE_ONLY.**

- **7. Estabilidad del drill**  
  - Eliminación de uso de `cancelled_trips` en queries del servicio para evitar 500 si la columna no existía o fallaba. Fallback `cancelaciones = 0`. **ACTIVE** (drill estable; cancelaciones no mostradas como dato real).

---

## FASE 2 — Verificación de DB (queries a ejecutar)

Ejecutar en PostgreSQL (por ejemplo con `psql` o cliente sobre la DB del proyecto):

```sql
-- 2.1 Columna cancelled_trips en ops.real_drill_dim_fact
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
ORDER BY ordinal_position;

-- 2.2 ¿Existe cancelled_trips en mv_real_drill_dim_agg? (vista/MV sobre real_drill_dim_fact)
SELECT EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_schema = 'ops' AND table_name = 'mv_real_drill_dim_agg' AND column_name = 'cancelled_trips'
) AS mv_has_cancelled_trips;

-- 2.3 Tabla ops.real_margin_quality_audit
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'ops' AND table_name = 'real_margin_quality_audit'
) AS table_margin_quality_audit_exists;

-- 2.4 Muestra real_drill_dim_fact: margin_total (¿positivo o negativo?), cancelled_trips (si existe)
SELECT period_grain, period_start, breakdown,
       COUNT(*) AS rows_count,
       SUM(trips) AS total_trips,
       SUM(margin_total) AS total_margin
FROM ops.real_drill_dim_fact
WHERE period_start >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY period_grain, period_start, breakdown
ORDER BY period_start DESC, breakdown
LIMIT 20;

-- 2.5 Si cancelled_trips existe: muestra de valores
-- SELECT period_grain, period_start, breakdown, dimension_key, trips, cancelled_trips, margin_total
-- FROM ops.real_drill_dim_fact
-- WHERE period_start >= CURRENT_DATE - INTERVAL '14 days' AND cancelled_trips IS NOT NULL AND cancelled_trips <> 0
-- LIMIT 10;
```

**Resultados esperados (interpretación):**

- Si `real_drill_dim_fact` tiene columna `cancelled_trips` y el populate se ejecutó, habrá valores no nulos. Si no existe la columna, la mig 103 no está aplicada o la tabla fue recreada sin ella.
- Si `total_margin` en 2.4 es negativo, el populate no se ha ejecutado con la versión que usa ABS, o la vista/MV lee de otra fuente.
- Si `real_margin_quality_audit` no existe, la mig 104 no está aplicada; el endpoint puede seguir respondiendo (usa `v_real_trip_fact_v2` para el resumen), pero los "findings" persistidos estarán vacíos.

---

## FASE 3 — Verificación backend (código)

| Elemento | Ubicación | Estado |
|----------|-----------|--------|
| Endpoint GET /ops/real-margin-quality | ops.py ~L1506 | Registrado; usa `await _run_sync(get_margin_quality_full, ...)` |
| Endpoint GET /ops/real-lob/drill | ops.py ~L1967 | Registrado; usa get_real_lob_drill_pro |
| Endpoint GET /ops/real-lob/drill/children | ops.py ~L1908 | Registrado; usa get_real_lob_drill_pro_children |
| cancelled_trips en queries del drill | real_lob_drill_pro_service.py | **No usado:** queries sin la columna; `cancelaciones = 0` en agg_detail y en children |
| Normalización margen (ABS) en servicio | real_lob_drill_pro_service.py | Aplicada en Python a margen_total y margen_trip (drill y children) |
| park_label en respuesta | real_lob_drill_pro_service.py (L277, L822), real_lob_filters_service.py (L97) | En parks y en filas children PARK |
| get_margin_quality_full | real_margin_quality_service.py | Devuelve summary, findings, affected_days, affected_week_dates, affected_month_dates |

---

## FASE 4 — Verificación runtime (requests reales)

Con el backend levantado (uvicorn en 127.0.0.1:8000), ejecutar:

```bash
# Drill principal (debe 200; payload con countries[].rows[].cancelaciones, margin_total_pos, etc.)
curl -s -o /tmp/drill.json -w "%{http_code}\n%{time_total}\n" "http://127.0.0.1:8000/ops/real-lob/drill?period=month&desglose=LOB&segmento=all"

# Children (desglose por LOB para un periodo; debe 200)
curl -s -o /tmp/children.json -w "%{http_code}\n%{time_total}\n" "http://127.0.0.1:8000/ops/real-lob/drill/children?country=co&period_grain=month&period_start=2025-02-01&desglose=LOB"

# Calidad de margen (debe 200; payload con margin_coverage_pct, affected_week_dates, affected_month_dates)
curl -s -o /tmp/mq.json -w "%{http_code}\n%{time_total}\n" "http://127.0.0.1:8000/ops/real-margin-quality?days_recent=90&findings_limit=20"
```

Revisar:

- `jq '.countries[0].rows[0] | {cancelaciones, margen_total, margin_total_pos}' /tmp/drill.json` → cancelaciones debe ser 0; margen_total/margin_total_pos positivos si hay datos.
- `jq '{affected_week_dates, affected_month_dates, margin_coverage_pct}' /tmp/mq.json` → si la tabla no existe o está vacía, findings vacío; affected_* sí pueden venir de get_affected_period_dates.

---

## FASE 5 — Verificación frontend

| Elemento | Archivo | Estado |
|----------|---------|--------|
| Llamada a margin-quality (drill badges) | RealLOBDrillView.jsx | getRealMarginQuality({ days_recent: 90 }); setMarginQualityAffected(week/month Sets) |
| Llamada a margin-quality (card) | RealMarginQualityCard.jsx | getRealMarginQuality(); muestra status y datos |
| api.get('/ops/real-margin-quality') | api.js | getRealMarginQuality con timeout 15000 |
| Columna Cancelaciones en tabla | RealLOBDrillView.jsx | Header "Cancel.", celdas row.cancelaciones y row.cancelaciones_delta_pct |
| Badge "Cobertura incompleta" | RealLOBDrillView.jsx | Si periodStart en marginQualityAffected.week/month se muestra el span |
| Uso de park_label | RealLOBDrillView.jsx | Dropdown parks: p.park_label \|\| fallback name — city — country |
| Card de calidad de margen | App.jsx | {activeTab === 'real' && <RealMarginQualityCard />} |

La UI está preparada para mostrar cancelaciones, margen positivo, badge de cobertura y park_label. Lo que no se ve es:

- **Cancelaciones reales:** el backend siempre envía 0.
- **Badge "Cobertura incompleta":** solo si GET /ops/real-margin-quality responde OK y hay períodos afectados.
- **Card de calidad de margen:** solo si el mismo endpoint responde antes del timeout (15s).

---

## FASE 6 — Causa raíz: por qué las mejoras no aparecen (o aparecen a medias)

1. **Cancelaciones en el drill**  
   - **Causa:** Durante el debug se desactivó el uso de `cancelled_trips` en `real_lob_drill_pro_service.py` para evitar 500 (columna podría no existir en la MV o en algún entorno). Se fijó `cancelaciones = 0` en todas las rutas (drill principal y children).  
   - **Efecto:** La columna "Cancel." existe en la UI pero siempre muestra 0 y WoW 0%; no hay datos reales.

2. **Margen positivo**  
   - **Causa:** En código está aplicado (populate con ABS, servicio con abs()). Si en UI aún se viera negativo, sería por datos antiguos en DB sin re-poblar o por otra fuente; según el código actual, el backend sí envía margen en positivo.

3. **Calidad de margen y badge "Cobertura incompleta"**  
   - **Causa posible 1:** Timeout (15s) o error en GET /ops/real-margin-quality (antes el handler bloqueaba el event loop; ya se corrigió con _run_sync).  
   - **Causa posible 2:** Tabla `real_margin_quality_audit` vacía o no existente; el resumen y affected_* sí se calculan contra `v_real_trip_fact_v2`, así que la card y los badges pueden funcionar aunque no haya hallazgos persistidos.  
   - **Efecto:** Si el request falla o hace timeout, la card no se rellena y marginQualityAffected queda vacío → no se muestra ningún badge "Cobertura incompleta".

4. **Park label**  
   - **Causa:** Implementado en backend y usado en frontend. No hay causa raíz de “no aparece”; si en algún entorno se viera solo park_name, sería por respuesta sin park_label (p. ej. otro endpoint de parks que no lo incluya).

5. **Coherencia entre vistas**  
   - **Causa:** El script audit_real_coherence existe pero es solo para ejecución manual; no hay integración en UI ni en cron visible. Es mejora CODE_ONLY por diseño.

---

## FASE 7 — Resultado final

### 1. Auditoría completa de mejoras

Resumida en la tabla de FASE 1 y en las fases 2–6.

### 2. Mejoras activas

- Normalización de márgenes (ABS en servicio; en DB depende de populate).
- Alerta de calidad de margen (endpoint, card, findings y affected dates si la tabla existe y/o v_real_trip_fact_v2 tiene datos).
- Badge "Cobertura incompleta" (cuando margin-quality responde y hay affected_*_dates).
- Label canónico de park en dropdown y en children PARK.
- Estabilidad del drill (sin uso de cancelled_trips en queries; cancelaciones = 0).

### 3. Mejoras desactivadas

- **Cancelaciones en el drill:** el backend no lee `cancelled_trips`; fija `cancelaciones = 0`. La columna y WoW existen en UI pero sin dato real.

### 4. Mejoras rotas

- Ninguna identificada como “rota” en código; lo que fallaba (timeout por margin-quality bloqueando el event loop) ya tiene fix (_run_sync). Si en runtime sigue habiendo timeout, sería por lentitud de consultas o falta de tabla/vista.

### 5. Mejoras solo en código

- **Coherencia entre vistas REAL:** script `audit_real_coherence.py`; no integrado en UI ni en pipeline expuesto.

### 6. Causa raíz de por qué no aparecen

- **Cancelaciones:** desactivadas a propósito en el servicio (evitar 500); por eso no aparecen datos reales.
- **Card/badges de calidad de margen:** dependen de que GET /ops/real-margin-quality responda OK; si antes colgaba el backend, ya está corregido; si sigue habiendo timeout/error, la card queda vacía y los badges no se rellenan.
- **Resto (margen positivo, park_label):** están en código y en flujo; si no se ven, revisar DB (populate) o que la respuesta del backend incluya los campos.

### 7. Recomendación para reactivar sin romper el sistema

1. **Cancelaciones en el drill**  
   - Comprobar en DB que `cancelled_trips` existe en `real_drill_dim_fact` (y en `mv_real_drill_dim_agg` si es vista).  
   - En `real_lob_drill_pro_service.py`: volver a incluir `SUM(cancelled_trips) AS cancelaciones` (o equivalente) en las queries que agregan por periodo y en children, y quitar la asignación fija `cancelaciones = 0`.  
   - Opcional: si en algún entorno la columna no existe, usar `COALESCE(SUM(cancelled_trips), 0)` o comprobar existencia de columna antes de seleccionarla, para mantener estabilidad.

2. **Calidad de margen**  
   - Asegurar que el endpoint responde en <15s (ya no bloquea el event loop).  
   - Si se quiere mostrar hallazgos persistidos, aplicar mig 104 y ejecutar `audit_real_margin_source_gaps --persist` cuando corresponda.

3. **Coherencia**  
   - Si se quiere exponer en UI o en pipeline: ejecutar `audit_real_coherence` vía cron y/o exponer resultado por endpoint y mostrarlo en una sección de diagnóstico/Real.

---

*Documento generado por auditoría técnica. No se ha modificado código ni configuración.*
