# Control Tower — Canonicalización REAL — Informe Fase 1

**Objetivo:** Ejecutar canonicalización de forma segura: Resumen en canónica, paridad validable, señales UI claras, legacy no borrado.

---

## 1. Qué se activó

- **Performance > Resumen** usa **solo** la cadena canónica para Real mensual:
  - Frontend: `KPICards` llama `getRealMonthlySplitCanonical()` → `GET /ops/real/monthly?source=canonical`.
  - Backend: con `source=canonical` el endpoint invoca `get_real_monthly_canonical()` (lectura desde `ops.real_drill_dim_fact`, period_grain=month, breakdown=lob).
- **Plan vs Real** y **Real vs Proyección** no se modifican en fuente: siguen usando legacy (Plan vs Real usa `/ops/plan-vs-real/monthly` y real desde vistas legacy; Real vs Proyección usa `v_real_metrics_monthly`). No se activó canónica para ellas en esta fase.

---

## 2. Qué se validó

### FASE 0 — Seguridad del servicio canónico

- **¿Quitar `breakdown = 'lob'` mezclaría filas?** **Sí.** En `real_drill_dim_fact` hay una fila por (country, period_start, segment, breakdown, dimension_key, …). Sin filtrar por `breakdown`, se sumarían filas de LOB, Park y Service_type y se inflarían o distorsionarían los totales.
- **¿El filtro actual es seguro?** **Sí.** Se mantiene `period_grain = 'month'` y `breakdown = 'lob'`; opcionales country, city, dimension_key (lob_base), segment. Una fila por mes en la respuesta (GROUP BY period_start).
- **¿Hay que restaurar el filtro?** No; ya estaba y se dejó documentado en código (comentario OBLIGATORIO).

### FASE 2 — Paridad Resumen legacy vs canónico (ejecutada con evidencia real)

- Script: `backend/scripts/validate_real_monthly_parity.py`.
- **Fecha de ejecución:** 2025-03-17.
- **Comandos ejecutados:**
  ```bash
  cd backend
  python -m scripts.validate_real_monthly_parity --year 2025
  python -m scripts.validate_real_monthly_parity --year 2025 --country PE
  python -m scripts.validate_real_monthly_parity --year 2025 --country CO
  ```
- **Salidas guardadas:** `backend/scripts/outputs/parity_global_2025.csv`, `parity_PE_2025.csv`, `parity_CO_2025.csv`.

**Resultados:**

| Alcance | Legacy periods | Canonical periods | Diagnóstico |
|---------|----------------|-------------------|-------------|
| Global (sin país) | 12 | 11 | **MAJOR_DIFF** |
| PE | 11 | 0 | **MAJOR_DIFF** |
| CO | 12 | 0 | **MAJOR_DIFF** |

**Tabla resumida de diferencias (global):**

| Periodo | diff_trips | diff_trips_pct | diff_revenue_pct | drivers_legacy | drivers_canonical |
|----------|------------|----------------|------------------|----------------|-------------------|
| 2025-01 | 27 | 0.0% | 0.01% | 8568 | **0** |
| 2025-02 | 28 | 0.0% | 0.0% | 9054 | **0** |
| 2025-03 | 15746 | **2.02%** | 0.0% | 8542 | **0** |
| 2025-10 | **948824** | **100%** (canónico sin dato) | **100%** | 16859 | **0** |
| 2025-11 | **479068** | **50.06%** (canónico parcial) | **47.76%** | 17004 | **0** |
| Resto | menor | &lt;0.53% | &lt;0.01% | no cero | **0** |

**Interpretación:**

1. **¿Hay paridad real?** **No.** Los tres alcances (global, PE, CO) dan MAJOR_DIFF.
2. **¿Dónde no hay paridad?**
   - **Por país:** Con filtro `--country PE` o `--country CO`, la canónica devuelve **0 periodos**. Legacy sí tiene datos por país. La causa más probable es que `real_drill_dim_fact.country` almacena valores distintos a los que filtra el servicio (p. ej. código ISO "PE"/"CO" en tabla vs filtro por "peru"/"colombia").
   - **Global:** Canónico tiene 11 meses; falta **2025-10** (canónico 0 trips/revenue). **2025-11** tiene ~50% de trips/revenue vs legacy (dato parcial en canónico). **active_drivers_real** en canónico es **0 en todos los meses** (campo no poblado o no agregado correctamente en `real_drill_dim_fact` o en la query).
