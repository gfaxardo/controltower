# Yango Loyalty — Paquete de Validación de Definiciones

**Para:** Equipo Yango Operaciones
**De:** Control Tower / Data Engineering
**Fecha:** Mayo 2026
**Estado:** PENDIENTE VALIDACIÓN — Scoring bloqueado hasta respuesta

---

## 1. Contexto

YEGO Control Tower está implementando Yango Loyalty Performance para Lima (piloto).
Tenemos AD y Supply Hours funcionando, pero **Nuevos + Reactivados (N+R) difiere fuertemente
del reporte oficial Yango de Abril 2026.** Necesitamos validar definiciones antes de activar
scoring Oro/Plata/Bronce.

---

## 2. Referencia Oficial Yango — Abril 2026 Lima

| Métrica | Target | Result |
|---------|--------|--------|
| Active Drivers | 5,295 | 5,601 |
| Supply Hours | 356,000 | 357,000 |
| N+R | 1,261 | 1,064 |
| **Metas cumplidas** | | **2/3** |
| **Categoría** | | **Plata** |

---

## 3. Cálculos de Control Tower por Definición Candidata

### 3.1 Tabla Comparativa

| Definition Set | AD | SH | Nuevos | Reactivados | N+R | Diff N+R vs Yango 1,064 | Fuente AD | Runtime |
|---|---|---|---|---|---|---|---|---|
| hybrid_ct_default | 5,496 | 310,730 | ~2,000 | ~937 | ~2,937 | +176% | real_business_slice Auto regular | ~10s |
| trips_based_fallback | consultar | 310,730 | consultar | consultar | ~1,906 | +79% | trips_2025+2026 | ~8s |
| connection_based | 5,087 | 310,730 | consultar | consultar | ~5,798 | +445% | fleet_summary conexión | ~5s |
| supply_based | 5,087 | 310,730 | consultar | consultar | ~5,798 | +445% | fleet_summary SH>0 | ~5s |
| lifecycle_candidate | 5,496 | 310,730 | consultar | consultar | ~2,937 | +176% | real_business_slice | ~10s |

### 3.2 Notas

- **AD**: hybrid_ct_default coincide dentro de 1.9% del reporte Yango (5,496 vs 5,601)
- **SH**: 310,730 vs 357,000 (-13%). La diferencia es porque `fleet_summary_daily` NO contiene todos los drivers de Lima. ~514 drivers Auto regular faltan en esta tabla.
- **N+R**: Ninguna definición candidata coincide. La mejor (trips_based_fallback) difiere +79%.

---

## 4. Preguntas Exactas para Yango

### Definición de Active Driver

1. Un **Active Driver** en el reporte Yango de abril, ¿se define como:
   - [ ] Driver con al menos 1 viaje completado en el mes
   - [ ] Driver con supply hours > 0 en el mes
   - [ ] Driver conectado al menos 1 día en el mes
   - [ ] Driver con lifecycle_status = "active"
   - [ ] Otro: ___________________

2. El universo de drivers para el reporte, ¿incluye solo el partner principal de Yango (Auto regular) o también Delivery, Tuk Tuk, Carga, YMA, PRO?

### Definición de Nuevo

3. Un **Nuevo** en el reporte Yango de abril, ¿se define como:
   - [ ] Primer viaje completado histórico en el mes (first completed trip ever)
   - [ ] Primer día con supply hours > 0 (first connection/online day)
   - [ ] Registro aprobado/habilitado dentro del mes (approval/activation date)
   - [ ] Primera aparición en el sistema del partner (first day in fleet_summary)
   - [ ] Otro: ___________________

### Definición de Reactivado

4. Un **Reactivado** en el reporte Yango de abril, ¿se define como:
   - [ ] Driver activo en abril que NO tuvo viajes en marzo (1 mes de inactividad)
   - [ ] Driver activo en abril que NO tuvo viajes en febrero+marzo (2 meses)
   - [ ] Driver activo en abril que NO tuvo viajes en los últimos 30 días antes de abril 1
   - [ ] Driver activo en abril que NO tuvo viajes en los últimos 60 días
   - [ ] Driver con flag lifecycle `reactivated_week = true`
   - [ ] Otro: ___________________

5. La inactividad, ¿se mide por ausencia de viajes completados o por ausencia de supply hours/conexión?

### Fuente de Datos

6. ¿Cuál es la fuente oficial de los números del reporte Yango abril 2026?
   - [ ] Tabla de trips (Yango platform trips)
   - [ ] Fleet summary / driver activity summary
   - [ ] Lifecycle / driver status table
   - [ ] Reporte KAM / Excel enviado por Yango
   - [ ] Otro: ___________________

7. ¿La fuente está disponible para consulta directa (tabla en DB) o es un reporte externo?

---

## 5. Recomendación Técnica Preliminar

**Definición candidata recomendada:** `hybrid_ct_default`

- **AD**: `SUM(active_drivers)` from `ops.real_business_slice_month_fact`, Auto regular only → coincidencia 98.1%
- **SH**: `SUM(work_time_hours)` from `public.module_ct_fleet_summary_daily` → cobertura 87% (gap conocido)
- **N+R**: Definición actual usa 30 días de inactividad + fleet_summary universe → +176% de diferencia. **Necesita validación Yango antes de usar.**

**Alternativa si N+R se define por trips:** `trips_based_fallback` con AD desde trips (valor exacto por validar).

---

## 6. NO-GO para Scoring

Hasta que las preguntas 1-7 sean respondidas y validadas, el scoring Performance Lima (Oro/Plata/Bronce)
permanece **BLOQUEADO** en Control Tower.

```
scoring_status = "blocked_pending_yango_definition_validation"
performance_category = null
```

---

## 7. Cómo Responder

Responder este documento marcando las opciones [x] o enviando un correo a:
- Control Tower Data Engineering
- Adjuntar definiciones oficiales de Yango si están documentadas

---

**Documento generado por:** YEGO Control Tower / Metric Definition Registry
**Versión:** 1.0 / Mayo 2026
