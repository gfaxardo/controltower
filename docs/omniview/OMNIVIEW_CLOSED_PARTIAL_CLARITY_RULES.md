# OMNI-P0-T6 — CLOSED / PARTIAL CLARITY RULES

**Motor:** Omniview P0 Recovery  
**Fecha:** 2026-06-03  
**Estado:** REGLAS DEFINIDAS — PENDIENTE IMPLEMENTACIÓN

---

## 1. EL PROBLEMA

> "caída -30% Auto Regular — no queda claro si es parcial o cerrado"

Una celda muestra -30% en rojo. El usuario no sabe si:
- El período ya **cerró** y la caída es definitiva → **ALARMA REAL**
- El período está **parcial** (ej. 3 de 30 días) y la caída puede recuperarse → **ALARMA TEMPRANA**
- Es el período **actual** y solo es una foto momentánea → **MONITOREO**

**Sin esta distinción, cualquier delta es ininterpretable.**

---

## 2. REGLA CANÓNICA

> **Toda celda con `delta_pct != null` DEBE mostrar `period_status` de forma visible e interpretable.**

No puede mostrarse un -30% sin contexto de estado del período.

---

## 3. ESTADOS DEFINIDOS

| Estado | Badge visual | Color celda | Significado operacional |
|--------|-------------|-------------|------------------------|
| **CLOSED** | Sin badge (o check verde) | Normal (con color de attainment) | "Este -30% es definitivo. El período cerró." |
| **PARTIAL** | `~` (tilde, amber) | Amber sutil | "Este -30% es parcial. Solo 3 de 30 días transcurridos. Puede recuperarse." |
| **CURRENT** | Anillo azul (present focus) | Normal | "Este es el período actual. Los datos están llegando." |
| **FUTURE** | `—` (em dash, gray) | Gray, opacity 35% | "Período futuro. Sin ejecución. Solo plan/proyección visible." |
| **NO_PLAN** | "Sin plan" (gray) | Gray | "No hay plan cargado para este período. Sin referencia." |
| **NO_REAL** | "Sin dato" (red) | Red sutil | "Debería haber dato real pero no llegó. Investigar." |

---

## 4. CÓMO CALCULAR PERIOD_STATUS

### 4.1 Daily

```
If trip_date > TODAY → FUTURE
If trip_date == TODAY → CURRENT
If trip_date < TODAY AND trip_date >= most_recent_closed_date → CLOSED
Else → PARTIAL (shouldn't happen for past days with data)
```

### 4.2 Weekly

```
If week_start > current_week_monday → FUTURE
If week_start == current_week_monday → PARTIAL (semana en curso)
If week_start < current_week_monday AND week_end <= TODAY → CLOSED
If week_start < current_week_monday AND week_end > TODAY → PARTIAL (semana pasada pero sin datos del fin de semana aún)
```

### 4.3 Monthly

```
If month_start > current_month_first → FUTURE
If month_start == current_month_first → PARTIAL (mes en curso)
If month_start < current_month_first → CLOSED
```

---

## 5. EJEMPLO: CAÍDA -30% AUTO REGULAR

### Escenario A: S23 (semana actual, 3 de 7 días)

```
real_value: 450 (trips)
plan_value: 643 (trips semanales)
delta_pct: -30%
period_status: PARTIAL
badge: "~"
tooltip: "-30% vs plan semanal. PARCIAL: 3 de 7 días transcurridos (43%).
         Proyección: 965 trips esperados al cierre. Ritmo actual: 150 trips/día → 1,050 estimado.
         Si mantiene ritmo, cerraría en +9% sobre plan."
color: amber (precaución, no alarma)
```

→ El usuario entiende que -30% es temprano y puede recuperarse.

### Escenario B: S22 (semana cerrada)

```
real_value: 450 (trips)
plan_value: 643 (trips semanales)
delta_pct: -30%
period_status: CLOSED
badge: ninguno
tooltip: "-30% vs plan semanal. CERRADO. Semana completa. Déficit definitivo: -193 viajes."
color: red (alarma real)
```

→ El usuario entiende que -30% es definitivo y requiere acción.

---

## 6. IMPLEMENTACIÓN

### Backend

El endpoint `/ops/business-slice/omniview-projection` debe añadir `period_status` a cada fila:

```json
{
  "country": "peru",
  "city": "lima",
  "month": "2026-06-01",
  "period_status": "PARTIAL",
  "period_elapsed_pct": 10.0,
  "period_days_total": 30,
  "period_days_elapsed": 3,
  ...
}
```

### Frontend

`BusinessSliceOmniviewMatrixCell.jsx` debe renderizar el badge según `period_status`:

- PARTIAL → badge "~" en amber, tooltip con días transcurridos
- CLOSED → sin badge especial (o check verde sutil)
- CURRENT → anillo azul (ya implementado en O3)
- FUTURE → celda gris, opacidad reducida
- NO_PLAN → texto "Sin plan" en gris
- NO_REAL → texto "Sin dato" en rojo

---

## 7. VERIFICACIÓN

- [ ] Celda con -30% CLOSED → sin tilde, color rojo, tooltip dice "CERRADO"
- [ ] Celda con -30% PARTIAL → tilde "~", color amber, tooltip dice "PARCIAL: X/Y días"
- [ ] Celda FUTURE → gris, sin número real
- [ ] Badge visible sin hover (no requiere tooltip para ver el estado)
- [ ] Consistente cross-métrica y cross-grain

---

**END OF RULES**
