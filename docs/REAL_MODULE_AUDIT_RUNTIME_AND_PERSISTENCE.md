# Auditoría REAL: existencia, persistencia y runtime

**Modo:** runtime-first, persistence-first.  
**Objetivo:** Evidenciar qué cambios del módulo REAL existen y persisten en DB, vistas/MVs, backend, frontend y runtime.

---

## Resumen ejecutivo (qué se entregó y qué debes hacer tú)

**Entregado en esta auditoría:**

1. **Matriz FASE 0** — Inventario de todos los cambios reclamados con columnas exists_in_code / exists_in_db / exists_in_runtime / visible_in_ui / status. Evidencia en código: referencias exactas (archivo:línea).
2. **FASE 1 — DB:** Script SQL `backend/scripts/verify_real_drill_db.sql` para comprobar en PostgreSQL: columnas de `real_drill_dim_fact` y `mv_real_drill_dim_agg`, existencia de `real_margin_quality_audit`, columnas `cancelled_trips` en day_v2/week_v3/month_v3, muestra de filas recientes.
3. **FASE 2 — Código:** Lista exacta de archivos y líneas críticas (real_lob_drill_pro_service, ops, api.js, componentes).
4. **FASE 3 — Runtime:** Script `backend/scripts/verify_real_runtime_requests.py` que ejecuta los 7 requests obligatorios e imprime status, tiempo y muestra. Debes ejecutarlo con el backend levantado en 127.0.0.1:8000.
5. **FASE 4 — Cancelaciones:** Opciones A/B/C/D y checklist para decidir el origen real de cancelaciones en el drill según el resultado de FASE 1.
6. **FASE 5–8:** Checklist UI, persistencia post-reinicio, corrección mínima y veredicto (CLOSED / PARTIALLY CLOSED / NOT CLOSED).

**Qué debes hacer para cerrar la auditoría:**

1. **Base de datos:** Ejecutar `verify_real_drill_db.sql` en tu PostgreSQL y pegar resultados (o resumen) en FASE 1.
2. **Runtime:** Con el backend reiniciado, ejecutar `python -m scripts.verify_real_runtime_requests` y pegar la salida en FASE 3. Comprobar que drill y children devuelven 200 y margin-quality 200 (o desactivar consumo en UI).
3. **UI:** Completar checklist FASE 5 (drill carga, children expanden, park_label, card margin-quality, badge “Cobertura incompleta”).
4. **Decisión cancelaciones:** Rellenar FASE 4 según si `cancelled_trips` existe y está poblado en DB.
5. **Veredicto:** Marcar CLOSED solo si se cumplen todos los criterios estrictos (children 200, margin-quality operativo o desactivado, origen cancelaciones definido, persistencia tras reinicio).

**No se puede marcar CLOSED** sin evidencia real de DB + runtime + UI en tu entorno.

---

## FASE 0 — Matriz de verificación (cambios reclamados vs evidencia)

Para cada ítem: **exists_in_code** (código fuente), **exists_in_db** (verificado con queries), **exists_in_runtime** (request 200), **visible_in_ui** (sí/no), **status**: OK / PARTIAL / MISSING / BROKEN.

