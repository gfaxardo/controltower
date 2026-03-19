# Data Trust Layer — Capa de confianza de data (minimalista)

Capa mínima para mostrar **estado de confianza de la data** en las vistas principales, sin rediseñar la UI ni añadir complejidad visual.

---

## 1. Estados

| Estado   | Significado breve | Uso en UI        |
|----------|-------------------|------------------|
| **ok**     | Data fresca, fuente canónica activa, sin errores recientes | Badge verde, texto corto (ej. "Data validada") |
| **warning** | Data parcialmente fresca, mezcla de fuentes o auditoría incompleta | Badge amarillo (ej. "Data parcial") |
| **blocked** | Errores de carga, falta de data crítica, paridad no validada | Badge rojo (ej. "Data no confiable") |

Si el backend no puede calcular el estado (timeout, error), se devuelve **warning** con mensaje "Estado de data no disponible".

---

## 2. Cómo se calcula

**Data Trust delega en el Confidence Engine central.**  
Backend: `app.services.data_trust_service.get_data_trust_status(view_name)` llama a `app.services.confidence_engine.get_confidence_status(view_name)` y mapea el resultado a `{ status, message, last_update }` para el contrato del badge.

El motor central usa:
- **Registry:** `app.config.source_of_truth_registry` — qué fuente manda por vista.
- **Señales:** freshness (data_freshness_audit, get_supply_freshness, MAX(last_completed_ts)), completeness (parity data_completeness cuando aplica), consistency (parity diagnosis MATCH/MINOR/MAJOR).
- **Score:** freshness 0–40, completeness 0–30, consistency 0–30; total 0–100 → 80+ ok, 50–79 warning, &lt;50 blocked.

Comportamiento por vista (resumido): **plan_vs_real** → paridad; **real_lob** → freshness operativo; **driver_lifecycle** → freshness mv_driver_lifecycle_base; **supply** → get_supply_freshness; **resumen** → combinación real_lob + plan_vs_real. Si falta señal → unknown, no se inventa ok; el score baja.

Cualquier excepción → respuesta **warning** con mensaje "Estado de data no disponible". Detalle completo: `docs/CONFIDENCE_ENGINE.md` y `docs/SOURCE_OF_TRUTH_REGISTRY.md`.

---

## 3. API

**GET /ops/data-trust?view=**`plan_vs_real` | `real_lob` | `driver_lifecycle` | `supply` | `resumen`

Respuesta:

```json
{
  "data_trust": {
    "status": "ok",
    "message": "Data validada",
    "last_update": "2026-03-18T12:00:00"
  }
}
```

- `status`: `ok` | `warning` | `blocked`
- `message`: texto corto para el badge
- `last_update`: opcional; ISO timestamp de última actualización relevante

Los contratos existentes de los endpoints de cada vista **no se modifican**; la UI obtiene el estado de confianza con esta llamada aparte.

---

## 4. Cómo interpretarlo

- **ok:** El usuario puede confiar en que la data mostrada está validada y alineada con la fuente canónica (cuando aplica).
- **warning:** La data puede estar en transición, parcialmente actualizada o el estado no pudo comprobarse; usar con precaución.
- **blocked:** No usar la data para decisiones críticas hasta resolver errores o paridad.

En la UI solo se muestra un badge/pill con color y texto corto; el tooltip puede incluir `message` y `last_update` para más detalle.

---

## 5. Dónde se usa

- **Resumen (Performance > Resumen):** Header de ExecutiveSnapshotView; estado combinado Real LOB + Plan vs Real.
- **Plan vs Real:** Header de la vista mensual (badge junto al título).
- **Real LOB:** Header de la vista drill y de la vista diaria.
- **Driver Lifecycle:** Junto al título "Driver Lifecycle (por Park)".
- **Supply (Driver Supply Dynamics):** Junto al título "Driver Supply Dynamics".

Mismo componente en todas: `DataTrustBadge` (status, message, last_update). Menos del 10% del header; sin modales ni alertas intrusivas.

---

## 6. Cómo extenderlo

1. **Nueva vista:** Registrar el dominio en `app.config.source_of_truth_registry.SOURCE_OF_TRUTH` y, si expone badge, en `DATA_TRUST_VIEWS`. Añadir señales en `app.services.confidence_engine` (freshness/completeness/consistency) para esa vista. El Data Trust seguirá devolviendo status a partir del score del engine.
2. **Observabilidad:** Usar `GET /ops/data-confidence?view=<vista>` para detalle (source_of_truth, score, freshness/completeness/consistency). Opcionalmente el frontend puede llamar este endpoint y pasar `source_of_truth`, `confidence_score`, `freshness_status`, etc. al `DataTrustBadge` para un tooltip enriquecido.
3. **Frontend:** Llamar `getDataTrustStatus('<view_name>')` al montar y renderizar `<DataTrustBadge status={...} message={...} last_update={...} />`. Si se desea tooltip con fuente y score, llamar también `GET /ops/data-confidence?view=...` y pasar las props opcionales al badge.

---

## 7. Fallback

Si la llamada a `GET /ops/data-trust` falla (red, 5xx, timeout):

- La UI muestra **warning** con mensaje "Estado de data no disponible".
- El componente `DataTrustBadge` acepta `status: "warning"` por defecto si no recibe datos.

No se bloquea la pantalla; la vista sigue siendo usable.

---

## 8. Vista Resumen: reglas de combinación

La vista **resumen** no tiene una fuente única; agrega el estado de **real_lob** y **plan_vs_real**:

| real_lob | plan_vs_real | resumen   |
|----------|--------------|-----------|
| ok       | ok           | **ok**    |
| ok       | warning      | **warning** |
| ok       | blocked      | **blocked** |
| warning  | ok           | **warning** |
| warning  | warning      | **warning** |
| warning  | blocked      | **blocked** |
| blocked  | *            | **blocked** |

En resumen: **solo OK si ambos están OK**. Cualquier BLOCKED domina; si no hay BLOCKED, cualquier WARNING resulta en WARNING.

**Ejemplos de interpretación:**

- "Data validada (Real LOB + Plan vs Real)" → Resumen y Plan vs Real están alineados y la paridad ha pasado.
- "Resumen: datos parciales (Real LOB o Plan vs Real en transición)" → Al menos una de las dos fuentes está en warning (frescura o paridad pendiente).
- "Resumen: datos no confiables (Real LOB o Plan vs Real con paridad bloqueada)" → Paridad con MAJOR_DIFF o problema grave en Real LOB; no tomar decisiones críticas con estos datos.
