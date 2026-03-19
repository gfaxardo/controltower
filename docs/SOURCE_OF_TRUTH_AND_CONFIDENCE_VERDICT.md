# Source of Truth Registry + Confidence Engine — Veredicto de implementación

**Objetivo:** Definir quién manda por dominio, cómo se evalúa la confianza y cómo se expone, sin rediseñar UI ni romper contratos.

---

## Entregables realizados

### 1. Source of Truth Registry

- **Archivo:** `backend/app/config/source_of_truth_registry.py`
- **Contenido:** `SOURCE_OF_TRUTH` con 9 dominios: real_lob, resumen, plan_vs_real, real_vs_projection, supply, driver_lifecycle, behavioral_alerts, leakage, real_margin_quality.
- Cada entrada: primary, secondary, legacy, grain, canonical_chain, source_mode, parity_audit_applies, notes.
- `DATA_TRUST_VIEWS` = vistas que exponen el badge (real_lob, resumen, plan_vs_real, supply, driver_lifecycle).
- Funciones: `get_registry_entry`, `get_primary_source`, `get_source_mode`.

### 2. Confidence Engine

- **Archivo:** `backend/app/services/confidence_engine.py`
- **Función:** `get_confidence_status(view_name, filters)` → source_of_truth, source_mode, freshness_status, completeness_status, consistency_status, confidence_score (0–100), trust_status (ok|warning|blocked), message, last_update, details (incl. completeness y consistency con coverage_ratio / diff_ratio).
- **Pesos:** freshness 0–40, completeness 0–30, consistency 0–30. Umbrales: 80+ ok, 50–79 warning, &lt;50 blocked.
- **Regla crítica:** Si completeness = missing **o** consistency = major_diff → **forzar trust_status = blocked**.
- **Señales reales:** Freshness como antes; **completeness y consistency** vía `app.services.confidence_signals` (get_completeness_status, get_consistency_status) por dominio: real_lob (días/semana, hour vs day), resumen (meses), plan_vs_real (parity), supply (semanas), driver_lifecycle (semanas y base reciente). Si falta señal → unknown, no se inventa ok.
- **Resumen:** vista compuesta real_lob + plan_vs_real; peor estado gana; score = mínimo de ambos; completeness/consistency = peor de ambos.
- **Logging:** `[CONFIDENCE_ENGINE] view=... completeness=... consistency=...` cuando completeness ≠ full o consistency ∉ {validated, minor_diff} (no saturar).
- **Resumen para observabilidad:** `get_confidence_summary()` con completeness_status y consistency_status por vista.

### 3. Integración con Data Trust

- **Archivo:** `backend/app/services/data_trust_service.py`
- **Cambio:** `get_data_trust_status(view_name)` delega en `get_confidence_status(view_name)` y mapea a `{ status, message, last_update }`.
- Contrato existente de API y UI se mantiene; el backend responde desde el motor central.

### 4. API de observabilidad

- **GET /ops/data-confidence?view=&lt;vista&gt;** — Detalle del Confidence Engine por vista.
- **GET /ops/data-confidence/registry** — Registro completo y lista de vistas registradas.
- **GET /ops/data-confidence/summary** — Resumen de confianza de todas las vistas (view, source_of_truth, source_mode, trust_status, confidence_score, message).

### 5. UI (minimalista)

- **DataTrustBadge:** Props opcionales para tooltip enriquecido: source_of_truth, confidence_score, freshness_status, completeness_status, consistency_status. Sin cambio obligatorio; las vistas siguen usando getDataTrustStatus y status/message/last_update.
- Aplicado en: Resumen, Real LOB, Plan vs Real, Supply, Driver Lifecycle (ya existente). under_review / source_incomplete se mantienen donde corresponda (real-source-status).

### 6. Documentación

- **Creados:** `docs/SOURCE_OF_TRUTH_REGISTRY.md`, `docs/CONFIDENCE_ENGINE.md`, `docs/SOURCE_OF_TRUTH_AND_CONFIDENCE_VERDICT.md`.
- **Actualizados:** `docs/DATA_TRUST_LAYER.md` (delegación al engine, cómo extender), `docs/CONTROL_TOWER_REAL_GOVERNANCE_STATUS.md` (sección 7.1 Registry y Engine), `docs/REAL_CANONICAL_CHAIN.md`, `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` (referencias al registry y engine).