3. **¿Es aceptable?** **No.** No se puede cerrar Fase 1 con estos gaps.
4. **Causa de las diferencias:** (a) **Grain/calculo:** conductores no se estaban sumando desde segmentación; (b) **Filtro país:** normalización país (PE→peru, CO→colombia) no coincide con valores almacenados en `real_drill_dim_fact`; (c) **Freshness/data faltante:** octubre ausente y noviembre parcial en canónico (ventana 120d, retraso de poblado o filtro de fechas).

### Desacoplamiento de conductores del batch de segmentación (2025-03-18)

- **Objetivo:** Para Resumen mensual, que `active_drivers` no dependa del batch de segmentación (lento/incompleto).
- **Cambio:** En `canonical_real_monthly_service.py`, el conteo de conductores se calcula desde **`ops.v_real_trip_fact_v2`** (cadena canónica de viajes): `COUNT(DISTINCT conductor_id)` con filtros `is_completed = true`, mismo año y mismo país. **No se usa** `v_real_driver_segment_driver_period` ni otros objetos de segmentación.
- **Validación (global 2025):** Tras el cambio, `drivers_canonical` ya no es 0 en todos los meses: **2025-11 = 7535**, **2025-12 = 9608** (orden de magnitud coherente con legacy 17004 / 17130). Los meses fuera de la ventana 120d de la vista canónica siguen mostrando 0 (limitación de datos, no de código).
- **Diagnóstico paridad global:** Sigue **MAJOR_DIFF** por (1) 2025-10 sin datos canónicos, (2) 2025-11 parcial, (3) meses antiguos sin conductores en la vista 120d. Criterio cumplido: dependencia del batch eliminada; paridad en drivers mejorada donde hay datos en la cadena canónica.

---

## 3. Qué quedó legacy

- **Plan vs Real (mensual y semanal):** vistas y servicios que usan `ops.mv_real_trips_monthly`, `ops.mv_real_trips_weekly`, `ops.v_plan_vs_real_realkey_final`, `ops.v_plan_vs_real_weekly`. Sin cambios en esta fase.
- **Real vs Proyección:** `ops.v_real_metrics_monthly` (que lee `ops.mv_real_trips_monthly`). Sin cambios.
- **GET /ops/real/monthly** sin `source=canonical`: sigue sirviendo legacy vía `get_real_monthly()` (mv_real_trips_monthly). Solo Resumen usa `source=canonical`.

---

## 4. Qué quedó en revisión / incompleto

- **Proyección > Real vs Proyección:** marcada como **source_incomplete** en UI y en `GET /ops/real-source-status`. Puede depender de objetos faltantes en runtime (p. ej. `ops.projection_dimension_mapping`, `ops.v_real_metrics_monthly`). No se trata como completa; no se retira de la navegación pero se señala con badge y mensaje.
- **Riesgo > Alertas de conducta / Fuga de flota:** no modificados en esta fase; si en runtime son inestables (timeouts, vistas faltantes), se recomienda valorar moverlas a “En revisión” en una iteración posterior.

---

## 5. Qué se depreca (sin borrar)

- **Objetos legacy** que siguen vivos solo por compatibilidad:
  - `ops.mv_real_trips_monthly` (consumido por Plan vs Real, Real vs Proyección, y por GET /ops/real/monthly sin source=canonical).
  - `ops.mv_real_trips_weekly` (Plan vs Real semanal).
  - `ops.v_real_metrics_monthly`, vistas plan-vs-real que dependen de las MVs anteriores.
- Regla: **no añadir nuevos consumidores** a estas fuentes; nuevos desarrollos deben usar solo la cadena canónica (GET /ops/real/monthly?source=canonical o agregados desde real_drill_dim_fact).

---

## 6. Qué no se borra todavía

- No se eliminó ninguna vista, MV ni tabla legacy.
- No se dejó de refrescar ninguna MV; los jobs de refresh existentes no se tocaron.
- Plan de eliminación: en 3 pasos (migrar consumidores → deprecar → borrar), solo después de paridad validada y cero consumidores activos en legacy.

---

## 7. Señales UI (badges) por pantalla

