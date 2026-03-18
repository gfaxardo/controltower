# Informe de monitoreo y cierre — Segmentación REAL

**Fecha:** 2026-03-17  
**Modo:** Monitoreo + validación + cierre. Sin rediseño ni reimplementación.

---

## FASE 1 — Estado del proceso batch

| Campo | Valor |
|--------|--------|
| **Proceso batch** | En ejecución (vivo) |
| **PID** | 21736 |
| **Comando** | `python -m scripts.update_real_drill_segmentation_only --batch --per-period-timeout 900` dentro de loop de reintentos (máx. 3 intentos) |
| **Tiempo acumulado** | ~2,25 h (running_for_ms ≈ 8,1e6) |
| **Último periodo procesado** | day 2025-12-05 (20/196) |
| **Periodos completados / total** | 20 / 196 (~10,2 %) |
| **Errores registrados** | Ninguno (todas líneas INFO) |
| **Intento actual** | 1 de 3 |

**Resumen ejecutivo:** El batch sigue corriendo en el primer intento, sin fallos. Avanza ~6 min por periodo; lleva 20 días procesados de 196 periodos.

---

## FASE 2 — Validación de avance en DB

Tabla: `ops.real_drill_dim_fact`. Columnas: `active_drivers`, `cancel_only_drivers`, `activity_drivers`, `cancel_only_pct`.

### Conteos globales

| Métrica | Valor |
|---------|--------|
| Total filas (ventana objetivo) | 13 153 |
| Filas con `activity_drivers > 0` | 719 |
| Filas con `activity_drivers` NULL | 12 434 |
| Filas con `activity_drivers` = 0 | 0 |
| `active_drivers` NULL | 12 434 |
| `cancel_only_drivers` NULL | 12 434 |
| `cancel_only_pct` NULL | 12 434 |

### Distribución por period_grain / country / breakdown

- **day + country co/pe + lob/park/service_type:** ya tienen filas con segmentación (`with_seg` > 0). Ej.: day co lob 60, day co park 119, day pe lob 121, day pe park 194, etc.
- **day + country "" (vacío):** 0 con segmentación (total 502+1566+1251).
- **week:** todos los bloques (co, pe, "") tienen `with_seg` = 0. Total week: 84+270+213+246+358+556+373+828+731.
- **month:** todos los bloques tienen `with_seg` = 0.

**Qué parte está poblada:** Solo los **días** ya procesados por el batch (2025-11-16 a 2025-12-05) para **países co y pe** (no el bucket country vacío).  
**Qué parte no:** Semanas (week), meses (month) y los días aún no procesados; además todas las filas con `country = ''`.

---

## FASE 3 — Validación funcional (muestras y fórmulas)

- Se tomaron hasta 20 filas con `activity_drivers > 0`.
- **Comprobaciones:**
  - `activity_drivers = active_drivers + cancel_only_drivers` → **OK** en todas las muestras.
  - `cancel_only_pct = cancel_only_drivers / activity_drivers` (redondeo 4 decimales) → **OK**.
  - No se detectaron valores imposibles ni doble conteo evidente en la muestra.
- **Resultado:** `formula_ok: true`, `errors: []`.

---

## FASE 4 — Validación API (runtime)

- **Estado:** El servidor backend **no estaba en ejecución** en el momento de la prueba (conexión rechazada en 127.0.0.1:8000).
- **Endpoints a validar cuando el servidor esté arriba:**
  - `GET /ops/real-lob/drill?period=month&desglose=LOB` (monthly LOB)
  - `GET /ops/real-lob/drill?period=week&desglose=LOB` (weekly LOB)
  - `GET /ops/real-lob/drill?period=month&desglose=PARK` (monthly PARK)
  - `GET /ops/real-lob/drill?period=week&desglose=SERVICE_TYPE` (weekly SERVICE_TYPE)
  - `GET /ops/real-lob/drill/children` (children)
- **Código:** El servicio `real_lob_drill_pro_service.py` ya expone las 4 métricas en KPIs por país y en filas (rows/children): `active_drivers`, `cancel_only_drivers`, `activity_drivers`, `cancel_only_pct`. Cuando el batch complete más periodos, la API devolverá datos donde la DB ya esté poblada.

---

## FASE 5 — Validación UI

- **Columnas:** En `RealLOBDrillView.jsx` están implementadas:
  - **Activos** (KPI y tabla)
  - **Solo cancelan** (KPI y tabla)
  - **% Solo cancelan** (KPI y tabla)
- **Comportamiento esperado:** En periodos ya procesados se muestran valores numéricos; en no procesados se muestra 0 o "—" según `formatNumber` y `cancel_only_pct != null`. La UI distingue ambos casos.
- **Regresión:** No se ha tocado lógica; no se detecta regresión en código. La validación visual en navegador debe hacerse con backend levantado y al menos un periodo con segmentación (por ejemplo month o week una vez el batch llegue a esos granos).

---

## FASE 6 — Diagnóstico de cierre

**Estado actual: PARCIAL**

- **Batch:** Sigue corriendo; no ha fallado.
- **DB:** Parcialmente poblada: 719 filas con segmentación (20 días × co/pe × lob/park/service_type); 12 434 filas aún NULL.
- **API:** No probada en runtime (servidor apagado); diseño y código listos para exponer las 4 métricas.
- **UI:** Columnas y lógica implementadas; reflejarán datos donde la DB tenga valores y 0/— donde no.

**Qué falta:** Que el batch termine de procesar los 176 periodos restantes (días restantes + semanas + meses). Hasta entonces, week y month seguirán en 0/NULL en DB y en UI/API.

---

## FASE 7 — Próximo paso correcto

1. **Dejar que el batch siga ejecutándose** (no matar el proceso). Tiempo restante estimado: del orden de **~18–20 h** (176 periodos × ~6 min).
2. **Cuando termine:**
   - Si termina con éxito (exit 0): ejecutar de nuevo el script de validación `scripts/validate_real_segmentation_closure` y comprobar que `with_activity_gt0` se acerque a `total_rows` (o al menos que week/month tengan `with_seg` > 0).
   - Si termina con fallos (algunos periodos en `failed`): revisar el log; los reintentos 2 y 3 volverán a intentar todos los periodos (idempotente). Si tras 3 intentos siguen fallando periodos, la corrección mínima sería reintentar solo esos periodos (p. ej. lista de (period_grain, period_start)) o subir `--per-period-timeout` para esos granos pesados, **sin** rediseñar vistas ni lógica.
3. **Validación runtime/UI:** Con el backend levantado, abrir la vista Real LOB Drill, elegir un periodo ya poblado (por ejemplo día 2025-12-05) y comprobar que Activos, Solo cancelan y % Solo cancelan muestran números coherentes.
4. **Checklist final (cuando estado sea COMPLETO):**
   - [ ] Batch terminó sin errores (o solo periodos conocidos fallidos y documentados)
   - [ ] DB: mayoría de filas con `activity_drivers` no NULL (o según criterio de “ventana objetivo”)
   - [ ] API: al menos un GET drill y un GET children devuelven las 4 métricas pobladas donde corresponde
   - [ ] UI: columnas visibles y valores coherentes en al menos un periodo

---

*Documento generado en el marco del monitoreo y cierre de la segmentación REAL. No se ha modificado la lógica del batch ni las vistas.*
