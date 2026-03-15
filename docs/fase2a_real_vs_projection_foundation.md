# FASE 2A — Base analítica Real vs Proyección

**Proyecto:** YEGO Control Tower  
**Objetivo:** Diseño e implementación aditiva de la base para comparar Real vs Proyección (metas/Excel), incluyendo palancas operativas y doble segmentación.

---

## 1. Principios

- No mezclar Plan y Real en una misma fuente base; compararlos desde una **capa de matching**.
- Proyección puede usar **nomenclatura/segmentación distinta**: resolver con **mapping** (alias, canonical, normalized), no modificando Real ni Plan.
- **Dos vistas comparativas** (si es viable): por segmentación del sistema y por segmentación de la proyección.
- Todo **aditivo**, trazable y reversible.

---

## 2. Artefactos diseñados

| Artefacto | Tipo | Propósito |
|-----------|------|-----------|
| `ops.projection_upload_staging` | Tabla | Carga cruda de proyección (Excel/CSV): columnas genéricas + raw_label por dimensión. |
| `ops.projection_normalized` | Vista o tabla | Proyección con dimensiones normalizadas (canonical) vía mapping. |
| `ops.v_real_metrics_monthly` | Vista | Métricas reales mensuales comparables: drivers, trips, avg_trips_per_driver, avg_ticket, revenue (desde mv_real_trips_monthly y/o agregados Real LOB según grain). |
| `ops.v_real_vs_projection_system_segmentation` | Vista | Comparativo alineado a la segmentación actual del sistema (country, city, lob_base, segment, month). |
| `ops.v_real_vs_projection_projection_segmentation` | Vista | Comparativo alineado a la segmentación de la proyección (tras mapping). |
| `ops.projection_dimension_mapping` | Tabla | Mapping: source_system, source_raw_label, normalized_label, target_canonical_label, dimension_type, matching_status, confidence, manual_override. |

---

## 3. Palancas operativas en el comparativo

- **active_drivers** (real / plan)
- **total_trips** (real / plan)
- **avg_trips_per_driver** = total_trips / active_drivers
- **avg_ticket** = revenue / total_trips
- **revenue**, **revenue_per_driver**, **revenue_per_trip**
- **required_drivers_for_target** = target_trips / real_avg_trips_per_driver
- **required_trips_for_target** = target_revenue / real_avg_ticket
- **drivers_delta_needed**, **trips_delta_needed**, **ticket_delta_needed**
- **gap_explained_by_driver_count**, **gap_explained_by_productivity**, **gap_explained_by_ticket** (campos para descomposición de brecha).

---

## 4. Estrategia de matching de nomenclaturas

- **Capa puente:** `ops.projection_dimension_mapping`.
- **Dimensiones:** ciudad, país, vertical/LOB, service_type, categoría (y las que traiga el Excel).
- **Flujo:** raw_label (Excel) → normalized_label (limpieza) → target_canonical_label (canónico del sistema). matching_status (matched / unmatched / manual), confidence (0–1), manual_override (opcional).
- **No destructivo:** No se modifica Real ni Plan; la proyección se interpreta vía mapping al consumirla.

---

## 5. Segmentación sistema vs proyección

- **Sistema:** country, city_norm, lob_base, segment (b2b/b2c), month; opcional park_id.
- **Proyección:** Según plantilla Excel (por definir). Si difiere, se exponen:
  1. **real_vs_projection_system_segmentation:** Real agregado/normalizado al grain del sistema; proyección mapeada a ese grain donde exista mapping.
  2. **real_vs_projection_projection_segmentation:** Proyección en su grain; Real mapeado al grain de la proyección donde exista mapping inverso o join por canonical.

---

## 6. Implementación (estado)

- Migración **097** (o siguiente): creación de `projection_upload_staging`, `projection_dimension_mapping`, `v_real_metrics_monthly`, vistas comparativas (con placeholders si no hay datos de proyección).
- Servicio **real_vs_projection_service**: overview, dimensions, mapping_coverage, real_metrics, projection_template_contract, system_segmentation_view, projection_segmentation_view.
- Router **/ops/real-vs-projection/** con endpoints aditivos.
- Frontend: tab o subtab **Real vs Proyección** con estructura, cobertura de mapping, métricas reales disponibles y placeholders de comparación.

---

## 7. Siguientes pasos cuando el usuario suba la plantilla Excel

1. Definir contrato exacto del Excel (columnas, valores de dimensión) en `docs/projection_template_contract.md`.
2. Parser de carga a `ops.projection_upload_staging`.
3. Reglas de normalización y poblado de `projection_dimension_mapping` (o carga inicial desde Excel).
4. Poblar `ops.projection_normalized` desde staging + mapping.
5. Validar vistas comparativas con datos reales de proyección y ajustar fórmulas de brecha si hace falta.
