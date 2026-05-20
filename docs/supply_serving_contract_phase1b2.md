# REPORTE FINAL — FASE 1B.2 SUPPLY SERVING CONTRACT REPAIR

**Fecha**: 2026-05-19
**Fase**: Control Foundation — 1B.2 Supply Serving Contract Repair
**Estado**: **GO** (19/19 PASS)

---

## 1. Causa raíz

Las MVs `ops.mv_supply_weekly` y `ops.mv_supply_monthly`, definidas en la migración 060, **no existían en la base de datos**. La función `ops.refresh_supply_mvs()` sí existía pero apuntaba a MVs inexistentes.

Los endpoints `GET /ops/supply/series`, `/summary` y `/global/series` consultaban estas MVs. Al no existir, las queries lanzaban `UndefinedTable`. El `try/except` en `supply_service.py` capturaba el error y retornaba `[]` **silenciosamente**, sin ninguna indicación al usuario de que los datos estaban rotos.

---

## 2. Qué pasó con la migración 060

- **Existe en el repo**: `backend/alembic/versions/060_supply_mvs_and_refresh.py`
- **Está en la cadena de alembic**: aplicada antes de 063 → ... → 139 (head)
- **Estado actual**: La función `ops.refresh_supply_mvs()` existe, pero las MVs que intenta refrescar (`mv_supply_weekly`, `mv_supply_monthly`) no existen. Las MVs fueron eliminadas en algún momento posterior o el `CREATE MATERIALIZED VIEW` original falló silenciosamente.
- **Decisión**: NO se volvió a aplicar la migración 060. En su lugar, se crearon views serving que agregan desde las MVs existentes y siempre reflejan datos frescos.

---

## 3. Solución implementada (Opción B)

### Migración 140 — Supply Serving Views

| Objeto | Tipo | Descripción |
|--------|------|-------------|
| `ops.v_supply_weekly_serving` | VIEW | Agrega `mv_driver_weekly_stats` + `v_driver_weekly_churn_reactivation` + `dim.v_geo_park` por park/semana. Mismas columnas que `mv_supply_weekly` habría tenido. |
| `ops.v_supply_monthly_serving` | VIEW | Agrega `mv_driver_monthly_stats` + `dim.v_geo_park` por park/mes. Mismas columnas que `mv_supply_monthly` habría tenido. |

