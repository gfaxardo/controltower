# Fase 1C.3B — Debug Refresh Inline + Barranquilla Repair

**Fecha**: 2026-05-19
**Fase**: Control Foundation — Fase 1C.3B
**Estado**: **GO** — Barranquilla 100%, coverage global 99.46%

---

## 1. Causa raíz técnica

**El park_id de la regla 95 (Taxi Moto) era incorrecto.**

| Elemento | Park ID |
|----------|---------|
| Regla 95 (original) | `ef21f793358144f589aabcbeb8bd7d5**1**` |
| dim.dim_park real | `ef21f793358144f589aabcbeb8bd7d5**0**` |
| trips_2026 real | `ef21f793358144f589aabcbeb8bd7d5**0**` |

El último carácter difería: `1` vs `0`. El join `lower(trim(b.park_id::text)) = lower(trim(rl.park_id::text))` nunca coincidía porque la normalización no corrige diferencias en el ID mismo. La regla 95 existía, estaba activa, tenía el `rule_type` correcto (`park_plus_tipo_servicio`) y los `tipo_servicio_values` correctos (`['moto']`), pero apuntaba a un park que no existe.

**Por eso el refresh inline NUNCA producía Taxi Moto**: ningún viaje real tiene ese park_id. El bug NO estaba en el motor de resolución (que funciona correctamente), sino en el dato de entrada (la regla).

---

## 2. Baseline

| Métrica | Antes del fix | Después del fix |
|---------|--------------|-----------------|
| Barranquilla raw | 23,653 | 23,653 |
| Barranquilla mapped | 11,032 (46.6%) | **23,653 (100%)** |
| Auto regular | 9,764 | 9,764 |
| Taxi Moto | **0** | **12,483** |
| Delivery moto | 1,268 | 1,406 |
| True unmatched | 12,621 | **0** |
| Coverage global | 96.80% | **99.46%** |

---

## 3. Fixes implementados

### Fix 1: Corregir park_id de rule 95

```sql
UPDATE ops.business_slice_mapping_rules 
SET park_id = 'ef21f793358144f589aabcbeb8bd7d50', 
    updated_at = NOW(),
    notes = COALESCE(notes,'') || ' [Fase 1C.3B: park_id corregido de ...d51 a ...d50]'
WHERE id = 95;
```

**Rollback**:
```sql
UPDATE ops.business_slice_mapping_rules 
SET park_id = 'ef21f793358144f589aabcbeb8bd7d51', updated_at = NOW()
WHERE id = 95;
```

### Fix 2: Nueva regla para Courier + Envíos (ID=144)

```sql
INSERT INTO ops.business_slice_mapping_rules (
    country, city, business_slice_name, fleet_display_name,
    is_subfleet, park_id, rule_type,
    tipo_servicio_values, works_terms_values,
    notes, is_active
) VALUES (
    'Colombia', 'Barranquilla', 'Delivery moto', 'Delivery Moto Barranquilla',
    false, 'ef21f793358144f589aabcbeb8bd7d50', 'park_plus_tipo_servicio',
    ARRAY['Courier', 'courier', 'Envios', 'envios', 'Envio', 'envio'],
    ARRAY[]::text[],
    'Fase 1C.3B: Courier y Envios del park ef21f793... deben ser Delivery moto.',
    true
);
```

**Rollback**:
```sql
UPDATE ops.business_slice_mapping_rules SET is_active = false WHERE id = 144;
```

---

## 4. Refresh ejecutado

| Campo | Valor |
|-------|-------|
| Método | `load_business_slice_month(cur, date(2026,5,1), conn)` directo |
| Scope | Mayo 2026 completo (todas las ciudades) |
| Materialización | 1,914,695 viajes en ~380s |
| Resolución | 9 chunks (city) en ~100s |
| Total rows inserted | 23 (mes completo) |
| Barranquilla rows | 4 (Auto regular, Taxi Moto, Delivery moto × 2 fleets) |

---

## 5. Validación Bogotá

| Métrica | Valor |
|---------|-------|
| Carga | 2,801 (sin cambios) |
| Delivery moto | 188 (sin cambios) |
| Total | 2,989 (sin cambios) |
| Rule 143 | Activa |
| Rule 142 | Inactiva |

---

## 6. Coverage global mayo 2026

| Ciudad | Raw | Mapped | Coverage |
|--------|-----|--------|----------|
| Barranquilla | 23,653 | 23,653 | **100%** |
| Bogotá | 2,989 | 2,989 | **100%** |
| Cúcuta | 315 | 315 | **100%** |
| Medellín | 2,057 | 2,057 | **100%** |
| Arequipa | 8,828 | 8,828 | **100%** |
| Trujillo | 17,738 | 17,738 | **100%** |
| Bucaramanga | 24 | 24 | **100%** |
| Cali | 148,476 | 147,225 | 99.2% |
| Lima | 270,954 | 269,639 | 99.5% |
| **GLOBAL** | **475,034** | **472,468** | **99.46%** |

---

## 7. Riesgos pendientes

| Riesgo | Fase |
|--------|------|
| Cali + Lima: ~2,566 viajes unmatched (~0.5% cada uno) | Fase 1C.3C (no bloquea Closed Period Protection) |
| 86 reglas park_only con tipos ignorados | Fase 1C.3C |
| Rule 95 park_id original era incorrecto — ¿hay más reglas con park_ids equivocados? | Fase 1C.3C |
| Resolved view >120s | Pendiente índices nocturnos |
| Refresh scoped por ciudad inexistente | Nice-to-have |

---

## 8. Recomendación

**Fase 1C puede cerrar.** Coverage global 99.46% está por encima del umbral mínimo (99%). Las reglas park_only pendientes no introducen errores de clasificación (solo son sub-óptimas porque no discriminan por tipo). Se puede avanzar a Fase 1D (Closed Period Protection).

**Siguiente**: Fase 1D — Closed Period Protection + period_state + snapshot ledger.
