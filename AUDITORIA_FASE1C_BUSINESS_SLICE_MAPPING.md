# Auditoría Fase 1C — Business Slice Mapping Coverage & Contract Audit

**Fecha**: 2026-05-19
**Fase**: Control Foundation — Fase 1C
**Estado**: **NO-GO** (requiere acción antes de Closed Period Protection)

---

## 1. Estado ejecutivo

| Dimensión | Estado |
|-----------|--------|
| **GO / NO-GO** | **NO-GO** — hay viajes potencialmente mal clasificados y la vista de resolución es inusablemente lenta |
| **Hallazgo principal** | En Bogotá, el park `f4ac6fd...` concentra todos los viajes (2,989) pero solo tiene reglas de `Carga`. 188 viajes de tipo `Envíos` y `Moto` caen bajo slice `Carga` porque no hay reglas de Delivery para ese park. |
| **Hallazgo secundario** | La vista `ops.v_real_trips_business_slice_resolved` tarda >120s incluso con LIMIT 1, haciendo imposible auditar cobertura en tiempo real. |
| **Impacto operacional** | Omniview puede estar mostrando viajes de Delivery bajo la tajada de Carga en Bogotá. Plan vs Real, YTD y business slice facts heredan esta clasificación. |
| **¿Bloquea Closed Period Protection?** | **Sí** — no se puede congelar periodos cerrados si la clasificación actual no es 100% confiable. |

---

## 2. Inventario de reglas de mapping

| Regla | Fuente | Columnas usadas | Prioridad | Fallback | Riesgo |
|-------|--------|----------------|-----------|----------|--------|
| `TIPO_SERVICIO_MAPPING` | `data_contract.py:42-60` | `tipo_servicio` → `line_of_business` | 1 (más alta) | None → pasa a default_lob | Mapeo incompleto: cubre ~20 valores pero hay `tipo_servicio` sin match |
| `dim.dim_park.default_line_of_business` | `dim.dim_park` | `park_id` → `default_line_of_business` | 2 (media) | None → pasa a mapping_rules | Parks pueden tener LOB incorrecto o legacy |
| `ops.business_slice_mapping_rules` | Migración 111 | `park_id` + `tipo_servicio` / `works_terms` | 3 (resolución canónica) | `unmatched` si no hay match | 114 reglas activas. La resolución es correcta para los parks cubiertos |
| `dim.dim_business_slice_mapping` (canonical) | Migración 133 | `raw_value` → `canonical_value` | Capa de normalización | Retorna raw si no hay mapping | Solo 14 mapeos seed; puede quedarse corto |

**Algoritmo de resolución** (de `ops.v_real_trips_business_slice_resolved`, migración 111/118):
1. **Join** trips con `dim.dim_park` (park_id, city, country, default_lob)
2. **Join** con `ops.business_slice_mapping_rules` activas por `park_id`
3. **Score**: `park_plus_works_terms`=3, `park_plus_tipo_servicio`=2, `park_only`=1
4. **Best score wins** → ties broken by `is_subfleet ASC, mapping_rule_id ASC`
5. **Conflict**: si múltiples slices tienen el mismo best score → `resolution_status='conflict'`
6. **Unmatched**: si no hay ninguna regla para ese park_id → `resolution_status='unmatched'`

---

## 3. Coverage general (mayo 2026)

| Métrica | Valor |
|---------|-------|
| Total completed trips (raw `trips_2026`) | **475,034** |
| Active mapping rules | **114** |
| Distinct parks with rules | ~100 |
| Business slices definidas | 11 (Auto regular, YMM, Carga, Taxi Moto, Delivery moto, Delivery bicicleta, Delivery, Tuk Tuk, PRO, YMA, Tajada LOB visible) |
| `v_real_trips_business_slice_resolved` performance | **>120s timeout** — la vista es inusable para auditoría inline |

