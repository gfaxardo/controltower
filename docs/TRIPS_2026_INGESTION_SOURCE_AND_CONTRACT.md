# trips_2026 — Origen de la ingestión y contrato (FASE 1 + FASE 2 CASO B)

## FASE 1 — Respuestas explícitas

### 1. ¿Dónde se alimenta trips_2026?

La tabla **`public.trips_2026`** se alimenta por un **proceso externo al repositorio YEGO Control Tower**. En este repo no existe ningún script, job ni pipeline que ejecute `INSERT` o `COPY` contra `trips_2026`.

### 2. ¿Qué proceso, script o fuente externa la llena?

**No está definido en este repo.** La documentación existente indica:
- "trips_2026: Fuente viva; debe estar en el pipeline de ingestión" (`docs/source_dataset_policy.md`).
- "Recibe la ingestión actual."
- El pipeline interno (`run_pipeline_refresh_and_audit`) solo **refresca derivados** (hourly → day → week → month) y **pobla el drill** leyendo desde las MVs; **no escribe** en trips_all ni trips_2026.

Se debe identificar en el entorno operativo (Airflow, Fivetran, script de carga, export desde sistema origen, etc.) el job que escribe en `public.trips_2026`.

### 3. ¿Ese proceso vive en este repo o fuera?

**Fuera de este repo.**

### 4. ¿Qué cambió alrededor de 2026-02-16?

Desconocido desde este repo. El diagnóstico muestra que desde la semana 2026-02-16 las columnas `comision_empresa_asociada` y `pago_corporativo` pasan a 0/NULL. Posibles causas en el sistema que alimenta:
- Cambio de schema o de mapeo de columnas en el export/ETL.
- Cambio de fuente de datos (otra API o tabla) que no incluye esos campos.
- Filtro o transformación que anula o no rellena esos campos.

### 5. ¿Hay mappings/computed columns que dejaron de venir?

Sí, en la práctica: **comision_empresa_asociada** y **pago_corporativo** dejaron de llegar poblados para filas con `fecha_inicio_viaje >= 2026-02-16`.

---

## FASE 2 CASO B — Contrato y validación en este repo

Al no poder corregir el proceso de carga desde este repo:

1. **Contrato mínimo** (ver abajo): columnas y reglas que debe cumplir quien escribe en `trips_2026`.
2. **Validación automática** en este repo: script que detecta si la cobertura comercial cae por debajo de umbral y falla (exit no cero) para integrar en cron o pipeline.
3. **Checklist para el equipo/sistema externo**: pasos para corregir la fuente y ejecutar backfill.

---

## Contrato mínimo para public.trips_2026

Cualquier proceso que escriba en `public.trips_2026` debe garantizar, **al menos para filas con fecha_inicio_viaje >= 2026-01-01**:

| Columna | Obligación | Descripción |
|---------|------------|-------------|
| `id` | Obligatoria | Identificador único del viaje |
| `fecha_inicio_viaje` | Obligatoria | Timestamp de inicio |
| `condicion` | Obligatoria | 'Completado', 'Cancelado', etc. |
| `tipo_servicio` | Recomendada | Para LOB; si NULL la fila puede excluirse en trip_fact |
| **`comision_empresa_asociada`** | **Obligatoria para margen** | Numérico; NULL/ausente implica margen_total/margin_trip vacíos en toda la cadena REAL |
| **`pago_corporativo`** | **Obligatoria para B2B** | Numérico; NULL/ausente implica segmento B2B en 0 en toda la cadena REAL |
| `park_id`, `fecha_finalizacion`, `distancia_km`, `conductor_id`, `motivo_cancelacion` | Según contrato completo | Ver `docs/real_trip_source_contract.md` |

**Umbral de cobertura esperado (semanas recientes):**  
Para viajes completados en las últimas 4 semanas, al menos **15%** de las filas deben tener `comision_empresa_asociada` no NULL, y al menos **0.05%** con `pago_corporativo` no NULL (o el histórico del producto), para que margen y B2B no aparezcan rotos en la UI.

---

## Validación automática en este repo

- **Script:** `backend/scripts/audit_trips_2026_commercial_coverage.py`
- **Uso:** `cd backend && python -m scripts.audit_trips_2026_commercial_coverage`
- **Comportamiento:** Calcula cobertura semanal de `comision_empresa_asociada` y `pago_corporativo` en `trips_2026`; si en la última semana completa la cobertura de comisión cae por debajo del umbral configurado, sale con código 1 (fallo). Integrable en cron o post-refresh para detectar recaídas.

---

## Checklist para el equipo que mantiene la fuente externa

1. Identificar el job/ETL que escribe en `public.trips_2026`.
2. Revisar logs o cambios alrededor de 2026-02-16 (deploy, cambio de mapping, cambio de fuente).
3. Asegurar que el export/carga vuelva a incluir y rellenar `comision_empresa_asociada` y `pago_corporativo` para todas las filas donde corresponda.
4. Ejecutar backfill para el rango **desde 2026-02-16 hasta la fecha actual** (re-carga o UPDATE desde export corregido).
5. Opcional: usar el script de backfill desde CSV de este repo si el equipo puede generar un CSV con `id`, `comision_empresa_asociada`, `pago_corporativo` para ese rango: `python -m scripts.backfill_trips_2026_commercial_from_csv --csv path/to/file.csv --dry-run` y luego sin `--dry-run`.
