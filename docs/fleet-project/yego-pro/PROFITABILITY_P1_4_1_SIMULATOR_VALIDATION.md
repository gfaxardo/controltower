# Profitability P1.4.1 — Simulator Validation & Hardening

## Objetivo

Validar que el Simulator MVP produce resultados coherentes con el modelo financiero historico de Yego Pro (Excel "Calculo Pagos.xlsx").

Solo se hicieron validacion, hardening y documentacion. NO se agregaron funcionalidades nuevas, IA, ni Decision Engine.

## FASE 1 — Auditoria de formulas

### Metodo

Se compararon las formulas del backend `run_simulation()` contra el modelo `MODELO PORCENTAJE` del Excel.

### Resultados

| Output | Formula Excel | Formula Simulator | Match | Diferencia |
|--------|--------------|-------------------|-------|------------|
| gross_revenue_week | trips * ticket_avg | trips_per_day * days * ticket_avg | YES | Identica |
| platform_commission | revenue * commission% | idem | YES | Identica |
| driver_payout | net_revenue * driver% | idem | YES | Identica |
| fuel_cost | km * fuel_rate | idem | YES | Identica |
| maintenance_cost | km * maint_rate | idem | YES | Identica |
| fixed_cost | daily * days | idem | YES | Identica |
| vehicle_weekly | monthly / 4 | monthly / 4.33 | MINOR | 8.25% diff (4.33 vs 4 semanas) |
| net_profit_week | gross - costs | idem | YES | Identica |
| net_profit_month | weekly * 4 | weekly * 4.33 | MINOR | 8.25% diff |
| margin_pct | profit / revenue | idem | YES | Identica |
| driver_income_week | payout + bonuses | idem | YES | Identica |
| break_even | fixed / net_per_trip | idem | YES | Logica identica |
| company_recovery | capital / monthly | idem | YES | Depende de monthly (diff menor) |

### Veredicto

**Formulas alineadas con Excel: YES**

La unica diferencia es el factor de conversion mensual (4.33 vs 4), que hace el Simulator mas preciso matematicamente. El impacto es <10%.

Los defaults de inputs son conservadores, basados en el Excel historico.

Riesgo: Bajo. Las diferencias son exclusivamente en el factor semanas/mes.

## FASE 2 — Escenarios de validacion

Se ejecutaron 8 escenarios cubriendo el espectro completo:

| Escenario | Trips/dia | Ticket | Payout | Margin | Status |
|-----------|-----------|--------|--------|--------|--------|
| Conservador | 15 | S/16 | 45% | 15.3% | VIABLE |
| Actual | 12 | S/14 | 45% | 12.3% | VIABLE |
| Optimista | 20 | S/18 | 40% | 23.3% | VIABLE |
| Dia Incentivado | 8 | S/16 | 50% | -2.0% | LOSS |
| Turno Noche | 6 | S/18 | 45% | -3.2% | LOSS |
| Capital Recuperable | 15 | S/16 | 45% | 15.3% | VIABLE (12.6m payback) |
| Payout 40% | 15 | S/16 | 40% | 20.0% | VIABLE |
| Payout 55% | 15 | S/16 | 55% | 6.3% | RISKY |

### Analisis

- Escenario conservador produce S/220 semanales de utilidad con margen 15.3%
- Escenario actual produce S/124 semanales (margen 12.3%), aun viable
- Escenarios con bonus/garantia caen a perdida (-S/15 a -S/17 semanales)
- Payback a 60 meses: viable con margen >15%. Riesgoso con margen <10%.
- Payout >50% convierte un escenario VIABLE en RISKY con los defaults

### Veredicto

**Escenarios comparables y realistas: YES**

El Simulator refleja correctamente como cambios en trips, ticket, payout y costos afectan la rentabilidad.

## FASE 3 — Trazabilidad de inputs

### Verificacion

Los 17 inputs del simulador fueron verificados:

| # | Input | Source | Confidence | Editable | Unit |
|---|-------|--------|------------|----------|------|
| 1 | trips_per_day | OPERATIONAL/LEGACY | REAL/LEGACY | YES | viajes/dia |
| 2 | days_per_week | LEGACY | LEGACY | YES | dias |
| 3 | ticket_avg | OPERATIONAL/LEGACY | REAL/LEGACY | YES | S/ |
| 4 | km_per_trip | OPERATIONAL/LEGACY | REAL/LEGACY | YES | km |
| 5 | fuel_cost_per_km | OPERATIONAL/LEGACY | REAL/LEGACY | YES | S//km |
| 6 | maintenance_cost_per_km | LEGACY | LEGACY | YES | S//km |
| 7 | platform_commission_pct | LEGACY | LEGACY | YES | % |
| 8 | driver_payout_pct | LEGACY | LEGACY | YES | % |
| 9 | fixed_daily_cost | LEGACY | LEGACY | YES | S//dia |
| 10 | vehicle_monthly_quota | MANUAL | LEGACY | YES | S//mes |
| 11 | insurance_gps_monthly | MANUAL | LEGACY | YES | S//mes |
| 12 | capital_to_recover | MANUAL | LEGACY | YES | S/ |
| 13 | payback_target_months | MANUAL | LEGACY | YES | meses |
| 14 | weekly_bonus_day | MANUAL | LEGACY | YES | S//sem |
| 15 | weekly_bonus_night | MANUAL | LEGACY | YES | S//sem |
| 16 | guarantee_weekly | MANUAL | LEGACY | YES | S//sem |
| 17 | wear_reserve_pct | MANUAL | LEGACY | YES | % |

Ningun input esta sin fuente o sin confidence.

### Veredicto

**Inputs trazables: YES**

## FASE 4 — Hardening de escenarios

### Mejoras implementadas

1. **Timestamp**: cada escenario guardado incluye `timestamp` ISO (YYYY-MM-DD HH:MM:SS)
2. **Duplicar escenario**: boton "Duplicar" en la tabla de escenarios que clona un escenario con "(copia)"
3. **Confidence general**: cada escenario guardado incluye score de confianza (HIGH/MEDIUM/LOW) basado en % de inputs operativos reales
4. **Columna Timestamp**: visible en la tabla de escenarios guardados
5. **Columna Confianza**: visible en la tabla, con color (verde/ambar/rojo)

### Estado

- Escenarios persisten solo en memoria del browser (no BD)
- Al recargar la pagina, los escenarios se pierden
- Sin persistencia planeada aun (scope P1.4 MVP)

## FASE 5 — Data Quality del Simulador

### Panel "Calidad del Escenario"

Agregado al SimulatorPanel, visible entre los resultados y los botones de accion.

Muestra:
- **Score general**: HIGH (>=50% inputs reales), MEDIUM (>=20%), LOW (<20%)
- **Inputs operativos reales**: etiquetas con los campos que vienen de produccion
- **Inputs manuales**: campos configurables por el usuario
- **Inputs legacy**: campos con defaults del Excel
- **Porcentaje**: "X% de los inputs provienen de produccion real"

### Source badges en inputs

Cada input en el panel izquierdo ahora muestra un badge:
- `REAL` (verde) = OPERATIONAL
- `MAN` (azul) = MANUAL  
- `LEG` (ambar) = LEGACY

### Veredicto

**Score de confianza implementado: YES**

## Limitaciones actuales

1. No hay persistencia de escenarios (solo memoria del browser)
2. No hay backtest contra datos historicos reales (se compara contra defaults y supuestos, no contra billing historico)
3. La conversion 4.33 semanas/mes difiere del Excel (4 semanas/mes) en ~8%
4. No hay validacion automatica contra cierres reales antes de simular
5. Los inputs legacy usan supuestos genericos, no parametros calibrados por parque
6. Escenarios de sensibilidad hacen multiples llamadas API secuenciales (puede ser lento)
7. El score de confianza es binario (si hay cierres, es REAL; si no, es LEGACY)

## QA

- `python -m compileall backend/app` — OK
- `cd frontend && npm run build` — OK (5.11s, sin errores)
- No se tocaron modulos externos (Drivers, Loyalty, Omniview, WorkOS)
- Waterfall, Data Quality, Overview siguen funcionales
- Simulator carga, calcula, guarda escenarios, duplica, muestra calidad

## Veredicto Final P1.4.1

| Criterio | Resultado |
|----------|-----------|
| Formulas alineadas con Excel | YES |
| Escenarios comparables | YES |
| Inputs trazables | YES |
| Score de confianza implementado | YES |
| Hardening de escenarios (timestamp, duplicar) | YES |
| Data Quality panel visible | YES |
| GO/NO-GO para P1.5 Diagnostic Layer | GO |

**Veredicto: GO para pasar a P1.5 Diagnostic Layer.**

El Simulator produce resultados coherentes con el modelo Excel, tiene hardening suficiente para uso exploratorio, y la calidad de datos es transparente. Pendiente para P1.5: persistencia, backtest historico, calibracion por parque, y diagnostic layer con ROI/TIR/VPN.

## Fecha

2026-05-29