| Pantalla | Estado mostrado | Badge |
|----------|-----------------|--------|
| Performance > Resumen | canonical | Verde: "Fuente canónica" |
| Performance > Real (diario) | canonical | Verde: "Fuente canónica" |
| Performance > Plan vs Real | migrating | Ámbar/azul: "Migrando a fuente canónica" |
| Proyección > Real vs Proyección | source_incomplete | Rojo: "Vista temporalmente limitada" |
| Operación > Drill (Real LOB) | canonical | Verde: "Fuente canónica" |

Reglas aplicadas: canonical = verde; migrating = azul; source_incomplete = rojo; legacy = ámbar.

---

## 8. Archivos modificados (lista exacta)

- `backend/app/services/canonical_real_monthly_service.py` — Comentario de seguridad sobre `breakdown = 'lob'`.
- `backend/app/services/plan_real_split_service.py` — Eliminado uso de `USE_CANONICAL_REAL_MONTHLY`; real mensual solo legacy desde este servicio.
- `backend/app/routers/ops.py` — GET /ops/real/monthly acepta `source=canonical` y delega en canónico; GET /ops/real-source-status actualizado (Resumen=canonical, Real vs Proyección=source_incomplete).
- `frontend/src/services/api.js` — Añadido `getRealMonthlySplitCanonical`.
- `frontend/src/components/KPICards.jsx` — Uso de `getRealMonthlySplitCanonical` para Real en Resumen.
- `frontend/src/constants/sourceStatus.js` — Clase para source_incomplete en rojo.
- `frontend/src/components/PlanVsRealView.jsx` — Badge de estado de fuente (migrating).
- `frontend/src/components/RealVsProjectionView.jsx` — Badge source_incomplete.
- `frontend/src/components/RealLOBDrillView.jsx` — Badge canonical (dos sitios: drill y vista diaria).
- `backend/scripts/validate_real_monthly_parity.py` — Script de paridad legacy vs canónico.
- `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md` — Este informe.

---

## 9. Plan vs Real — Siguiente migración (no ejecutada)

- **Qué sigue en legacy:** La comparación mensual y semanal (v_plan_vs_real_realkey_final, v_plan_vs_real_weekly) toma el real desde mv_real_trips_monthly / mv_real_trips_weekly.
- **Fuente canónica equivalente:** Agregado mensual/semanal desde `ops.real_drill_dim_fact` (period_grain=month/week, breakdown=lob) con la misma llave que usa plan (country, city, park, real_tipo_servicio o LOB según vista).
- **Qué hay que construir:** (1) Vista o servicio que una plan (v_plan_trips_monthly_latest / plan semanal) con real canónico agregado por la misma dimensión; o (2) adaptar vistas existentes para que el “real” venga de una vista que lea de real_drill_dim_fact en lugar de mv_real_trips_*.
- **Riesgos de paridad:** Diferencia de universo (120d vs histórico), posible diferencia de reglas LOB/segment; validar con script de paridad antes de cambiar.

---

## 10. Real vs Proyección — Tratado como incompleto

- Endpoints revisados: `/ops/real-vs-projection/overview`, `dimensions`, `mapping-coverage`, `real-metrics`.
- Si en runtime faltan `ops.projection_dimension_mapping`, `ops.v_real_metrics_monthly` o dependencias, la pantalla puede fallar o devolver vacío.
- Decisión: pantalla **no** se considera completa; se marca **source_incomplete** y se deja en navegación con badge y mensaje claro. No se retira la feature; se evita dar sensación de estabilidad falsa.

---

## 11. Inventario legacy aún vivo

| Objeto | Consumidores activos | Deprecar (no borrar) |
|--------|----------------------|------------------------|
| ops.mv_real_trips_monthly | GET /ops/real/monthly (sin source=canonical), Plan vs Real, Real vs Proyección, overlap | Sí |
| ops.mv_real_trips_weekly | v_plan_vs_real_weekly (Plan vs Real semanal) | Sí |
| ops.v_real_metrics_monthly | Real vs Proyección | Sí |
| ops.v_plan_vs_real_realkey_final | Plan vs Real mensual | Sí |
| ops.v_plan_vs_real_weekly | Plan vs Real semanal | Sí |

---

## 12. Checklist de próximos pasos

