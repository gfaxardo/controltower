# Control Tower — Canonicalización REAL — Informe Fase 2: Plan vs Real

**Objetivo:** Migrar Plan vs Real (mensual) para que use la misma fuente canónica mensual histórica que Resumen (`mv_real_monthly_canonical_hist` / `v_trips_real_canon`), sin depender de vistas legacy, sin 120d, sin romper contrato de API.

---

## 1. Qué se implementó

### Fuente REAL usada en Plan vs Real (canónica)

- **Origen:** `ops.v_trips_real_canon` (misma base que `mv_real_monthly_canonical_hist`).
- **Vistas nuevas (migración 109):**
  - **ops.v_real_universe_by_park_realkey_canon:** Real agregado por (country, city, park_id, real_tipo_servicio, period_date). Lógica city/country idéntica a 038; revenue = `SUM(ABS(comision_empresa_asociada))`; solo viajes `condicion = 'Completado'`.
  - **ops.v_plan_vs_real_realkey_canonical:** Mismo FULL OUTER JOIN que `v_plan_vs_real_realkey_final`, pero usando la real canónica anterior; resolución de `park_name` como 040.

### Backend

- **plan_vs_real_service.py:** Parámetro `use_canonical: bool = False`. Si `True`, lee de `ops.v_plan_vs_real_realkey_canonical`; si `False`, de `ops.v_plan_vs_real_realkey_final`. Afecta a `get_plan_vs_real_monthly()` y `get_alerts_monthly()`.
- **ops.py (router):** Query param `source=canonical` en `GET /ops/plan-vs-real/monthly` y `GET /ops/plan-vs-real/alerts`. Respuesta incluye `source_status`: `"canonical"` o `"legacy"`.

### Contrato de API

- **Sin cambios.** Mismo shape: country, city, park_id, park_name, real_tipo_servicio, period_date, trips_plan, trips_real, revenue_plan, revenue_real, variance_trips, variance_revenue, status_bucket, gap_trips, gap_revenue. Grano: (country, city, park_id, real_tipo_servicio, period_date).

### Validación de paridad

- **Script:** `backend/scripts/validate_plan_vs_real_parity.py`.
- Compara agregado por (month, country): sum(trips_real), sum(revenue_real) legacy vs canónico.
- Criterios: MATCH → OK; MINOR_DIFF → OK documentado; MAJOR_DIFF → STOP.
- Uso: `python -m scripts.validate_plan_vs_real_parity [--year 2025] [--country pe|co] [--out plan_vs_real_parity.csv]`.

---

## 2. Archivos modificados / creados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/109_plan_vs_real_canonical_views.py` | Nuevo: vistas `v_real_universe_by_park_realkey_canon`, `v_plan_vs_real_realkey_canonical` |
| `backend/app/services/plan_vs_real_service.py` | Constante `VIEW_REALKEY_CANONICAL`, parámetro `use_canonical` en ambas funciones |
| `backend/app/routers/ops.py` | Parámetro `source` en endpoints plan-vs-real/monthly y plan-vs-real/alerts; `source_status` en respuesta |
| `backend/scripts/validate_plan_vs_real_parity.py` | Nuevo: script de paridad legacy vs canónico |
| `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` | Actualizado: Plan vs Real mensual implementado, switch y script de paridad |
| `docs/REAL_CANONICAL_CHAIN.md` | Añadidos objetos Plan vs Real canónicos y sección "Plan vs Real mensual (real canónica)" |
| `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE2_REPORT.md` | Este informe |

---

## 3. Resultado de paridad

- **Estado:** Pendiente de ejecución. Ejecutar desde `backend`:
  ```bash
  python -m scripts.validate_plan_vs_real_parity --year 2025 --out outputs/plan_vs_real_parity_2025.csv
  python -m scripts.validate_plan_vs_real_parity --year 2025 --country pe
  python -m scripts.validate_plan_vs_real_parity --year 2025 --country co
  ```
- Tras ejecutar, rellenar aquí: DIAGNOSIS global / PE / CO (MATCH / MINOR_DIFF / MAJOR_DIFF) y adjuntar CSV como evidencia.

---

## 4. Activación controlada y fallback

- **Activación:** Por defecto el endpoint sigue en **legacy** (sin `source=canonical`). Para usar canónica: llamar con `?source=canonical`.
- **Fallback:** No pasar `source` o pasar cualquier valor distinto de `canonical` → legacy. No se rompe la UI si la canónica falla; la UI puede seguir sin el param hasta que paridad esté validada.
- **UI (Fase 4):** Cuando paridad sea MATCH o MINOR_DIFF documentado: actualizar frontend para llamar con `source=canonical` y mostrar badge/mensaje consistente con Resumen (canonical). No realizado en esta entrega; solo backend y script listos.

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
| Paridad validada | **Pendiente** (ejecutar `validate_plan_vs_real_parity.py`) |
| Veredicto | **PLAN_VS_REAL_IMPLEMENTATION_DONE** — Activación en UI y veredicto **PLAN_VS_REAL_CANONICALIZED** o **PLAN_VS_REAL_BLOCKED_BY_PARITY** tras ejecutar paridad y documentar resultado aquí. |

---

## 7. Riesgos abiertos

- **PE residual / diferencias por país:** Posibles diferencias menores (MINOR_DIFF) por redondeo o filtros de país; documentar en evidencia CSV si aparecen.
- **UI:** Hasta no activar `source=canonical` en frontend, la pantalla Plan vs Real sigue mostrando datos legacy; impacto en UI = ninguno hasta Fase 4.