**Ventajas sobre MVs**:
- Siempre frescas (leen de MVs ya refrescadas por el pipeline)
- No requieren refresh adicional
- No ocupan almacenamiento duplicado
- No introducen nuevo paso en el pipeline

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/140_supply_serving_views.py` | **NUEVO** — crea 2 serving views + repara vistas de migración 075 |
| `backend/app/services/supply_service.py` | `mv_supply_weekly` → `v_supply_weekly_serving`, `mv_supply_monthly` → `v_supply_monthly_serving`. `get_supply_freshness()` usa nueva fuente + retorna `source_name`/`data_status`. |
| `backend/app/routers/ops.py` | Endpoints `/supply/series`, `/summary`, `/global/series` retornan `source_name` y `data_status`. |
| `backend/scripts/run_supply_refresh_pipeline.py` | Paso 2 reemplazado: ya no llama `ops.refresh_supply_mvs()` (roto). Verifica serving views existan y tengan datos. |

---

## 4. Endpoints validados

| Endpoint | Antes | Ahora |
|----------|-------|-------|
| `GET /ops/supply/series` | Retornaba `[]` silenciosamente (MV no existe) | Retorna 20+ filas con `source_name` y `data_status: ok` |
| `GET /ops/supply/summary` | Retornaba `{periods_count: 0}` silenciosamente | Retorna `{periods_count: 7, source_name: "...", data_status: "ok"}` |
| `GET /ops/supply/global/series` | Retornaba `[]` silenciosamente | Retorna 20+ filas con `source_name` y `data_status: ok` |
| `GET /ops/supply/freshness` | Usaba `mv_supply_segments_weekly` para freshness (inconsistente) | Usa `v_supply_weekly_serving` + `source_name` + `data_status` |

---

## 5. Evidencia de no más [] silencioso

- `get_supply_series(park, "2026-01-01", "2026-06-30", "weekly")` → **20 rows** (antes: 0 rows)
- `get_supply_summary(park, "2026-04-01", "2026-06-30", "weekly")` → **periods=7** (antes: 0)
- `get_supply_global_series("2026-01-01", "2026-06-30", "weekly")` → **20 rows** (antes: 0)
- `get_supply_series(park, ..., "monthly")` → **14 rows**
- `get_supply_freshness()` → `source_name: "ops.v_supply_weekly_serving"`, `data_status: "ok"`

---

## 6. refresh_run_log + /ops/refresh/status

- `run_supply_refresh_pipeline.py` usa `refresh_guard` que registra en `ops.refresh_run_log`
- Paso 2 verifica las serving views y loguea max week_start y max month_start
- `/ops/refresh/status?refresh_name=supply_refresh_pipeline` muestra el estado real

---

## 7. Tests ejecutados

**19/19 PASS** — script `_validate_supply_serving_phase1b2.py`:

| # | Test | Resultado |
|---|------|-----------|
| 1.1-1.5 | Serving views existen, tienen datos frescos (431 filas en 2026) | PASS |
| 2.1-2.4 | Endpoints retornan datos reales (20 weekly, 7 periods, 20 global, 14 monthly) | PASS |
| 3.1-3.3 | Freshness devuelve source_name + data_status correctos | PASS |
| 4.1 | Supply pipeline registrado en refresh_run_log | PASS |
| 5.1-5.2 | Endpoints son read-only (sin REFRESH/INSERT/DELETE/DROP) | PASS |
| 6.1-6.2 | Pipeline verifica serving views, no llama refresh_supply_mvs roto | PASS |
| 7.1 | mv_supply_segments_weekly intacto (22 parks) | PASS |
| 8.1 | Omniview sin cambios | PASS |

---

## 8. Riesgos pendientes

| Riesgo | Fase |
|--------|------|
| Full refresh histórico (C1) | Fase 1D |
| Closed period protection | Fase 1D |
| Business Slice mapping audit (hallazgo Bogotá) | Fase 1C |
| `ops.refresh_supply_mvs()` es función legacy que apunta a MVs inexistentes | Mantener documentado; no se usa |

---

## 9. Recomendación para cerrar Fase 1B

Con la resolución de C3 (este fix) + C2 (advisory locks) + C4 (ledger/status endpoint) + C5 (DROP guardrail):

- **Fase 1B queda GO para producción** con `CT_SCHEDULER_ENABLED=false` y `CT_ALLOW_DESTRUCTIVE_REFRESH=false`.
- La validación staging ahora pasa 74/76 (los 2 fallos de C3 están resueltos).

### Comandos de deploy

```bash
cd backend

# 1. Aplicar migración 140
alembic upgrade head

# 2. Verificar serving views
python -c "
from app.db.connection import get_db
with get_db() as conn:
    cur = conn.cursor()
    cur.execute('SELECT MAX(week_start) FROM ops.v_supply_weekly_serving')
    print('Weekly max:', cur.fetchone()[0])
    cur.execute('SELECT MAX(month_start) FROM ops.v_supply_monthly_serving')
    print('Monthly max:', cur.fetchone()[0])
    cur.close()
"

# 3. Verificar endpoints
curl http://localhost:8000/ops/supply/series?park_id=PARK_ID&from=2026-01-01&to=2026-06-30
curl http://localhost:8000/ops/supply/freshness
curl http://localhost:8000/ops/refresh/status?refresh_name=supply_refresh_pipeline
```

---

## 10. Siguiente fase recomendada

**Fase 1C — Business Slice Mapping Coverage & Contract Audit**

- Auditar reglas de business_slice por park/LOB/tipo_servicio (hallazgo Bogotá)
- Verificar que todos los viajes completados caen en una tajada correcta
- Validar cobertura de mapeo park → business slice en todos los países
- Preparar base para Fase 1D: Closed Period Protection
