# Diagnóstico: brecha service_type → LOB (Real LOB Drill)

**Fecha:** 2026-03-08  
**Objetivo:** Trazabilidad exacta de la brecha residual entre `service_type` y LOB, y decisión mínima de corrección.

---

## 1. Pipeline y fuentes (recordatorio)

| Paso | Origen | Destino |
|------|--------|---------|
| Raw | `public.trips_all.tipo_servicio` | — |
| Normalizado | `ops.normalized_service_type(tipo_servicio)` | — |
| Validado | `ops.validated_service_type(tipo_servicio)` | `tipo_servicio_norm` en backfill |
| Drill service_type | — | `ops.real_drill_dim_fact` (breakdown=`service_type`, dimension_key=`tipo_servicio_norm`) |
| Mapping LOB | `canon.map_real_tipo_servicio_to_lob_group` (real_tipo_servicio = tipo_servicio_norm) | lob_group |
| Drill LOB | COALESCE(lob_group, 'UNCLASSIFIED') | `ops.real_drill_dim_fact` (breakdown=`lob`, dimension_key=lob_group) |

**Fuente del drill UI:** `ops.mv_real_drill_dim_agg` (= vista sobre `real_drill_dim_fact`).  
**No existe** `ops.mv_real_lob_base` en este proyecto; las consultas de diagnóstico usan `real_drill_dim_fact` + `canon.map_real_tipo_servicio_to_lob_group`.

---

## 2. Cifras actuales (diagnóstico ejecutado)

### 2.1 UNCLASSIFIED por breakdown

| breakdown     | dimension_key | trips    |
|--------------|---------------|----------|
| service_type | UNCLASSIFIED  | 158      |
| lob          | UNCLASSIFIED  | 142.630  |

### 2.2 Totales y % residual

| breakdown     | total_trips | unclassified_trips | pct_unclassified |
|--------------|-------------|--------------------|------------------|
| service_type | 22.997.704  | 158                | 0,00 %           |
| lob          | 23.113.487  | 142.630            | 0,62 %           |

### 2.3 Consistencia matemática

- **Suma LOB UNCLASSIFIED:** 142.630 trips.  
- **Suma trips con service_type sin mapping (explicación teórica de la brecha):** 172 trips.

Por tanto, **142.458 trips en LOB UNCLASSIFIED no están explicados** por los `dimension_key` de `service_type` actuales sin mapping. Esto indica **desincronización histórica**: LOB se generó en runs anteriores (con más tipos sin mapear o con otro rango de fechas) y **service_type** se limpió y re-backfilleó después (cleanup + backfill 2025-01 a 2026-04), por lo que el estado actual de `service_type` es “limpio” y el de LOB sigue reflejando el estado antiguo.

### 2.4 LOB UNCLASSIFIED por año

| year_start | lob_uncl_trips | total_lob_trips |
|------------|----------------|-----------------|
| 2024       | 245            | 83.008          |
| 2025       | 110.027        | 19.566.492      |
| 2026       | 32.358         | 3.463.987       |

La brecha está repartida en 2024–2026; no es solo un año “stale”.

### 2.5 validated_service_type SIN mapping (top que explican los 172 trips actuales)

| validated_service_type | trips | Clasificación propuesta |
|------------------------|-------|-------------------------|
| UNCLASSIFIED           | 158   | **ALREADY_UNCLASSIFIED** (no mapear) |
| 336968                 | 2     | **GARBAGE** (ID numérico) |
| 337199                 | 2     | **GARBAGE** |
| 341834                 | 2     | **GARBAGE** |
| 110017                 | 2     | **GARBAGE** |
| 346659                 | 2     | **GARBAGE** |
| el_progreso            | 2     | **LEGIT_NO_MAPPING** (posible LOB; revisar negocio) |
| 343921                 | 2     | **GARBAGE** |

---

## 3. Clasificación de la brecha