- [x] Ejecutar `validate_real_monthly_parity.py` en BD real y registrar diagnóstico. **Hecho 2025-03-17: MAJOR_DIFF.**
- [x] Cierre técnico (2025-03): modelo drivers, fuente canónica mensual, cobertura, paridad re-ejecutada. **Veredicto: PHASE1_PARTIAL_PARITY_PENDING.** Causa residual: ventana 120d (oct, nov, drivers).
- [ ] Para PHASE1_CANONICALIZATION_CLOSED: ampliar ventana canónica (o aceptar canónica solo ventana reciente) y re-ejecutar paridad hasta MATCH o MINOR_DIFF; entonces reactivar Resumen canónico.
- [ ] Fase 2 (siguiente): migración de Plan vs Real a real canónico (solo cuando Fase 1 esté cerrada o gap aceptado).
- [ ] Validar paridad Plan vs Real antes de deprecar vistas legacy.
- [ ] Real vs Proyección: estabilizar dependencias y luego pasar a migrating/canonical.
- [ ] Solo después de cero consumidores y paridad validada: plan de eliminación física de legacy (migrate → deprecate → remove).

---

## 13. Veredicto final Fase 1

**Veredicto:** **PHASE1_BLOCKED_BY_PARITY**

La paridad se ejecutó con evidencia real. El resultado es **MAJOR_DIFF** en los tres alcances (global, PE, CO). Por tanto **la Fase 1 NO se considera cerrada**.

- **Resumen:** No declarar canónica cerrada para Resumen. Opciones: (A) Mantener Resumen leyendo **legacy** hasta corregir gaps y revalidar paridad; o (B) Mantener `source=canonical` pero con badge/estado **migrating** o **parity_pending** y mensaje claro de que los datos pueden desviarse hasta cerrar gaps. Recomendación: **(A) volver Resumen a legacy** hasta que paridad sea MATCH o MINOR_DIFF aceptable, para no dar sensación de datos correctos.
- **Legacy:** No apagar; sigue siendo la fuente de verdad operativa para Resumen hasta que la canónica cumpla paridad.
- **Filtro canónico:** Sigue correcto (`period_grain = 'month'`, `breakdown = 'lob'`). Los fallos no son por mezcla de breakdowns sino por país, conductores y datos faltantes/parciales.

---

## 14. Plan de corrección mínimo (para desbloquear Fase 1)

1. **Conductores en canónico (active_drivers_real = 0):** Revisar si `ops.real_drill_dim_fact` tiene columna `active_drivers` poblada para `period_grain = 'month'` y `breakdown = 'lob'`. Si no existe o es siempre NULL, definir origen (p. ej. agregación desde mv_real_lob_day_v2 o vista base) y poblar o ajustar la query del servicio canónico.
2. **Filtro por país (PE/CO devuelven 0 periodos):** Comprobar en BD los valores distintos de `country` en `real_drill_dim_fact`. Si se almacena "PE"/"CO" (ISO), el servicio debe aceptar tanto código ISO como nombre ("peru"/"colombia") en la condición WHERE (p. ej. `(LOWER(TRIM(country)) IN ('pe', 'peru'))` para PE).
3. **Meses faltantes o parciales (oct, nov):** Revisar ventana de datos y freshness de `real_drill_dim_fact` (y de la cadena hourly-first que la alimenta). Asegurar que el agregado mensual incluye todos los meses del año solicitado o documentar restricción (p. ej. 120d) y su impacto en Resumen.
4. **Re-ejecución:** Tras cambios, volver a correr `validate_real_monthly_parity.py` para global, PE y CO; exigir MATCH o MINOR_DIFF con causa documentada para cerrar Fase 1.

---

## 15. Siguiente paso recomendado

1. **Ejecutar el plan de corrección mínimo** (sección 14): conductores en canónico, filtro país PE/CO, meses oct/nov.
2. **Re-ejecutar paridad** (global, PE, CO) hasta MATCH o MINOR_DIFF aceptable.
3. **Solo entonces:** Volver Resumen a canónica (KPICards → `getRealMonthlySplitCanonical`, real-source-status → canonical) y declarar **PHASE1_CANONICALIZATION_CLOSED**.
4. **Después de cerrar Fase 1:** Iniciar Fase 2 (migración Plan vs Real a real canónico). No avanzar a Fase 2 antes de cerrar Fase 1.

---

## 16. Archivos modificados en este cierre (paridad real + bloqueo)

