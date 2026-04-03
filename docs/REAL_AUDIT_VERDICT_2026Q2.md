# Veredicto de Auditoría REAL — Q2 2026

**Fecha:** 2026-04-02
**Ejecutado por:** Auditoría automatizada sobre `public.trips_2025` + `public.trips_2026` + `dim.dim_park`
**Scripts:** `backend/scripts/audit_real_completados_vs_cancelados.py`, `backend/scripts/audit_real_universe_unmapped.py`

---

## 1. RESUMEN EJECUTIVO

### Hallazgos confirmados

1. **Fuentes raw oficiales (`trips_2025` + `trips_2026`) son funcionales y auditables.** Ambas tablas comparten schema idéntico con las 15 columnas críticas.
2. **El universo territorial está 100% mapeado.** Los 29 parks de `dim.dim_park` cubren la totalidad de los 59.2M viajes. No hay pérdida de universo por unmapped.
3. **La cobertura de campos operativos (ticket, driver, park, tipo_servicio, fecha_fin) es 100%** en completados y cancelados.
4. **`comision_empresa_asociada` tiene un problema REAL y GRAVE** en `trips_2025` (0% cobertura en completados) y parcial en `trips_2026` (solo enero 2026 tiene 94.45%).
5. **El null masivo previo de comisión era PARCIALMENTE un falso positivo** por auditar sobre todo el universo (incluyendo ~46M cancelados que no tienen comisión), pero el problema subyacente es real: la columna simplemente no fue poblada en trips_2025.

### Qué queda pendiente

1. Migrar las cadenas productivas de `trips_all` a `trips_2025 + trips_2026`
2. Resolver el vacío de `comision_empresa_asociada` en trips_2025 y los meses faltantes de trips_2026
3. Ejecutar rebuild de facts/MVs una vez resueltos los puntos anteriores

---

## 2. FASE 0 — Reglas congeladas

### Archivos creados/actualizados

| Archivo | Acción |
|---------|--------|
| `docs/SOURCE_OF_TRUTH_REAL_AUDIT_V2.md` | **CREADO** — Definición oficial de fuentes raw |
| `docs/source_dataset_policy.md` | **ACTUALIZADO** — trips_2025 agregado, trips_all marcado explícitamente como legacy |
| `docs/real_trip_source_contract.md` | **ACTUALIZADO** — trips_2025 agregado, trips_all marcado como LEGACY |

### Reglas congeladas

| Regla | Definición |
|-------|-----------|
| Raw oficial | `public.trips_2025` + `public.trips_2026` |
| Legacy | `public.trips_all` — solo compatibilidad temporal |
| Completados | `condicion = 'Completado'` → revenue, ticket, drivers, comisión |
| Cancelados | `condicion = 'Cancelado' OR ILIKE '%cancel%'` → métricas de cancelación |
| Unmapped | NO excluir; visibilizar como fallback |

---

## 3. FASE 1 — Uso de trips_all vs trips_2025/trips_2026

### Archivo creado

`docs/REAL_SOURCE_USAGE_AUDIT_2026Q2.md`

### Tabla resumida

| Fuente | Archivos productivos (runtime) | Archivos scripts/SQL | Migraciones Alembic | Docs |
|--------|-------------------------------|---------------------|--------------------|----|
| `trips_all` | 5 (1 query directa + 4 docstrings) | ~18 scripts Python + ~13 SQL | ~35 migraciones | ~48 docs |
| `trips_2025` | 0 directos (via mig 118) | 0 | 1 (mig 118) | 4 |
| `trips_2026` | 2 (adapters/services ref) | ~15 scripts | ~20 migraciones | ~40 docs |

### Riesgos principales

| Riesgo | Detalle |
|--------|---------|
| **CRÍTICO** | `territory_quality_service.py` hace `FROM public.trips_all` en endpoint productivo |
| **CRÍTICO** | `v_trips_real_canon_120d` (base de cadena hourly-first) une trips_all + trips_2026 |
| **CRÍTICO** | `mv_real_trips_monthly` se construyó desde trips_all (Resumen, Plan vs Real) |
| **ALTO** | `trips_unified` (Driver Lifecycle) une trips_all + trips_2026 |
| **CERRADO** | Business Slice ya migrado a trips_2025 + trips_2026 (mig 118) |

---

## 4. FASE 2 — Auditoría semántica completados vs cancelados

### Universo total

| Tabla | Total viajes | Completados | Cancelados | Otros |
|-------|-------------|-------------|------------|-------|
| trips_2025 | 47,952,973 | 10,198,269 (21.3%) | 37,751,902 (78.7%) | 2,802 |
| trips_2026 | 11,254,761 | 2,659,652 (23.6%) | 8,594,227 (76.3%) | 882 |
| **TOTAL** | **59,207,734** | **12,857,921 (21.7%)** | **46,346,129 (78.3%)** | **3,684** |

### Valores de `condicion` encontrados

