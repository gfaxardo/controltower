# Fase 1C.1 — Business Slice Mapping Repair Bogotá

**Fecha**: 2026-05-19
**Fase**: Control Foundation — Fase 1C.1
**Estado**: **GO** (fix confirmado, 188 viajes corregidos)

---

## 1. Causa raíz

El park `f4ac6fdbf26043dfabdd3315bb4d679e` (Bogotá, Carga) es el único park de Bogotá con viajes en mayo 2026 (2,989 viajes). Sus únicas reglas activas eran dos `park_only` para Carga (IDs 108 y 109). Al ser `park_only`, **todos** los viajes se clasificaban como Carga sin importar el `tipo_servicio`.

Los parks con reglas Delivery (`3146c78...`, `05458a8...`, `42473216...`) tienen **cero viajes** en mayo 2026, por lo que los 188 viajes de Envíos + Moto del park Carga no tenían forma de clasificarse como Delivery.

---

## 2. Baseline antes del cambio

| Métrica | Valor |
|---------|-------|
| Raw completed trips (park f4ac6fd...) | 2,989 |
| Cargo | 2,801 |
| Envíos | 147 |
| Moto | 41 |
| **Fact table**: Carga | 2,989 |
| **Fact table**: Delivery | 0 |

---

## 3. Regla implementada

| Campo | Valor |
|-------|-------|
| **ID** | `143` |
| **Park ID** | `f4ac6fdbf26043dfabdd3315bb4d679e` |
| **Ciudad** | `Bogota` |
| **País** | `Colombia` |
| **Slice** | `Delivery moto` |
| **Fleet display** | `Delivery Moto Bogota` |
| **Rule type** | `park_plus_tipo_servicio` (score=2) |
| **Tipo servicio values** | `['Envios', 'envios', 'Moto', 'moto', 'Envio', 'envio']` |
| **Subfleet** | `false` |
| **Activa** | `true` |
| **Notas** | "Fase 1C.1 — Audit repair: Envios/Moto del park f4ac6fd deben ser Delivery moto, no Carga." |

La regla es **aditiva** — no se modificó ninguna regla existente. Las reglas `park_only` de Carga (IDs 108 y 109) siguen activas para el resto de `tipo_servicio` (Cargo).

---

## 4. Validación de precedencia

| Rule ID | Slice | Rule Type | Score | Tipos |
|---------|-------|-----------|-------|-------|
| **143** | Delivery moto | `park_plus_tipo_servicio` | **2** | Envios, Moto |
| 108 | Carga | `park_only` | 1 | Cargo |
| 109 | Carga | `park_only` | 1 | Cargo |

La regla `park_plus_tipo_servicio` (score=2) **gana** sobre `park_only` (score=1) para los `tipo_servicio` especificados. Para `tipo_servicio=Cargo`, solo aplican las reglas `park_only`, por lo que Carga sigue clasificándose correctamente.

---

## 5. Resultado post-change

| Métrica | Antes | Después | Delta |
|---------|-------|---------|-------|
| Raw completed (park) | 2,989 | 2,989 | **0** |
| Fact: Carga | 2,989 | 2,801 | **-188** |
| Fact: Delivery moto | 0 | 188 | **+188** |
| Fact: Total | 2,989 | 2,989 | **0** |
| Cargo (raw) → slice | Carga | Carga | Correcto |
| Envíos (raw) → slice | Carga | Delivery moto | **Corregido** |
| Moto (raw) → slice | Carga | Delivery moto | **Corregido** |
| Unmatched | 0 | 0 | Sin cambio |
| Ambiguous | 0 | 0 | Sin cambio |

---

## 6. Refresh ejecutado

| Campo | Valor |
|-------|-------|
| Script | `refresh_business_slice_mvs --month 2026-05 --chunk-grain city` |
| Scope | Mes completo (mayo 2026), todas las ciudades |
| Bogotá chunk | `[2/9] colombia/bogota inserted=2` |
| Duration | ~107s para month_fact (day_fact continuó en background) |
| refresh_run_log | Registrado vía `refresh_guard` en `ops.refresh_run_log` |

**Nota**: El refresh fue del mes completo porque `--chunk-grain city` procesa todas las ciudades del mes. No existe refresh scoped a una sola ciudad. Esto recalcula mayo para todas las ciudades (~1.9M viajes materializados), no solo Bogotá.

---

## 7. Rollback

```sql
-- Desactivar la regla (soft delete)
UPDATE ops.business_slice_mapping_rules 
SET is_active = false, notes = notes || ' [ROLLBACK Fase 1C.1 ' || NOW()::text || ']'
WHERE id = 143;

-- Para revertir completamente (borrar):
-- DELETE FROM ops.business_slice_mapping_rules WHERE id = 143;

-- Refrescar month_fact para restaurar estado anterior:
-- cd backend && python -m scripts.refresh_business_slice_mvs --month 2026-05 --chunk-grain city
```

---

## 8. Impacto en Omniview

Omniview y todos los consumidores de `ops.real_business_slice_month_fact` ahora reflejan la clasificación corregida:
- Bogotá mayo 2026: Carga=2,801, Delivery moto=188
- Sin cambios en otros países/ciudades
- Sin cambios en KPIs o fórmulas

---

## 9. Riesgos pendientes

| Riesgo | Estado |
|--------|--------|
| `ops.v_real_trips_business_slice_resolved` lenta (>120s timeout) | **Pendiente Fase 1C.2** |
| 102 reglas `park_only` activas — posibles más parks con el mismo problema | **Pendiente auditoría global Fase 1C.2** |
| Parks Delivery con 0 viajes (reglas legacy) | **Pendiente validación con operaciones** |
| No se pudo medir coverage global (unmatched/ambiguous) por timeout del resolved view | **Pendiente Fase 1C.2** |
| Coverage medida solo vía fact tables (confiable pero derivada) | Aceptable para Fase 1C.1 |

---

## 10. Siguiente fase recomendada

**Fase 1C.2 — Business Slice Resolved View Performance + Auditoría Global park_only**

1. Optimizar `ops.v_real_trips_business_slice_resolved` con índices
2. Auditar todas las reglas `park_only` (102 activas) para detectar más parks mal clasificados
3. Medir coverage global: matched%, unmatched%, conflict%, suspected_wrong%
4. Establecer umbral de cobertura mínima antes de Closed Period Protection

---

## Apéndice: Comandos ejecutados

```bash
# 1. Insertar regla (aditiva, no modifica reglas existentes)
# Ejecutado vía _fix_bogota_rule.py
INSERT INTO ops.business_slice_mapping_rules (...) VALUES (...)
-- ID resultante: 143

# 2. Refrescar month_fact (scope = mes completo, todas las ciudades)
cd backend
python -m scripts.refresh_business_slice_mvs --month 2026-05 --chunk-grain city

# 3. Validar (ejecutado vía _validate_bogota_fix.py)
# Resultado: Carga 2989→2801, Delivery 0→188, total unchanged 2989
```
