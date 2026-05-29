# Yego Pro Profitability — P0 Hotfix: KPIs + Shifts

**Date:** 2026-05-29
**Fix Type:** P0 Hotfix
**Related Audit:** `PROFITABILITY_LOADING_AUDIT.md`

---

## Bug #1 — Overview KPIs "No disponible"

### Bug detectado

Los KPIs principales del overview (utilidad neta semanal, revenue, margen %) mostraban "No disponible" permanentemente. El usuario percibía carga incompleta o página colgada.

### Causa

Doble mismatch entre backend y frontend:

1. **Nombres de key distintos**: El backend devuelve `profit_weekly`, `revenue_gross_30d`; el frontend buscaba `net_profit_weekly`, `revenue_weekly`, etc.

2. **Formato de valor diferente**: El backend devuelve `{value: -5509.9, source: "...", metric_type: "REAL", confidence: "HIGH"}` (objeto con metadata); el frontend usaba `num()` que solo acepta valores planos numéricos.

### Fix aplicado

**Archivo:** `frontend/src/components/YegoProProfitabilityPage.jsx`

1. Se agregó el helper `getMetricValue(obj, ...keys)`:
   - Itera sobre múltiples alias de key (ej: `profit_weekly`, `net_profit_weekly`, `net_profit`, `profit`, `weekly_profit`)
   - Soporta tanto valores planos (`-5509.9`) como objetos con `.value` (`{value: -5509.9, ...}`)
   - Retorna `null` si ningún key/alias produce un número válido

2. Se agregó `getMetricMeta(obj, key)` para extracción de source/confidence cuando sea necesario.

3. Se actualizaron los siguientes llamados:

| Componente | Antes | Después |
|---|---|---|
| `DiagnosticHeader:netWeekly` | `extractNum(ovFlat, 'net_profit_weekly', ...)` | `getMetricValue(ovFlat, 'profit_weekly', 'net_profit_weekly', ...)` |
| `DiagnosticHeader:revWeekly` | `extractNum(ovFlat, 'revenue_weekly', ...)` | `getMetricValue(ovFlat, 'revenue_gross_30d', 'revenue_weekly', ...)` |
| `DiagnosticHeader:marginPct` | `extractNum(ovFlat, 'margin_pct', ...)` | `getMetricValue(ovFlat, 'margin_pct', ...)` |
| `UtilizationDiagnostics:totalDrivers` | `num(ovFlat.total_drivers)` | `getMetricValue(ovFlat, 'active_drivers', ...)` |
| `UtilizationDiagnostics:totalTrips` | `num(ovFlat.trips)` | `getMetricValue(ovFlat, 'trips_completed_30d', ...)` |
| `UtilizationDiagnostics:totalRevenue` | `num(ovFlat.revenue)` | `getMetricValue(ovFlat, 'revenue_gross_30d', ...)` |
| `UtilizationDiagnostics:totalHours` | `num(ovFlat.hours)` | `getMetricValue(ovFlat, 'work_hours_weekly', ...)` |
| `KeyFindings:totalTrips` | `num(ovFlat.trips)` | `getMetricValue(ovFlat, 'trips_completed_30d', ...)` |
| `KeyFindings:totalD` | `num(ovFlat.total_drivers)` | `getMetricValue(ovFlat, 'active_drivers', ...)` |

### Verificación

```powershell
# Simulación de getMetricValue con respuesta real del backend
profit_weekly: S/-5509.9    ✓
revenue_gross_30d: S/142474  ✓
margin_pct: -14.0%           ✓
trips_completed_30d: 13951   ✓
active_drivers: 26           ✓
work_hours_weekly: 1361.46   ✓
```

---

## Bug #2 — /shifts 500 Error

### Bug detectado

El endpoint `/fleet-project/yego-pro/profitability/shifts` retornaba HTTP 500 consistentemente. La pestaña "Shifts" mostraba un error genérico.

### Causa

Mismatch de nombre de parámetro entre router y service:

- **Router** (`yego_pro_profitability.py:104`): `get_shifts(park_id=park_id, weeks=weeks)`
- **Service** (`yego_pro_profitability_service.py:414`): `def get_shifts(park_id=PARK_ID, days=35)`

El router pasaba `weeks` como keyword argument, pero el service solo acepta `days`. Esto producía `TypeError: get_shifts() got an unexpected keyword argument 'weeks'`.

### Fix aplicado

**Archivo:** `backend/app/routers/yego_pro_profitability.py`

Línea 104 — Cambio único:

```python
# Antes:
return get_shifts(park_id=park_id, weeks=weeks)

# Después:
return get_shifts(park_id=park_id, days=weeks * 7)
```

`weeks=8` (default) → `days=56`. El service multiplica `days * 4` para el LIMIT de la query.

### Verificación

```
GET /fleet-project/yego-pro/profitability/shifts?park_id=...&weeks=8
→ 200 OK, 224 shift records, 3555ms
Source: module_calculated_shifts (native shift types from operational system)
```

---

## Archivos tocados

| Archivo | Cambio | Scope |
|---|---|---|
| `frontend/src/components/YegoProProfitabilityPage.jsx` | +12 líneas: `getMetricValue`, `getMetricMeta`; actualización de 9 llamados | Bug #1 |
| `backend/app/routers/yego_pro_profitability.py` | 1 línea: `weeks=weeks` → `days=weeks * 7` | Bug #2 |

---

## QA

| Check | Result |
|---|---|
| Backend compile (`py_compile`) | PASS |
| Frontend build (`npm run build`) | PASS |
| `/overview` 200 | PASS |
| `/weekly` 200 | PASS |
| `/daily` 200 | PASS |
| `/drivers` 200 | PASS |
| `/vehicles` 200 | PASS |
| `/shifts` 200 | PASS |
| `/input-mapping` 200 | PASS |
| `/quality` 200 | PASS |
| `/root-cause` 200 | PASS |
| KPIs overview visibles | YES |
| Shifts carga sin error | YES |
| Contaminación de scope | NO |
| NaN/undefined rendering | NO |
| Loading infinito | NO |

---

## Veredicto

| Check | Result |
|---|---|
| KPIs overview visibles | **YES** |
| /shifts 200 | **YES** |
| Build backend | **PASS** |
| Build frontend | **PASS** |
| Contaminación de scope | **NO** |
| **GO/NO-GO para prueba humana** | **GO** |
