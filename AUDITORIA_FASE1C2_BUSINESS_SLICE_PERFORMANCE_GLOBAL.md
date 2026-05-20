# Fase 1C.2 — Business Slice Resolved View Performance + Auditoría Global park_only

**Fecha**: 2026-05-19
**Fase**: Control Foundation — Fase 1C.2
**Estado**: **NO-GO** (coverage 96.80%, Barranquilla crítico en 46.6%)

---

## 1. Estado ejecutivo

| Dimensión | Valor |
|-----------|-------|
| **Coverage global** | **96.80%** (459,847 / 475,034 viajes mapeados) |
| **Mayor gap** | **Barranquilla: 46.6%** — solo 11,032 de 23,653 viajes mapeados |
| **Bogotá** | **100%** — fix confirmado (Carga=2,801, Delivery moto=188) |
| **Performance** | Audit view: **7.5s**. Resolved view: still >120s timeout |
| **Park_only rules** | **86/102 (84%) son sospechosas** — declaran `tipo_servicio_values` pero son `park_only` y los ignoran |
| **¿Cierra Fase 1C?** | **NO** — requiere Fase 1C.3 para reparar Barranquilla y reglas park_only |

---

## 2. Problema de performance — resuelto parcialmente

### Causa raíz

La vista `ops.v_real_trips_business_slice_resolved` (migración 118) encadena:
1. `v_real_trips_enriched_base`: UNION ALL de trips_2025+trips_2026 con DISTINCT ON, más LOWER(TRIM(...)) en joins de park_id y driver_id
2. `v_real_trips_business_slice_resolved`: INNER JOIN con rules usando `lower(trim(park_id))`, unnest de arrays, funciones normalizadoras, 6 CTEs encadenadas (m → mx → best → outcome → winner)

Los `LOWER(TRIM(...))` en las condiciones de join impiden el uso de índices. Las funciones `ops.normalized_service_type()` y `ops.normalized_works_terms()` en WHERE añaden overhead por fila.

### Solución implementada

**Opción C — Audit view sobre fact tables**:
- **Migración 141**: `ops.v_business_slice_mapping_coverage` — calcula coverage desde `trips_2026` vs `real_business_slice_month_fact` sin pasar por la vista resolved.
- **Tiempo**: 7.5s para mayo 2026 completo (9 ciudades en 2 países) vs >120s de la vista anterior.
- **Índices recomendados**: expresión `lower(trim(park_id::text))` en dim_park, trips_2026, trips_2025, mapping_rules. La creación con `CONCURRENTLY` toma >10min por tabla y se recomienda ejecutar durante ventana de bajo tráfico.

---

## 3. Benchmarks antes/después

| Query | Antes | Ahora | Mejora |
|-------|-------|-------|--------|
| Coverage global May 2026 (resolved view) | >120s timeout | N/A (sigue lento) | — |
| Coverage global May 2026 (audit view) | No existía | **7.5s** | Nueva |
| LIMIT 1 resolved view | >60s timeout | >60s timeout | Sin cambio |
| Bogotá park aggregation (resolved view) | >60s timeout | >60s timeout | Sin cambio |

**Conclusión**: La audit view es el camino correcto para auditorías. La vista resolved requiere refactor más profundo (normalizar columnas de join) que está fuera del alcance de esta fase.

---

## 4. Coverage global mayo 2026

| País | Ciudad | Raw completed | Mapped | Unmatched est. | Coverage |
|------|--------|--------------|--------|----------------|----------|
| Colombia | Barranquilla | 23,653 | 11,032 | 12,621 | **46.6%** |
| Colombia | Cali | 148,476 | 147,225 | 1,251 | 99.2% |
| Perú | Lima | 270,954 | 269,639 | 1,315 | 99.5% |
| Colombia | Cúcuta | 315 | 315 | 0 | 100% |
| Colombia | Medellín | 2,057 | 2,057 | 0 | 100% |
| Perú | Arequipa | 8,828 | 8,828 | 0 | 100% |
| Perú | Trujillo | 17,738 | 17,738 | 0 | 100% |
| Colombia | Bogotá | 2,989 | 2,989 | 0 | **100%** |
| Colombia | Bucaramanga | 24 | 24 | 0 | 100% |
| **TOTAL** | | **475,034** | **459,847** | **15,187** | **96.80%** |

---

## 5. Auditoría global park_only

### Estadísticas

| Métrica | Valor |
|---------|-------|
| Total park_only rules activas | **102** |
| Con viajes en mayo 2026 | 65 |
| Sin viajes (zerotrips) | 37 |
| Parks distintos | 28 |
| Slices distintas | 10 |
| **Reglas sospechosas (park_only CON tipo_servicio_values)** | **86 (84.3%)** |

### Top casos sospechosos (park_only con tipos declarados pero ignorados)

| City | Slice | Park | May trips | Tipos declarados | Riesgo |
|------|-------|------|-----------|-----------------|--------|
| Lima | Auto regular | 08e20910... | 209,703 | Económico, Start, Confort, Confort+, Exprés, Premier, xl | Estos tipos incluyen Exprés (delivery). Si hay viajes Exprés en este park, se clasifican como Auto regular. |
| Lima | Tuk Tuk | e3e07c00... | 17,824 | Tuk-tuk | Bajo — el tipo coincide |
| Lima | YMA | fafd6231... | 14,195 | Económico, Start, Confort, Confort+, Exprés, Premier, xl | Alto — Exprés en YMA es incorrecto |
| Lima | PRO | 64085dd8... | 8,478 | Económico, Start, Confort, Confort+, Exprés, Premier, xl | Alto — Exprés en PRO es incorrecto |
| Lima | Delivery | 962afaa3... | 5,950 | Moto, envíos, courier | Bajo — el tipo coincide |
| Trujillo | Auto regular | 851e3075... | 17,738 | (vacío) | Medio — sin tipos, captura todo |
| Arequipa | Auto regular | 56e4607d... | 8,828 | (vacío) | Medio — sin tipos, captura todo |
| Barranquilla | Auto regular | ef21f793... | ? | Económico, Start, Confort, Confort+, Exprés, Premier, xl | **CRÍTICO** — solo 46.6% coverage. Exprés en Auto es incorrecto |
| Bogotá | Delivery moto | 3146c78... | **0** | Moto, envíos, courier | Park sin actividad |
| Bogotá | Carga | f4ac6fd... | 2,801 | Cargo | **Corregido** — ahora tiene regla park_plus_tipo_servicio (ID=143) |

