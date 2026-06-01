# UX-H3 — COMPACT OPERATIONAL HEADER REPORT

**Motor:** Control Foundation UX Hardening  
**Fecha:** 2026-05-31  
**Estado:** COMPLETADO  
**Build:** PASS  

---

## 1. Estado: GO

El header se compactó sin perder governance crítica. El KPI selector ahora es inline y la matriz se siente más protagonista.

---

## 2. Altura Antes / Después

| Zona | Antes | Después | Delta |
|------|-------|---------|-------|
| KPI Focus | Card independiente 80px | Inline en controls row 0px | -80px |
| Filter row padding | `py-1.5 gap-y-1.5` (55-100px) | `py-1 gap-y-1` (44-80px) | -10-20px |
| Controls row | `px-4 py-2 gap-4` (36-100px) | `px-3 py-1.5 gap-3` (30-70px) | -10-15px |
| DataHelp wrapper | `px-4 py-2` (56px) | `px-3 py-1` (36px) | -20px |
| **Total estimado** | ~720-900px | ~640-800px | **~11-15%** |

Con **Focus Mode** activado, se eliminan ~500-800px adicionales (Insights, banners de proyección, priority layer, etc.).

---

## 3. Componentes Compactados

| Componente | Cambio |
|-----------|--------|
| **KPI Focus** | Card `px-4 py-3` de 80px eliminada. KPI buttons ahora inline en controls row con label "KPI" + botones cortos (Viajes, Rev., Cond., Ticket, TPD) |
| **Controls row** | `px-4 py-2` → `px-3 py-1.5`. KPI selector integrado a la derecha del modo/perspectiva |
| **Filter row** | `px-3 py-1.5 gap-x-3 gap-y-1.5` → `px-3 py-1 gap-x-2 gap-y-1` |
| **DataHelp** | `px-4 py-2` → `px-3 py-1`. Ya colapsado por defecto |
| **Priority Layer** | Sin cambios — ya era compacto con prop `compact` |

---

## 4. Qué Quedó Colapsable

- **OmniviewDataHelp** ("¿Qué significan estos números?") — colapsado por defecto (`useState(false)`)
- **OperationalStatusBar** — colapsado por defecto
- **Insights Panel** — colapsable. Focus Mode lo oculta.
- **FACT tables** — toggleable vía botón
- **Todos los banners** — ocultos en Focus Mode

---

## 5. Visual Description (Post-Compact)

```
┌─────────────────────────────────────────────────────┐
│ CommandHeader: [Operational] [Diagnostic]  ⚠ 3 🔴 2 │
│ ExecutiveBanner: (solo si hay problemas)             │
├─────────────────────────────────────────────────────┤
│ [Grano: Mensual|Semanal|Diario] [País] [Ciudad] ...  │
│ ¿Qué significan estos números? [+]                   │
├─────────────────────────────────────────────────────┤
│ Modo: [Evolución|Vs Proy] KPI: [Viajes|Rev.|Cond.|…]│
│ Vista: [Data|Insight] Densidad: [Cómodo|Compacto]   │
│ Zoom: [−] [100%] [+]  [Enfocar] [⬇ Descargar] [⊙ Ir] │
├─────────────────────────────────────────────────────┤
│ Freshness OK: RAW 30 May · Daily 30 May · Weekly…   │
│ Priority: ▼ Lima Auto -25% · ▼ Cali Moto -63% · …   │
├─────────────────────────────────────────────────────┤
│                     MATRIZ                            │
│ Ciudad │ Línea │ LUN │ MAR │ MIÉ │ JUE │ VIE │ …     │
│────────┼───────┼─────┼─────┼─────┼─────┼─────┼────   │
│ Lima   │ Auto  │ 3.2K│ 2.8K│ 3.1K│ …               │
│ …                                                   │
└─────────────────────────────────────────────────────┘
```

---

## 6. Backlog Registrado

Ver `docs/omniview/OMNIVIEW_POST_UX_H3_BACKLOG.md`:
- P1: Revenue Detail Certification
- P2: KPI Semantic Layer
- P3: Present Focus Validation
- P4: Freshness Copy Refinement
- P5: Header/Grid Width Alignment
- P6: Diagnostic Engine

---

## 7. Riesgos Pendientes

| Riesgo | Nivel | Nota |
|--------|-------|------|
| KPI buttons demasiado cortos | Bajo | Tooltips muestran nombre completo en hover |
| Focus Mode no persistente | Medio | Se pierde al recargar. Recomendado para UX-H4 |
| Reducción menor al 40% target | Bajo | El 40-60% requiere Focus Mode activo o colapsar banners |
| Build FAIL | N/A | Build PASS |

---

## 8. Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `BusinessSliceOmniviewMatrix.jsx` | KPI Focus inline, controls compact, filter compact, KPI_FOCUS_OPTIONS con `short` |
| `docs/omniview/UX_H3_VERTICAL_SPACE_AUDIT.md` | Creado |
| `docs/omniview/OMNIVIEW_POST_UX_H3_BACKLOG.md` | Creado |
| `docs/omniview/UX_H3_COMPACT_OPERATIONAL_HEADER_REPORT.md` | Creado |