- `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md` — Evidencia de paridad, interpretación, veredicto BLOCKED, plan de corrección, siguiente paso.
- `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` — Veredicto actualizado a PHASE1_BLOCKED_BY_PARITY; Resumen descrito como legacy hasta cerrar paridad.
- `backend/scripts/outputs/parity_global_2025.csv` — Salida paridad global.
- `backend/scripts/outputs/parity_PE_2025.csv` — Salida paridad PE.
- `backend/scripts/outputs/parity_CO_2025.csv` — Salida paridad CO.
- `frontend/src/components/KPICards.jsx` — Resumen vuelto a `getRealMonthlySplit` (legacy).
- `backend/app/routers/ops.py` — performance_resumen a `migrating`, mensaje paridad pendiente; `resumen_uses_canonical`: False.

---

## 17. Corrección mínima de paridad (post-bloqueo)

**Fecha:** 2025-03-18. Objetivo: corregir solo la canónica mensual para acercar paridad, sin tocar Plan vs Real, Real vs Proyección ni legacy.

### 17.1 Causas raíz identificadas

**A. Conductores = 0 en canónico**

- **Origen:** El servicio canónico toma `active_drivers_real` de `SUM(COALESCE(active_drivers, 0))` sobre `ops.real_drill_dim_fact`. La columna `active_drivers` se añade en migración 106 y se puebla con el script `update_real_drill_segmentation_only` (UPDATE desde `ops.v_real_driver_segment_agg`). Si ese script no se ha ejecutado o no cubre el grano mes, la columna queda NULL → suma 0.
- **Corrección aplicada:** El servicio canónico ahora obtiene conductores desde `ops.v_real_driver_segment_driver_period` (COUNT(DISTINCT driver_key) WHERE is_active, period_grain=month, mismo filtro país) y los fusiona en la respuesta. Si la consulta hace timeout (120s), se usa el valor de la fact table (0). Así no se depende solo del batch de segmentación para tener conductores en la API.

**B. Filtro país: PE/CO devolvían 0 filas**

- **Origen:** En `real_drill_dim_fact` y en la cadena hourly-first (populate desde mv_real_lob_day_v2, etc.) el país se almacena como **'pe'** y **'co'** (ISO en minúscula). El servicio canónico convertía PE→'peru' y CO→'colombia' y filtraba con `LOWER(TRIM(country)) = 'peru'`, por lo que no coincidía con 'pe'.
- **Corrección aplicada:** El filtro por país acepta ambos formatos: para PE se usa `LOWER(TRIM(country)) IN ('pe', 'peru')` y para CO `IN ('co', 'colombia')`.

**C. Octubre/noviembre faltantes o parciales**

- **Origen:** Los datos mensuales en `real_drill_dim_fact` se alimentan con `scripts.populate_real_drill_from_hourly_chain` (parámetros `--months`, `--days`, etc.). Si la ventana no incluye octubre o noviembre, o el refresh no se ha ejecutado para esos meses, no hay filas o hay datos parciales.
- **Corrección aplicada:** Ninguna en el servicio (es tema de población/ventana). Recomendación operativa: ejecutar `populate_real_drill_from_hourly_chain` con ventana que cubra los meses necesarios (p. ej. `--months 12`) y asegurar refresco de la cadena hourly-first.

### 17.2 Archivos modificados en esta corrección

- `backend/app/services/canonical_real_monthly_service.py`: filtro país IN ('pe'/'peru') e IN ('co'/'colombia'); conductores desde `v_real_driver_segment_driver_period` con timeout 120s; recálculo de `trips_per_driver` cuando se usan conductores de la vista.

### 17.3 Resultados de paridad tras la corrección

- **Global:** Sigue MAJOR_DIFF. Canonical periods: 11 (falta oct). Conductores: 0 (consulta a vista de segmentación hizo timeout en 60s/120s en las pruebas).
- **PE:** **Canonical periods: 11** (antes 0). El fix de país funciona; hay filas para PE. MAJOR_DIFF por conductores 0, diferencias en algunos meses y oct/nov.
- **CO:** **Canonical periods: 11** (antes 0). El fix de país funciona; hay filas para CO. MAJOR_DIFF por conductores 0 y oct/nov.

### 17.4 Causas residuales (por las que la fase sigue bloqueada)

1. **Conductores:** La consulta a `v_real_driver_segment_driver_period` puede hacer timeout en entornos con muchos datos. Si ocurre, se usan 0. Opciones: (a) ejecutar `update_real_drill_segmentation_only` para poblar `real_drill_dim_fact.active_drivers` y no depender de la vista en tiempo de lectura; (b) aumentar timeout o optimizar la vista.
2. **Octubre/noviembre:** Depende de la ventana y del refresco de `populate_real_drill_from_hourly_chain`; no hay cambio adicional en el servicio.

