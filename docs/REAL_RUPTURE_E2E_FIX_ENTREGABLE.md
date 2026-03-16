# Corrección E2E causa raíz común REAL — Entregable final

**Objetivo:** Resolver de forma definitiva la ruptura común (margen_total, margen_trip, viajes B2B) desde la causa raíz, propagar por la cadena y dejar guardrails.

---

## 1. Causa raíz exacta

La tabla **`public.trips_2026`** deja de recibir valores en **`comision_empresa_asociada`** y **`pago_corporativo`** desde la **semana 2026-02-16**. El proceso que **escribe** en esa tabla **no está en este repositorio**; es un ETL/ingestión externo. Las vistas y MVs del Control Tower solo leen; la ruptura nace en la fuente.

---

## 2. Fecha exacta de quiebre

**Lunes 16 de febrero de 2026** (week_start 2026-02-16). Última semana buena: 2026-02-09.

---

## 3. Dónde estaba el proceso roto

**Fuera del repo.** En este repo no existe ningún script que haga INSERT/COPY en `trips_2026`. El proceso roto es el que alimenta esa tabla (sistema externo: ETL, export, API, etc.). Documentado en `docs/TRIPS_2026_INGESTION_SOURCE_AND_CONTRACT.md`.

---

## 4. Cómo se corrigió (en este repo)

**CASO B (proceso fuera del repo):**

- **Contrato y documentación:** Contrato mínimo de columnas para quien escribe en `trips_2026` y checklist para el equipo externo (`docs/TRIPS_2026_INGESTION_SOURCE_AND_CONTRACT.md`).
- **Validación automática:** Script `audit_trips_2026_commercial_coverage.py` que falla (exit 1) si la cobertura de comisión/pago_corporativo en las últimas 4 semanas cae por debajo de umbral. Integrado en el pipeline (`run_pipeline_refresh_and_audit`) como paso de auditoría (se puede omitir con `--skip-coverage-audit`).
- **Backfill desde CSV:** Script `backfill_trips_2026_commercial_from_csv.py` para actualizar `comision_empresa_asociada` y `pago_corporativo` en `trips_2026` a partir de un CSV proporcionado por el equipo externo (ventana desde 2026-02-16).
- **Orden de propagación:** Documentado más abajo; el pipeline ya refresca hourly → day → week → month y puebla drill (day/week/month) con `--drill-months` incluido.

**Corrección del proceso que escribe en trips_2026:** debe hacerla el equipo o sistema que mantiene esa ingestión (ver checklist en `TRIPS_2026_INGESTION_SOURCE_AND_CONTRACT.md`).

---

## 5. Ventana backfilleada

**Ventana a repoblar:** desde **2026-02-16** hasta la fecha actual.  
El backfill **no se ejecuta automáticamente** desde este repo porque los datos deben venir del sistema que alimenta `trips_2026`. Opciones:

- El equipo externo re-ejecuta la carga/ETL para esa ventana con columnas corregidas; o
- El equipo externo genera un CSV con `id`, `comision_empresa_asociada`, `pago_corporativo` y se ejecuta:  
  `python -m scripts.backfill_trips_2026_commercial_from_csv --csv /ruta/export.csv`

---

## 6. Refreshes ejecutados (orden oficial)

Tras corregir la fuente y (opcionalmente) ejecutar el backfill en `trips_2026`:

1. **Refresh cadena hourly-first** (en orden):  
   `ops.mv_real_lob_hour_v2` → `ops.mv_real_lob_day_v2` → `ops.mv_real_lob_week_v3` → `ops.mv_real_lob_month_v3`  
   Comando: `python -m scripts.refresh_hourly_first_chain` (o sin `--skip-hour`).
2. **Poblar drill:**  
   `python -m scripts.populate_real_drill_from_hourly_chain --days 120 --weeks 18 --months 6`
3. (Opcional) Refresh driver lifecycle y supply según necesidad.
4. **Pipeline unificado:**  
   `python -m scripts.run_pipeline_refresh_and_audit`  
   hace 1 + 2 + audit (incl. auditoría de cobertura trips_2026).

---

## 7. Evidencia DB pre/post

