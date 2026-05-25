# LOYALTY TO OMNIVIEW — PATTERN TRANSFER

**Date**: 2026-05-25

---

## PATTERNS FROM LOYALTY

| Pattern | Loyalty Implementation | TRANSFER to Omniview? | Why (not) |
|---------|----------------------|----------------------|-----------|
| `ct-workbench-header` | Full header: title left, actions right | ✅ YES — but compact | Omniview needs context above matrix |
| `ct-workbench-header-left` / title+subtitle | Title + period + progress | ✅ YES — period + mode + freshness |
| `ct-secondary-action` tabs | Resumen / Detalle KPI / Configurar Metas | ✅ YES — Evolution/Projection toggle, compact/full toggle |
| `ct-kpi-strip` | Category count cards | ✅ YES — condensed as inline KPI strip |
| `ct-collapsible` | City ranking accordion | ❌ NO — matrix is already the primary navigation |
| `ct-compact-config-panel` | Config form panel | ❌ NO — Omniview doesn't have per-view config |
| Severity badges (DecisionSeverityBadge) | Per city badge | ✅ YES — per cell/row in attention mode |
| DiagnosticDominantFactor | Config/data warnings | ✅ YES — in command header for blocked/critical |
| DecisionPriorityStrip | City ranking strip | ✅ YES — in command header showing blocked/critical counts |
| `ct-kpi-grid` + `ct-kpi-card` | Category count grid | ❌ NO — matrix IS the KPI display |
| `ct-action-zone` | Submit button zone | ❌ NO — matrix actions are in toolbar |
| `ct-form-grid--dense` | KPI config grid | ❌ NO — filters aren't form fields |

## WHAT OMNIVIEW GETS (5 patterns transferred)

1. **Command header** (from workbench-header) — title + period + mode + attention strip
2. **Tabs as ct-secondary-action** — Evolution/Projection, grain toggle, compact toggle
3. **Severity integration** — DecisionSeverityBadge + DecisionPriorityStrip in command header + per-row
4. **Diagnostic explanation** — DiagnosticDominantFactor for blocked/critical states
5. **Compact toolbar** — ct-toolbar-compact for filter row

## WHAT OMNIVIEW KEEPS UNIQUE

- Matrix table (no Loyalty equivalent)
- Fullscreen mode
- ECharts
- Projection drill
- Executive banner (enhanced, not replaced)
- Multi-dimensional filtering (country/city/KPI/sort/grain/plan version)