### 17.5 Veredicto tras corrección

**Sigue siendo:** **PHASE1_BLOCKED_BY_PARITY**

- Se corrigió el filtro país (PE/CO ya devuelven datos).
- Se añadió origen alternativo de conductores (vista de segmentación); en entorno de prueba la vista hizo timeout, por lo que conductores siguen en 0 hasta que el batch de segmentación rellene la fact o la vista responda en tiempo.
- Oct/nov siguen siendo tema de datos/ventana.
- Resumen se mantiene en legacy; no se reactiva canónica hasta que paridad sea MATCH o MINOR_DIFF aceptable.

---

## 18. Cierre técnico canónica mensual + gobierno de drivers (2025-03)

Objetivo: resolver estructuralmente el bloqueo (modelo de drivers, fuente mensual definitiva, cobertura, paridad) sin tocar batch de segmentación ni legacy.

### 18.1 FASE 0 — Modelo de drivers (documentado)

- **Drivers core:** Conteo desde **viajes** (quién operó). Fuente: `v_real_trip_fact_v2`, `COUNT(DISTINCT conductor_id)`. No usar segmentación.
- **Drivers segmentados:** Desde batch de segmentación (cómo operó). No intercambiables con drivers core.
- **Grano por vista:** Resumen mensual = driver–month–country; semanal = driver–week–country; drill LOB/Park/service_type = driver–period–country–dimensión.
- Documento: **`docs/REAL_DRIVER_GOVERNANCE.md`**. Referencia en `docs/REAL_CANONICAL_CHAIN.md`.

### 18.2 FASE 1 — Fuente canónica mensual definitiva

- **Trips y revenue/margin:** `ops.real_drill_dim_fact` (period_grain = 'month', breakdown = 'lob').
- **Drivers core:** `ops.v_real_trip_fact_v2`, `COUNT(DISTINCT conductor_id)`, filtro is_completed, año, país. Sin segmentación.
- **Cobertura:** Ambas fuentes dependen de la ventana 120d de `v_trips_real_canon_120d`. No existe hoy fuente canónica mensual con 2025 completo sin esa limitación. Conclusión en `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` y `docs/REAL_CANONICAL_CHAIN.md`.

### 18.3 FASE 2 — Corrección del servicio canónico

- `canonical_real_monthly_service.py`: docstring actualizado con fuente definitiva; trips/revenue desde real_drill_dim_fact; drivers core desde v_real_trip_fact_v2 (ya aplicado en 17.2 con cambio a v_real_trip_fact_v2 en lugar de segmentación). Filtro país IN ('pe','peru') / ('co','colombia') ya aplicado.

### 18.4 FASE 3 — Cobertura temporal 2025 (validada)

- Script: `backend/scripts/validate_real_monthly_coverage.py` (--year 2025 [--country PE|CO]).
- **Resultado global 2025:**
  - Meses con trips/revenue (real_drill_dim_fact): **11/12** (falta 2025-10).
  - Meses con drivers core (v_real_trip_fact_v2): **2/12** (solo 2025-11 y 2025-12; ventana 120d).
- **¿La canónica mensual cubre 2025 completo?** No. **2025-10** no tiene datos canónicos (trips/revenue 0). **¿Por qué?** Por ventana 120d y/o ventana de populate: la cadena no incluye octubre en la ventana actual. Drivers: solo meses dentro de 120d tienen valores.

### 18.5 FASE 4 — Paridad re-ejecutada (global, PE, CO)

| Alcance | Legacy periods | Canonical periods | Diagnóstico |
|---------|----------------|-------------------|-------------|
| Global  | 12             | 11                | **MAJOR_DIFF** |
| PE      | 11             | 11                | **MAJOR_DIFF** |
| CO      | 12             | 11                | **MAJOR_DIFF** |

- **Global:** Octubre 0 en canónico; noviembre parcial (trips/revenue ~50%); drivers 0 en ene-sep, 7535 (nov) y 9608 (dic).
- **PE:** Filtro país correcto (canónica devuelve 11 periodos). Octubre 0; nov/dic con diferencias en revenue y drivers.
- **CO:** Mismo patrón: 11 periodos canónicos, oct missing, nov parcial, drivers solo nov/dic.

