# Contrato Plan vs Real REALKEY — Reporte de verificación

## Resumen

- **Vista oficial:** `ops.v_plan_vs_real_realkey_final`
- **Llave:** `(country, city, park_id, real_tipo_servicio, period_date)`
- **Sin LOB / sin homologación:** no se usan `plan_lob_name`, `lob_name`, `unmapped` ni tablas de homologación en este flujo.
- **park_name:** resuelto siempre por `parks` (PLAN_ONLY no debe quedar NULL).

---

## 1. Endpoints verificados

| Método | Path | Handler | Descripción |
|--------|------|---------|-------------|
| GET | `/ops/plan-vs-real/monthly` | `get_plan_vs_real_monthly_endpoint` (ops.py) | Comparación mensual Plan vs Real |
| GET | `/ops/plan-vs-real/alerts` | `get_plan_vs_real_alerts_endpoint` (ops.py) | Alertas (solo filas matched) |

**Parámetros:**

- **monthly:** `country`, `city`, `real_tipo_servicio`, `park_id`, `month` (YYYY-MM o YYYY-MM-DD)
- **alerts:** `country`, `month`, `alert_level` (CRITICO, MEDIO, OK)

---

## 2. Query / vista usada

| Endpoint | Origen |
|----------|--------|
| `/ops/plan-vs-real/monthly` | `ops.v_plan_vs_real_realkey_final` (SELECT explícito de columnas) |
| `/ops/plan-vs-real/alerts` | Misma vista; filtro `trips_plan IS NOT NULL AND trips_real IS NOT NULL`; cálculo de `gap_trips_pct`, `gap_revenue_pct`, `alert_level` en SQL |

**Servicio:** `backend/app/services/plan_vs_real_service.py`  
**Rutas:** `backend/app/routers/ops.py`

---

## 3. Tabla: DB vs API vs FE

### Vista DB: `ops.v_plan_vs_real_realkey_final`

| Columna DB | Tipo (conceptual) | API (monthly) | FE (comparación) |
|------------|-------------------|---------------|------------------|
| country | text | country | country |
| city | text | city | city |
| park_id | text | park_id | (no columna; filtro opcional) |
| park_name | text | park_name | park_name |
| real_tipo_servicio | text | real_tipo_servicio | real_tipo_servicio |
| period_date | date | month (YYYY-MM-DD) | month / period_date |
| trips_plan | numeric | trips_plan | trips_plan |
| trips_real | numeric | trips_real | trips_real |
| revenue_plan | numeric | revenue_plan | revenue_plan |
| revenue_real | numeric | revenue_real | revenue_real |
| variance_trips | numeric | (gap_trips = plan - real) | gap_trips |
| variance_revenue | numeric | (gap_revenue = plan - real) | gap_revenue |
| — | — | status_bucket (derivado) | status_bucket |

### API (alertas)

- **Origen:** misma vista, solo filas matched.
- **Keys:** country, month, city_norm_real (= city), lob_base (= real_tipo_servicio), segment (null), projected_trips, projected_revenue, trips_real_completed, revenue_real_yego, gap_trips, gap_revenue, gap_trips_pct, gap_revenue_pct, alert_level.
- **FE:** consume city_norm_real, lob_base (muestra como "Tipo servicio"), gap_*, alert_level.

### Mismatches corregidos en este PR

| Antes | Después |
|-------|---------|
| Backend leía `v_plan_vs_real_monthly_latest` (LOB: lob_base, segment, city_norm_real) | Backend lee `v_plan_vs_real_realkey_final` (real_tipo_servicio, park_name, city) |
| FE columnas LOB + Segment | FE columnas Park + Tipo servicio |
| Filtros API: lob_base, segment | Filtros API: real_tipo_servicio, park_id |
| park_name podía ser NULL en PLAN_ONLY | Validado en contract_check: null_count_plan_month debe ser 0 |

### Validaciones específicas

- **park_name en plan_month:** en el mes `MAX(period_date)` de `staging.plan_projection_realkey_raw`, ninguna fila con `park_name IS NULL` → si count > 0, contract_check FAIL.
- **matched_pct:** si `real_month < plan_month` → no se considera error (solo aviso "sin real aún"). Si `real_month >= plan_month` y matched_pct < 30% → warning, no obligatorio FAIL.
- **Sin columnas antiguas:** el script detecta referencias a `plan_lob_name`, `lob_name`, `unmapped`, `homologation` en rutas plan_vs_real y marca FAIL si las encuentra (excluyendo phase2c/LobUniverse y territory unmapped parks).

---

## 4. Cómo ejecutar

### 1) Script de verificación de contrato

Desde la raíz del repo (o desde `backend`):

```bash
# Con variables de entorno de DB (o .env en backend/)
python backend/scripts/contract_check_plan_vs_real_realkey.py
```

- **Exit 0:** contrato OK.
- **Exit 1:** vista ausente, columnas faltantes, park_name NULL en plan_month, o referencias prohibidas en código.

### 2) Tests (pytest)

Desde `backend`:

```bash
cd backend
pytest tests/test_contract_plan_vs_real_realkey.py -v
```

El test ejecuta el script anterior; si no hay conexión a DB, el test se omite (skip).

---

## 5. Archivos modificados / añadidos

- `backend/app/services/plan_vs_real_service.py` — usa `ops.v_plan_vs_real_realkey_final`, filtros realkey, cálculo de alertas desde la misma vista.
- `backend/app/routers/ops.py` — parámetros de `/plan-vs-real/monthly` y docstrings actualizados.
- `frontend/src/components/PlanVsRealView.jsx` — columnas Park, Tipo servicio; consumo de month/city/park_name/real_tipo_servicio/trips_plan/trips_real/gap_*; compatibilidad con keys antiguas donde aplique.
- `backend/scripts/contract_check_plan_vs_real_realkey.py` — verificación automática DB + código.
- `backend/tests/test_contract_plan_vs_real_realkey.py` — test CI que ejecuta el contract check.
- `docs/contracts/plan_vs_real_realkey_contract_report.md` — este reporte.

---

## 6. Resultado esperado al finalizar

- **Endpoints verificados:** GET `/ops/plan-vs-real/monthly`, GET `/ops/plan-vs-real/alerts`
- **Vistas verificadas:** `ops.v_plan_vs_real_realkey_final`
- **Resultado:** PASS si DB está al día, park_name no NULL en plan_month y no hay referencias prohibidas en plan_vs_real; en caso contrario FAIL.
- **Ejecución:**  
  1) `python backend/scripts/contract_check_plan_vs_real_realkey.py`  
  2) `cd backend && pytest tests/test_contract_plan_vs_real_realkey.py -v`

---

## 7. Salida esperada al ejecutar el script

```
=== Plan vs Real REALKEY contract check ===

View: ops.v_plan_vs_real_realkey_final

Result: PASS
```

O en caso de fallo:

```
Errors:
  - park_name NULL in plan_month 2025-02-01: count=3 (must be 0)
  - Forbidden 'plan_lob_name' in backend/app/services/plan_vs_real_service.py:45

Result: FAIL
```

- **Endpoints verificados:** `GET /ops/plan-vs-real/monthly`, `GET /ops/plan-vs-real/alerts`
- **Vistas verificadas:** `ops.v_plan_vs_real_realkey_final`
- **Resultado:** PASS (exit 0) o FAIL (exit 1)
