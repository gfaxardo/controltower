# OMNI-P0 — ALERTS / ROLLUP / MISMATCH AUDIT

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Estado:** AUDITORÍA COMPLETADA — PENDIENTE RESOLUCIÓN

---

## 1. ALERTAS DETECTADAS

### 1.1 Tipos de alerta en el sistema

| Tipo | Origen | Visible en |
|------|--------|-----------|
| **Rollup mismatch** | `omniview_matrix_integrity_service.py` | Trust banner, OperationalStatusBar |
| **Mismatch activo** | `MONTH_TRIPS_MISMATCH` y similares | Trust banner |
| **Freshness BLOCKED** | `omniview_freshness_governance_service.py` | FreshnessBanner, OmniviewFreshnessGovernanceCard |
| **Data loss** | CF-H1L.1/CF-H1L.5 | Serving integrity guard |
| **Falta data** | `business_slice_real_freshness_service.py` | OperationalStatusBar, FreshnessBanner |
| **Trust WARNING** | `matrixOperationalTrust` | DataTrustBadge |
| **Projection integrity broken** | Vs Proy | `projectionIntegrityBroken` flag |

---

## 2. ¿SON REALES LAS ALERTAS?

### 2.1 Rollup Mismatch

**Estado actual según OMNIVIEW_HARDENING_CLOSURE.md (línea 48)**:
> MONTH_TRIPS_MISMATCH resuelto (0 diff). No hay mismatches activos.

**Verificación**: Si los datos de day_fact/week_fact están perdidos, cualquier rollup mensual (que depende de day_fact o week_fact) va a mostrar mismatch contra month_fact (que sí tiene datos).

**Conclusión**: El mismatch **es real** cuando hay data loss en day_fact/week_fact. Cuando los datos están completos, el mismatch debería ser 0.

### 2.2 Freshness

**Evidencia de la auditoría de reconciliación** (UI_SERVING_RECONCILIATION_AUDIT.md):
- Backend: daily fact max date = Jun 2, 2026; lag = 2 días → WARNING
- Backend: weekly fact max = S23 (Jun 1-7); → OK si lag ≤7
- day_fact sin datos Mayo 26-31 → gap de 6 días → posible BLOCKED

**Conclusión**: Las alertas de freshness **son reales** porque reflejan el data loss real en day_fact/week_fact.

### 2.3 Trust

**Evidencia**: B1 fix (confidence.score) ya está aplicado. El trust score es numérico.

**Problema**: Si trust muestra "OK" pero hay data loss masivo en daily/weekly, hay una **contradicción** entre trust y datos reales.

---

## 3. ¿ESTÁN STALE?

| Alerta | ¿Stale? | Evidencia |
|--------|---------|-----------|
| MONTH_TRIPS_MISMATCH | **Posiblemente sí** — se declaró resuelto pero puede reactivarse con data loss | El closure dice 0 diff pero la situación de datos cambió |
| Freshness WARNING/BLOCKED | **No** — refleja estado actual de day_fact/week_fact | El data loss es actual (Mayo 26-31 sin datos) |
| Trust OK | **Posiblemente stale** — si se calculó cuando los datos estaban completos | La confianza debería bajar si faltan datos en daily/weekly |

---

## 4. ¿VIENEN DE EVOLUTION O VS PROY?

| Alerta | Origen |
|--------|--------|
| Freshness (GlobalFreshnessBanner) | **Compartido** — visible en ambos modos |
| OperationalStatusBar | **Solo Evolution** (`BusinessSliceOmniviewMatrix.jsx:1804-1812`) |
| sliceRealFreshnessBanner | **Solo Evolution** (L1813) |
| ProjectionIntegrityBanner | **Solo Vs Proy** (L1815-1817) |
| OmniviewFreshnessGovernanceCard | **Solo Vs Proy** (L1838-1840) |
| Trust badge (DataTrustBadge) | **Compartido** |
| matrixOperationalTrust | **Compartido** — misma API para ambos modos |

---

## 5. ¿CONTRADICEN TRUST OK?

### Escenario problemático:

```
Trust Badge: "OK — Confianza 87%"
Freshness: "WARNING — day_fact lag 2 días, gap Mayo 26-31"
Revenue daily: "—" (vacío)
Revenue weekly: "—" (vacío)
```

**Conclusión**: **FAIL**. Trust OK + Revenue vacío + Freshness WARNING = contradicción no explicada.

El usuario ve "Todo OK" en confianza pero los datos están incompletos. Esto genera desconfianza operativa.

### Causa probable:

El `matrixOperationalTrust` se calcula con datos de `month_fact` (que están completos), pero no pondera suficientemente el data loss en `day_fact`/`week_fact`. El algoritmo de trust debería degradar el score cuando hay gaps en granularidades finas, aunque la granularidad gruesa esté bien.

---

## 6. ¿DEBEN BLOQUEAR?

| Alerta | ¿Bloquea GO? | Justificación |
|--------|-------------|---------------|
| Freshness WARNING (day_fact lag) | **Sí** — hasta restaurar day_fact | Sin datos diarios, las decisiones operativas no son confiables |
| Freshness WARNING (week_fact lag) | **Sí** — hasta restaurar week_fact | Sin datos semanales, el análisis de tendencia es incompleto |
| Trust OK + contradicción | **Sí** — hasta reconciliar trust con datos reales | La confianza debe reflejar el estado real |
| MONTH_TRIPS_MISMATCH | **Solo si es >0** — verificar estado actual | Si realmente es 0 diff, no bloquea |

---

## 7. REMEDIATION REQUERIDA

### P0 — Antes de GO

1. **Restaurar day_fact y week_fact**: Refrescar datos para eliminar gaps.
2. **Re-ejecutar matrix integrity checks**: Verificar que MONTH_TRIPS_MISMATCH y otros rollups son 0.
3. **Verificar trust post-refresh**: El trust score debe reflejar datos completos (no "OK" con datos vacíos).
4. **Alinear freshness con datos**: Si day_fact/week_fact están completos → OK. Si no → WARNING/BLOCKED con remediation clara.

### P1 — Post-GO

5. **Alert fatigue prevention**: Si una alerta persiste >24h sin cambio, escalar visualmente.
6. **Trust ↔ Freshness cross-validation**: Si freshness != OK, trust no puede ser OK automáticamente.
7. **CF-H1L.9**: Refresh Family Atomicity para evitar data loss cross-grain.

---

## 8. VEREDICTO DE ALERTAS

| Alerta | Estado | Veredicto |
|--------|--------|-----------|
| Rollup mismatch | Posiblemente 0 (según closure) | **Verificar** — si >0, FAIL |
| Freshness day_fact | WARNING/BLOCKED activo | **FAIL** — datos incompletos |
| Freshness week_fact | WARNING/BLOCKED activo | **FAIL** — datos incompletos |
| Trust OK + Revenue vacío | Contradicción | **FAIL** — confianza inflada |
| MONTH_TRIPS_MISMATCH | Reportado como resuelto | **Verificar** — re-ejecutar |

---

**END OF ALERTS AUDIT**
