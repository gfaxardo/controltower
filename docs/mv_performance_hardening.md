# MV Performance Hardening — CT-MV-PERFORMANCE-HARDENING

**YEGO CONTROL TOWER — Fase CT-MV-PERFORMANCE-HARDENING**

## Objetivo

Eliminar timeouts y refreshes lentos en Materialized Views críticas del sistema (`ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2`), mejorando:

- **Performance**: índices, ventana de cálculo reducida, memoria de sesión.
- **Refresh strategy**: `REFRESH MATERIALIZED VIEW CONCURRENTLY` cuando la MV ya tiene datos.
- **Observabilidad**: registro de cada refresh con `rows_before`, `rows_after`, `duration_seconds`.
- **Resiliencia**: timeout 6h, work_mem 512MB, maintenance_work_mem 1GB.

La solución es **aditiva y segura**: no se borran MVs, no se cambian contratos de API ni queries existentes.

---

## Problema original

- Refreshes de las MVs de Real LOB v2 podían superar el timeout (p. ej. 3h o 2h).
- Sin ventana de cálculo: se recalculaba todo el histórico en cada refresh.
- Observabilidad limitada: no se registraban filas ni duración para detectar degradación.

---

## Solución aplicada

### 1. Detección de MVs pesadas (STEP 1–2)

Script: `backend/scripts/detect_heavy_mvs.py`

- Escanea MVs en `ops`, `bi`, `plan`.
- Salida: tabla con `mv_name`, `schema`, `estimated_rows`, `source_tables`, `refresh_cost_estimate`, `risk_level`.
- MVs críticas confirmadas: `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2`.

Uso:

```bash
cd backend && python scripts/detect_heavy_mvs.py
```

### 2. Índices (STEP 3–4)

- **Índices UNIQUE** ya existían (`uq_mv_real_lob_month_v2`, `uq_mv_real_lob_week_v2`) y permiten `REFRESH CONCURRENTLY`.
- **Índices de consulta** añadidos (migración 095):
  - `idx_mv_real_lob_week_lookup` en `ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)`
  - `idx_mv_real_lob_month_lookup` en `ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)`

### 3. Session performance (STEP 5)

Antes de cada refresh se aplica:

- `work_mem = '512MB'`
- `maintenance_work_mem = '1GB'`
- `statement_timeout = '6h'` (21_600_000 ms)

Reducen spills en disco y evitan timeouts prematuros.

### 4. Ventana de cálculo 120 días (STEP 6)

Migración **096**: las MVs críticas se recrean con:

```sql
WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
```

en la CTE `base`. El refresh pasa de varias horas a unos minutos. El histórico fuera de 120 días no se recalcula (ventana fija).

### 5. Observabilidad (STEP 7)

- Tabla `ops.observability_refresh_log` ampliada con:
  - `rows_before`, `rows_after`, `duration_seconds`
- Los scripts de refresh (`close_real_lob_governance.py`, `refresh_real_lob_mvs_v2.py`) registran cada ejecución con estos campos.

Consulta reciente:

```sql
SELECT artifact_name, refresh_started_at, refresh_finished_at, refresh_status,
       rows_before, rows_after, duration_seconds, error_message
FROM ops.observability_refresh_log
WHERE artifact_name LIKE 'ops.mv_real_lob%'
ORDER BY refresh_started_at DESC
LIMIT 10;
```

### 6. Pipeline seguro de refresh (STEP 8)

**Script principal:** `backend/scripts/close_real_lob_governance.py`

- Orden: 1) refresh monthly, 2) refresh weekly, 3) validación de rowcount, 4) log en observabilidad.
- Opciones:
  - `--skip-refresh`: no refresca; solo inspección y validación.
  - `--only-month`: solo `ops.mv_real_lob_month_v2`.
  - `--only-week`: solo `ops.mv_real_lob_week_v2`.
  - `--refresh-only`: solo refresh (sin cambiar resto del flujo).

Variables de entorno:

- `REAL_LOB_REFRESH_TIMEOUT_MS` (default 21600000 = 6h)
- `REAL_LOB_REFRESH_WORK_MEM` (default 512MB)
- `REAL_LOB_REFRESH_MAINTENANCE_WORK_MEM` (default 1GB)

---

## Cómo refrescar

Desde `backend/`:

```bash
# Cierre completo (inspección + refresh monthly + weekly + validación)
python scripts/close_real_lob_governance.py

# Solo refresh de MVs
python scripts/close_real_lob_governance.py --refresh-only

# Solo monthly o solo weekly
python scripts/close_real_lob_governance.py --only-month
python scripts/close_real_lob_governance.py --only-week

# Sin refresh (solo comprobaciones)
python scripts/close_real_lob_governance.py --skip-refresh
```

Alternativa (solo MVs v2, mismo orden y observabilidad):

```bash
python -m scripts.refresh_real_lob_mvs_v2
```

---

## Cómo detectar degradación

1. **Log de refresh**  
   Revisar `ops.observability_refresh_log`: si `duration_seconds` sube de forma sostenida o `refresh_status = 'error'`, investigar (tamaño de datos, locks, tiempo de plan).

2. **Conteos**  
   Comparar `rows_before` / `rows_after` entre ejecuciones; caídas bruscas pueden indicar filtros o datos fuente.

3. **Validación manual (STEP 9)**  
   Comprobar que los conteos son coherentes con la vista base:

   ```sql
   SELECT COUNT(*) FROM ops.mv_real_lob_month_v2;
   SELECT COUNT(*) FROM ops.mv_real_lob_week_v2;
   ```

   Y para medir tiempo de plan/ejecución:

   ```sql
   EXPLAIN ANALYZE SELECT COUNT(*) FROM ops.mv_real_lob_month_v2;
   EXPLAIN ANALYZE SELECT COUNT(*) FROM ops.mv_real_lob_week_v2;
   ```

4. **Detección de MVs pesadas**  
   Ejecutar de forma periódica:

   ```bash
   python scripts/detect_heavy_mvs.py
   ```
   para ver riesgo y tamaño estimado de todas las MVs en ops/bi/plan.

---

## Resultado esperado

Tras aplicar esta fase:

- Refresh sin timeouts (ventana 120d + timeout 6h).
- Refresh concurrente cuando la MV ya está poblada.
- Observabilidad completa (filas y duración en `observability_refresh_log`).
- Índices correctos (UNIQUE para CONCURRENTLY + lookup por tipo de servicio).
- Ventana de cálculo optimizada (120 días).

---

## Migraciones

- **095**: Índices de lookup en las dos MVs; columnas `rows_before`, `rows_after`, `duration_seconds` en `observability_refresh_log`.
- **096**: Recreación de `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` con filtro `fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'`.

Si se hace downgrade de 096, las MVs vuelven a la definición sin ventana (histórico completo).

## Causa raíz y guardrails (098+)

A partir de la migración **098** (CT-REAL-LOB-ROOT-CAUSE-FIX) se corrige el cuello de botella en la capa base: índices sobre `fecha_inicio_viaje` en `trips_all`/`trips_2026` y vistas _120d que aplican el filtro en cada rama del UNION. Ver:

- `docs/real_lob_root_cause_diagnosis.md` — diagnóstico
- `docs/real_lob_execution_plan_validation.md` — validación del plan
- `docs/query_performance_guardrails.md` — reglas para futuras migraciones
- `docs/migration_performance_checklist.md` — checklist de performance