| Categoría | claimed_change | exists_in_code | exists_in_db | exists_in_runtime | visible_in_ui | status |
|-----------|----------------|----------------|--------------|-------------------|---------------|--------|
| **A. Márgenes** | | | | | | |
| A1 | Normalización a positivo en populate | Sí: `populate_real_drill_from_hourly_chain.py` usa `ABS(SUM(margin_total))` | Pendiente verificar filas en fact | — | — | PARTIAL |
| A2 | Normalización en servicio drill | Sí: `real_lob_drill_pro_service.py` hace `abs(float(...))` en margen (varias líneas) | — | — | — | PARTIAL |
| A3 | WoW coherente sobre margen positivo | Sí: mismo servicio normaliza antes de comparativos | — | — | — | PARTIAL |
| **B. Cancelaciones** | | | | | | |
| B1 | Migración 103 para `cancelled_trips` | Sí: `alembic/versions/103_real_drill_dim_fact_cancelled_trips.py` ADD COLUMN | **Ejecutar verify_real_drill_db.sql 1.1** | — | — | PENDIENTE DB |
| B2 | Populate de cancelaciones en real_drill_dim_fact | Sí: `populate_real_drill_from_hourly_chain.py` INSERT con `cancelled_trips` (requiere columna) | **Ejecutar 1.6 / 1.7** | — | — | PENDIENTE DB |
| B3 | Columnas cancelaciones en drill UI | Código devuelve `cancelaciones` en payload (siempre; hoy = 0 si no hay columna) | — | — | Depende de UI si muestra columna | PARTIAL |
| B4 | Children usando cancelaciones | **NO**: código actual no usa `cancelled_trips`; devuelve `cancelaciones = 0` | — | Ver FASE 3 | — | OK (fallback) |
| B5 | Fallback temporal `cancelaciones = 0` | Sí: `real_lob_drill_pro_service.py` ~427, 774, 817, 875 | — | — | — | OK |
| **C. Calidad de margen** | | | | | | |
| C1 | Tabla audit `ops.real_margin_quality_audit` | Sí: migración `104_real_margin_quality_audit.py` | **Ejecutar verify_real_drill_db.sql 1.4** | — | — | PENDIENTE DB |
| C2 | Endpoint `/ops/real/margin-quality` | Sí: `ops.py` línea 1495 | — | **Request 7** | — | PENDIENTE RUNTIME |
| C3 | Alias `/ops/real-margin-quality` | Sí: `ops.py` línea 1494 | — | **Request 6** | — | PENDIENTE RUNTIME |
| C4 | Card UI calidad de margen | Sí: `RealMarginQualityCard.jsx`, `App.jsx` | — | — | Sí (si endpoint responde) | PARTIAL |
| C5 | Badge "Cobertura incompleta" en drill | Sí: `RealLOBDrillView.jsx` línea 651 | — | — | Sí (si data.affected_* existe) | PARTIAL |
| **D. Coherencia REAL** | | | | | | |
| D1 | park_label = park_name — city — country | Sí: `real_lob_drill_pro_service.py` 273-277, 822; `real_lob_filters_service.py` 93-97 | — | — | Sí (dropdown y filas PARK) | OK |
| D2 | Filtro park coherente con drill | Sí: misma fuente `real_drill_dim_fact` en get_drill_parks y drill | — | — | — | OK |
| D3 | Script audit_real_coherence | Sí: `scripts/audit_real_coherence.py` | — | — | — | OK |
| D4 | Tests backend asociados | Sí: `tests/test_real_coherence.py`, `test_real_margin_quality.py` | — | — | — | OK |

---

## FASE 1 — Verificación de base de datos y vistas

**Acción obligatoria:** Ejecutar en PostgreSQL el script `backend/scripts/verify_real_drill_db.sql` y pegar resultados (o resumir hallazgos).

```bash
# Desde backend/ con conexión a tu DB (ajustar si usas .env o psql con -h -U -d):
psql -f scripts/verify_real_drill_db.sql
# O copiar/pegar el contenido del .sql en tu cliente (DBeaver, pgAdmin, etc.)
```

### 1.1 Columna `cancelled_trips`

- **ops.real_drill_dim_fact:** Query 1.1 lista columnas. Si `cancelled_trips` aparece → migración 103 aplicada.
- **ops.mv_real_drill_dim_agg:** Query 1.2 lista columnas; query 1.3 devuelve true/false. Si es vista `SELECT * FROM real_drill_dim_fact`, tendrá la columna si la tabla la tiene. Si es MV con definición explícita, puede no tenerla.

### 1.2 Tabla `ops.real_margin_quality_audit`

- Query 1.4: existe sí/no; 1.4b lista columnas. Si no existe → migración 104 no aplicada.

### 1.3 Vistas fuente (day_v2, week_v3, month_v3)

- Query 1.5: cada una tiene o no `cancelled_trips`. En 099 están definidas con esa columna.

### 1.4 Contenido reciente de `real_drill_dim_fact`

- Query 1.6: filas por grain/period_start/breakdown (sin depender de cancelled_trips).
- Query 1.7 (opcional): descomentar solo si 1.1 mostró `cancelled_trips`; muestra filas con cancelaciones no nulas.

**Resultados (rellenar tras ejecutar):**

```
[Pegar aquí salida de 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 o resumen:]
- real_drill_dim_fact columnas: ...
- mv_real_drill_dim_agg tiene cancelled_trips: sí/no
- real_margin_quality_audit existe: sí/no
- day_v2/week_v3/month_v3 tienen cancelled_trips: ...
```

---

## FASE 2 — Verificación de código y contrato backend

### A. `real_lob_drill_pro_service.py`

| Qué | Ubicación | Evidencia |
|-----|-----------|-----------|
| Constante MV drill | Línea 26 | `MV_DIM = "ops.mv_real_drill_dim_agg"` |
| get_drill: query principal por periodo | 413-423 | Query a MV_DIM **sin** cancelled_trips; luego `ad["cancelaciones"] = 0` (427-428) |
| get_drill_children: query principal (LOB/PARK/SERVICE_TYPE) | 775-793 | Query a MV_DIM **sin** cancelled_trips; luego `r["cancelaciones"] = 0` (817-818) |
| get_drill_children: query periodo anterior (WoW/MoM) | 858-875 | Misma query sin cancelled_trips; `pr["cancelaciones"] = 0` (875-876) |
| Rama SERVICE_TYPE + park_id | 691-721 | Usa MV_SERVICE_BY_PARK; no usa cancelled_trips |
| park_label en get_drill_parks | 273-277 | `p["park_label"] = f"{name} — {city} — {country}"` |
| park_label en get_drill_children (PARK) | 818-822 | `row["park_label"] = f"{name} — {city} — {country}"` |
| Uso de `cancelled_trips` en SQL | Ninguno | Grep: solo comentarios en 427 y 774 |

