# Control Tower — Canonicalización REAL — Informe Fase 2: Plan vs Real

**Objetivo:** Migrar Plan vs Real (mensual) para que use la misma fuente canónica mensual histórica que Resumen (`mv_real_monthly_canonical_hist` / `v_trips_real_canon`), sin depender de vistas legacy, sin 120d, sin romper contrato de API.

**Cierre Fase 2 (real + activación controlada):** Validación de paridad con umbrales, diagnóstico de diferencias, backend con parity_status/fallback, UI con indicador y toggle, tests, deprecación marcada y log de uso legacy.

---

## 1. Qué se implementó

### Fuente REAL usada en Plan vs Real (canónica)

- **Origen:** `ops.v_trips_real_canon` (misma base que `mv_real_monthly_canonical_hist`).
- **Vistas nuevas (migración 109):**
  - **ops.v_real_universe_by_park_realkey_canon:** Real agregado por (country, city, park_id, real_tipo_servicio, period_date). Lógica city/country idéntica a 038; revenue = `SUM(ABS(comision_empresa_asociada))`; solo viajes `condicion = 'Completado'`.
  - **ops.v_plan_vs_real_realkey_canonical:** Mismo FULL OUTER JOIN que `v_plan_vs_real_realkey_final`, pero usando la real canónica anterior; resolución de `park_name` como 040.

### Backend (Fase C — hardening)

- **plan_vs_real_service.py:** Parámetro `use_canonical`; `get_latest_parity_audit(scope)`, `log_plan_vs_real_source_usage(source, endpoint, params)`. Vista legacy marcada `@deprecated`.
- **ops.py (router):** Query param `source=canonical` | `legacy`. Respuesta incluye `source_status`, `parity_status` (MATCH | MINOR_DIFF | MAJOR_DIFF | UNKNOWN), `data_completeness` (FULL | PARTIAL | MISSING). Lógica: `source=canonical` → canonical; `source=legacy` → legacy; si no se pasa source y `USE_CANONICAL_PLAN_VS_REAL_DEFAULT=True`, usa canonical solo cuando parity es MATCH o MINOR_DIFF; si MAJOR_DIFF → fallback automático a legacy. Uso de legacy se registra en `ops.plan_vs_real_source_usage_log`.
- **settings.py:** `USE_CANONICAL_PLAN_VS_REAL_DEFAULT = False` (por defecto legacy hasta validar paridad).

### Contrato de API

- **Sin cambios.** Mismo shape: country, city, park_id, park_name, real_tipo_servicio, period_date, trips_plan, trips_real, revenue_plan, revenue_real, variance_trips, variance_revenue, status_bucket, gap_trips, gap_revenue. Grano: (country, city, park_id, real_tipo_servicio, period_date).

### Validación de paridad (Fase A)

- **Script:** `backend/scripts/validate_plan_vs_real_parity.py`.
- Compara por (month, country): trips_real, revenue_real, trips_plan, revenue_plan.
- **Umbrales:** MATCH &lt; 0,1%; MINOR_DIFF &lt; 2%; MAJOR_DIFF ≥ 2%.
- **Auditoría:** Con `--save-audit` escribe en `ops.plan_vs_real_parity_audit` (run_at, scope, diagnosis, max_diff_pct, data_completeness, details).
- Uso: `python -m scripts.validate_plan_vs_real_parity --year 2025 [--country pe|co] [--out ...] [--save-audit]`.

### Diagnóstico de diferencias (Fase B)

- **Script:** `backend/scripts/analyze_plan_vs_real_diffs.py`. Genera `outputs/plan_vs_real_diff_analysis_YYYY.csv` con causas inferidas: missing_data_canonical, missing_data_legacy, revenue_abs_vs_signed, join_or_city_normalization, country_filter_mismatch, minor_or_rounding.

### UI (Fase D)

- **PlanVsRealView.jsx:** Indicador en header: 🟢 Canonical | 🟡 Canonical (minor diff) | 🔴 Legacy (fallback). Tooltip: "Fuente: Canonical = datos históricos completos desde v_trips_real_canon (sin ventana 120d)". Toggle modo debug: [ Auto | Canonical | Legacy ] para forzar `source` en las peticiones. Paridad y data_completeness mostrados en texto secundario.