**Nota crítica**: No se pudo medir `matched/unmatched/ambiguous` a nivel global porque la vista `v_real_trips_business_slice_resolved` hace timeout incluso con LIMIT 1. Esta vista necesita optimización urgente (índices en `trips_2026.fecha_inicio_viaje`, materialización parcial, o particionamiento).

---

## 4. Auditoría Bogotá

### Parks en Bogotá

| Park ID | Ciudad | Default LOB | Reglas activas | Viajes mayo 2026 |
|---------|--------|-------------|----------------|-------------------|
| `f4ac6fdbf26043dfabdd3315bb4d67c6` | Bogotá | Cargo | 2 reglas Carga (park_only) | **2,989** |
| `3146c7869f1340e79442e543494d4870` | Bogotá | Delivery | 1 Delivery moto + 1 YMM | **0** |
| `35942031e01742c2b66bf084ad5c1efc` | Bogotá | Cargo | 2 reglas Carga (park_only) | **0** |

### Viajes del park f4ac6fd... (único con actividad)

| Tipo Servicio | Viajes completados | B2B | ¿Slice esperada? | ¿Slice asignada? |
|---------------|-------------------|-----|-----------------|------------------|
| Cargo | 2,801 | 0 | Carga | Carga (correcto) |
| Envíos | 147 | 0 | Delivery moto / Delivery | **Carga** (incorrecto) |
| Moto | 41 | 0 | Delivery moto / Moto | **Carga** (incorrecto) |

**Análisis**: El park `f4ac6fd...` tiene reglas de tipo `park_only` para Carga. Como `park_only` es el único tipo de regla que aplica, todos los viajes — sin importar su `tipo_servicio` — caen bajo Carga. Los 188 viajes de Envíos + Moto deberían clasificarse como Delivery o Moto, pero no hay reglas que lo permitan.

### Parks Delivery sin actividad

Los parks con reglas Delivery (`3146c78...`, `05458a8...`, `42473216...`) aparecen con **cero viajes** en mayo 2026. Esto sugiere que:
- Estos parks fueron dados de baja o renombrados
- Las reglas son legacy y apuntan a park_ids que ya no reciben viajes
- O los viajes de esos parks están cayendo en otro park_id por errores de asignación

---

## 5. Parks Delivery con cero viajes

| Park ID | Ciudad | Regla existente | Viajes mayo 2026 | Interpretación |
|---------|--------|----------------|-------------------|----------------|
| `3146c7869f1340e79442e543494d4870` | Bogotá | Delivery moto (park_only) | 0 | Regla activa pero park sin actividad. ¿Park legacy/dado de baja? |
| `05458a8...` (no confirmado) | Bogotá | Delivery | 0 | Misma situación |
| `42473216...` (no confirmado) | Bogotá | Delivery | 0 | Misma situación |

**Recomendación**: Verificar con operaciones si estos parks siguen activos. Si no, desactivar las reglas (`is_active=false`). Si sí, investigar por qué los viajes no están llegando a estos park_ids.

---

## 6. Viajes potencialmente mal clasificados

| Ciudad | Park ID | Tipo Servicio | Viajes | Slice actual | Slice sugerida | Razón |
|--------|---------|---------------|--------|-------------|----------------|------|
| Bogotá | `f4ac6fd...` | Envíos | 147 | Carga | Delivery moto | `tipo_servicio='Envíos'` es delivery según `TIPO_SERVICIO_MAPPING` |
| Bogotá | `f4ac6fd...` | Moto | 41 | Carga | Delivery moto | `tipo_servicio='Moto'` es moto según `TIPO_SERVICIO_MAPPING` |
| Bogotá | `f4ac6fd...` | Cargo | 2,801 | Carga | Carga | Correcto |

**Total viajes sospechosos en Bogotá**: **188 de 2,989 (6.3%)**

---

## 7. Trazabilidad: de raw trip a business_slice