**Pre (ruptura):** En `trips_2026`, para week_start >= 2026-02-16: con_comision=0, con_pago_corp=0. En week_v3/month_v3: sum_margin=NULL, b2b_trips=0.

**Post (cuando la fuente esté corregida y backfill ejecutado):**  
Ejecutar de nuevo:

- `python -m scripts.investigate_real_rupture_2026`  
  y comprobar que para semanas >= 2026-02-16 vuelvan con_comision > 0 y con_pago_corp >= 0 con valores coherentes.
- Queries de validación en FASE 5 del documento de investigación (cobertura por semana en trips_2026, trip_fact, day_v2, week_v3, month_v3, real_drill_dim_fact).

---

## 8. Evidencia runtime pre/post

**Endpoints a comprobar tras la corrección:**

- `GET /ops/real-lob/drill?period=week&desglose=LOB&segmento=all`
- `GET /ops/real-lob/drill?period=month&desglose=LOB&segmento=all`
- `GET /ops/real-margin-quality?days_recent=90&findings_limit=20`

**Post:** margin_total y margin_trip deben venir poblados para periodos >= 2026-02-16; b2b_trips/b2b_pct coherentes; sin 500/404 en margin-quality.

---

## 9. Evidencia UI final

Verificar en REAL: drill semanal/mensual LOB, tipo de servicio, park; children; card margin-quality; que margen_total, margen_trip y B2B dejen de estar vacíos desde febrero 2026; cancelaciones y labels park/city/country consistentes. Checklist manual en FASE 7 de la solicitud.

---

## 10. Guardrails añadidos

| Guardrail | Descripción |
|-----------|-------------|
| Auditoría semanal de cobertura | `audit_trips_2026_commercial_coverage.py` — cobertura de comision_empresa_asociada y pago_corporativo en últimas 4 semanas |
| Umbral y alerta | Si cobertura de comisión < 15% en alguna de esas semanas, el script sale con código 1 |
| Integración en pipeline | Ejecutado en `run_pipeline_refresh_and_audit` tras audit (salvo `--skip-coverage-audit`) |
| Contrato trips_2026 | `docs/TRIPS_2026_INGESTION_SOURCE_AND_CONTRACT.md` + `docs/real_trip_source_contract.md` |

---

## 11. Lista exacta de archivos modificados / creados

| Archivo | Acción |
|---------|--------|
| `docs/REAL_RUPTURE_2026_FASE0_DIAGNOSTICO_CONGELADO.md` | Creado |
| `docs/TRIPS_2026_INGESTION_SOURCE_AND_CONTRACT.md` | Creado |
| `docs/REAL_RUPTURE_E2E_FIX_ENTREGABLE.md` | Creado (este documento) |
| `backend/scripts/audit_trips_2026_commercial_coverage.py` | Creado |
| `backend/scripts/backfill_trips_2026_commercial_from_csv.py` | Creado |
| `backend/scripts/run_pipeline_refresh_and_audit.py` | Modificado (coverage audit, drill-months, run_populate_drill con months) |

Referencia previa (sin cambios en esta entrega): `docs/REAL_RUPTURE_2026_ROOT_CAUSE_ENTREGABLE.md`, `backend/scripts/investigate_real_rupture_2026.py`.

---

## 12. Veredicto final

**PARTIALLY_RECOVERED**

- **Causa raíz:** Identificada y documentada (trips_2026, comision_empresa_asociada, pago_corporativo, desde 2026-02-16; proceso de carga externo).
- **En este repo:** Contrato, validación automática, script de backfill desde CSV, orden de propagación y guardrails implementados. Pipeline incluye auditoría de cobertura y populate con month.
- **Fuente y backfill:** Dependen del sistema/equipo externo que alimenta `trips_2026`. Cuando ese proceso se corrija y se ejecute el backfill (o se use el CSV + script), ejecutar refresh + populate propagará la corrección de punta a punta (DB → vistas/MVs → drill → API → UI).

**No se marca ROOT_CAUSE_FIXED_AND_PROPAGATED** porque la fuente `trips_2026` sigue actualmente sin poblar comisión/B2B para fechas >= 2026-02-16 hasta que el proceso externo se repare y se haga el backfill. Este entregable deja el sistema preparado para recuperar la verdad en cuanto la fuente esté corregida.
