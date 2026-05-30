# PROFITABILITY P1.4.2 — SIMULATOR BONUS + TRACEABILITY HARDENING

## Resumen

El Simulator del modulo Yego Pro Profitability se transforma de una calculadora simple de payout en una herramienta auditable para comparar escenarios reales de Yego Pro, incluyendo bonos Yango, turnos, brandeo, Premier y trazabilidad matematica completa.

**Ruta:** Control Tower → Fleet Project → Yego Pro → Profitability → Simulator

**Archivos modificados:**
- `backend/app/services/yego_pro_profitability_service.py` — bonus tables, run_simulator, calculation_trace
- `backend/app/routers/yego_pro_profitability.py` — POST /simulator/run, GET /simulator/defaults
- `frontend/src/services/api.js` — runYegoProSimulator, getYegoProSimulatorDefaults
- `frontend/src/components/YegoProProfitabilityPage.jsx` — SimulatorPanel completo

---

## 1. Modelo de Turnos

### Inputs
| Input | Descripcion | Default |
|---|---|---|
| `shifts_per_vehicle` | 1 o 2 turnos por vehiculo | 2 |
| `selected_shift` | day / night / both | day |
| `trips_day_week` | Viajes turno dia por semana | 85 |
| `trips_night_week` | Viajes turno noche por semana | 45 |
| `trips_premier_day_week` | Viajes Premier turno dia | 6 |
| `trips_premier_night_week` | Viajes Premier turno noche | 3 |

### Reglas
- **2 turnos:** viajes semanales = dia + noche. Ambos turnos activos.
- **1 turno:** solo el turno seleccionado (dia o noche).

En UI se muestra claramente: "Modelo: 2 turnos por vehiculo" o "Modelo: 1 turno (noche)".

---

## 2. Bonos Yango como Ingreso

El flujo correcto modelado:

```
Revenue bruto de viajes
  + Bono Yango general
  + Bono Yango Premier
  = Ingreso total empresa

  - Costos variables (combustible, mantenimiento, comision)
  - Costos fijos (cuota vehiculo, seguro/GPS)
  - Reserva desgaste
  = Base neta antes de reparto

  - Payout conductor %
  - Garantia (si aplica)
  = Utilidad empresa
```

Los bonos Yango son **INGRESO** de la empresa, no egreso.

---

## 3. Tablas de Bonos

### Bono General con Brandeo
| Viajes Min | % Bonus | Monto (S/) |
|---|---|---|
| 190 | 27% | 720 |
| 150 | 25% | 550 |
| 125 | 23% | 470 |
| 100 | 21% | 390 |
| 75 | 20% | 320 |
| 50 | 19% | 260 |
| 30 | 18% | 175 |

### Bono General sin Brandeo
| Viajes Min | % Bonus | Monto (S/) |
|---|---|---|
| 150 | 20% | 450 |
| 125 | 18% | 390 |
| 100 | 16% | 315 |
| 75 | 14% | 230 |
| 50 | 13% | 170 |
| 30 | 12% | 125 |
| 10 | 11% | 60 |

### Bono Premier
| Viajes Premier Min | % Bonus | Monto (S/) |
|---|---|---|
| 20 | 40% | 600 |
| 15 | 36% | 410 |
| 10 | 33% | 250 |
| 8 | 31% | 190 |
| 6 | 29% | 130 |
| 4 | 27% | 85 |
| 2 | 25% | 40 |

**Regla:** Se usa el tramo mayor alcanzado. Si un vehiculo con brandeo tiene 126 viajes → tramo 125 → S/470.

---

## 4. Referencias Operativas

Junto a cada input editable se muestra:
- Referencia operacion (valor observado)
- Fuente (modulo origen)
- Confianza (REAL_OPERATIONAL / ESTIMATED)
- Periodo de referencia

Si no hay referencia: "Sin referencia operativa. Usando manual/legacy."

---

## 5. Subtotales por Card

### Produccion
- Viajes semanales
- Viajes Premier
- Revenue bruto viajes
- Bono general
- Bono Premier
- Ingreso total empresa

### Costos Variables
- Km total
- Combustible
- Mantenimiento
- Comision plataforma
- Costo variable total

### Pago Conductor
- Base reparto
- Payout conductor
- Garantia
- Ingreso conductor total

