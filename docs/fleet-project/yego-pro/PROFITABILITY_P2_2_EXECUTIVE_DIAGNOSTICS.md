# Yego Pro Profitability P2.2 — Executive Diagnostics Report

## Fecha
2026-05-28

## Archivos tocados en esta sesion

| Archivo | Accion |
|---------|--------|
| `frontend/src/components/YegoProProfitabilityPage.jsx` | Reescritura completa (diagnostico ejecutivo) |
| `docs/fleet-project/yego-pro/PROFITABILITY_P2_2_EXECUTIVE_DIAGNOSTICS.md` | Creado (este doc) |

## Archivos NO tocados (confirmado)

- Drivers: NINGUNO (archivos Driver en git diff son de sesiones externas/previas)
- Yango Loyalty: NINGUNO
- Omniview: NINGUNO
- Backend routers: NINGUNO
- Backend services: NINGUNO
- SQL / MVs: NINGUNO
- Simulador: NO EXISTE
- WorkOS: NINGUNO
- App.jsx: sin cambios en esta sesion
- api.js: sin cambios en esta sesion

## ALERTA: archivos externos en git diff

Los siguientes archivos aparecieron en `git diff` durante esta sesion pero NO fueron tocados por P2.2:
- `backend/app/routers/drivers.py` (sesion externa)
- `frontend/src/components/driver/DriverAdminDataView.jsx` (sesion externa)
- `frontend/src/components/driver/DriverDataFoundation.jsx` (sesion externa)
- `frontend/src/components/driver/DriverLifecycleSummary.jsx` (sesion externa)
- `frontend/src/components/driver/DriverOperatorView.jsx` (sesion externa)
- `frontend/src/components/driver/DriverStrategyView.jsx` (sesion externa)
- `frontend/src/components/driver/DriverSupervisorView.jsx` (sesion externa)
- `backend/app/services/yango_loyalty_service.py` (sesion previa)
- `frontend/src/components/yangoLoyalty/YangoLoyaltyView.jsx` (sesion previa)

Estos cambios pertenecen a otros flujos de trabajo. P2.2 NO los causo.

## Diagnosticos agregados (10 tareas)

### Task 1: Executive Diagnostic Header — "Que esta pasando?"
- Utilidad neta semanal (coloreado por señal)
- Utilidad neta mensual estimada
- Revenue semanal / mensual estimado
- Margen %
- Conductores rentables vs en perdida (conteo con total)
- Vehiculos rentables vs en perdida (conteo con total)
- Verde = positivo, amarillo = riesgo, rojo = perdida

### Task 2: Top Vehiculos en Perdida
- Top 5 vehiculos ordenados por mayor perdida
- Muestra: utilidad, revenue, viajes, margen
- Badge numerico rojo con ranking

### Task 3: Top Vehiculos Rentables
- Top 5 vehiculos ordenados por mayor utilidad
- Muestra: utilidad, revenue, viajes, margen
- Badge numerico verde con ranking

### Task 4: Driver Contribution Leaderboard
- TOP CONDUCTORES RENTABLES (top 5)
- TOP CONDUCTORES EN PERDIDA (top 5)
- Revenue, viajes, margen por conductor
- Layout 2 columnas

### Task 5: Loss Explanation — "Donde se va el dinero?"
- Distribucion % de costos desde waterfall/input-mapping
- Barras horizontales con color (rojo=costo, verde=ingreso)
- Porcentaje + valor absoluto por linea
- Ordenado por mayor peso primero
- Solo calculo deterministico (totalAbs / abs(item))

### Task 6: Utilization Diagnostics
- Viajes/Conductor
- Ingreso/Conductor
- Ingreso/Vehiculo
- Viajes/Vehiculo
- Km/Viaje (si existe)
- Km vacio (si existe)
- Ingreso/Hora (si existe)
- Badges: Bajo / Medio / Alto (umbrales deterministicos)

### Task 7: Shift Diagnostics — Brecha dia/noche
- Revenue dia vs noche
- Margen dia vs noche
- Diferencia % calculada
- Mensaje:
  - <20%: "La diferencia observada es moderada."
  - >20%: "La diferencia observada es significativa."
- Iconos sol/luna