| Grupo | Descripción | Trips (aprox.) | Decisión |
|-------|-------------|----------------|----------|
| **A) Legítimos sin mapping** | Tipos de servicio de negocio sin entrada en mapping | 2 (el_progreso) | Opcional: añadir mapping si se confirma LOB (ej. delivery u otro). No perseguir 0 absoluto. |
| **B) Basura residual** | IDs numéricos, strings que no son tipos de servicio | 12 (6×2) | Dejar en UNCLASSIFIED. No mapear. |
| **C) Ya UNCLASSIFIED en service_type** | validated_service_type = UNCLASSIFIED | 158 | Correcto que caigan en LOB UNCLASSIFIED. No tocar. |
| **D) Stale LOB (desincronización)** | LOB rellenado en runs antiguos; service_type actual ya limpio | 142.458 | **Re-sincronizar**: ejecutar backfill completo (todos los breakdowns, mismo rango que se quiera mantener) para que LOB se recalcule con el mapping actual. Tras eso, LOB UNCLASSIFIED debería bajar a ~172. |

---

## 4. Decisiones aplicables

1. **No añadir mapping para:** UNCLASSIFIED, 336968, 337199, 341834, 110017, 346659, 343921.  
2. **Opcional:** Si se confirma que `el_progreso` es un tipo de servicio de negocio, añadir una fila en `canon.map_real_tipo_servicio_to_lob_group` (LOB a definir; ej. delivery).  
3. **Corrección estructural de la brecha:** Ejecutar backfill completo de Real LOB (service_type + lob + park) para el rango de fechas que se considere fuente de verdad (ej. 2025-01-01 a 2026-04-01 o el rango completo donde exista LOB), para que LOB se regenere con el mapping actual y la brecha residual quede solo en ~172 trips (A+B+C).  
4. **No inventar taxonomía nueva de LOB:** Usar solo LOBs ya existentes en el mapping (delivery, auto taxi, taxi moto, tuk tuk, etc.).

---

## 5. Consultas SQL de referencia (esquema real)

- Tabla de hecho: `ops.real_drill_dim_fact` → columnas `breakdown`, `dimension_key`, `trips` (no `breakdown_value` ni `metric_trips`).
- Script de diagnóstico: `backend/scripts/diagnose_lob_gap.py` (ejecuta las comprobaciones anteriores).

**A) UNCLASSIFIED por breakdown:**

```sql
SELECT breakdown, dimension_key AS breakdown_value, SUM(trips) AS trips
FROM ops.real_drill_dim_fact
WHERE breakdown IN ('service_type','lob') AND dimension_key = 'UNCLASSIFIED'
GROUP BY breakdown, dimension_key ORDER BY breakdown;
```

**B) validated_service_type que explican LOB UNCLASSIFIED (sin mapping):**

```sql
SELECT s.dimension_key AS validated_service_type, SUM(s.trips) AS trips
FROM ops.real_drill_dim_fact s
WHERE s.breakdown = 'service_type'
  AND NOT EXISTS (SELECT 1 FROM canon.map_real_tipo_servicio_to_lob_group m WHERE m.real_tipo_servicio = s.dimension_key)
GROUP BY s.dimension_key ORDER BY trips DESC;
```

**C) Consistencia:**

```sql
SELECT
  (SELECT SUM(trips) FROM ops.real_drill_dim_fact WHERE breakdown = 'lob' AND dimension_key = 'UNCLASSIFIED') AS lob_unclassified_trips,
  (SELECT SUM(trips) FROM ops.real_drill_dim_fact s WHERE s.breakdown = 'service_type'
   AND NOT EXISTS (SELECT 1 FROM canon.map_real_tipo_servicio_to_lob_group m WHERE m.real_tipo_servicio = s.dimension_key)) AS unmapped_service_type_trips;
```

---

## 6. Resumen ejecutivo de la brecha

- **Por qué service_type está “limpio” y LOB no:**  
  service_type se limpió y se volvió a backfillear; LOB no se regeneró para el mismo rango con el mapping actual, por lo que sigue conteniendo UNCLASSIFIED de runs antiguos.  
- **Brecha residual “legítima” (tras re-backfill):** 172 trips (158 UNCLASSIFIED + 12 basura + 2 el_progreso).  
- **Acción recomendada:** Re-ejecutar backfill Real LOB (todos los breakdowns) para el rango objetivo; opcionalmente mapear `el_progreso` si se confirma en negocio.

---

## 7. Resumen ejecutivo final (cierre microfase)

### 1. Estado actual service_type vs LOB

| Métrica | service_type | LOB |
|--------|---------------|-----|
| Total trips | 22.997.704 | 23.113.487 |
| UNCLASSIFIED trips | 158 | 142.630 |
| % UNCLASSIFIED | 0,00 % | 0,62 % |

### 2. Explicación exacta de la brecha residual