### Costos Fijos
- Cuota vehiculo semanal
- Seguro/GPS semanal
- Reserva desgaste
- Total costos fijos

### Resultado
- Utilidad semanal
- Utilidad mensual
- Margen %
- Payback (viajes)
- Break-even (viajes)

---

## 6. Escenarios

### Funcionalidades
- Nombre editable antes de guardar (default: "Escenario {n} — {payout}% — {fecha/hora}")
- Boton "Guardar escenario" en memoria (sin BD)
- Tabla de escenarios muestra: nombre, fecha, modelo, brandeo, viajes, bonos, payout, utilidad, margen, ingreso conductor, payback, status

### Acciones
- **Renombrar:** click en nombre → input editable
- **Duplicar:** crea copia con "(copia)" en el nombre
- **Cargar:** restaura todos los inputs y resultado desde el escenario
- **Eliminar:** remueve de memoria

---

## 7. Trazabilidad Matematica

POST `/simulator/run` devuelve `calculation_trace` con 18 pasos:

1. Revenue bruto viajes
2. Bono general Yango
3. Bono Premier
4. Ingreso total empresa
5. Km total
6. Combustible
7. Mantenimiento
8. Comision plataforma
9. Costos fijos
10. Reserva desgaste
11. Base reparto
12. Payout conductor
13. Garantia
14. Utilidad semanal
15. Utilidad mensual
16. Margen %
17. Payback
18. Break-even

Cada paso contiene: step, label, formula, inputs, result, source, confidence.

En frontend: panel colapsable "Ver calculo" con tabla completa.

---

## 8. Sensibilidad con Bonos

### Payout sensitivity
Para cada % de payout (30%, 35%, 40%, 45%, 50%, 55%, 60%) se muestra:
- Utilidad semanal
- Ingreso conductor
- Margen %
- Diferencia vs escenario actual

### Bonus scenarios
- Sin bono
- Tramo actual
- Siguiente tramo general
- Siguiente tramo Premier

Para cada uno: ingreso empresa, utilidad, ingreso conductor, margen, diferencia vs actual.

---

## Formulas Clave

```
gross_trip_revenue = trips_week * ticket_avg
general_bonus = lookup(bonus_table, general_bonus_trips_week)
premier_bonus = lookup(premier_table, premier_bonus_trips_week)
total_company_income = gross_trip_revenue + general_bonus + premier_bonus

km_total = trips_week * km_per_trip
fuel_cost = km_total * fuel_per_km
maintenance_cost = trips_week * maintenance_per_trip
platform_commission = gross_trip_revenue * (platform_commission_pct / 100)
total_variable_cost = fuel_cost + maintenance_cost + platform_commission

fixed_weekly = vehicle_weekly_cost + insurance_gps_weekly
reserve_amount = total_company_income * (reserve_pct / 100)
total_costs = total_variable_cost + fixed_weekly + reserve_amount

base_before_payout = total_company_income - total_costs
payout_driver = gross_trip_revenue * (driver_payout_pct / 100)
driver_income_total = max(payout_driver, guarantee_amount)

company_profit_weekly = total_company_income - total_costs - driver_income_total
company_profit_monthly = company_profit_weekly * 4.33
margin_pct = (company_profit_weekly / total_company_income) * 100
```

---

## Limitaciones

- Tablas de bonos hardcodeadas (no configurable desde UI aun)
- No persistencia en BD (escenarios solo en memoria)
- Referencias operativas son valores estaticos (no consultan BD)
- Sensibilidad solo cubre payout y bonos; no produccion
- Sin IA ni recomendaciones automaticas

---

## GO / NO-GO

| Criterio | Estado |
|---|---|
| Simulator carga | GO |
| Bonos general y Premier se calculan correctamente | GO |
| Brandeo cambia tabla de bono general | GO |
| 1 turno y 2 turnos funcionan | GO |
| Subtotales visibles | GO |
| Escenario puede nombrarse antes de guardar | GO |
| Escenarios pueden renombrarse, duplicarse y eliminarse | GO |
| calculation_trace visible | GO |
| No NaN, no undefined, no loading infinito | GO |
| No toca otros modulos | GO |
| Backend compila sin errores | GO |
| Frontend build sin errores | GO |
