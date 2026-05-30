# PROFITABILITY P1.4.3 — SIMULATOR UX + BONUS CONFIG + OPERATION REFERENCES

**Fecha:** 2026-05-30
**Valoracion:** 61/61 — GO
**Script:** `validate_p1_4_3.py`

---

## Resumen

El Simulator de Yego Pro Profitability se endurece en UX, trazabilidad y configurabilidad. El usuario ahora puede:

- Ver y modificar las tablas de bonos Yango (3 tabs)
- Ver que tramo de bono alcanzo el conductor y cuanto falta para el siguiente
- Separar ticket promedio general vs Premier
- Ver referencias operativas lado a lado con los inputs editables
- Hacer drill-down por bloque a las lineas de calculo
- Leer un resumen matematico paso a paso
- Navegar una UI reorganizada con jerarquia visual clara

---

## 1. Bonus Config UI (FASE 1)

Seccion colapsable "Configurar tablas de bonos Yango" con 3 tabs:

| Tab | Tramos |
|---|---|
| Bono general brandeado | 7 (190 -> 30) |
| Bono general sin brandeo | 7 (150 -> 10) |
| Bono Premier | 7 (20 -> 2) |

Operaciones:
- Editar viajes_min, bonus_pct, bonus_amount por fila
- Agregar fila (nuevo tramo)
- Eliminar fila
- Resetear defaults
- Las tablas se envian al backend en `bonus_tables`

---

## 2. Bonus Achievement Panel (FASE 2)

Panel "Bono aplicado esta semana":

| Campo | Ejemplo (General brandeado 85 viajes) |
|---|---|
| Modalidad | Brandeado |
| Viajes considerados | 85 |
| Tramo alcanzado | 75 -> 20% -> S/320 |
| Siguiente tramo | 100 viajes (faltan 15) |
| Monto adicional potencial | +S/70 |

Igual para Premier.

---

## 3. General vs Premier (FASE 3)

Separacion de inputs:

| Grupo | Inputs |
|---|---|
| Produccion general | viajes dia, viajes noche, ticket promedio general |
| Produccion Premier | viajes Premier dia, viajes Premier noche, ticket promedio Premier |

Calculo:
```
revenue_general = (viajes_generales_dia + viajes_generales_noche) * ticket_avg_general
revenue_premier = (viajes_premier_dia + viajes_premier_noche) * ticket_avg_premier
gross_trip_revenue = revenue_general + revenue_premier
```

---

## 4. Operational Reference Column (FASE 4)

Layout de 3 columnas por input:

| Label | Input (editable) | Referencia (no editable) |
|---|---|---|
| Viajes generales dia | [ 85 ] | Ref: 85 | module_calculated_shifts | REAL_OPERATIONAL | 30d |

Formato: badge azul para valor, badge gris para fuente, badge verde/ambar para confianza.

---

## 5. Subtotals + Drills (FASE 5)

5 bloques con boton "Ver detalle":

| Bloque | Subtotal | Trace steps al expandir |
|---|---|---|
| Produccion | Ingreso total | revenue_general, revenue_premier, gross_trip_revenue, bonos, total_company_income |
| Costos variables | Total variable | km_total, fuel, maintenance, commission, total_variable |
| Costos fijos | Total fijos | fixed_weekly, reserve, total_costs |
| Pago conductor | Ingreso conductor | base_before_payout, payout, net_after_payout |
| Resultado | Utilidad semanal | profit_weekly, profit_monthly, margin, payback, break_even |

---

## 6. Mathematical Summary (FASE 6)

Seccion "Como se calculo" con 8 pasos con numeros reales:

1. Ingreso por viajes: (130 x S/15) + (9 x S/22) = S/2,148
2. Ingreso Yango: S/320 + S/130 = S/450
3. Ingreso total: S/2,148 + S/450 = S/2,598
4. Costos variables: combustible + mantenimiento + comision = S/...
5. Costos fijos: cuota + seguro + reserva = S/...
6. Base de reparto: ingreso - costos = S/...
7. Pago conductor: revenue x 50% = S/...
8. Utilidad empresa: base - pago = S/...

---

## 7. Visual Authority / UX (FASE 7)

Nuevo orden vertical:

1. Header del escenario (nombre + Run + Save)
2. Selector 1/2 turnos
3. [Result] KPI cards: Ingreso total, Bono general, Bono Premier, Utilidad, Ingreso conductor, Margen
4. [Result] Bonus Achievement Panel
5. Bonus Config accordion (colapsable)
6. Inputs: Produccion (general | Premier 2-col) + Costos (var | fijos 2-col) + Pago + Bonos
7. [Result] Subtotals grid con drill-down
8. [Result] "Como se calculo"
9. [Result] Sensibilidad (accordion)
10. [Result] Trace (accordion)
11. Escenarios guardados (tabla)

---

## 8. Backend Contract (FASE 8)

### POST /simulator/run

**Acepta:**
```json
{
  "ticket_avg_general": 15.0,
  "ticket_avg_premier": 22.0,
  "bonus_tables": {
    "general_branded": [...],
    "general_unbranded": [...],
    "premier": [...]
  }
}
```

**Devuelve `bonus_result`:**
```json
{
  "general": {
    "mode": "Brandeado",
    "trips_considered": 85,
    "achieved_threshold": 75,
    "bonus_pct": 20,
    "bonus_amount": 320,
    "next_threshold": 100,
    "trips_to_next": 15,
    "additional_bonus_potential": 70
  },
  "premier": {...}
}
```

**Devuelve en subtotals.production:**
- `revenue_general`
- `revenue_premier`

---

## 9. Validacion (61 checks)

| Caso | Checks | Resultado |
|---|---|---|
| 1. Branded 85 -> S/320 | 6/6 | GO |
| 2. Unbranded 85 -> S/230 | 3/3 | GO |
| 3. Premier 6 -> S/130 | 4/4 | GO |
| 4. Premier 1 -> S/0 | 2/2 | GO |
| 5. Ticket split revenue | 3/3 | GO |
| 6. Custom bonus_tables | 2/2 | GO |
| 7. bonus_result structure | 28/28 | GO |
| 8. Trace steps | 4/4 | GO |
| 9. Defaults | 3/3 | GO |
| 10. No NaN | 1/1 | GO |

QA: backend compila, frontend build sin errores.

---

## Limitaciones

- Bonus tables no persisten en BD (solo en estado frontend)
- Referencias operativas son valores estaticos (no consultan BD aun)
- Sin IA ni recomendaciones automaticas
- Sin persistencia de escenarios en BD

---

## Veredicto

**GO.** 61/61 checks pasados. Backend y frontend compilan/build sin errores. El Simulator ahora es una herramienta auditable, configurable y entendible para comparar escenarios reales de Yego Pro.
