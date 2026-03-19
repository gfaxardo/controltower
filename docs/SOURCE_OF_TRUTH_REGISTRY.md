# Source of Truth Registry

Registro central de **qué fuente manda** por dominio/vista en Control Tower. Ninguna vista nueva puede salir a UI sin estar registrada aquí.

---

## Ubicación

- **Backend:** `app/config/source_of_truth_registry.py`
- **Estructura:** `SOURCE_OF_TRUTH` (dict por dominio) con `primary`, `secondary`, `legacy`, `grain`, `canonical_chain`, `source_mode`, `notes`.

---

## Dominios registrados

| Dominio | Primary | Grano | source_mode | Notas |
|--------|---------|-------|-------------|--------|
| real_lob | ops.real_drill_dim_fact | daily | canonical | Drill y Real diario; cadena hourly-first. |
| resumen | ops.mv_real_monthly_canonical_hist | monthly | canonical | Resumen mensual canónico (KPICards). |
| plan_vs_real | ops.v_plan_vs_real_realkey_canonical | monthly | migrating | Canonical solo si parity MATCH/MINOR. |
| real_vs_projection | ops.v_real_metrics_monthly | monthly | source_incomplete | Real desde legacy; vista limitada. |
| supply | ops.mv_supply_segments_weekly | weekly | canonical | Supply conductores; dominio propio. |
| driver_lifecycle | ops.mv_driver_lifecycle_base | weekly | canonical | Ciclo de vida por park. |
| behavioral_alerts | ops.v_driver_behavior_alerts_weekly | weekly | under_review | En revisión. |
| leakage | ops.v_fleet_leakage_snapshot | weekly | under_review | En revisión. |
| real_margin_quality | ops.v_real_trip_fact_v2 | daily | canonical | Margin quality; cadena hourly-first. |

---

## Campos por entrada

- **primary:** Objeto (tabla/vista/MV) que manda hoy. Sin ambigüedad.
- **secondary:** Fuentes alternativas o derivadas; no reemplazan a primary salvo fallback documentado.
- **legacy:** Fuentes en desuso o paralelas; no borrar aún; deben estar marcadas.
- **grain:** daily | weekly | monthly (y excepciones).
- **canonical_chain:** true si la vista usa la cadena canónica definida para su dominio.
- **source_mode:** canonical | migrating | legacy | under_review | source_incomplete.
- **freshness_dataset:** Nombre en `ops.data_freshness_audit` si aplica (para el Confidence Engine).
- **parity_audit_applies:** true solo para plan_vs_real (paridad Plan vs Real).
- **notes:** Texto breve para gobierno y documentación.

---

## Reglas de gobierno

1. **Ninguna vista nueva** puede salir a UI sin estar en `SOURCE_OF_TRUTH`.
2. **Legacy** puede existir, pero debe estar en `legacy` y/o `source_mode` legacy/under_review/source_incomplete.
3. Si **primary falla** y se usa fallback, el Confidence Engine debe reflejarlo en `source_mode` y bajar el score.
4. **No dejar ambigüedad:** una sola primary por dominio; secondary/legacy explícitos.

---

## Cómo registrar una nueva vista

1. Añadir clave en `SOURCE_OF_TRUTH` (ej. `"nueva_vista"`).
2. Rellenar `primary`, `secondary`, `legacy`, `grain`, `canonical_chain`, `source_mode`, `parity_audit_applies`, `notes`.
3. Si la vista expone Data Trust en UI, añadirla a `DATA_TRUST_VIEWS` en el mismo módulo.
4. Implementar señales en el Confidence Engine para esa vista (freshness/completeness/consistency) o dejar unknown (score se reduce).
5. Documentar en este doc y en CONFIDENCE_ENGINE.md.

---

## API de observabilidad

- **GET /ops/data-confidence/registry** — Devuelve el registro completo y la lista de vistas registradas.
- **GET /ops/data-confidence?view=&lt;dominio&gt;** — Detalle del Confidence Engine por vista (incluye source_of_truth y source_mode).

---

## Referencias

- Auditoría: `docs/CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md`
- Motor de confianza: `docs/CONFIDENCE_ENGINE.md`
- Data Trust UI: `docs/DATA_TRUST_LAYER.md`
