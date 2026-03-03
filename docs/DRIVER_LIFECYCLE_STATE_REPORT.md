# Driver Lifecycle — STATE REPORT & NEXT STEPS

**Proyecto:** YEGO CONTROL TOWER  
**Módulo:** Driver Lifecycle (Postgres MVs + Python + API/UI)  
**Fecha reporte:** 2026-03-02  
**Trazabilidad:** rutas y queries reales del repo; sin inventar columnas.

---

## A) STATE REPORT (1 página)

### Entorno local (FASE 0)

| Item | Estado |
|------|--------|
| **Raíz proyecto** | `c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER` |
| **Backend** | `backend/` (venv y .venv presentes; **logs/** creado en esta sesión) |
| **Requirements** | `backend/requirements.txt` (psycopg2-binary, fastapi, etc.) |
| **DRIVER_LIFECYCLE_REFRESH_MODE** | No set (default: `concurrently`) |
| **DRIVER_LIFECYCLE_TIMEOUT_MINUTES** | No set (default: 60) |
| **DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES** | No set (default: 5) |
| **DRIVER_LIFECYCLE_FALLBACK_NONC** | No set (default: true) |
| **.env raíz** | Existe pero vacío (1 línea) |

- Diagnóstico (solo lectura): ejecutar desde **backend** y guardar salida:
  - `cd backend && python -m scripts.check_driver_lifecycle_and_validate --diagnose`
  - Redirigir a `backend/logs/driver_lifecycle_diagnose_YYYYMMDD.log` (crear carpeta `logs` si no existe).

---

### DB objects (inventario a completar en BD)

- **Listado MVs ops:**  
  `SELECT schemaname, matviewname FROM pg_matviews WHERE schemaname='ops' ORDER BY 2;`
- **Conteos:** ejecutar cada query del archivo  
  `backend/sql/driver_lifecycle_inventory.sql`  
  (si una MV no existe, anotar "NO existe" para esa fila).
- **Funciones refresh:**  
  `SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ops' AND p.proname ILIKE '%refresh_driver_lifecycle%';`
- **Columnas inspeccionadas (information_schema):**  
  Tablas: `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`, `ops.mv_driver_lifecycle_weekly_kpis`.  
  Reportar columnas reales: driver_key, last_completed_ts, activation_ts, park_id, period (week_start / month_start) según salida del inventario.
- **Freshness:**  
  `SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base;` (si existe la MV).
- **Park quality:**  
  `SELECT COUNT(DISTINCT park_id) FROM ops.mv_driver_weekly_stats;`  
  `SELECT COUNT(*) FILTER (WHERE park_id IS NULL)::float/NULLIF(COUNT(*),0) FROM ops.mv_driver_weekly_stats;`
- **Viewdefs:** usar `pg_get_viewdef('ops.mv_driver_lifecycle_base'::regclass, true)` (y análogo para weekly_stats, weekly_kpis) y guardar en `backend/logs/` para auditoría.

*Nota: sin conexión a la BD en esta máquina no se pueden rellenar aquí los valores (conteos, freshness, % park null). Ejecutar el script de inventario y pegar resultados en este apartado.*

---

### Scripts y estado (repo)

| Script | Ruta real | Última modificación (git) |
|--------|-----------|----------------------------|
| check_driver_lifecycle_and_validate | `backend/scripts/check_driver_lifecycle_and_validate.py` | 2026-03-01 |
| diagnose_pg_timeouts | `backend/scripts/diagnose_pg_timeouts.py` | 2026-03-01 |
| refresh_driver_lifecycle | `backend/scripts/refresh_driver_lifecycle.py` | presente |
| apply_driver_lifecycle_v2 | `backend/scripts/apply_driver_lifecycle_v2.py` | 2026-03-01 |

- **apply_driver_lifecycle_v2** referencia:  
  `backend/sql/driver_lifecycle_hardening_v2.sql`,  
  `backend/sql/driver_lifecycle_consistency_validation.sql`,  
  `backend/sql/driver_lifecycle_indexes_and_analyze.sql`,  
  `backend/sql/driver_lifecycle_cohort_indexes.sql`,  
  `backend/sql/driver_lifecycle_cohorts.sql`,  
  `backend/sql/driver_lifecycle_refresh_with_cohorts.sql`,  
  `backend/sql/driver_lifecycle_refresh_timed.sql`,  
  `backend/sql/driver_lifecycle_park_quality.sql`,  
  `backend/scripts/sql/driver_lifecycle_cohort_validation.sql`,  
  y rollback en `backend/sql/rollback/restore_driver_lifecycle_v1.sql`.

---

### SQLs (repo)

| Archivo | Existe | Referenciado por apply_v2 |
|---------|--------|----------------------------|
| backend/sql/driver_lifecycle_refresh_hardening.sql | Sí | No (hardening usa hardening_v2) |
| backend/sql/driver_lifecycle_hardening_v2.sql | Sí | Sí |
| backend/sql/driver_lifecycle_consistency_validation.sql | Sí | Sí |
| backend/sql/driver_lifecycle_cohorts.sql | Sí | Sí |
| backend/sql/driver_lifecycle_indexes_and_analyze.sql | Sí | Sí |
| backend/sql/driver_lifecycle_cohort_indexes.sql | Sí | Sí |
| backend/scripts/sql/driver_lifecycle_cohort_validation.sql | Sí | Sí |
| backend/sql/driver_lifecycle_inventory.sql | Sí (nuevo) | No (solo inventario) |

---

### Endpoints API (FastAPI)

- **Prefix:** `/ops/driver-lifecycle`  
- **Archivo:** `backend/app/routers/driver_lifecycle.py`  
- **Inclusión:** `backend/app/main.py` → `app.include_router(driver_lifecycle.router)`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /ops/driver-lifecycle/weekly, /weekly-kpis | KPIs semanales (from, to, park_id opcional) |
| GET | /ops/driver-lifecycle/monthly, /monthly-kpis | KPIs mensuales |
| GET | /ops/driver-lifecycle/drilldown, /kpi-drilldown | Drilldown por period_start, park_id, metric |
| GET | /ops/driver-lifecycle/base-metrics | time_to_first_trip, lifetime_days (avg/median) |
| GET | /ops/driver-lifecycle/base-metrics-drilldown | Lista drivers por métrica base y park |
| GET | /ops/driver-lifecycle/parks-summary | Ranking parks (activations, churn_rate, net_growth, FT/PT) |
| GET | /ops/driver-lifecycle/parks | Lista park_id para selector (incl. PARK_DESCONOCIDO) |
| GET | /ops/driver-lifecycle/cohorts | KPIs cohortes (from_cohort_week, to_cohort_week, park_id opcional) |
| GET | /ops/driver-lifecycle/cohort-drilldown | Lista driver_key por cohort_week, horizon, park_id |

---

### UI / Views

- **Vista:** `frontend/src/components/DriverLifecycleView.jsx`  
- **Ruta en app:** `App.jsx` → tab `driver_lifecycle`, componente `<DriverLifecycleView />`.  
- **API usada:** `frontend/src/services/api.js` (getDriverLifecycleWeekly, Monthly, Drilldown, ParksSummary, ParksList, BaseMetrics, BaseMetricsDrilldown, Cohorts, CohortDrilldown) contra base URL + `/ops/driver-lifecycle/...`.  
- **Funcionalidad:** Filtros From/To, Park (multi-select), Weekly/Monthly; bloque KPI + desglose por park; celdas clickeables abren modal con lista de drivers (drilldown). Cohortes: rango y park; mensaje si no hay cohortes sugiere ejecutar `apply_driver_lifecycle_v2`.

---

### Último freshness y calidad park

- **Freshness:** rellenar tras ejecutar  
  `SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base;`  
- **Parks distintos:**  
  `SELECT COUNT(DISTINCT park_id) FROM ops.mv_driver_weekly_stats;`  
- **% park_id NULL:**  
  `SELECT COUNT(*) FILTER (WHERE park_id IS NULL)::float/NULLIF(COUNT(*),0)*100 FROM ops.mv_driver_weekly_stats;`  

*(Valores a completar con salida real del inventario en BD.)*

---

## B) NEXT STEPS (máximo 8, con comandos exactos)

1. **Crear carpeta de logs y fijar ENV (opcional pero recomendado)**  
   - Objetivo: tener logs trazables y timeouts explícitos.  
   - Comandos:  
     - `mkdir backend\logs` (o `New-Item -ItemType Directory -Path backend\logs`)  
     - En `.env` del backend (o variables de entorno) definir si se desea:  
       `DRIVER_LIFECYCLE_REFRESH_MODE=concurrently`,  
       `DRIVER_LIFECYCLE_TIMEOUT_MINUTES=60`,  
       `DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES=5`,  
       `DRIVER_LIFECYCLE_FALLBACK_NONC=1`.  
   - Éxito: carpeta `backend/logs` existe; variables visibles en diagnóstico (sin imprimir secretos).

2. **Ejecutar diagnóstico (solo lectura)**  
   - Objetivo: ver timeouts, locks y REFRESH en curso.  
   - Comando:  
     `cd backend && python -m scripts.check_driver_lifecycle_and_validate --diagnose`  
   - Redirigir salida a `backend/logs/driver_lifecycle_diagnose_YYYYMMDD.log`.  
   - Éxito: exit code 0; log con statement_timeout, lock_timeout, pg_stat_activity y locks.

3. **Ejecutar inventario SQL en la BD**  
   - Objetivo: estado real de MVs, conteos, columnas, freshness, park quality.  
   - Comando: ejecutar cada bloque de  
     `backend/sql/driver_lifecycle_inventory.sql`  
     contra la base (psql, DBeaver o script que use connection string del backend).  
   - Éxito: listado de MVs en ops, conteos por MV, columnas de base/weekly_stats/weekly_kpis, MAX(last_completed_ts), COUNT(DISTINCT park_id), % NULL. Anotar "NO existe" donde falle la query.

4. **Validar refresh y validaciones (no destructivo)**  
   - Objetivo: confirmar que el check completo (refresh + validaciones) funciona.  
   - Comando:  
     `cd backend && python -m scripts.check_driver_lifecycle_and_validate`  
     (sin `--diagnose`).  
   - Éxito: modo refresh indicado, duración mostrada, conteos, unicidad OK, freshness mostrado, parks distintos y park null share sin fallo de validación (exit 0). Si falla por timeout/lock, revisar paso 1 y 2.

5. **Confiabilidad: timeouts y locks**  
   - Objetivo: que statement_timeout y lock_timeout no queden en 15s por rol/db.  
   - Comando:  
     `cd backend && python -m scripts.diagnose_pg_timeouts`  
     (si existe y está documentado en backend/docs/PG_TIMEOUTS_DIAGNOSTICO.md).  
   - Éxito: diagnóstico indica que los SET de la sesión aplican o se identifica quién fuerza 15s (rol, db, config).

6. **Calidad de datos: freshness y park null**  
   - Objetivo: vigilar freshness y % park_id NULL &lt; umbral (ej. 5%).  
   - Comando:  
     `cd backend && python -m scripts.audit_driver_lifecycle_freshness`  
     (si existe). O usar salida del paso 3/4.  
   - Éxito: MAX(last_completed_ts) reciente; % NULL por debajo del umbral o plan de corrección definido.

7. **Consistencia matemática (Σ park = global)**  
   - Objetivo: que las validaciones de consistency no devuelvan filas con diff.  
   - Comando: no ejecutar apply completo; si ya se aplicó v2, ejecutar solo las queries de  
     `backend/sql/driver_lifecycle_consistency_validation.sql`  
     (los 4 bloques WITH ... diff).  
   - Éxito: ningún resultado con diff; si hay filas, investigar y corregir antes de más despliegues.

8. **Cohortes y producto (API/UI)**  
   - Objetivo: si se quieren cohortes, desplegar MVs de cohortes y validar API/UI.  
   - Comando (solo si se decide desplegar y no hay riesgo destructivo):  
     `cd backend && python -m scripts.apply_driver_lifecycle_v2`  
     (hace preflight, hardening_v2, consistency, quality gates, índices, cohortes, refresh con cohortes).  
   - Éxito: apply termina con exit 0; cohort validation OK; endpoints /cohorts y /cohort-drilldown devuelven datos; UI de cohortes muestra datos. Si no se desea aplicar aún, limitarse a verificar que los SQLs referenciados existen (ya inventariado en este reporte).

---

**Resumen trazable**

- **DB:** inventario con `backend/sql/driver_lifecycle_inventory.sql` + queries indicadas en este documento.  
- **Scripts:** `backend/scripts/` (check, diagnose, refresh, apply_v2).  
- **SQLs:** `backend/sql/` y `backend/scripts/sql/` según tabla anterior.  
- **API:** `backend/app/routers/driver_lifecycle.py`, prefix `/ops/driver-lifecycle`.  
- **UI:** `frontend/src/components/DriverLifecycleView.jsx`, tab `driver_lifecycle` en App.

No se ha ejecutado nada destructivo; los pasos 3–4 y 7–8 requieren conexión a la BD y, en el caso del apply, decisión explícita de despliegue.
