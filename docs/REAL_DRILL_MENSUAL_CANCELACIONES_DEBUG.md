# Debug: cancelaciones en drill mensual LOB

## Problema observado

En Real → Drill (semanal/mensual) → Periodo **Mensual** → Desglose **LOB**, la columna "Cancel." mostraba **0** en todos los meses para PE y CO.

---

## FASE 1–2 — Evidencia por capa

| Capa | ¿Cancelaciones? | Evidencia |
|------|------------------|-----------|
| day_v2 / week_v3 / month_v3 | Sí | month_v3 tiene `cancelled_trips` (cadena hourly-first). |
| real_drill_dim_fact **month** | **No (NULL)** | Query C: `SUM(cancelled_trips)` por month/lob devolvía **NULL** para todos los meses. |
| mv_real_drill_dim_agg **month** | **No (NULL)** | Query D: mismo resultado (vista sobre la tabla). |
| Endpoint `period=month&desglose=LOB` | Antes 0 | `COALESCE(SUM(cancelled_trips), 0)` = 0 cuando todos son NULL. |

**Query C ejecutada (resumen):**

```text
real_drill_dim_fact period_grain=month breakdown=lob:
  co 2026-02-01 trips=322320 cancelled_trips=None
  pe 2026-02-01 trips=531680 cancelled_trips=None
  ...
```

---

## FASE 3 — Punto exacto de ruptura

**B. month_v3 sí tiene cancelaciones, pero real_drill_dim_fact para month no se pobló con ellas.**

- El script `populate_real_drill_from_hourly_chain` solo insertaba granos **day** y **week** (desde day_v2 y week_v3).
- No existía inserción para **month** desde `mv_real_lob_month_v3`.
- Las filas con `period_grain = 'month'` en `real_drill_dim_fact` provenían de otro origen (p. ej. migración 064 o backfill antiguo) y **nunca tuvieron `cancelled_trips`** (columna añadida en 103; ese origen no la rellenaba).
- Por tanto, para month, `cancelled_trips` era **NULL** en todas las filas → el backend devolvía `cancelaciones = 0`.

No aplican como causa principal: A (se pierde antes de month_v3), C (la vista no expone), D (el servicio no selecciona), E (la UI reemplaza), F (código distinto). El servicio sí selecciona `SUM(cancelled_trips)`; la vista expone la columna; la UI muestra el valor recibido.

---

## FASE 4 — Populate mensual

- **1.** ¿El populate llena grano `month`? **Antes: NO.** Solo day y week.
- **2.** ¿Solo day y week? **Sí.**
- **3.** ¿La UI mensual depende de una tabla no repoblada con cancelaciones? **Sí.** La tabla tenía filas month legacy con `cancelled_trips` NULL.

---

## FASE 5 — Corrección aplicada

**Archivo:** `backend/scripts/populate_real_drill_from_hourly_chain.py`

1. **Parámetro `--months`** (default 6): ventana de meses a repoblar.
2. **DELETE** de filas con `period_grain = 'month'` en esa ventana (junto con day/week).
3. **INSERT month** desde `ops.mv_real_lob_month_v3` para los tres breakdowns (lob, park, service_type), con:
   - `trips` = SUM(completed_trips),
   - `cancelled_trips` = SUM(cancelled_trips),
   - margen y resto igual que en week.

Tras ejecutar el populate con `--months 6`:

- **Query C/D:** month/lob muestran `cancelled_trips` > 0 (ej. CO 2026-02-01: 1 007 750).
- **Endpoint:** `GET /ops/real-lob/drill?period=month&desglose=LOB&segmento=all` devuelve `cancelaciones` reales en KPIs y en cada fila de `rows`.

---

## FASE 6 — Validación

1. **Query mensual en DB con cancelaciones > 0:** realizada; CO 2026-02-01 cancelled_trips=1 007 750.
2. **Endpoint mensual con cancelaciones > 0:** PE/CO y meses recientes con valores distintos de 0.
3. **UI:** Tras recargar la vista mensual LOB, la columna "Cancel." debe mostrar esos valores (sin reiniciar backend; los datos vienen de la misma API).
4. **Archivos modificados:**
   - `backend/scripts/populate_real_drill_from_hourly_chain.py` (añadido grano month desde month_v3).

---

## Cómo repoblar en el futuro

Para que el drill mensual siga mostrando cancelaciones actualizadas:

```bash
cd backend
python -m scripts.populate_real_drill_from_hourly_chain --days 120 --weeks 18 --months 6
```

Incluir siempre `--months` (p. ej. 6 o 12) para refrescar el grano month con `cancelled_trips` desde month_v3.
