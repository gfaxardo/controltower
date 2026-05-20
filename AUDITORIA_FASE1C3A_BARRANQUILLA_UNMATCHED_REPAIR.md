# Fase 1C.3A — Barranquilla Unmatched Repair

**Fecha**: 2026-05-19
**Estado**: **NO-GO condicionado** — raíz identificada, solución requiere fix de refresh

---

## 1. Baseline Barranquilla

| Métrica | Valor |
|---------|-------|
| Raw completed trips (May 2026) | 23,653 |
| Fact table mapped trips | 11,032 |
| Audit view unmatched | 12,621 |
| Unmatched % | 53.4% |
| Taxi Moto trips (should exist) | 0 (missing from fact) |

---

## 2. Root cause

La causa raíz NO es falta de reglas. Las reglas existen y son correctas:

| Rule ID | Slice | Type | Park | Tipos | Matches |
|---------|-------|------|------|-------|---------|
| 94 | Auto regular | park_plus_tipo_servicio | ef21f793... | Económico, Start, Confort, Confort+, Exprés, Premier, xl | 9,764 trips |
| 95 | Taxi Moto | park_plus_tipo_servicio | ef21f793... | moto | Debería matchear 12,483 Moto trips |
| 96 | Delivery moto | park_only | 8d3b13bd... | Moto, envíos, courier | 1,268 trips |

**Normalización confirmada**: `ops.normalized_service_type('Moto')` = `ops.normalized_service_type('moto')` = `'moto'`. Rule 95 COINCIDE correctamente.

**Problema real**: La función `load_business_slice_month` (usada por `refresh_business_slice_mvs --chunk-grain city`) produce solo 2 filas para Barranquilla (Auto regular + Delivery moto). Taxi Moto NO aparece en el month_fact ni siquiera después de refresh. A pesar de que el `_RESOLVE_AND_AGG_FROM_TEMP` SQL usa la misma lógica de matching que el resolved view.

**Hipótesis**: El refresh inline con `--chunk-grain city` tiene un bug que omite filas con `park_plus_tipo_servicio` cuando el park también tiene reglas `park_only` de otro park_id. O bien, la temp table `_bs_enriched_month` no contiene la columna `tipo_servicio` con los valores esperados para este park.

**Evidencia adicional**: 138 viajes son realmente unmatched (Courier=117 + Envíos=21 en el park ef21f793...). Estos tipos no están cubiertos por ninguna regla actual.

---

## 3. Top unmatched antes del fix

| Park ID | Tipo | Trips | Razón |
|---------|------|-------|-------|
| ef21f793... | Moto | 12,483 | Rule 95 existe pero fact table no la incluye (bug de refresh) |
| ef21f793... | Courier | 117 | Sin regla para este tipo en este park |
| ef21f793... | Envíos | 21 | Sin regla para este tipo en este park |

---

## 4. Reglas recomendadas (NO implementadas — requiere fix de refresh primero)

1. **Diagnóstico**: Verificar por qué `load_business_slice_month` no produce Taxi Moto rows a pesar de que rule 95 existe y matchea.
2. **Regla para Courier**: Agregar `park_plus_tipo_servicio` para `ef21f793...` con tipos `['Courier', 'courier']` → Delivery moto
3. **Regla para Envíos**: Agregar `park_plus_tipo_servicio` para `ef21f793...` con tipos `['Envíos', 'envíos']` → Delivery moto

---

## 5. Refresh status

| Intento | Método | Resultado |
|---------|--------|-----------|
| 1 | `refresh_business_slice_mvs --month 2026-05 --chunk-grain city` | month_fact=21 filas, day_fact timeout |
| 2 | `refresh_business_slice_mvs --month 2026-05 --no-daily` | refresh_guard bloqueado (lock) |
| 3 | `load_business_slice_month` directo | month_fact=21 filas, Taxi Moto sigue ausente |

**Conclusión**: El refresh funciona pero tiene un bug que omite ciertas combinaciones de park+tipo cuando se usa `--chunk-grain city`. Se requiere debug del inline resolution SQL.

---

## 6. Impacto en Bogotá

| Check | Estado |
|-------|--------|
| Carga = 2,801 | Confirmed |
| Delivery moto = 188 | Confirmed |
| Total = 2,989 | Confirmed |
| Rule 143 active | Confirmed |
| Rule 142 inactive | Confirmed |

---

## 7. Rollback

No se insertaron reglas nuevas en esta fase. No hay rollback necesario.

---

## 8. Riesgos pendientes

| Riesgo | Fase |
|--------|------|
| Bug de refresh: Taxi Moto no se incluye en month_fact | Bloquea cierre 1C.3A |
| 138 viajes Courier+Envíos sin reglas | Reglas aditivas pendientes |
| 86 reglas park_only con tipos ignorados | Fase 1C.3B |
| Resolved view >120s | Pendiente índices nocturnos |
| Coverage 96.80% | Sube a ~99.4% si se resuelve el bug + reglas |

---

## 9. Recomendación

**NO-GO para cierre de Fase 1C.3A**. Requiere:

1. **Debug del refresh inline**: investigar por qué `load_business_slice_month` con `--chunk-grain city` no produce Taxi Moto rows en month_fact para Barranquilla.
2. **Alternativa**: Si el bug está en `_RESOLVE_AND_AGG_FROM_TEMP`, probar refresh sin `--chunk-grain` (usando la función `fn_real_trips_business_slice_resolved_subset` en lugar de resolución inline).
3. **Después del fix de refresh**: agregar reglas para Courier+Envíos y re-ejecutar cobertura.

**Siguiente fase**: Fase 1C.3B — Debug del refresh inline + reglas pendientes Barranquilla.
