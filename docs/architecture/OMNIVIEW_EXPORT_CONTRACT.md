# OMNIVIEW EXPORT CONTRACT

## Propósito

Descargar la vista completa de Omniview Matrix (Evolución y Vs Proyección) con todos los KPIs, filtros, metadata y trazabilidad mínima. Satisface necesidades de auditoría, operación y reporting sin depender del backend.

## Motor arquitectónico

**Control Foundation (ACTIVE)** — Fase 1

No pertenece a Suggestion Engine, Decision Engine, Action Engine ni Learning Engine.

## Qué exporta

### Modo Evolución (`viewMode === 'evolucion'`)
- Matrix completa (ciudad × línea × periodo × KPI)
- Valores reales por celda
- Deltas vs periodo anterior (MoM, WoW, DoD)
- Señal semántica (up/down/neutral)
- Modo de comparación

### Modo Vs Proyección (`viewMode === 'proyeccion'`)
- Matrix completa (ciudad × línea × periodo × KPI)
- Real vs Proyección (actual, expected, total)
- Gap (absoluto, porcentual)
- Attainment (cumplimiento %)
- Señal semántica
- Confianza de proyección
- Método de curva
- Nivel de fallback

### Metadata general
- Fecha/hora de generación
- Modo de export
- Grano temporal
- Filtros aplicados (país, ciudad, tajada, flota, año, mes, plan)
- Versión de plan
- Ruta frontend
- Última fecha de datos disponibles

### Data Quality
- Estado de frescura (freshness)
- Cobertura de mapeo
- Estado de confianza operativa (trust)
- Integridad de proyección
- Filas de plan sin ejecución real

### YTD Summary (solo Vs Proyección)
- Resumen YTD por slice/tajada
- KPIs: trips, revenue, active_drivers
- Real, Plan, Gap, Fulfillment
- Señal semántica

### Oportunidades (compacto, informativo)
- Lista de oportunidades detectadas por proyección
- Tipo (operacional / contextual)
- Headline, ubicación, prioridad, confianza
- **NO incluye decisiones, campañas, ni acciones ejecutables**

## Qué NO exporta

- Decisiones automáticas (Decision Engine)
- Acciones ejecutables (Action Engine)
- Campañas
- Recomendaciones priorizadas con botones
- Datos no visibles en la UI
- Datos no cargados
- Valores inventados o recalculados
- Endpoints de backend nuevos

## Hojas del archivo (CSV multi-sección)

| Sección CSV | Contenido |
|---|---|
| `METADATA` | Clave-valor: timestamp, modo, grano, filtros, selected_plan_version_key, ruta frontend, nota |
| `VERSION_METADATA` | Metadata de la versión seleccionada: display_name, source_filename, uploaded_at, status, row_count, min/max_period |
| `DATA_QUALITY` | Indicadores de calidad: freshness, coverage, trust, integridad |
| `FILTERS` | Todos los filtros aplicados en la UI |
| `EVOLUTION_MATRIX` | (Solo modo Evolución) Datos de la matriz con deltas |
| `PROJECTION_VS_REAL_LONG` | (Solo modo Vs Proyección) Real vs Plan con gaps |
| `YTD_SUMMARY` | (Solo Vs Proyección) Acumulado año por slice |
| `OPPORTUNITIES_COMPACT` | Resumen informativo de oportunidades detectadas |

## Campos incluidos

### Evolution Matrix
`country, city, business_slice, fleet, is_subfleet, period_key, period_label, kpi, value, delta_pct, delta_abs, signal, previous_value, comparison_mode`

### Projection Matrix
`country, city, business_slice, is_subfleet, period_key, period_label, kpi, real_value, projected_expected, projected_total, gap_abs, gap_pct, attainment_pct, signal, confidence, curve_method, fallback_level`

### KPIs exportados
- `commission_pct` (%)
- `trips_completed` (Viajes)
- `avg_ticket` (Ticket)
- `active_drivers` (Conductores)
- `revenue_yego_net` (Revenue)
- `cancel_rate_pct` (Cancel %)
- `trips_per_driver` (TPD)

En modo Vs Proyección: `trips_completed`, `revenue_yego_net`, `active_drivers`

## Nombre de archivo

```
yego_omniview_{mode}_{grain}_{country}_{city}_{YYYYMMDD_HHmm}.csv
```

Ejemplo:
```
yego_omniview_projection_weekly_peru_all_20260517_1530.csv
```

## Limitaciones

1. **CSV, no Excel multi-hoja**: No se instaló `xlsx` para mantener minimalismo de dependencias (Fase 1). El CSV multi-sección es compatible con Excel, Google Sheets y cualquier visor de datos. Las secciones usan marcadores `--- SECTION ---` para evitar inyección de fórmulas en Excel.
2. **Frontend-only**: No recalcula KPIs (salvo `computeDeltas` que es la misma función pura usada por la UI). Exporta exactamente lo que la UI ya tiene cargado.
3. **Sin backend**: Si los datos no están en la UI (ej. no se cargaron por filtros), no se exportan.
4. **Oportunidades compactas**: Solo se exportan si `projectionMeta` contiene `operational_suggestions` o `contextual_suggestions`.
5. **Protección CSV Injection**: Valores que empiezan con `=`, `+`, `@` o `-` (no numérico) se escapan con `'`. Los números negativos (ej. `-2800`) se preservan como datos numéricos válidos.
6. **XLSX queda como mejora futura**: Instalar `xlsx` permitiría exportar con hojas reales (README, MATRIX, PROJECTION, YTD, QUALITY, FILTERS) en un solo archivo `.xlsx`.

## Diferencia con futuro export backend

| Aspecto | Frontend export (actual) | Backend export (futuro) |
|---|---|---|
| Origen de datos | UI state (ya cargado) | Base de datos directa |
| KPIs | Los ya computados | Recomputados desde facts |
| Rendimiento | Instantáneo (<100ms) | Puede tardar (SQL pesado) |
| Scope | Lo que ve el usuario | Todo el universo |
| Autenticación | No aplica | Requiere token |
| Frescura | Snapshot de UI | Tiempo real |

**Criterio para migrar a backend export:**
Cuando se necesite exportar datos que NO están en la UI actual (ej. todos los países de una sola vez, ventanas de 12+ meses, joins cross-LOB) se implementará un endpoint `/ops/omniview/export` en el backend.

## Archivos

| Archivo | Rol |
|---|---|
| `frontend/src/utils/omniviewExport.js` | Lógica de export (construcción CSV, descarga) |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Botón "Descargar" y handler `handleExport` |
| `docs/architecture/OMNIVIEW_EXPORT_CONTRACT.md` | Este documento |

## Seguridad y control de fase

- El botón aparece solo cuando hay datos cargados (`rows.length > 0` o `projectionRows.length > 0`).
- No llama endpoints nuevos.
- No activa motores ocultos (Decision/Action/Learning).
- Las oportunidades se exportan como metadata informativa, sin botones ni acciones.
- El CSV incluye BOM (`\uFEFF`) para compatibilidad con Excel en Windows.

---

*Documento generado para Fase 1 — Control Foundation. YEGO Control Tower.*