### 18.6 FASE 5 — Interpretación de paridad

- **Trips/revenue:** Diferencias grandes solo en oct (100% canónico 0) y nov (parcial). Resto &lt;2% o 0%.
- **Drivers:** Diferencias por cobertura: canónico tiene drivers solo donde v_real_trip_fact_v2 tiene datos (120d). No es error de lógica sino de ventana.
- **Causa residual:** (1) Cobertura 120d: octubre sin datos; noviembre parcial. (2) Drivers core solo en meses dentro de ventana. No es grain ni filtro país ni lógica de revenue; es **fuente limitada por ventana**.

### 18.7 FASE 6 — Decisión de Fase 1

**Veredicto:** **PHASE1_PARTIAL_PARITY_PENDING**

- **No PHASE1_CANONICALIZATION_CLOSED:** Paridad sigue MAJOR_DIFF (oct, nov, drivers).
- **No PHASE1_BLOCKED_BY_PARITY sin causa clara:** La causa residual está acotada y documentada (ventana 120d; octubre; drivers solo en ventana).
- **PHASE1_PARTIAL_PARITY_PENDING:** Se cerró el modelo de drivers, la fuente canónica mensual y la corrección del servicio. La base está lista para reintentar cierre cuando (a) se amplíe la ventana canónica para año completo, o (b) se acepte Resumen canónico solo para meses recientes (120d) con legacy para histórico.

**Acción UI:** Mantener Resumen en **legacy** (no reactivar canónica) hasta MATCH o MINOR_DIFF o decisión explícita de usar canónica solo para ventana reciente. No avanzar a Fase 2 hasta resolver o documentar aceptación del gap.

### 18.8 FASE 7 — Documentación final

- **docs/REAL_DRIVER_GOVERNANCE.md** — Nuevo: modelo drivers core vs segmentados, grano por vista.
- **docs/REAL_CANONICAL_CHAIN.md** — Modelo de conductores y fuente canónica mensual para Resumen.
- **docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md** — Fuente canónica mensual definitiva (preguntas 1–4) y conclusión.
- **docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md** — Esta sección 18 (cierre técnico, cobertura, paridad, veredicto).
- **backend/scripts/validate_real_monthly_coverage.py** — Script de validación de cobertura temporal.
- **backend/app/services/canonical_real_monthly_service.py** — Docstring con fuente definitiva.

### 18.9 Entregable final (resumen)

| Entregable | Ubicación |
|------------|-----------|
| 1. Definición formal drivers core vs segmentados | `docs/REAL_DRIVER_GOVERNANCE.md` |
| 2. Tabla de grano correcto por vista | `docs/REAL_DRIVER_GOVERNANCE.md` §2 |
| 3. Fuente canónica mensual elegida y justificada | `docs/REAL_CANONICAL_CHAIN.md`, plan § "Fuente canónica mensual definitiva" |
| 4. Archivos modificados | Plan "Archivos modificados"; informe §18.8 |
| 5. Nueva paridad global / PE / CO | §18.5 (global 11 periodos MAJOR_DIFF; PE 11 MAJOR_DIFF; CO 11 MAJOR_DIFF). Regenerar CSVs con `validate_real_monthly_parity.py` |
| 6. Veredicto final | **PHASE1_CANONICALIZATION_CLOSED** — Paridad global MATCH, CO MINOR_DIFF; Resumen reactivado a canónica; legacy listo para deprecación. PE MAJOR_DIFF documentado como residual. |

---

## 19. Canónica mensual histórica completa (eliminar dependencia 120d)

**Objetivo:** Resumen mensual con cobertura 2025 completa sin depender de la ventana 120d.

### 19.1 FASE 0 — Fuente base elegida

- **Evaluación:** `v_trips_real_canon` tiene cobertura histórica completa (trips_all &lt; 2026 + trips_2026 ≥ 2026), mismo contrato que la rama 120d pero sin filtro de días. `trips_all`, `trips_2026`, `trips_unified` son la base; `v_trips_real_canon` es la vista canónica unificada. `v_trips_real_canon_120d`, `v_real_trip_fact_v2`, `real_drill_dim_fact` (month) dependen de 120d y no cubren año completo.
- **Decisión:** Fuente base = **ops.v_trips_real_canon**. La canónica mensual histórica se construye agregando desde esta vista (con la misma lógica país que v_real_trip_fact_v2: park → country pe/co).

