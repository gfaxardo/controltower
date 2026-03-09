# Cierre microfase Real LOB — Resumen ejecutivo

## 1. Objeto real en lugar de `ops.mv_real_lob_base`

- **No existe** `ops.mv_real_lob_base` en el schema.
- **Objeto base por viaje:** `ops.v_real_trips_with_lob_v2` (columnas `real_tipo_servicio_norm`, `lob_group`). Consultarla sobre todo el histórico es lenta.
- **Objeto usado para diagnóstico rápido:** `ops.real_lob_residual_diagnostic` (tabla de agregado últimos 90 días). Creada por el script de diagnóstico; se rellena con `scripts/populate_real_lob_residual_diagnostic.py`.

## 2. Pipeline real confirmado

```
tipo_servicio (raw, ops.v_trips_real_canon)
  → normalización inline (CASE) = real_tipo_servicio_norm [v_real_trips_with_lob_v2] / tipo_servicio_norm [backfill]
  → LEFT JOIN canon.map_real_tipo_servicio_to_lob_group
  → lob_group = COALESCE(m.lob_group, 'UNCLASSIFIED')
  → ops.real_drill_dim_fact (breakdown=lob → dimension_key=lob_group; breakdown=service_type → dimension_key=tipo_servicio_norm)
  → ops.mv_real_drill_dim_agg → API drill
```

## 3. Resultado del diagnóstico residual

- **A) Drill (fact):** LOB UNCLASSIFIED **142 630** viajes; service_type UNCLASSIFIED **158** viajes.
- **B) Ventana 90 días (tabla diagnóstico):** Top validated_service_type en LOB UNCLASSIFIED: **envíos** (3 381), UNCLASSIFIED (11), focos led para auto, moto (2).
- **D) Totales 90 días:** 2 652 909 viajes; 3 394 UNCLASSIFIED LOB → **0,13 %**.

## 4. Categorías que explican la brecha

| validated_service_type     | trips | Categoría              |
|----------------------------|-------|------------------------|
| envíos                     | 3 381 | LEGIT_NO_MAPPING       |
| UNCLASSIFIED               | 11    | ALREADY_UNCLASSIFIED   |
| focos led para auto, moto  | 2     | GARBAGE                |

## 5. Mappings agregados

- **envíos** → **delivery** (insertado en `canon.map_real_tipo_servicio_to_lob_group`). Variante con tilde; `envios` ya estaba mapeado.

## 6. Basura dejada en UNCLASSIFIED y por qué

- **UNCLASSIFIED:** ya es el valor de service_type para strings largos; no se mapea a un LOB.
- **focos led para auto, moto:** producto/catálogo, no tipo de servicio de negocio; se deja como basura en UNCLASSIFIED.

## 7. Cambios UX aplicados (en microfase anterior)

- Cabecera drill: etiqueta **"Totales (periodos listados)"** y tooltip.
- Desglose expandido: título **"Desglose de [periodo] por [dimensión]"**; borde visual.
- Estado periodo: tooltips para Abierto/Parcial/Cerrado.
- **LOW_VOLUME** no se muestra en UI (filtro en backend + defensivo en frontend).

## 8. SQL ejecutado

- Introspección: `information_schema.tables`, `information_schema.views`, `information_schema.columns` en schemas ops, canon, dim, public.
- A: `SELECT breakdown, dimension_key, SUM(trips) FROM ops.real_drill_dim_fact WHERE breakdown IN ('service_type','lob') AND dimension_key = 'UNCLASSIFIED' GROUP BY ...`
- B/C/D: desde `ops.real_lob_residual_diagnostic` (tras rellenar con `populate_real_lob_residual_diagnostic.py`).
- Evidencia completa: `docs/real_lob_gap_evidence.json`.

## 9. Archivos modificados / creados

- **Scripts:** `backend/scripts/run_real_lob_gap_diagnosis.py`, `run_real_lob_gap_diagnosis_quick.py`, `populate_real_lob_residual_diagnostic.py`, `insert_envios_mapping.py`, `run_real_lob_query_b.py`.
- **Migración:** `backend/alembic/versions/069_real_lob_residual_diagnostic.py` (tabla diagnóstico; cadena de migraciones no aplicada en el entorno, tabla creada por script).
- **Docs:** `docs/real_lob_lob_gap_diagnosis.md`, `docs/real_lob_service_type_hardening.md`, `docs/real_lob_drill_ux_notes.md`, `docs/real_lob_gap_evidence.json`, este resumen.

## 10. Veredicto final

**LISTO CON OBSERVACIONES**

- Diagnóstico ejecutado de punta a punta con objetos reales; evidencia en JSON.
- Brecha explicada: envíos (variante con tilde) sin mapping → corregido.
- Residual restante (UNCLASSIFIED + basura) se deja en UNCLASSIFIED por diseño.
- Para que el drill refleje el nuevo mapping en la UI hay que **re-ejecutar el backfill** de Real LOB (ventana reciente). Opcional: volver a ejecutar `populate_real_lob_residual_diagnostic.py` y luego `run_real_lob_gap_diagnosis.py` para validar el % UNCLASSIFIED tras el cambio.
