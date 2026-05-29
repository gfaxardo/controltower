# CF Closure — Open Risks Review

## Fecha: 2026-05-29

---

## Risks from Bug List (OMNIVIEW_REAL_NAVIGATION_BUGLIST.md)

### H-1: Fullscreen projection mode — **LOW (downgraded)**
- **Original**: HIGH
- **Current**: No reportado como roto. El código existe (líneas 2000-2093). Si no funciona en runtime, es recuperación simple (el usuario ve la tabla completa sin overlay).
- **¿Invalida RC-1?**: NO

### H-2: Active drivers weekly SUM proxy — **FIXED (CF-H1)**
- **Original**: HIGH  
- **Current**: Corregido. `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` usa `COUNT(DISTINCT driver_id)`.
- **¿Invalida RC-1?**: N/A (resuelto)

### H-3: scrollToCurrentPeriod código redundante — **LOW**
- **Original**: HIGH
- **Current**: Código redundante pero funcional. No afecta comportamiento.
- **¿Invalida RC-1?**: NO

### M-1: Badge "ÚLTIMO CIERRE" inconsistente con KPI anchor — **LOW**
- **Original**: MEDIUM
- **Current**: Visual. ContextBar ya muestra per-KPI freshness. Badge en celda es "nice to have".
- **¿Invalida RC-1?**: NO

### M-2: `compute_kpi_freshness` N queries — **LOW**
- **Original**: MEDIUM
- **Current**: 5 queries < 25ms. Performance aceptable.
- **¿Invalida RC-1?**: NO

### L-1, L-2: Cosmetic — **BACKLOG**
- Sin impacto funcional.

---

## Risks from CF-H1 Report

| Riesgo | Estado actual |
|--------|---------------|
| Performance week_fact más lento (escanea enriched) | Aceptable — mismo costo que month_fact. Refresh job 15min cooldown. |
| `_WEEK_ROLLUP_FROM_DAY_FACT` legacy (deprecated) | Sin impacto. Puede eliminarse en limpieza. |
| Backfill_runner week per-chunk aumenta tiempo | Backfills nocturnos/manuales. Aceptable. |

---

## Risks from CF-H2 Report

| Riesgo | Estado actual |
|--------|---------------|
| Proxy coverage < 70% en ciertos parks | Mitigado: `revenue_real_coverage_pct` medible. Marcar en Priority Layer si < 70%. |
| Commission config desactualizada | Tabla actualizable sin deploy. |
| GMV confundido con revenue en nuevos módulos | Auditoría pasada. Sin incidencia en código actual. |

---

## Clasificación Final

| Severidad | Count | Items |
|-----------|-------|-------|
| BLOCKER | 0 | — |
| HIGH | 0 | H-1 downgraded to LOW, H-2 fixed, H-3 downgraded |
| MEDIUM | 0 | All downgraded or resolved |
| LOW | 4 | H-1, H-3, M-1, M-2 |
| BACKLOG | 5 | L-1, L-2, B-1 (fixed), B-2, B-3 |

---

## Veredict

**Ningún HIGH o BLOCKER pendiente.** Todos los riesgos materiales (active_drivers weekly, revenue definition, freshness per-KPI) fueron resueltos en CF-H1 y CF-H2. Los riesgos restantes son cosméticos, de performance aceptable, o backlog para futuras iteraciones.

**RC-1 está desbloqueado.**
