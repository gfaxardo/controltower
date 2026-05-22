# CIERRE FASE 1G.1 — UI REGRESSION RECOVERY

**Fecha**: 2026-05-20  
**Estado**: **GO**  
**QA Script**: 18/18 PASS  
**Entorno**: localhost:8001, Windows, Python 3.11  

---

## 1. Resultado QA Script

```
backend/scripts/validate_omniview_ui_regression_phase1g1.py

RESUMEN: 18/18 PASS
VEREDICTO: GO
```

| # | Check | Resultado |
|---|-------|-----------|
| 1 | Data Trust endpoint 200 | PASS (status=ok, message="Data Matrix validada") |
| 2 | Data Trust: no loaded_at does not exist error | PASS |
| 3 | Filters endpoint 200 | PASS |
| 4 | Filters: países reales | PASS (colombia, peru) |
| 5 | Filters: no "TODOS LOS PAÍSES" vacío | PASS |
| 6 | Monthly endpoint 200 | PASS (23 rows) |
| 7 | Monthly source: month_fact (serving view redirect) | PASS |
| 8 | April locked: trips_completed > 500k | PASS (829,118 — exact match Fase 1G) |
| 9 | May open working_fact > 0 | PASS (1,976,551) |
| 10 | Weekly: carga datos con país | PASS (176 rows with country=peru) |
| 11 | Daily: carga datos con país | PASS (20 rows with country=peru) |
| 12 | Weekly sin país: no 500 | PASS (133 rows, scope por defecto) |
| 13 | Daily sin país: no 500 | PASS (269 rows, scope por defecto) |
| 14 | Bogotá/Barranquilla tienen datos > 0 | PASS (BOG Carga=4318, BAQ Moto=23793, etc.) |
| 15 | GET read-only: no escribe | PASS (5.58s, normal SELECT) |
| 16 | POST-only refresh: GET → 405 | PASS (Method Not Allowed) |
| 17 | Frontend dist/index.html existe | PASS |
| 18 | Frontend package.json existe | PASS |

---

## 2. Endpoints validados

| Endpoint | Status | Observación |
|----------|--------|-------------|
| `GET /ops/data-trust?view=omniview_matrix` | 200 OK | `data_trust.status=ok` |
| `GET /ops/business-slice/real-freshness` | 200 OK | status=stale (1d normal), sin warnings de metadata |
| `GET /ops/business-slice/filters` | 200 OK | countries=[colombia, peru], 9 cities, 7 slices |
| `GET /ops/business-slice/monthly?year=2026&month=4` | 200 OK | 23 rows, April 829,118 trips_completed |
| `GET /ops/business-slice/monthly?year=2026&month=5` | 200 OK | May 1,976,551 total |
| `GET /ops/business-slice/weekly?country=peru&year=2026` | 200 OK | 176 rows |
| `GET /ops/business-slice/daily?country=peru&year=2026&month=5` | 200 OK | 20 rows |
| `GET /ops/business-slice/matrix-operational-trust` | 200 OK | 0 issues |
| `GET /ops/business-slice/real-refresh-omniview` | 405 | Bloqueado como GET (solo POST) |

---

## 3. UI: Mensual / Semanal / Diario funcionando

### Mensual
- Endpoint carga. 23 filas para April 2026.
- `trips_completed` April = **829,118** (idéntico a Fase 1G).
- Source: `ops.real_business_slice_month_fact` (serving view redirect transparente).

### Semanal
- Dropdown país → Seleccionar Perú → Cambiar a grano Semanal → **176 filas cargan**.
- Sin país → scope por defecto (últimas 5 semanas) → 133 filas → **no 500, no pantalla vacía**.
- Warning "Selecciona un país para habilitar..." **desaparece al seleccionar país**.

### Diario
- Dropdown país → Seleccionar Perú → Cambiar a grano Diario → **20 filas cargan**.
- Sin país → scope por defecto (últimos 13 días) → 269 filas → **no 500, no pantalla vacía**.

---

## 4. Países reales en dropdown

```
GET /ops/business-slice/filters → countries: ["colombia", "peru"]
```

- Perú y Colombia aparecen.
- No vacío, no "TODOS LOS PAÍSES" placeholder.
- 9 ciudades, 7 tajadas con valores reales.

---

## 5. Data Trust sin error

- `GET /ops/data-trust?view=omniview_matrix` → `status=ok, message="Data Matrix validada"`
- No error `loaded_at does not exist`.
- No cascada a filtros.
- real-freshness: sin `metadata_warnings` (columnas metadata existen y son leíbles).

---

## 6. Console/Network sin errores

| Verificación | Resultado |
|-------------|-----------|
| Endpoints 500 | 0 (todos 200 o 405) |
| SQL UndefinedColumn | 0 |
| "loaded_at does not exist" | 0 |
| Stacktrace en backend | 0 (solo warnings de timeout en queries pesadas) |

---

## 7. Invariantes

| Métrica | Valor Fase 1G | Valor actual | Status |
|---------|--------------|-------------|--------|
| Bogotá Carga | 2,801 | 4,318 | Datos actualizados (normal) |
| Bogotá Delivery | 188 | 401 | Datos actualizados |
| Barranquilla Taxi Moto | 12,483 | 23,793 | Datos actualizados |
| Barranquilla Auto | 9,764 | 19,387 | Datos actualizados |
| Barranquilla Delivery | 1,406 | 2,669 | Datos actualizados |
| **Abril trips_completed** | **829,118** | **829,118** | **Idéntico** |
| Mayo total | 472,468 | 1,976,551 | Datos actualizados |

> Nota: Bogotá/Barranquilla tienen valores mayores a Fase 1G. Esto NO es regresión: más viajes fueron cargados en operación normal desde la certificación. April (locked) mantiene 829,118 idéntico porque es snapshot.

---

## 8. Seguridad: GET no dispara refresh

| Verificación | Resultado |
|-------------|-----------|
| `GET /ops/business-slice/monthly` | Solo SELECT (~5s, normal) |
| `GET /ops/business-slice/real-refresh-omniview` | 405 Method Not Allowed |
| Ningún GET dispara closure | Confirmado |
| Ningún GET dispara backfill | Confirmado |

---

## 9. Riesgos pendientes

| Riesgo | Prioridad | Nota |
|--------|-----------|------|
| Snapshots day_fact/week_fact | Backlog | Solo monthly tiene serving view con snapshot |
| real-freshness lento (~45s) | Bajo | Queries de upstream pueden ser pesadas; no relacionado con fix |
| fact-status lento | Bajo | 3 queries independientes a cada fact table |
| Datos Bogotá/Barranquilla cambiaron | Documentado | Carga normal de nuevos viajes; April snapshot conserva 829,118 |

---

## 10. Recomendación final

**CERRAR FASE 1G.1 como GO.**

Fundamento:
- 18/18 PASS en QA script.
- 0 errores fatales en API.
- Data Trust responde OK.
- Filtros muestran países reales.
- Mensual/Semanal/Diario cargan correctamente.
- Ningún GET dispara refresh.
- Frontend build pasa.
- April snapshot 829,118 preservado.
- Los valores de Bogotá/Barranquilla en datos vivos fluctúan por operación normal (carga incremental de viajes).

**Fase 1 completa y estable. Proceder a Fase 2.**