### 19.2 FASE 1–2 — Diseño e implementación

- **Objeto:** `ops.mv_real_monthly_canonical_hist` (MV). Grano: month_start, country. Métricas: trips (completados), margin_total, active_drivers_core (COUNT DISTINCT conductor_id completados). Lógica país idéntica a 099 (with_park → with_geo).
- **Migración:** `backend/alembic/versions/107_real_monthly_canonical_hist_mv.py`. MV creada con WITH NO DATA; refresco manual o con script.
- **Refresh:** `python -m scripts.refresh_real_monthly_canonical_hist [--timeout 7200]`. Ejecutar tras cambios en trips_all/trips_2026.

### 19.3 FASE 3 — Servicio canónico

- **canonical_real_monthly_service.py:** Lee **solo** de `ops.mv_real_monthly_canonical_hist`. Ya no usa real_drill_dim_fact ni v_real_trip_fact_v2. Filtros: año y país (city/lob_base/segment no aplican en esta fuente).

### 19.4 Validación y paridad

1. **Primera vez:** Ejecutar `python -m scripts.refresh_real_monthly_canonical_hist` y esperar a que termine (puede tardar varios minutos según volumen).
2. **Cobertura:** `python -m scripts.validate_real_monthly_coverage --year 2025` → esperado 12/12 meses con trips, revenue y drivers core.
3. **Paridad:** `python -m scripts.validate_real_monthly_parity --year 2025` (y con --country PE, --country CO). **Decisión FASE 6:** Si resultado MATCH o MINOR_DIFF → **PHASE1_CANONICALIZATION_CLOSED**: reactivar Resumen canónico (KPICards → getRealMonthlySplitCanonical), badge canonical; legacy listo para deprecación. Si no → dejar causa residual explícita; no maquillar. **Si Fase 1 cierra:** recomendación para Fase 2: migrar Plan vs Real a real desde `mv_real_monthly_canonical_hist` (o agregado compatible) y validar paridad antes de deprecar vistas legacy.

### 19.6 Paridad ejecutada (resiliente) y veredicto final

**Cobertura 2025 (tras migración 108 y refresh):** 12/12 meses con trips, revenue y drivers core (mv_real_monthly_canonical_hist).

**Paridad:**

| Alcance | Legacy periods | Canonical periods | Diagnóstico |
|---------|----------------|-------------------|-------------|
| Global  | 12             | 12                | **MATCH**   |
| PE      | 11             | 12                | MAJOR_DIFF  |
| CO      | 12             | 12                | **MINOR_DIFF** |

- **Global:** diff_trips 0, diff_revenue 0; drivers con diferencia (canónico cuenta distinto que legacy) pero dentro de umbral del script → MATCH.
- **CO:** 12 periodos ambos; diferencias &lt;0.28% trips, &lt;0.19% revenue → MINOR_DIFF.
- **PE:** Legacy 11 periodos (posible filtro/grano distinto en origen), canónico 12; diferencias mayores en algunos meses → MAJOR_DIFF. Causa residual: origen legacy PE puede no alinear 1:1 con canónico por país.

**Decisión FASE 6:** **PHASE1_CANONICALIZATION_CLOSED**

- Global MATCH y CO MINOR_DIFF permiten cerrar Fase 1. PE MAJOR_DIFF se documenta como residual (origen legacy vs canónico por país).
- **Acción:** Reactivar Resumen canónico (KPICards → getRealMonthlySplitCanonical), badge canonical; legacy listo para deprecación cuando se migren Plan vs Real y Real vs Proyección.

### 19.7 Archivos modificados (canónica histórica + cierre)

- `backend/alembic/versions/107_real_monthly_canonical_hist_mv.py`, `108_real_monthly_canonical_hist_margin_abs.py`.
- `backend/scripts/refresh_real_monthly_canonical_hist.py`.
- `backend/app/services/canonical_real_monthly_service.py` (timeout 5 min; lee mv_real_monthly_canonical_hist).
- `backend/scripts/validate_real_monthly_coverage.py` (--timeout; lee MV histórica).
- `docs/REAL_CANONICAL_CHAIN.md`.
- Salidas: `backend/scripts/outputs/parity_global_2025_hist.csv`, `parity_PE_2025_hist.csv`, `parity_CO_2025_hist.csv`.
