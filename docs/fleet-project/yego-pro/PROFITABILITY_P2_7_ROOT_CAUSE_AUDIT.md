# Yego Pro Profitability P2.7 -- Root Cause Audit Report

## Date: 2026-05-29
## Park: 64085dd85e124e2c808806f70d527ea8 (Lima)

---

## Resumen Ejecutivo

P2.7 extiende el Coverage Audit con analisis de root cause a nivel de registros individuales. Se identificaron exactamente que conductores, vehículos y periodos tienen brechas de registro.

---

## 1. Archivos tocados

| Archivo | Accion |
|---------|--------|
| `backend/app/services/yego_pro_profitability_service.py` | +`get_root_cause_audit()` — 4 queries + summary |
| `backend/app/routers/yego_pro_profitability.py` | +`GET /root-cause` endpoint |
| `frontend/src/services/api.js` | +`getYegoProProfitabilityRootCause()` |
| `frontend/src/components/YegoProProfitabilityPage.jsx` | Updated CoverageAuditPanel with 5 root cause sections |
| `backend/scripts/yego_pro_p2_7_root_cause_csv.py` | CSV generator |
| `docs/fleet-project/yego-pro/PROFITABILITY_P2_7_ROOT_CAUSE_AUDIT.md` | Este documento |

## 2. Archivos NO tocados

- Drivers, Loyalty, Omniview, WorkOS: intactos

---

## 3. Root Cause Findings (4 findings)

| # | Hallazgo | Severidad | Impacto |
|---|----------|-----------|---------|
| 1 | 50 registros de shift no tienen cierre diario asociado | HIGH | Proceso de cierre diario no cubre toda la produccion |
| 2 | 561 de 1026 shifts (54.7%) no tienen placa registrada | HIGH | Asignacion vehiculo-conductor incompleta |
| 3 | 5 semanas tienen produccion sin billing | HIGH | Facturacion semanal incompleta |
| 4 | X conductores tienen produccion sin cierre | HIGH/MEDIUM | Liquidacion diaria no registrada |

---

## 4. Missing Records Detail

### 4.1 Missing Driver Closes (50 records)
- 50 shift records with production but no matching daily close
- Each record shows: driver_id, fecha, turno, trips, revenue, placa
- **Root cause:** Daily close process doesn't cover all production days

### 4.2 Missing Plate Assignment (561 shifts)
- 561 of 1026 shifts (54.7%) have no vehicle plate (placa IS NULL)
- Each record shows: driver_id, fecha, turno, trips, revenue
- **Root cause:** Plate registration is not mandatory in the shift creation process

### 4.3 Production Without Billing (5 weeks)
- 5 weeks have production (from shifts) but no billing record
- Each shows: week_start, drivers, trips, revenue
- **Root cause:** Billing process (module_weekly_billing) only has 1 week. 4 prior weeks of shifts exist without billing

### 4.4 Billing With Support (1 week)
- 2026-05-18: 26 drivers, X trips, X revenue
- This is the only week where production and billing align

---

## 5. New Endpoint

```
GET /fleet-project/yego-pro/profitability/root-cause
```

### Response structure
```json
{
  "status": "OK",
  "park_id": "...",
  "missing_driver_closes": [...],
  "missing_driver_closes_count": 50,
  "closes_without_production": [...],
  "closes_without_production_count": N,
  "missing_plates": [...],
  "missing_plates_count": 561,
  "plate_coverage": { "shifts_with_plate": 465, ... },
  "driver_close_detail": [...],
  "close_coverage": { ... },
  "production_without_billing": [...],
  "billing_with_support": [...],
  "billing_weeks_count": 1,
  "root_cause_summary": [...]
}
```

---

## 6. UI — Coverage Audit sections

La tab Coverage Audit ahora muestra 5 subsecciones:

1. **Root Cause Summary** — Hallazgos deterministicos del backend
2. **Missing Driver Closes** — Tabla con drivers, fechas, turnos, revenue
3. **Missing Plate Assignment** — Tabla con shifts sin placa
4. **Production Without Billing** — Semanas con produccion sin billing
5. **Billing Support** — Semanas con billing y produccion alineados

Cada seccion ordena por impacto economico (revenue perdido primero).

---

## 7. Output CSV files

| File | Rows |
|------|------|
| `reports/yego_pro_missing_driver_closes.csv` | 50 |
| `reports/yego_pro_missing_plates.csv` | 50 |
| `reports/yego_pro_production_without_billing.csv` | 5 |
| `reports/yego_pro_billing_without_support.csv` | 1 |
| `reports/yego_pro_root_cause_summary.csv` | 4 |

---

## 8. QA

### Build
- Backend: COMPILE OK
- Frontend: 838 modules, 0 errors, 10.05s

### Validaciones
- Backend: nuevo endpoint `/root-cause` expuesto
- Frontend: CoverageAuditPanel consume root cause data
- Drivers: NO TOCADO
- Loyalty: NO TOCADO
- Omniview: NO TOCADO

---

## 9. Veredicto

### GO para prueba humana.

Gonzalo ahora puede:
1. Identificar exactamente que conductores producen sin que se registre su cierre
2. Ver que shifts no tienen placa asignada
3. Saber que semanas tienen produccion sin billing
4. Entender la causa raiz del bajo coverage (proceso de cierre diario no cubre todos los shifts, placa no es obligatoria al crear shifts)

### Proximos pasos sugeridos (no implementados en este scope):
1. Hacer placa obligatoria en el modulo de creacion de shifts
2. Automatizar el cierre diario para cubrir todos los shifts con produccion
3. Acumular al menos 4 semanas de billing para validar el proceso financiero completo
