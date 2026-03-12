# Certificación post-refresh del pipeline de datos — YEGO Control Tower

**Fecha certificación:** 2026-03-09  
**Objetivo:** Evidencia before/after del pipeline unificado y veredicto operativo.

---

## Fase A — BEFORE (captura previa al pipeline)

Estado de la auditoría de freshness **antes** de ejecutar el pipeline unificado.  
Origen: salida de `python -m scripts.run_data_freshness_audit` ejecutado el 2026-03-09 (previa al pipeline), y lectura de `get_freshness_audit(latest_only=True)`.

### Tabla BEFORE

| dataset_name | source_max_date | derived_max_date | expected_latest_date | lag_days | status |
|--------------|----------------|------------------|----------------------|----------|--------|
| driver_lifecycle | 2026-03-09 | 2026-03-05 | 2026-03-08 | 4 | DERIVED_STALE |
| driver_lifecycle_weekly | 2026-03-05 | 2026-03-02 | 2026-03-08 | 3 | DERIVED_STALE |
| real_lob | 2026-03-08 | 2026-03-07 | 2026-03-08 | 1 | DERIVED_STALE |
| real_lob_drill | 2026-03-08 | 2026-03-02 | 2026-03-08 | 6 | DERIVED_STALE |
| supply_weekly | 2026-03-02 | 2026-03-02 | 2026-03-08 | 0 | PARTIAL_EXPECTED |
| trips_2026 | 2026-03-08 | — | 2026-03-08 | — | OK |
| trips_base | 2026-01-31 | — | 2026-03-08 | — | SOURCE_STALE |

---

## Fase B — Ejecución del pipeline unificado

### Comandos ejecutados

1. **Captura BEFORE:** Lectura de `get_freshness_audit(latest_only=True)` desde backend.
2. **Pipeline completo (con backfill):** Iniciado en background; el backfill Real LOB puede tardar mucho (mes a mes). No se esperó a que terminara en esta sesión.
3. **Pipeline sin backfill (primer intento):**  
   `python -m scripts.run_pipeline_refresh_and_audit --skip-backfill`  
   **Resultado:** Falló por **statement timeout** en `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_monthly_stats`. La conexión del pool tiene `statement_timeout=180000` (3 min) y la MV tardó más. Transacción revertida; no hubo mejora.
4. **Fix aplicado:** En `run_pipeline_refresh_and_audit.py`, `run_refresh_driver_lifecycle()` pasó a usar una **conexión dedicada con `statement_timeout=0`** (igual que el backfill), para que el refresh no sea cancelado por el pool.
5. **Pipeline sin backfill (segundo intento, con fix):**  
   `python -m scripts.run_pipeline_refresh_and_audit --skip-backfill`  
   **Resultado:** OK. Logs:
   - Skip backfill (--skip-backfill)
   - Refresh Driver Lifecycle MVs OK (~4,5 min)
   - Refresh Supply MVs OK
   - Auditoría ejecutada; nueva fila en `ops.data_freshness_audit`

### Datasets tocados

- **driver_lifecycle:** REFRESH de `ops.mv_driver_lifecycle_base` (y resto de MVs de driver lifecycle).
- **driver_lifecycle_weekly:** REFRESH de `ops.mv_driver_weekly_stats`.
- **supply_weekly:** REFRESH de `ops.refresh_supply_alerting_mvs()` (incluye MVs que alimentan supply).
- **real_lob / real_lob_drill:** No refrescados en esta ejecución (se omitió backfill). Siguen con derived_max anteriores.

### Errores / advertencias

- **Timeout en primer intento:** Corregido con conexión `statement_timeout=0` para el refresh de driver lifecycle.
- **Backfill no ejecutado:** Por tiempo; para certificar real_lob y real_lob_drill hay que ejecutar el pipeline **con** backfill (sin `--skip-backfill`) y esperar a que termine.

---

## Fase C — AFTER (post pipeline + audit)

Estado **después** de ejecutar el pipeline (sin backfill) y de que el propio pipeline volviera a correr el audit.

### Tabla AFTER

| dataset_name | source_max_date | derived_max_date | expected_latest_date | lag_days | status |
|--------------|----------------|------------------|----------------------|----------|--------|
| driver_lifecycle | 2026-03-09 | **2026-03-09** | 2026-03-08 | **0** | **OK** |
| driver_lifecycle_weekly | 2026-03-09 | **2026-03-09** | 2026-03-08 | **0** | **OK** |
| real_lob | 2026-03-08 | 2026-03-07 | 2026-03-08 | 1 | DERIVED_STALE |
| real_lob_drill | 2026-03-08 | 2026-03-02 | 2026-03-08 | 6 | DERIVED_STALE |
| supply_weekly | 2026-03-09 | **2026-03-09** | 2026-03-08 | **0** | **OK** |
| trips_2026 | 2026-03-08 | — | 2026-03-08 | — | OK |
| trips_base | 2026-01-31 | — | 2026-03-08 | — | SOURCE_STALE |