- **172 trips** están explicados por `validated_service_type` sin entrada en `canon.map_real_tipo_servicio_to_lob_group`: UNCLASSIFIED (158), IDs numéricos (12), `el_progreso` (2).
- **142.458 trips** de LOB UNCLASSIFIED son **stale**: LOB se generó en runs anteriores (antes de limpieza/backfill de service_type) y no se ha vuelto a generar para el mismo rango con el mapping actual. Tras un backfill completo, LOB UNCLASSIFIED debería bajar a ~172.

### 3. Cambios aplicados en mapping LOB

- **Ninguno** en esta microfase. No se mapea basura ni UNCLASSIFIED. `el_progreso` (2 trips) queda como **opcional** pendiente de confirmación de negocio.

### 4. Cambios aplicados en UI

- **LOW_VOLUME:** ya oculto en el drill (filtro en subrows en `RealLOBDrillView.jsx`).
- **Cabecera/drill:** la tabla expandida tiene columna “Dimensión” (LOB / Park / Tipo de servicio) según desglose; estado de periodo (Abierto/Cerrado/Falta data) visible en columna Estado.
- Sin cambios de métricas de negocio.

### 5. Qué quedó pendiente

- **Ejecutar backfill completo** para re-sincronizar LOB con el mapping actual (mismo rango que se desee mantener, p. ej. 2024-01-01 a 2026-04-01):
  ```bash
  cd backend
  python -m scripts.backfill_real_lob_mvs --from 2024-01-01 --to 2026-04-01 --resume false
  ```
- **Opcional:** Añadir `el_progreso` → LOB en `canon.map_real_tipo_servicio_to_lob_group` si negocio confirma (ej. delivery), luego re-ejecutar backfill para ese impacto.

### 6. Veredicto final

**LISTO CON OBSERVACIONES**

- Trazabilidad de la brecha documentada y verificada con SQL.
- Residual actual explicado: mayormente LOB stale; residual legítimo ~172 trips (basura + UNCLASSIFIED + el_progreso).
- UI: LOW_VOLUME oculto; drill coherente.
- Para bajar LOB UNCLASSIFIED a ~0,00 % en línea con service_type es **necesario ejecutar el backfill** indicado arriba; sin ello, el 0,62 % LOB UNCLASSIFIED se mantiene por datos históricos no regenerados.

---

## 8. Referencias

- Tabla mapping: `canon.map_real_tipo_servicio_to_lob_group` (seed en migración 044).
- Backfill: `backend/scripts/backfill_real_lob_mvs.py`.
- Vista por viaje (equivalente “base” para diagnóstico): `ops.v_real_trips_with_lob_v2`.
- Drill API: `real_lob_drill_pro_service.get_drill`, `get_drill_children`.

---

## 9. Resumen ejecutivo (plantilla)

| Sección | Contenido |
|--------|------------|
| **1. Estado actual service_type vs LOB** | UNCLASSIFIED service_type ≈ 0%; UNCLASSIFIED LOB ≈ 0,62%. service_type y LOB comparten la misma normalización (tipo_servicio_norm) y mapping; la brecha viene de tipos sin fila en `canon.map_real_tipo_servicio_to_lob_group`. |
| **2. Explicación exacta de la brecha residual** | Rellenar con resultado de consultas B/C: qué `validated_service_type` (real_tipo_servicio_norm) cae en LOB UNCLASSIFIED y clasificación (legítimo sin mapping / basura / ya UNCLASSIFIED). |
| **3. Cambios aplicados en mapping LOB** | Solo si se añadieron filas a `canon.map_real_tipo_servicio_to_lob_group`; si no, "Ninguno en esta microfase". |
| **4. Cambios aplicados en UI** | Drill: breakdown=service_type alineado a tipo_servicio_norm (trazabilidad). LOW_VOLUME oculto en desglose LOB (backend + filtro defensivo frontend). Cabecera: "Totales (periodos listados)"; desglose con título "Desglose de [periodo] por LOB/..."; estado Abierto con tooltip "Mes/semana en curso (datos parciales)". |
| **5. Pendiente** | Ejecutar SQL de diagnóstico (A–D) en entorno objetivo; clasificar residual y, si hay legítimos, insertar en mapping y re-ejecutar backfill. |
| **6. Veredicto** | LISTO PARA CERRAR / LISTO CON OBSERVACIONES / NO LISTO — según evidencia SQL y revisión visual. |