| Valor | trips_2025 | trips_2026 | Clasificación |
|-------|-----------|-----------|--------------|
| Completado | 10,198,269 | 2,659,652 | completado |
| Cancelado | 37,751,902 | 8,594,227 | cancelado |
| En viaje | 1,241 | 113 | otro |
| Sin condición | 1,125 | 251 | otro |
| Esperando | 384 | 44 | otro |
| Выполнен (ruso: completado) | 31 | 13 | otro* |
| Conduciendo | 18 | 460 | otro |
| Отменён (ruso: cancelado) | 3 | 1 | otro* |

*Nota: Existen 44 viajes en ruso (Выполнен = completado, Отменён = cancelado). Son despreciables pero deberían clasificarse correctamente en la normalización.*

### Cobertura de campos sobre COMPLETADOS

| Campo | trips_2025 (todos los meses) | trips_2026 ene | trips_2026 feb | trips_2026 mar | trips_2026 abr |
|-------|------------------------------|----------------|----------------|----------------|----------------|
| **comision_empresa_asociada (nonzero)** | **0.00%** | **94.45%** | **49.91%** | **0.00%** | **0.00%** |
| precio_yango_pro (ticket) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| conductor_id | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| park_id | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| tipo_servicio | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| fecha_finalizacion | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

### Cobertura de campos sobre CANCELADOS

| Campo | Cobertura (todas las tablas/meses) |
|-------|-----------------------------------|
| motivo_cancelacion | ~100% |
| park_id | 100% |
| tipo_servicio | 100% |
| conductor_id | 100% |

### Veredicto sobre `comision_empresa_asociada`

**MIXTO (A + B):**

- **(A) La auditoría previa ESTABA mal planteada**: medir cobertura de `comision_empresa_asociada` sobre todo el universo (59.2M viajes) producía un 2.15% de cobertura, que es alarmante. Al filtrar solo completados, sube a 9.89%. Esto confirma que la métrica sobre el universo bruto distorsionaba el diagnóstico porque los ~46M cancelados nunca deben tener comisión.

- **(B) PERO HAY un hueco REAL y GRAVE**:
  - **trips_2025**: `comision_empresa_asociada` está VACÍA (literalmente 6 registros de 10.2M completados). Esto NO es un falso positivo; el campo simplemente no fue ingerido/poblado para 2025.
  - **trips_2026 enero**: 94.45% cobertura → BUENO
  - **trips_2026 febrero**: 49.91% → PARCIAL (degradación mid-month)
  - **trips_2026 marzo-abril**: 0.00% → VACÍO (regresión de ingestión)

**Causa raíz probable**: El proceso de ingestión de `comision_empresa_asociada` solo estuvo activo parcialmente en enero-febrero 2026. Para 2025 nunca se pobló. Para marzo 2026 en adelante, se perdió o nunca se activó.

**Impacto**: Revenue (`SUM(comision_empresa_asociada)`) es NULL/0 para todo 2025 y para marzo 2026+. Esto afecta a Resumen, Plan vs Real, Business Slice y cualquier vista que calcule revenue.

---

## 5. FASE 3 — Reconciliación universo unmapped

### Hallazgo principal: 100% MAPEADO

| Categoría | Viajes | Porcentaje |
|-----------|--------|-----------|
| **fully_mapped** | **59,207,734** | **100.00%** |
| park_unmapped | 0 | 0% |
| park_null | 0 | 0% |
| country_unmapped | 0 | 0% |
| city_unmapped | 0 | 0% |

### Distribución por ciudad (top 9 — son todas)

| País | Ciudad | Viajes | % mapeado |
|------|--------|--------|-----------|
| Colombia | Cali | 22,484,314 | 100% |
| Perú | Lima | 18,504,374 | 100% |
| Colombia | Barranquilla | 9,283,058 | 100% |
| Colombia | Medellín | 6,712,554 | 100% |
| Perú | Trujillo | 1,354,288 | 100% |
| Perú | Arequipa | 698,543 | 100% |
| Colombia | Bucaramanga | 87,382 | 100% |
| Colombia | Bogotá | 68,032 | 100% |
| Colombia | Cúcuta | 15,189 | 100% |

### dim.dim_park

- 29 parks registrados
- Todos con country y city poblados
- 0 parks unmapped en trips_2025/trips_2026

### tipo_servicio (completados)

| tipo_servicio | Viajes | % |
|---------------|--------|---|
| Económico | 9,209,848 | 71.63% |
| Moto | 1,828,793 | 14.22% |
| Confort | 710,569 | 5.53% |
| Standard | 403,837 | 3.14% |
| Tuk-tuk | 198,745 | 1.55% |
| Confort+ | 137,203 | 1.07% |
| Courier | 84,484 | 0.66% |
| Minivan | 66,888 | 0.52% |
| Mensajería | 59,837 | 0.47% |
| Cargo | 49,808 | 0.39% |
| Start | 48,808 | 0.38% |
| Exprés | 28,646 | 0.22% |
| Envíos | 21,408 | 0.17% |
| Premier | 8,919 | 0.07% |
| (basura/direcciones) | ~75 | <0.01% |
| (null/vacío) | 5 | <0.01% |

**Nota**: Hay ~75 registros con datos de dirección en `tipo_servicio` (datos contaminados). Son despreciables (<0.01%) pero deben clasificarse como "otro" en LOB.