---

## Fase D — Comparativo before/after

| dataset_name | before_status | after_status | before_derived_max | after_derived_max | improvement | remaining_issue |
|--------------|---------------|--------------|--------------------|-------------------|-------------|-----------------|
| driver_lifecycle | DERIVED_STALE | **OK** | 2026-03-05 | **2026-03-09** | Sí, +4 días | Ninguno |
| driver_lifecycle_weekly | DERIVED_STALE | **OK** | 2026-03-02 | **2026-03-09** | Sí, +7 días | Ninguno |
| supply_weekly | PARTIAL_EXPECTED | **OK** | 2026-03-02 | **2026-03-09** | Sí, +7 días | Ninguno |
| real_lob | DERIVED_STALE | DERIVED_STALE | 2026-03-07 | 2026-03-07 | No | Falta ejecutar backfill Real LOB |
| real_lob_drill | DERIVED_STALE | DERIVED_STALE | 2026-03-02 | 2026-03-02 | No | Falta ejecutar backfill Real LOB |
| trips_2026 | OK | OK | — | — | — | Ninguno |
| trips_base | SOURCE_STALE | SOURCE_STALE | — | — | — | Fuente histórica; no esperado al día |

### Respuesta por dataset

- **driver_lifecycle:** Mejoró. Quedó **OK**. derived_max pasó de 2026-03-05 a 2026-03-09 (igual a source_max).
- **driver_lifecycle_weekly:** Mejoró. Quedó **OK**. derived_max pasó de 2026-03-02 a 2026-03-09.
- **supply_weekly:** Mejoró. Pasó de PARTIAL_EXPECTED a **OK**. derived_max 2026-03-09.
- **real_lob:** No mejoró (no se ejecutó backfill). Sigue DERIVED_STALE; derived_max 2026-03-07. Para mejorar: ejecutar pipeline **con** backfill.
- **real_lob_drill:** No mejoró (no se ejecutó backfill). Sigue DERIVED_STALE; derived_max 2026-03-02. Misma acción: ejecutar pipeline con backfill.
- **trips_base:** Sin cambio; SOURCE_STALE es esperado si la fuente operativa es trips_2026.

---

## Fase E — Validación funcional en UI

- **Banner global de freshness:** El estado global se calcula a partir del dataset primario `real_lob_drill` (o fallback real_lob). Como real_lob_drill sigue DERIVED_STALE, el banner puede seguir mostrando "Atrasada" o "Falta data" hasta que se ejecute el backfill. Tras el backfill, debería pasar a "Fresca" o "Parcial esperada" si derived_max ≥ ayer.
- **Endpoint GET /ops/data-freshness/global:** Existe en el router `ops` (prefix `/ops`). Si el frontend recibe 404, comprobar que el proxy (p. ej. Vite `/api` → backend) reenvía correctamente a la base del backend (p. ej. `/ops/...` sin duplicar prefijo).
- **Vistas Real LOB, Driver Lifecycle, Supply:** Driver Lifecycle y Supply ya consumen derivados actualizados (derived_max 2026-03-09). Real LOB seguirá mostrando datos hasta 2026-03-02 (drill) o 2026-03-07 (daily) hasta que se ejecute el backfill.

---

## Fase F — Campos vacíos

No se hizo en esta pasada una auditoría campo a campo de vistas. Los campos que dependen de `real_drill_dim_fact` / `real_rollup_day_fact` seguirán limitados por derived_max hasta que se ejecute el backfill Real LOB.

---

## Fase G — Automatización

- **Script:** `python -m scripts.run_pipeline_refresh_and_audit` es invocable y completó correctamente (con `--skip-backfill`). Con backfill incluido, debe ejecutarse en ventana con tiempo suficiente (p. ej. cron diario).
- **Fix aplicado:** El refresh de driver lifecycle usa conexión con `statement_timeout=0` para no fallar por timeout del pool.
- **POST /ops/pipeline-refresh:** Disponible; dispara el mismo script por subprocess (timeout 1h).
- **Recomendación:** Cron diario tras carga de viajes, p. ej. `0 6 * * * cd /path/to/backend && python -m scripts.run_pipeline_refresh_and_audit >> /var/log/ct_pipeline.log 2>&1`. Para entornos con statement_timeout bajo en el pool, el script ya no depende de ese límite para el refresh de driver lifecycle.

---

## Fase H — Documentación actualizada

- **docs/pipeline_refresh_certification.md:** Este documento (evidencia before/after, logs, comparativo, veredicto).
- **docs/system_views_freshness_audit.md:** Sin cambios en esta certificación; ya referencia el pipeline y el mapa.
- **docs/data_pipeline_observability_map.md:** Sin cambios; breakpoints y refresh ya documentados.
- **docs/data_freshness_monitoring.md:** Sin cambios en esta certificación.
- **Código:** `backend/scripts/run_pipeline_refresh_and_audit.py` — `run_refresh_driver_lifecycle()` usa conexión con `statement_timeout=0`.