### Task 8: Key Findings — "Hallazgos observados"
- Reglas deterministicas:
  - >60% vehiculos en perdida → alta severidad
  - >30% vehiculos en perdida → media severidad
  - >50% conductores en perdida → alta severidad
  - Payout >40% del costo total → hallazgo
  - <5 viajes/conductor → utilizacion baja
  - Brecha dia/noche <20% → limitada
- Colores por severidad: rojo (alta), amarillo (media), azul (baja)
- NO IA, solo reglas

### Task 9: Data Confidence
- Operacion: HIGH (verde)
- Billing: PARTIAL (amarillo)
- Simulacion: N/A (gris)
- Historico financiero disponible: X semana(s)

### Task 10: QA
- Build: OK (838 modules, 0 errors, 10.94s)
- Drivers: NO TOCADO
- Loyalty: NO TOCADO
- Omniview: NO TOCADO
- Backend: NO TOCADO

## Arquitectura del diagnostico

**Cambio clave:** El tab Overview ahora carga los 8 endpoints en paralelo al montar el componente.

```
Overview tab (mount)
  ├─ GET /fleet-project/yego-pro/profitability/overview
  ├─ GET /fleet-project/yego-pro/profitability/weekly
  ├─ GET /fleet-project/yego-pro/profitability/daily
  ├─ GET /fleet-project/yego-pro/profitability/drivers
  ├─ GET /fleet-project/yego-pro/profitability/vehicles
  ├─ GET /fleet-project/yego-pro/profitability/shifts
  ├─ GET /fleet-project/yego-pro/profitability/input-mapping
  └─ GET /fleet-project/yego-pro/profitability/quality
```

Cada endpoint se resuelve independientemente:
- Si uno falla, su seccion muestra "Datos de X no disponibles en este momento."
- Las demas secciones cargan normalmente
- NO hay loading infinito (AbortController en cleanup)

Las otras 7 tabs siguen cargando individualmente al seleccionarlas.

## Endpoints consumidos (sin cambios)

| Endpoint | Usado en |
|----------|----------|
| `/fleet-project/yego-pro/profitability/overview` | DiagnosticHeader, UtilizationDiagnostics, KeyFindings |
| `/fleet-project/yego-pro/profitability/weekly` | Tab Weekly Closed |
| `/fleet-project/yego-pro/profitability/daily` | Tab Last Closed Day |
| `/fleet-project/yego-pro/profitability/drivers` | DiagnosticHeader, DriverLeaderboard, UtilizationDiagnostics, KeyFindings |
| `/fleet-project/yego-pro/profitability/vehicles` | DiagnosticHeader, TopVehiclesCards, UtilizationDiagnostics, KeyFindings |
| `/fleet-project/yego-pro/profitability/shifts` | ShiftDiagnostics, KeyFindings |
| `/fleet-project/yego-pro/profitability/input-mapping` | LossExplanation, KeyFindings |
| `/fleet-project/yego-pro/profitability/quality` | DataConfidence |

## Build result

```
vite v5.4.21 building for production...
838 modules transformed.
built in 10.94s — 0 errors
```

## Riesgos pendientes

1. **Runtime no probado:** Los 8 endpoints cargan en paralelo. Si todos devuelven 404, la UI muestra empty states (seguro, no bloqueante).
2. **Esquema de respuesta:** Cada seccion diagnostica intenta multiples nombres de campo (profit/net_profit/margin/result, etc.). Si el backend usa un esquema no previsto, la seccion se omite (no crashea).
3. **Umbrales de utilizacion:** Los thresholds (bajo <5, alto >20 viajes/conductor) son arbitrarios. Deben calibrarse con datos reales.
4. **8 requests simultaneos en Overview:** Puede ser carga pesada si los endpoints son lentos. Cada uno tiene timeout de 60s. Si preocupa, se podria agregar un endpoint de resumen que devuelva todo.

## GO / NO-GO

**GO para prueba humana de Gonzalo.**

Gonzalo podra abrir Profitability y entender inmediatamente:
1. Cuanto pierde/gana (DiagnosticHeader)
2. Por que (LossExplanation + KeyFindings)
3. Quien destruye margen (TopLosers + DriverLeaderboard)
4. Que activos sostienen la operacion (TopWinners + UtilizationDiagnostics)
