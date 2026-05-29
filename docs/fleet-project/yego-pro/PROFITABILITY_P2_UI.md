# Yego Pro Profitability P2 — UI

## Ruta UI

```
Control Tower > Fleet Project > Yego Pro > Profitability
URL: /fleet-project/yego-pro/profitability
```

## Tabs

| Tab | Endpoint |
|-----|----------|
| Overview | `GET /fleet-project/yego-pro/profitability/overview` |
| Weekly Closed | `GET /fleet-project/yego-pro/profitability/weekly` |
| Last Closed Day | `GET /fleet-project/yego-pro/profitability/daily` |
| Drivers | `GET /fleet-project/yego-pro/profitability/drivers` |
| Vehicles | `GET /fleet-project/yego-pro/profitability/vehicles` |
| Shifts | `GET /fleet-project/yego-pro/profitability/shifts` |
| Waterfall | `GET /fleet-project/yego-pro/profitability/input-mapping` |
| Data Quality | `GET /fleet-project/yego-pro/profitability/quality` |

## Banner obligatorio

> Historico financiero parcial: billing disponible para 1 semana.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `frontend/src/services/api.js` | 8 funciones API para profitability endpoints |
| `frontend/src/components/YegoProProfitabilityPage.jsx` | Componente principal con 8 tabs |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Entrada `fleet_yegopro_profitability` en tab "Fleet Project" |
| `frontend/src/App.jsx` | Ruta, constante TAB_FLEET_PROJECT, import, render section |
| `docs/fleet-project/yego-pro/PROFITABILITY_P2_UI.md` | Esta documentacion |

## Reglas de scope

- Sin simulador
- Sin IA
- Sin recomendaciones automaticas
- Sin calculos pesados en frontend
- Sin modificacion de historico real
- Muestra source/confidence cuando existe
- Manejo de missing_source sin loading infinito

## No tocado

- Drivers (ninguna ruta, componente o endpoint)
- Yango Loyalty
- Backend
- Scripts debug
- Omniview

## Hardening

Ver [PROFITABILITY_P2_1_QA_HARDENING.md](./PROFITABILITY_P2_1_QA_HARDENING.md) para:
- 14 bugs corregidos
- Empty states por tab
- Moneda corregida (S/)
- Sorting de tablas
- Banner dinamico
- Data Quality agrupada por REAL/DERIVED/ASSUMPTION/NOT_AVAILABLE
