# Confidence Engine

Motor central que calcula **confianza por vista/dominio**: freshness, completeness, consistency, score 0–100 y trust_status. Data Trust delega aquí; no se inventa ok cuando falta señal.

---

## Ubicación

- **Backend:** `app/services/confidence_engine.py`
- **Función principal:** `get_confidence_status(view_name, filters) -> dict`

---

## Respuesta del engine

```python
{
  "source_of_truth": "ops.real_drill_dim_fact",
  "source_mode": "canonical",
  "freshness_status": "fresh | stale | missing | unknown",
  "completeness_status": "full | partial | missing | unknown",
  "consistency_status": "validated | minor_diff | major_diff | unknown",
  "confidence_score": 0-100,
  "trust_status": "ok | warning | blocked",
  "message": "texto corto",
  "last_update": "ISO timestamp o null",
  "details": { ... }
}
```

---

## Pesos del score (documentados)

| Dimensión    | Peso | Origen de la señal |
|-------------|------|--------------------|
| Freshness   | 0–40 | data_freshness_audit, get_supply_freshness, MAX(last_completed_ts), parity run_at |
| Completeness| 0–30 | `confidence_signals.get_completeness_status` por vista (full/partial/missing/unknown) |
| Consistency | 0–30 | `confidence_signals.get_consistency_status` por vista (validated/minor_diff/major_diff/unknown) |

**Total máximo:** 100.

---

## Umbrales trust_status

| Score       | trust_status |
|------------|--------------|
| 80 – 100   | **ok**       |
| 50 – 79    | **warning**  |
| 0 – 49     | **blocked**  |

Constantes en código: `THRESHOLD_OK = 80`, `THRESHOLD_WARNING = 50`.

**Regla crítica:** Si `completeness_status == "missing"` **o** `consistency_status == "major_diff"` → se **fuerza** `trust_status = "blocked"` independientemente del score.

---

## Señales reales (no inventadas)

Módulo **`app.services.confidence_signals`**: `get_completeness_status(view_name)` y `get_consistency_status(view_name)`.

### Freshness

- **real_lob:** `get_freshness_global_status(group="operational")` → sin_datos/falta_data/atrasada → stale o missing; fresca/parcial_esperada → fresh.
- **plan_vs_real:** Presencia de parity audit + run_at → fresh; sin audit → unknown.
- **supply:** `get_supply_freshness()` → status stale → stale; fresh → fresh.
- **driver_lifecycle:** `MAX(last_completed_ts)` en `ops.mv_driver_lifecycle_base`; &gt; 7 días → stale; sin data → missing.
- **resumen:** Combinación de real_lob + plan_vs_real (peor estado gana).
- **Otras vistas:** Sin señal específica → unknown (score 20).

### Completeness (reales por dominio)

- **real_lob:** Últimos 7 días: `COUNT(DISTINCT trip_date)` en `ops.mv_real_lob_day_v2` vs 7. 100% full, &gt;70% partial, &lt;70% missing.
- **resumen:** Últimos 12 meses: `COUNT(DISTINCT month_start)` en `ops.mv_real_monthly_canonical_hist`. Misma regla de ratio.
- **plan_vs_real:** `data_completeness` del parity audit (FULL/PARTIAL).
- **supply:** Últimas 4 semanas: `COUNT(DISTINCT week_start)` en `ops.mv_supply_segments_weekly`.
- **driver_lifecycle:** Últimas 8 semanas: `COUNT(DISTINCT week_start)` en `ops.mv_driver_lifecycle_weekly_kpis`.
- **Otras vistas:** unknown → 15 puntos.

### Consistency (reales por dominio)

- **plan_vs_real:** Parity audit: MATCH → validated, MINOR_DIFF → minor_diff, MAJOR_DIFF → major_diff.
- **real_lob:** Comparación hourly vs day: `SUM(completed_trips)` en `mv_real_lob_hour_v2` vs `mv_real_lob_day_v2` para ayer. diff_ratio &lt;1% validated, 1–5% minor_diff, &gt;5% major_diff.
- **resumen:** Peor de real_lob y plan_vs_real consistency.
- **supply:** Validado si hay filas recientes en `mv_supply_segments_weekly` (últimos 28 días).
- **driver_lifecycle:** Validado si hay filas en `mv_driver_lifecycle_base` con `last_completed_ts` en últimos 14 días.
- **Otras vistas:** unknown → 15 puntos.

Si **falta una señal** (ej. tabla no existe): **unknown**, no inventar ok; el score baja.

---

## Integración con Data Trust

- `get_data_trust_status(view_name)` (data_trust_service) llama a `get_confidence_status(view_name)` y mapea a `{ status, message, last_update }` para el contrato actual del badge.
- Si el engine falla, Data Trust devuelve **warning** y mensaje "Estado de data no disponible".

---

## API de observabilidad

- **GET /ops/data-confidence?view=&lt;vista&gt;** — Detalle completo del engine para esa vista.
- **GET /ops/data-confidence/summary** — Resumen de todas las vistas (view, source_of_truth, source_mode, trust_status, confidence_score, completeness_status, consistency_status, message).
- **GET /ops/data-trust?view=&lt;vista&gt;** — Contrato UI (status, message, last_update); respaldado por el engine.

---

## Cómo extender

1. **Nueva vista en el registry:** Ver `docs/SOURCE_OF_TRUTH_REGISTRY.md`.
2. **Nueva señal de freshness:** En `_signal_freshness()`, añadir rama para el `view_name` y devolver `(freshness_status, score_0_40, last_update)`.
3. **Nueva señal de completeness:** En `_signal_completeness()`, añadir lógica (periodo esperado, filas esperadas, etc.) y devolver `(completeness_status, score_0_30)`.
4. **Nueva señal de consistency:** En `_signal_consistency()`, si existe parity o validación cruzada, añadir rama y devolver `(consistency_status, score_0_30)`.
5. **Vista compuesta (como resumen):** Añadir rama en `get_confidence_status()` que llame al engine para las vistas que combina y agregue según reglas (ej. peor estado gana).

---

## Reglas

- No inventar **ok** cuando la señal es **unknown**.
- Fallo de consulta o excepción → respuesta con **trust_status warning** y score bajo (ej. 40).
- Pesos y umbrales deben permanecer documentados y estables para gobierno.
