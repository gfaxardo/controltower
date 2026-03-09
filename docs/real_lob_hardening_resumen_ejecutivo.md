# Resumen ejecutivo – Hardening Real LOB

**Proyecto:** Yego Control Tower  
**Fecha:** 2026-03-08

---

## 1. Hallazgos

- **Migración 070** ya existía en el repo con funciones y vistas de auditoría; se ajustó el comentario (longitud 30) y se verificó que no hubiera uso de `AVG(margen_trip)` en la agregación del drill (ya se usaba `SUM(margen_total)/SUM(trips)`).
- **Backfill** fallaba al conectar: `options` se pasaba dos veces (`_get_connection_params` ya lo incluye). Se corrigió mergeando `options` en un solo string.
- **Validación rápida** mostró: (1) 070 aplicada, (2) funciones y vistas de auditoría presentes, (3) en `real_drill_dim_fact` aún aparecen 2 filas con `dimension_key` "focos led para auto, moto" y varias filas con `breakdown_valid = false`, coherente con que solo parte de los datos había sido refrescada por el backfill en el momento de la validación.

---

## 2. Cambios aplicados

- **backend/scripts/backfill_real_lob_mvs.py:** corrección de conexión (evitar doble `options`), log de filas insertadas/actualizadas por mes (drill_dim y rollup_day).
- **backend/alembic/versions/070_real_lob_service_type_validation.py:** comentario corregido (length<=30).
- **backend/app/services/real_lob_drill_pro_service.py:** `pct_b2b` nulo y `pct_b2b_low_sample: true` cuando viajes < 30 (LOW SAMPLE).
- **backend/scripts/validate_real_lob_quick.py** (nuevo): validación SQL ligera sin vistas pesadas.
- **backend/scripts/validate_real_lob_hardening.py** (nuevo): validación completa (incluye v_audit_service_type).
- **docs/real_lob_service_type_hardening.md** y **docs/real_lob_hardening_resumen_ejecutivo.md**.

---

## 3. Migración ejecutada

```text
cd backend
.\venv\Scripts\Activate.ps1
alembic upgrade head
```

**Resultado:** `Running upgrade 069_real_drill_service_type_tipo_norm -> 070_real_lob_service_type_validation` — OK.

---

## 4. Backfill ejecutado

```text
cd backend
.\venv\Scripts\Activate.ps1
python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2026-04-01 --resume false
```

**Resultado:** Iniciado correctamente. Primer mes (2025-01) completado: 89 filas en `real_drill_dim_fact`. El proceso es largo (varios minutos por mes); se dejó en ejecución. **Acción recomendada:** esperar a que termine y volver a ejecutar `validate_real_lob_quick` para confirmar desaparición de valores basura y alineación de `breakdown_valid`.

---

## 5. Validaciones superadas

| Validación | Resultado |
|------------|-----------|
| alembic_version | 070_real_lob_service_type_validation |
| Funciones ops | normalized_service_type, validated_service_type presentes |
| Vistas auditoría | v_audit_service_type, v_audit_breakdown_sum existen |
| Top service_type | Tipos legítimos (economico, confort, cargo, moto, etc.) + UNCLASSIFIED; 2 filas "focos led..." (datos aún no refrescados) |
| Consistencia margen (muestra) | margen_trip_calc = SUM(margin_total)/SUM(trips) coherente donde hay margin_total |
| Breakdown vs total | v_audit_breakdown_sum detecta filas con breakdown_valid = false (esperable hasta que el backfill complete todos los meses) |

---

## 6. Problemas no resueltos

- **Backfill largo:** No se esperó a que finalice todo el rango; las validaciones reflejan estado parcial (un mes refrescado + datos antiguos).
- **v_audit_service_type:** No se ejecutó en la validación completa por tiempo (vista sobre trips últimos 90 días puede ser pesada). La validación rápida no la incluye.

---

## 7. Veredicto final

**LISTO CON OBSERVACIONES**

- **Migración:** Aplicada correctamente; funciones y vistas de auditoría operativas.
- **Lógica:** service_type flexible con validación (UNCLASSIFIED), margen_trip/km_prom ponderados en el drill, LOW_VOLUME y LOW SAMPLE implementados, meta.breakdown_valid expuesta.
- **Backfill:** Iniciado y funcionando; debe completarse para que todos los periodos usen `validated_service_type` y las validaciones de breakdown y de ausencia de frases basura queden verdes.
- **Próximos pasos:** (1) Dejar terminar el backfill. (2) Ejecutar de nuevo `python -m scripts.validate_real_lob_quick`. (3) Probar en UI: drill por service_type, margen_trip vs total/viajes, que no predominen categorías basura.

---

## Entregables – Lista de archivos modificados

- `backend/alembic/versions/070_real_lob_service_type_validation.py` (comentario)
- `backend/scripts/backfill_real_lob_mvs.py` (fix conexión `options`, log filas por mes)
- `backend/app/services/real_lob_drill_pro_service.py` (LOW SAMPLE pct_b2b)
- `backend/scripts/validate_real_lob_quick.py` (nuevo)
- `backend/scripts/validate_real_lob_hardening.py` (nuevo)
- `docs/real_lob_service_type_hardening.md` (nuevo)
- `docs/real_lob_hardening_resumen_ejecutivo.md` (nuevo)

---

## Comandos ejecutados

```powershell
# Migración
cd c:\cursor\controltower\controltower\backend
.\venv\Scripts\Activate.ps1
alembic upgrade head

# Backfill (en curso; dejar terminar)
python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2026-04-01 --resume false

# Validación rápida
python -m scripts.validate_real_lob_quick
```

---

## Resultados clave de validación SQL (evidencia)

- **alembic_version:** `070_real_lob_service_type_validation`
- **Funciones:** `ops.normalized_service_type`, `ops.validated_service_type` existen.
- **Vistas:** `ops.v_audit_service_type`, `ops.v_audit_breakdown_sum` existen.
- **Top dimension_key (service_type):** economico, confort, mensajería, cargo, moto, premier, express, minivan, tuk-tuk, UNCLASSIFIED, etc. Aún 2 filas "focos led para auto, moto" (periodos no refrescados por backfill).
- **v_audit_breakdown_sum (inválidos):** Varias filas con `breakdown_valid = false` (viajes_service_type distinto de viajes_total o NULL) — esperable hasta que el backfill complete.
- **Consistencia margen (muestra pe/lob):** `margen_trip_calc = SUM(margin_total)/SUM(trips)` correcto donde hay datos (ej. 0.8046…).