### Parks con >1 business_slice (discriminación por tipo funciona)

| Park | Slices | May trips |
|------|--------|-----------|
| 05b1c83... (Cali) | Auto regular + Taxi Moto | 296,952 |
| 962afaa... (Lima) | Delivery + YMM | 11,900 |
| f4ac6fd... (Bogotá) | Carga + Delivery moto | 8,967 |
| e081e2d... | Auto regular + Taxi Moto | 4,112 |
| 7ca266b... | Auto regular + Taxi Moto | 630 |
| 96f5a1e... (Bucaramanga) | Auto regular + Taxi Moto | 48 |
| 3146c78... (Bogotá) | Delivery moto + YMM | 0 |

---

## 6. Casos sospechosos prioritarios

| # | Ciudad | Problema | Impacto | Acción |
|---|--------|----------|---------|--------|
| 1 | **Barranquilla** | 46.6% coverage — 12,621 viajes unmatched | **CRÍTICO** | Auditoría detallada de parks y tipos faltantes |
| 2 | **Lima — YMA/PRO/Auto** | park_only con Exprés en tipo_servicio_values (delivery) | **HIGH** | Verificar si hay viajes Exprés en parks YMA/PRO/Auto |
| 3 | **Cali** | 1,251 viajes unmatched (0.8%) | MEDIUM | Auditoría de los viajes unmatched |
| 4 | **Lima** | 1,315 viajes unmatched (0.5%) | MEDIUM | Auditoría de los viajes unmatched |
| 5 | **86 reglas park_only con tipos** | Los tipos declarados son ignorados por ser park_only | MEDIUM | Convertir a park_plus_tipo_servicio si los tipos son confiables |

---

## 7. Trazabilidad

```
raw trip (trips_2026) → trip.park_id → LOWER(TRIM(join))
  → ops.business_slice_mapping_rules (is_active, park_id match)
    → rule_type scoring: works_terms=3, tipo_servicio=2, park_only=1
    → best score wins → winner (tie-break: is_subfleet ASC, rule_id ASC)
      → business_slice_name final
        → ops.real_business_slice_{month,week,day}_fact
          → business_slice_omniview_service → Omniview Matrix
```

**Limitación**: La vista `v_real_trips_business_slice_resolved` sigue siendo la única fuente de trazabilidad por viaje, y tarda >120s. La audit view `v_business_slice_mapping_coverage` da agregados rápidos pero no trazabilidad por viaje individual.

---

## 8. Validación Omniview

| Métrica | Raw trips_2026 | Fact table | Delta |
|---------|---------------|------------|-------|
| May 2026 completed | 475,034 | 459,847 | **-15,187 (3.20%)** |
| Bogotá Carga | 2,801 | 2,801 | 0 |
| Bogotá Delivery moto | 188 | 188 | 0 |

El delta de 15,187 coincide exactamente con los viajes unmatched estimados. Omniview muestra datos consistentes con la clasificación actual, pero los 15,187 viajes unmatched no aparecen en ninguna slice.

---

## 9. Riesgos pendientes

| Riesgo | Fase |
|--------|------|
| **Barranquilla 46.6% coverage** — 12,621 viajes sin slice | **Fase 1C.3** urgente |
| 86 reglas park_only con tipo_servicio_values ignorados | **Fase 1C.3** |
| Resolved view >120s — bloquea trazabilidad por viaje | **Fase 1C.3** o Fase 1D |
| Índices CONCURRENTLY no creados por timeout | Ejecutar en ventana de bajo tráfico |
| Cali + Lima con ~1,300 viajes unmatched cada uno | **Fase 1C.3** |
| Closed Period Protection bloqueado hasta cobertura >=99% | **Fase 1D** |

---

## 10. Prompt recomendado de implementación correctiva (Fase 1C.3)

```
Fase 1C.3 — Barranquilla Coverage Repair + park_only Cleanup

1. Auditar Barranquilla: listar parks, tipos_servicio, trips, y qué reglas faltan.
2. Agregar reglas park_plus_tipo_servicio para Barranquilla (similar a Bogotá fix).
3. Convertir reglas park_only con tipo_servicio_values a park_plus_tipo_servicio
   para parks donde los tipos son confiables (Lima, Cali, Trujillo, Arequipa).
4. Refrescar month_fact para mayo 2026.
5. Verificar coverage >=99% global.
6. Crear índices CONCURRENTLY en ventana nocturna.
7. Cerrar Fase 1C → avanzar a Fase 1D (Closed Period Protection).
```

---

## Apéndice — Archivos creados/modificados

| Archivo | Acción |
|---------|--------|
| `backend/alembic/versions/141_business_slice_performance_indexes.py` | **NUEVO** — audit view `ops.v_business_slice_mapping_coverage` |
| `backend/scripts/_phase1c2_create_indexes.py` | Script manual de índices (timeout, ejecutar en ventana) |
| `backend/scripts/_phase1c2_audit.py` | Script de auditoría completa (ejecutado, resultados en este reporte) |