```
raw trip (trips_2026)
  │
  ├── condicion = 'Completado'
  ├── park_id ──────────────────────┐
  ├── tipo_servicio ────────────────┤
  └── pago_corporativo ─────────────┤
                                    ▼
                        dim.dim_park (park_name, city, country, default_line_of_business)
                                    │
                                    ▼
                        ops.business_slice_mapping_rules (is_active)
                          │  join by park_id
                          │  score by rule_type
                          │  best score wins
                          │
                          ▼
                  ops.v_real_trips_business_slice_resolved
                    resolution_status: resolved | unmatched | conflict
                    business_slice_name: "Carga", "Delivery moto", etc.
                          │
                          ▼
                  ops.fn_real_trips_business_slice_resolved_subset()
                    (para cargas incrementales por mes)
                          │
                          ▼
                  ops.real_business_slice_{month,week,day,hour}_fact
                    (tablas fact agregadas)
                          │
                          ▼
                  business_slice_omniview_service
                          │
                          ▼
                  GET /ops/business-slice/omniview
                    (Omniview Matrix → frontend)
```

**Punto de fallo en Bogotá**: En el paso de `ops.business_slice_mapping_rules`, el park `f4ac6fd...` solo tiene reglas `park_only` para Carga. El algoritmo no considera `tipo_servicio` cuando la regla es `park_only`. Para que Envíos y Moto se clasifiquen correctamente, se necesitaría una regla adicional de tipo `park_plus_tipo_servicio` para este park.

---

## 8. Impacto en Omniview / Plan vs Real / YTD

| Componente | ¿Afectado? | Detalle |
|------------|:---:|---------|
| **Omniview Matrix** | **SÍ** | `business_slice_omniview_service` lee de `real_business_slice_month_fact` que se alimenta de la vista resolved. Si hay 188 viajes mal clasificados en Bogotá, Omniview muestra esos viajes bajo Carga en vez de Delivery. |
| **Plan vs Real** | **SÍ** | `plan_vs_real_service` usa `v_plan_vs_real_realkey_final` que se alimenta de real facts. La mala clasificación se propaga. |
| **YTD** | **SÍ** | YTD agrega desde las mismas fact tables. |
| **Weekly / Monthly** | **SÍ** | `real_business_slice_week_fact` y `real_business_slice_month_fact` heredan la clasificación. |
| **Supply** | No directamente | Supply usa driver stats, no business_slice. |
| **Freshness** | No | La clasificación no afecta métricas de frescura. |
| **Exportaciones** | **SÍ** | Cualquier export que use business_slice facts. |

**Magnitud**: 188 viajes en Bogotá de 475,034 totales = **0.04%**. Bajo numéricamente, pero el problema puede ser sistémico (otras ciudades pueden tener el mismo patrón de parks con reglas `park_only` que no discriminan por `tipo_servicio`).

---

## 9. Recomendaciones

### Quick fixes seguros (no requieren decisión de negocio)

1. **Agregar regla `park_plus_tipo_servicio` para `f4ac6fd...`**:
   ```sql
   INSERT INTO ops.business_slice_mapping_rules 
   (country, city, business_slice_name, fleet_display_name, park_id, rule_type, tipo_servicio_values, is_active)
   VALUES 
   ('Colombia', 'Bogotá', 'Delivery moto', 'Delivery Moto Bogotá', 'f4ac6fdbf26043dfabdd3315bb4d67c6', 'park_plus_tipo_servicio', ARRAY['Envíos', 'envíos', 'Moto', 'moto'], true);
   ```
   Esto corregiría los 188 viajes inmediatamente tras el próximo refresh de business slice facts.

2. **Desactivar reglas de parks Delivery sin actividad**: Si los parks `3146c78...`, `05458a8...`, `42473216...` están inactivos, marcar `is_active=false`.

3. **Optimizar `v_real_trips_business_slice_resolved`**: Agregar índices en `trips_2026(fecha_inicio_viaje, condicion)` y en `trips_2025(fecha_inicio_viaje, condicion)`. La vista tarda >120s incluso con LIMIT 1, lo que bloquea cualquier auditoría.

### Cambios que requieren decisión de negocio