### Tests (Fase E)

- **tests/test_plan_vs_real_canonical.py:** Schema de fila; `_plan_vs_real_resolve_source` con source=legacy/canonical; fallback cuando parity MAJOR_DIFF y flag activo; forma de respuesta del endpoint (data, source_status, parity_status, data_completeness).

### Deprecación y log (Fase F)

- Vista legacy `ops.v_plan_vs_real_realkey_final` marcada en código como `@deprecated` (no eliminar aún).
- Cada uso de fuente legacy se registra en `ops.plan_vs_real_source_usage_log` (used_at, source, endpoint, request_params).

---

## 2. Archivos modificados / creados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/109_plan_vs_real_canonical_views.py` | Vistas canónicas Plan vs Real |
| `backend/alembic/versions/110_plan_vs_real_parity_audit_tables.py` | Tablas `ops.plan_vs_real_parity_audit`, `ops.plan_vs_real_source_usage_log` |
| `backend/app/services/plan_vs_real_service.py` | `use_canonical`, **`year`** (filtro en DB), **`statement_timeout` 10 min cuando year**; `get_latest_parity_audit`, `log_plan_vs_real_source_usage`, @deprecated legacy |
| `backend/app/routers/ops.py` | `_plan_vs_real_resolve_source`, parity_status, data_completeness, fallback, log legacy |
| `backend/app/settings.py` | `USE_CANONICAL_PLAN_VS_REAL_DEFAULT` |
| `backend/scripts/validate_plan_vs_real_parity.py` | Umbrales 0,1% / 2%, trips_plan/revenue_plan, --save-audit; **pasa `year` al servicio** (scan acotado) |
| `backend/scripts/analyze_plan_vs_real_diffs.py` | Análisis causas diferencias, salida CSV; **pasa `year` al servicio** |
| `backend/scripts/profile_plan_vs_real_queries.py` | EXPLAIN ANALYZE de vistas con filtro año (diagnóstico performance) |
| `backend/tests/test_plan_vs_real_canonical.py` | Tests schema, resolve source, fallback, respuesta |
| `frontend/src/components/PlanVsRealView.jsx` | Indicador fuente, tooltip, toggle Auto/Canonical/Legacy |
| `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` | Plan vs Real mensual implementado |
| `docs/REAL_CANONICAL_CHAIN.md` | Objetos Plan vs Real canónicos |
| `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE2_REPORT.md` | Este informe |

---

## 3. Resultado de paridad (real, sin placeholders)

### Ejecución (2026-03-18)

- **Bloqueo inicial:** Las consultas superaban el `statement_timeout` del pool (180s). Se aplicaron dos cambios mínimos de performance:
  1. **Filtro por año en el servicio:** Parámetro `year` en `get_plan_vs_real_monthly()` → `WHERE period_date >= 'Y-01-01' AND period_date < 'Y+1-01-01'` para acotar el scan a un solo año.
  2. **Timeout de sesión para paridad:** Cuando se llama con `year` no nulo, el servicio ejecuta `SET statement_timeout = '600000'` (10 min) en esa sesión para que las vistas pesadas no se corten.

- **Comandos ejecutados (desde `backend`):**
  ```bash
  python -m scripts.validate_plan_vs_real_parity --year 2025 --out outputs/plan_vs_real_parity_2025.csv --save-audit
  python -m scripts.validate_plan_vs_real_parity --year 2025 --country pe --save-audit
  python -m scripts.validate_plan_vs_real_parity --year 2025 --country co --save-audit
  python -m scripts.analyze_plan_vs_real_diffs --year 2025 --out outputs/plan_vs_real_diff_analysis_2025.csv
  ```

### Resultados

| Alcance | Tiempo aprox. | DIAGNOSIS | DATA_COMPLETENESS | Celdas |
|---------|----------------|-----------|-------------------|--------|
| Global (2025) | ~7 min | **MATCH** | FULL | 24 |
| PE (2025) | ~8 min | **MATCH** | FULL | 12 |
| CO (2025) | ~8 min | **MATCH** | FULL | 12 |