### 7. Señales de completeness y consistency (cierre engine)

- **Archivo:** `backend/app/services/confidence_signals.py`
- **Funciones:** `get_completeness_status(view_name)` → status (full|partial|missing|unknown), coverage_ratio, expected_periods, actual_periods. `get_consistency_status(view_name)` → status (validated|minor_diff|major_diff|unknown), diff_ratio.
- **Vistas con completeness real:** real_lob, resumen, plan_vs_real, supply, driver_lifecycle.
- **Vistas con consistency real:** plan_vs_real (parity), real_lob (hour vs day), resumen (composición), supply (data reciente), driver_lifecycle (base reciente).

### 8. Reglas de gobierno (documentadas)

- Ninguna vista nueva puede salir a UI sin estar en SOURCE_OF_TRUTH.
- Ninguna vista nueva sin confidence engine mínimo (señales o unknown explícito).
- Legacy puede existir pero debe estar marcado.
- Si primary falla y se usa fallback, debe reflejarse en source_mode y bajar el score.
- No mostrar ok si completeness o consistency son unknown graves (el score baja y trust_status puede ser warning).

---

## Lista de vistas y source_of_truth

| Vista | source_of_truth (primary) | source_mode | completeness real | consistency real |
|-------|---------------------------|-------------|-------------------|------------------|
| real_lob | ops.real_drill_dim_fact | canonical | sí (7 días) | sí (hour vs day) |
| resumen | ops.mv_real_monthly_canonical_hist | canonical | sí (12 meses) | sí (composición) |
| plan_vs_real | ops.v_plan_vs_real_realkey_canonical | migrating | sí (parity) | sí (parity) |
| real_vs_projection | ops.v_real_metrics_monthly | source_incomplete | no (unknown) | no (unknown) |
| supply | ops.mv_supply_segments_weekly | canonical | sí (4 semanas) | sí (data reciente) |
| driver_lifecycle | ops.mv_driver_lifecycle_base | canonical | sí (8 semanas) | sí (base reciente) |
| behavioral_alerts | ops.v_driver_behavior_alerts_weekly | under_review | no | no |
| leakage | ops.v_fleet_leakage_snapshot | under_review | no | no |
| real_margin_quality | ops.v_real_trip_fact_v2 | canonical | no | no |

---

## Veredicto final

- **SOURCE_OF_TRUTH_REGISTRY_APPLIED** — Registro implementado y cubre las vistas principales; primary/secondary/legacy y source_mode definidos por dominio.
- **CONFIDENCE_ENGINE_NEAR_PRODUCTION** — Motor con señales **reales** de completeness y consistency por dominio:
  - **Completeness:** real_lob (7 días distinct en mv_real_lob_day_v2), resumen (12 meses en mv_real_monthly_canonical_hist), plan_vs_real (parity data_completeness), supply (4 semanas en mv_supply_segments_weekly), driver_lifecycle (8 semanas en mv_driver_lifecycle_weekly_kpis). Ratio 100% → full, &gt;70% → partial, &lt;70% → missing.
  - **Consistency:** plan_vs_real (parity diagnosis), real_lob (hour vs day SUM(completed_trips) para ayer; &lt;1% validated, 1–5% minor_diff, &gt;5% major_diff), resumen (peor de real_lob + plan_vs_real), supply/driver_lifecycle (validado si hay data reciente).
  - **Forzar blocked** cuando completeness = missing o consistency = major_diff.
  - **Logging** cuando completeness &lt; full o consistency ≠ validated/minor_diff.
  - Vistas sin señal (behavioral_alerts, leakage, real_vs_projection) siguen en unknown; el sistema no inventa ok.
- **NOT_CLOSED** — Legacy no borrado; sistema reversible. Cierre total implicaría señales para vistas under_review y deprecación controlada según plan.

**Regla final cumplida:** El sistema castiga data incompleta (missing → blocked) e inconsistente (major_diff → blocked); incomoda cuando la data está mal.