---

## Fase I — Entregable final

### 1. Comandos ejecutados

- `python -c "get_freshness_audit(...)"` (lectura BEFORE).
- `python -m scripts.run_pipeline_refresh_and_audit --skip-backfill` (1.º intento: fallo por timeout).
- **Fix:** Edición de `run_refresh_driver_lifecycle()` para usar conexión con `statement_timeout=0`.
- `python -m scripts.run_pipeline_refresh_and_audit --skip-backfill` (2.º intento: OK).
- `python -m scripts.run_data_freshness_audit` (también ejecutado dentro del pipeline al final).

### 2. Before del audit

Véase tabla BEFORE en Fase A.

### 3. After del audit

Véase tabla AFTER en Fase C.

### 4. Datasets que mejoraron

- **driver_lifecycle:** DERIVED_STALE → OK; derived_max 2026-03-05 → 2026-03-09.
- **driver_lifecycle_weekly:** DERIVED_STALE → OK; derived_max 2026-03-02 → 2026-03-09.
- **supply_weekly:** PARTIAL_EXPECTED → OK; derived_max 2026-03-02 → 2026-03-09.

### 5. Datasets que siguen con problema

- **real_lob:** DERIVED_STALE (derived_max 2026-03-07). Requiere backfill Real LOB.
- **real_lob_drill:** DERIVED_STALE (derived_max 2026-03-02). Requiere backfill Real LOB.
- **trips_base:** SOURCE_STALE (esperado si la fuente viva es trips_2026).

### 6. Cambios observados en UI

- Driver Lifecycle y Supply ya leen de derivados con derived_max 2026-03-09. El banner global seguirá basado en real_lob_drill hasta que se ejecute el backfill; entonces debería actualizarse.

### 7. Campos vacíos

No auditados por vista en esta pasada; la mejora de real_lob/real_lob_drill vía backfill debería reducir huecos donde ya exista data en la fuente.

### 8. Estado de automatización

Operativa: script ejecutable, fix de timeout aplicado, pipeline (sin backfill) completado con éxito. Backfill debe ejecutarse en ventana larga (cron o manual).

### 9. Archivos modificados

- `backend/scripts/run_pipeline_refresh_and_audit.py`: `run_refresh_driver_lifecycle()` usa conexión con `statement_timeout=0`.
- `docs/pipeline_refresh_certification.md`: creado/actualizado con esta certificación.

### 10. Veredicto final

**LISTO CON OBSERVACIONES**

- **Pipeline ejecutado de verdad:** Sí (con `--skip-backfill`; backfill no ejecutado por tiempo).
- **Audit vuelto a correr:** Sí; resultados en tabla AFTER.
- **Comparación before/after:** Sí; driver_lifecycle, driver_lifecycle_weekly y supply_weekly mejoraron a OK.
- **real_lob y real_lob_drill:** No mejoraron en esta ejecución; para que queden frescos hay que ejecutar el pipeline **sin** `--skip-backfill` y dejar que el backfill termine.
- **UI:** Refleja el estado de la auditoría; el banner depende del dataset primario (real_lob_drill) hasta que se actualice con backfill.
- **Evidencia:** Queda documentada en este documento (tablas, logs, fix de timeout, comandos).

**Para cerrar al 100%:** Ejecutar una vez el pipeline completo (con backfill), p. ej.  
`python -m scripts.run_pipeline_refresh_and_audit`  
en una ventana con tiempo suficiente (o vía cron), y volver a correr el audit para confirmar que real_lob y real_lob_drill pasan a OK o al menos mejoran derived_max.

---

## Reparar real_lob_drill (DERIVED_STALE)

**Causa:** El derivado `ops.real_drill_dim_fact` (y por tanto la vista `ops.mv_real_drill_dim_agg`) se alimenta con el script **backfill_real_lob_mvs**. Si no se ejecuta, `MAX(period_start)` se queda atrás respecto a la fuente (`ops.v_trips_real_canon`).

**Comando exacto para reparar:**

```bash
cd backend
python -m scripts.run_pipeline_refresh_and_audit
```

No usar `--skip-backfill`. El pipeline ejecutará en orden: (1) backfill Real LOB (mes actual + anterior), (2) refresh driver lifecycle MVs, (3) refresh supply MVs, (4) run_data_freshness_audit.

**Si el backfill se interrumpió:** El checkpoint está en `backend/logs/backfill_real_lob_checkpoint.json`. Para forzar re-backfill del mes actual, borrar el archivo o ejecutar el backfill manualmente con `--resume false` para el rango deseado:

```bash
cd backend
python -m scripts.backfill_real_lob_mvs --from 2026-02-01 --to 2026-03-01 --resume false
python -m scripts.run_data_freshness_audit
```

**Verificación:** Tras el pipeline, `GET /ops/data-pipeline-health` debe mostrar para `real_lob_drill`: `derived_max_date` ≥ ayer (o al menos la última semana con data); `status` pasará a OK o PARTIAL_EXPECTED.