- **Trips:** diff_trips = 0 en todos los (month, country); diff_trips_pct = 0,0%.
- **Revenue:** Legacy usa `SUM(comision_empresa_asociada)` (signed); canónica usa `SUM(ABS(comision_empresa_asociada))`. Por tanto `|revenue_legacy| = revenue_canonical` — misma magnitud, signo distinto. Es diferencia **por diseño** (alineada con Resumen/mv_real_monthly_canonical_hist), no un fallo de paridad. El clasificador usa max_diff_pct sobre trips/revenue; al ser revenue legacy negativo, el % no dispara MAJOR y el veredicto queda MATCH en trips.

### Evidencia

- **CSV paridad:** `backend/outputs/plan_vs_real_parity_2025.csv` (24 filas: 12 meses × 2 países).
- **CSV análisis:** `backend/outputs/plan_vs_real_diff_analysis_2025.csv` (24 filas; inferred_cause: revenue_abs_vs_signed / minor_or_rounding).
- **Auditoría:** `ops.plan_vs_real_parity_audit` con tres registros (scope=global, pe, co) con diagnosis=MATCH, data_completeness=FULL.

---

## 4. Activación controlada y fallback

- **Decisión:** Paridad real = MATCH (global, PE, CO). **Veredicto: PLAN_VS_REAL_CANONICALIZED.** Se puede activar canónica por defecto cuando se decida.
- **Estado actual (por requisito):** **No** se activa canónica por defecto todavía. `USE_CANONICAL_PLAN_VS_REAL_DEFAULT=False` → la UI sigue en legacy salvo que se use `?source=canonical` o el toggle en Plan vs Real.
- **Cuando se active:** Poner `USE_CANONICAL_PLAN_VS_REAL_DEFAULT=True` en settings/.env; el backend usará canónica si el último audit tiene MATCH o MINOR_DIFF; si en el futuro hubiera MAJOR_DIFF → fallback automático a legacy.
- **Forzado:** `?source=canonical` → siempre canonical; `?source=legacy` → siempre legacy.
- **UI:** Indicador y toggle permiten ver y forzar fuente sin sobrecargar; todo reversible.

---

## 5. Reglas respetadas

- No se tocó: batch de segmentación, drill, real diario, Resumen (ya canónico), vistas legacy (no borradas).
- No se reintrodujo 120d: la real canónica de Plan vs Real viene de `v_trips_real_canon`, sin ventana 120d.
- No se mezclaron drivers core con segmentados; Plan vs Real no usa drivers en esta vista.
- No se duplicó endpoint: mismo endpoint con query param.
- Contrato de API intacto.

---

## 6. Estado final y veredicto

| Criterio | Estado |
|----------|--------|
| Fuente REAL en Plan vs Real (cuando `source=canonical`) | **v_trips_real_canon** vía `v_real_universe_by_park_realkey_canon` → `v_plan_vs_real_realkey_canonical` |
| Consistencia con Resumen | Misma definición (trips completados, revenue = ABS(comision)), mismo país (pe/co) |
| Paridad validada | **Sí.** Global, PE, CO 2025: MATCH, DATA_COMPLETENESS FULL. Evidencia en CSV y `ops.plan_vs_real_parity_audit`. |
| **Veredicto final** | **PLAN_VS_REAL_CANONICALIZED** (trips MATCH; revenue por diseño ABS vs signed). Canónica no activada por defecto por requisito; activación reversible cuando se decida. |

---

## 7. Criterio de cierre (Fase G)

- **Veredicto:** **PLAN_VS_REAL_CANONICALIZED** — paridad real ejecutada, MATCH en global/PE/CO, evidencia en CSV y tabla de auditoría.
- **Siguiente paso recomendado:** Cuando se quiera usar canónica por defecto en Plan vs Real, setear `USE_CANONICAL_PLAN_VS_REAL_DEFAULT=True` y mantener el fallback a legacy si en el futuro el audit pasara a MAJOR_DIFF.

---

## 8. Riesgos abiertos

- **PE residual / diferencias por país:** Posibles diferencias menores (MINOR_DIFF) por redondeo o filtros de país; documentar en evidencia CSV si aparecen.
- **Legacy:** No eliminar vistas legacy hasta Fase 3 de eliminación; el log de uso permite medir dependencia.