### B. `ops.py`

| Qué | Ubicación | Evidencia |
|-----|-----------|-----------|
| Ruta GET margin-quality (alias) | 1494 | `@router.get("/real-margin-quality")` |
| Ruta GET margin-quality (path original) | 1495 | `@router.get("/real/margin-quality")` |
| Handler | 1496-1505 | `get_real_margin_quality_endpoint` → `get_margin_quality_full(...)` |
| Import servicio | 101 | `from app.services.real_margin_quality_service import get_margin_quality_full` |
| Prefijo router | 165 | `router = APIRouter(prefix="/ops", ...)` → rutas finales: `/ops/real-margin-quality`, `/ops/real/margin-quality` |

### C. Frontend (`api.js`, componentes)

| Qué | Archivo:Línea | Evidencia |
|-----|----------------|-----------|
| Endpoint llamado por margin quality | `api.js`:479 | `api.get('/ops/real-margin-quality', ...)` |
| Timeout / catch | `api.js`:479, `RealMarginQualityCard.jsx`:26-32 | timeout 15000; catch setError |
| Card en pestaña Real | `App.jsx`:154 | `{activeTab === 'real' && <RealMarginQualityCard />}` |
| Badge "Cobertura incompleta" | `RealLOBDrillView.jsx`:651 | `affected_week_dates` / `affected_month_dates` desde getRealMarginQuality |
| Drill view llama margin-quality | `RealLOBDrillView.jsx`:111-120 | getRealMarginQuality; catch → setMarginQualityAffected vacío |

---

## FASE 3 — Verificación de runtime real

**Requisito:** Reiniciar backend (`uvicorn app.main:app --host 127.0.0.1 --port 8000`), luego ejecutar cada request y pegar **status code**, **tiempo** y, si aplica, **muestra de JSON o mensaje de error**.

| # | Request | Status | Tiempo | JSON/Error | Contrato completo |
|---|---------|--------|--------|------------|--------------------|
| 1 | GET /ops/real-lob/drill?period=week&desglose=LOB&segmento=all | | | | |
| 2 | GET /ops/real-lob/drill?period=month&desglose=PARK&segmento=all | | | | |
| 3 | GET /ops/real-lob/drill/children?country=pe&period=week&period_start=2026-03-09&desglose=LOB&segmento=all | | | | |
| 4 | GET /ops/real-lob/drill/children?country=pe&period=month&period_start=2026-02-01&desglose=PARK&segmento=all | | | | |
| 5 | GET /ops/real-lob/drill/children?country=pe&period=month&period_start=2026-03-01&desglose=SERVICE_TYPE&segmento=all | | | | |
| 6 | GET /ops/real-margin-quality?days_recent=90&findings_limit=20 | | | | |
| 7 | GET /ops/real/margin-quality?days_recent=90&findings_limit=20 | | | | |

Ejemplo de evidencia para 3 (children LOB):

```
Status: 200
Time: 2.1s
Sample: {"data":[{"dimension_key":"autos regular","viajes":12345,"cancelaciones":0,...}]}
```

Si status ≠ 200, marcar BROKEN y pegar cuerpo de error.

---

## FASE 4 — Definición correcta de cancelaciones en el drill

### Decisión explícita (a rellenar según FASE 1 y 3)

- **A.** Si `real_drill_dim_fact.cancelled_trips` **existe y está poblado** (queries 1.1, 1.6/1.7):  
  → Usar esa columna como **fuente canónica** del drill (agregar de nuevo en el servicio la selección de `cancelled_trips` desde MV_DIM y quitar el fallback 0 solo cuando la columna exista).

- **B.** Si la columna **existe pero no está poblada o es inconsistente**:  
  → Documentar que **no es fuente confiable**; mantener fallback `cancelaciones = 0` y marcar como TEMPORARY.

- **C.** Si la columna **no existe** (mig 103 no aplicada o MV sin esa columna):  
  → Fuente canónica de cancelaciones del drill: **mv_real_lob_day_v2 / mv_real_lob_week_v3** (y month_v3 si aplica), que sí tienen `cancelled_trips` (099). Reconciliación: el populate `populate_real_drill_from_hourly_chain` ya escribe desde day_v2/week_v3 a `real_drill_dim_fact`; por tanto la vía correcta es **aplicar mig 103** y **volver a ejecutar el populate** para que el drill tenga cancelaciones reales desde la cadena hourly-first.