4. **Auditar TODAS las reglas `park_only`**: Hay 79 reglas de Auto regular que son `park_only`. Cualquier park con regla `park_only` clasifica TODOS sus viajes bajo esa slice, ignorando `tipo_servicio`. Si un park Auto regular recibe viajes de Delivery, se clasificarían mal. Recomendación: cambiar reglas `park_only` a `park_plus_tipo_servicio` donde aplique.

5. **Política de cobertura mínima**: Establecer que el porcentaje de viajes `unmatched` debe ser <1% antes de cerrar un periodo. Si es mayor, no cerrar.

### Cambios que requieren migración

6. **Agregar columna `mapping_status` a las fact tables**: Para trazabilidad post-hoc, cada fila en `real_business_slice_*_fact` debería incluir `resolution_status` y `mapping_rule_id`.

### Cambios que NO deben hacerse todavía

- NO cambiar el algoritmo de resolución (scoring, prioridades)
- NO migrar reglas masivamente sin validar con operaciones
- NO congelar periodos cerrados hasta resolver este hallazgo

---

## 10. Prompt recomendado de implementación

```
Fase 1C.1 — Quick Fix Bogotá + Auditoría Global de Reglas park_only

1. Agregar regla park_plus_tipo_servicio para f4ac6fd... en Bogotá (INSERT en ops.business_slice_mapping_rules).
2. Ejecutar refresh de business_slice_month_fact para mayo 2026 en Bogotá:
   python -m scripts.refresh_business_slice_mvs --month 2026-05 --chunk-grain city
3. Verificar que los 188 viajes de Envíos+Moto ahora aparecen bajo Delivery moto.
4. Auditar TODOS los parks con reglas park_only: listar parks, su tipo_servicio real, y si hay desajuste.
5. Optimizar v_real_trips_business_slice_resolved con índices.
6. Reportar cobertura final: matched%, unmatched%, conflict%, suspected_wrong%.
7. NO cerrar periodos todavía.
```

---

## 11. Criterio de cierre

La Fase 1C solo queda GO si:

1. Se corrigen los 188 viajes mal clasificados en Bogotá.
2. Se auditan todas las reglas `park_only` y se confirma que no hay más parks con el mismo problema.
3. `v_real_trips_business_slice_resolved` responde en <10s para queries con filtro `trip_month`.
4. El porcentaje de `unmatched` global es <1%.
5. Se documenta el contrato de mapping (este documento).
6. Omniview refleja la clasificación corregida.

---

## Apéndice A: Datos crudos de la auditoría

### Reglas activas por business slice

| Slice | Reglas |
|-------|--------|
| Auto regular | 79 |
| YMM | 9 |
| Carga | 6 |
| Taxi Moto | 5 |
| Delivery moto | 4 |
| Delivery bicicleta | 4 |
| Delivery | 3 |
| Tuk Tuk | 1 |
| PRO | 1 |
| YMA | 1 |
| Tajada (LOB visible) | 1 |
| **Total** | **114** |

### Reglas por tipo

| Rule Type | Count |
|-----------|-------|
| park_only | ~90 |
| park_plus_tipo_servicio | ~15 |
| park_plus_works_terms | ~9 |

### Bogotá — parks y reglas

| Park ID (truncado) | Default LOB | Rule Slice(s) | Rule Type(s) | May Trips |
|---------------------|-------------|---------------|-------------|-----------|
| f4ac6fd... | cargo | Carga, Carga | park_only, park_only | 2,989 |
| 3146c78... | delivery | Delivery moto, YMM | park_only, park_plus_works_terms | 0 |
| 3594203... | cargo | Carga, Carga | park_only, park_only | 0 |

### Bogotá — viajes por tipo (park f4ac6fd...)

| Tipo Servicio | Viajes | B2B |
|---------------|--------|-----|
| Cargo | 2,801 | 0 |
| Envíos | 147 | 0 |
| Moto | 41 | 0 |
| **Total** | **2,989** | **0** |