### Propuesta para visibilizar unmapped (fase posterior)

Aunque hoy el universo está 100% mapeado, la recomendación es:
1. Mantener la categoría `UNMAPPED` en la capa de resolución territorial
2. Si se onboardean nuevos parks o se ingesta nueva data que no mapee, aparecerá como `UNMAPPED` automáticamente
3. Implementar en `ops.v_real_trips_enriched_base` (ya hace LEFT JOIN con dim.dim_park)
4. Agregar alerta automática si `pct_unmapped > 2%` en cualquier mes

---

## 6. CAMBIOS REALIZADOS EN EL REPO

| # | Archivo | Tipo | Qué cambió |
|---|---------|------|-----------|
| 1 | `docs/SOURCE_OF_TRUTH_REAL_AUDIT_V2.md` | **CREADO** | Definición oficial: raw = trips_2025 + trips_2026, semántica completados/cancelados, reglas de unmapped |
| 2 | `docs/REAL_SOURCE_USAGE_AUDIT_2026Q2.md` | **CREADO** | Inventario completo de referencias a trips_all/trips_2025/trips_2026 en todo el repo |
| 3 | `docs/REAL_AUDIT_VERDICT_2026Q2.md` | **CREADO** | Este documento: veredicto final con evidencia concreta |
| 4 | `docs/source_dataset_policy.md` | **ACTUALIZADO** | Agregado trips_2025, marcado trips_all como legacy explícitamente |
| 5 | `docs/real_trip_source_contract.md` | **ACTUALIZADO** | Agregado trips_2025, marcado trips_all como LEGACY, referencia a SOURCE_OF_TRUTH_REAL_AUDIT_V2 |
| 6 | `backend/scripts/audit_real_completados_vs_cancelados.py` | **CREADO** | Script de auditoría read-only para FASE 2 |
| 7 | `backend/scripts/audit_real_universe_unmapped.py` | **CREADO** | Script de auditoría read-only para FASE 3 |

**NO se tocaron:** facts, MVs, vistas SQL, frontend, migraciones, servicios productivos, routers.

---

## 7. NO-GO / GO PARCIAL / GO

### Dictamen: **GO PARCIAL**

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Fuente raw oficial definida | **GO** | trips_2025 + trips_2026 congelados como oficiales |
| Semántica completados/cancelados | **GO** | Definición clara y verificada con datos |
| Inventario trips_all | **GO** | 100% inventariado; riesgos clasificados |
| Mapeo territorial | **GO** | 100% mapeado; sin pérdida de universo |
| comision_empresa_asociada | **NO-GO** | 0% en trips_2025, parcial en trips_2026 |
| Migración de cadenas a trips_2025+2026 | **PENDIENTE** | Requiere nuevas migraciones Alembic |
| Rebuild de facts/MVs | **PENDIENTE** | Requiere resolver comisión primero |

**Condiciones para GO completo:**
1. Resolver ingestión de `comision_empresa_asociada` en trips_2025 (backfill o decisión de negocio)
2. Resolver la regresión de ingestión en trips_2026 marzo+
3. Migrar `v_trips_real_canon_120d` a trips_2025 + trips_2026
4. Migrar `mv_real_trips_monthly` a trips_2025 + trips_2026
5. Rebuild de facts y MVs

---

## 8. SIGUIENTE PASO PROPUESTO

### Plan de fase posterior (priorizado)

| # | Acción | Prioridad | Esfuerzo | Dependencia |
|---|--------|-----------|----------|-------------|
| 1 | **Investigar y resolver `comision_empresa_asociada`** en trips_2025 y trips_2026 mar+ | P0 | ALTO | Equipo de ingestión / fuente upstream |
| 2 | **Migrar `territory_quality_service.py`** de trips_all a trips_2025+2026 | P1 | BAJO | Ninguna |
| 3 | **Crear migración** para recrear `v_trips_real_canon_120d` con trips_2025+2026 | P1 | MEDIO | Decidir si se mantiene ventana 120d o se expande |
| 4 | **Crear migración** para recrear `trips_unified` con trips_2025+2026 | P2 | MEDIO | #3 |
| 5 | **Crear migración** para rebuild `mv_real_trips_monthly` con trips_2025+2026 | P2 | MEDIO-ALTO | #1 (comisión resuelta) |
| 6 | **Ejecutar rebuild** de cadena hourly-first y facts | P3 | ALTO | #3, #1 |
| 7 | **Deprecar trips_all** de forma segura (mantener tabla, eliminar de code paths) | P3 | BAJO | #3, #4, #5 |
| 8 | **Clasificar los ~44 viajes en ruso** (Выполнен/Отменён) correctamente | P4 | BAJO | Ninguna |
| 9 | **Limpiar ~75 registros con direcciones en tipo_servicio** | P4 | BAJO | Ninguna |

### Riesgo clave

Si no se resuelve `comision_empresa_asociada`, el rebuild de facts producirá revenue = NULL/0 para todo 2025 y para marzo 2026+. Esto no es aceptable. **El paso #1 es bloqueante.**