- **D.** Mientras no haya fuente confiable en DB:  
  → Mantener **fallback `cancelaciones = 0`** en el backend y marcarlo como **TEMPORARY / NOT REAL** en documentación y en UI (tooltip o leyenda).

**Origen real decidido (rellenar tras verificación):**

```
[ ] A. real_drill_dim_fact.cancelled_trips existe y poblado → usar como canónico
[ ] B. Existe pero no confiable → temporal 0
[ ] C. No existe → aplicar 103 + populate; fuente: day_v2/week_v3
[ ] D. Fallback 0 temporal hasta tener fuente confiable
```

---

## FASE 5 — Verificación de UI y persistencia visual

Checklist (marcar tras probar en navegador):

- [ ] El drill carga sin spinner infinito
- [ ] Children expanden sin 500 (LOB, PARK, SERVICE_TYPE)
- [ ] Columnas de cancelaciones aparecen en tabla (si la UI las muestra)
- [ ] Cancelaciones mostradas son reales o se indica “0 (temporal)”
- [ ] Parks se ven como `park_name — city — country`
- [ ] Card/banner de calidad de margen aparece
- [ ] Card usa endpoint correcto (network: `/ops/real-margin-quality`)
- [ ] Badge “Cobertura incompleta” existe y se activa cuando `affected_*` tiene datos

Screenshot final o anotación: _________________

---

## FASE 6 — Reconciliación de persistencia

Tras **reiniciar el servidor**:

- [ ] Repetir requests 1–7; todos 200 (o documentar los que fallen)
- [ ] Repetir checklist UI mínima (drill + children + margin card)
- [ ] Confirmar que nada dependía de hot-reload o estado en memoria

Marcar cada cambio relevante:

- **persisted_and_working**
- **persisted_but_broken**
- **code_only_not_runtime**
- **db_exists_but_unused**
- **ui_visible_but_not_real**

---

## FASE 7 — Corrección mínima necesaria

Solo después de FASE 0–6:

1. Corregir **solo** lo necesario para dejar estable: drill, children, margin-quality, labels de park.
2. No agregar features, no rediseñar, no tocar Plan.
3. Prioridad: contrato mínimo funcionando en runtime.

---

## FASE 8 — Entrega final ejecutiva

### 1. Matriz de cambios reclamados vs reales

→ Ver tabla FASE 0; rellenar **exists_in_db** y **exists_in_runtime** con resultados de FASE 1 y 3.

### 2. Qué sí existe en DB

→ Rellenar con salida de `verify_real_drill_db.sql` (columnas, tablas, MVs).

### 3. Qué sí existe en runtime

→ Rellenar con códigos HTTP y tiempos de FASE 3.

### 4. Qué sí existe en UI

→ Rellenar con checklist FASE 5.

### 5. Qué quedó solo en código pero no funciona

→ Listar ítems con status BROKEN o code_only_not_runtime.

### 6. Origen real decidido para cancelaciones del drill

→ Rellenar decisión FASE 4.

### 7. Archivos modificados (referencia actual)

- `backend/app/services/real_lob_drill_pro_service.py` — drill sin cancelled_trips; cancelaciones=0; park_label
- `backend/app/routers/ops.py` — rutas real-margin-quality y real/margin-quality
- `frontend/src/services/api.js` — getRealMarginQuality → /ops/real-margin-quality
- `backend/scripts/verify_real_drill_db.sql` — nuevo
- `docs/REAL_MODULE_AUDIT_RUNTIME_AND_PERSISTENCE.md` — este doc

### 8. Requests reales con status

→ Tabla FASE 3 rellenada.

### 9. Checklist final de validación manual

→ FASE 5 + FASE 6 completados.

### 10. Veredicto

Criterio estricto: **no** marcar CLOSED si:

- `/ops/real-lob/drill/children` no responde 200
- margin-quality no responde o no está desactivado limpiamente en UI
- El origen de cancelaciones sigue ambiguo
- No hay evidencia de DB + runtime + UI
- Los cambios no persisten tras reinicio

- [ ] **CLOSED** — Todo verificado; drill, children, margin-quality y labels estables; persistencia confirmada.
- [ ] **PARTIALLY CLOSED** — Estable en runtime con fallbacks; pendiente DB o decisión cancelaciones.
- [ ] **NOT CLOSED** — Faltan evidencias o hay 500/404 activos.

---

*Documento generado para auditoría runtime-first y persistence-first del módulo REAL.*
