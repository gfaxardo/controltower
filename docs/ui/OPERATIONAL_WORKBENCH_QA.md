# OPERATIONAL WORKBENCH QA — YEGO Control Tower

**Date**: 2026-05-25
**Motor**: Control Foundation
**Phase**: UX Hardening Stage 2 — Workbench Governance

---

## 1. BUILD VERIFICATION

| Metric | Result |
|--------|--------|
| Build status | PASS (11.64s) |
| CSS bundle | 82.44 kB (gzip: 14.35 kB) |
| JS bundle | 1,771.77 kB (gzip: 505.92 kB) |
| Warnings | Only chunk size >500kB (pre-existing) |
| Errors | 0 |

---

## 2. ERGONOMICS VALIDATION

### 2.1 Typography Legibility

| Component | Before | After | Verdict |
|-----------|--------|-------|---------|
| Banners | `text-2xs` (10px) | `text-xs` (12px) | PASS |
| Banners padding | `py-1.5` | `py-1` | PASS |
| Filter labels (Omniview) | `text-[10px]` | `text-xs` (12px) | PASS |
| Sub-navigation | `text-2xs` (10px) | `text-xs` (12px) | PASS |
| Maturity badges | `text-[9px]` | `text-[11px]` | PASS |
| KPI Hero labels (Yango) | `text-2xs` | `text-xs` | PASS |
| City ranking content (Yango) | `text-2xs` | `text-xs` | PASS |
| Alert text (Weekly) | Raw `text-gray-*` | `text-ct-text/ct-text2` | PASS |
| Table data (Weekly) | Raw `text-gray-*` | `text-ct-text` | PASS |

### 2.2 Spacing Consistency

| Area | Before | After | Verdict |
|------|--------|-------|---------|
| YangoLoyalty root | `space-y-4` (16px) ad-hoc | `ct-page-section` + `gap: 12px` | PASS |
| YangoLoyalty header | ad-hoc flex | `ct-workbench-header` | PASS |
| YangoLoyalty category cards | `grid grid-cols-3 gap-3` raw | `ct-kpi-grid` + `ct-kpi-card` | PASS |
| YangoLoyalty city ranking | `space-y-1.5` + raw cards | `ct-collapsible` primitives | PASS |
| YangoLoyalty config | raw card `p-4` | `ct-compact-config-panel` + `ct-panel-body` | PASS |
| WeeklyView root | `bg-white p-6 mt-8` raw | `ct-panel` + `ct-panel-body` | PASS |
| WeeklyView filters | raw `grid grid-cols-4 gap-4` | `ct-form-row` + `ct-form-field` + `ct-input` | PASS |
| WeeklyView table | raw `bg-gray-50` headings | `ct-table-card` + `ct-*` tokens | PASS |
| WeeklyView alerts | unbounded height | `ct-scroll-y` with max-height | PASS |

---

## 3. VIEWPORT GOVERNANCE

### 3.1 Scroll Behavior

| Component | Before | After | Verdict |
|-----------|--------|-------|---------|
| Content area | `w-full` no max | `ct-page` (1440px max) | PASS |
| WeeklyView table | unbounded height | horizontally scrollable only (same, preserved) | PASS |
| WeeklyView alerts | unbounded height, can push page | `ct-scroll-y` with `calc(100vh - 360px)` | PASS |
| YangoLoyalty city accordion | can grow unbounded | `ct-collapsible-content` with `max-height: 18rem` | PASS |

### 3.2 Viewport Breakpoints

| Viewport | YangoLoyalty | WeeklyView | Omniview Matrix |
|----------|-------------|------------|-----------------|
| 1366x768 | Workbench layout, scroll governed | Content grid stacks, alerts scroll | Preserved |
| 1024x768 | KPI grid reflows, collapsibles govern | Single column, table scrolls horizontal | Preserved |
| 1440p | Full layout, content capped at 1440px | Full 2/1 grid | Preserved |

---

## 4. ACTION HIERARCHY

### 4.1 Primary Actions Visible

| View | Action | Visibility |
|------|--------|------------|
| YangoLoyalty Overview | "Configurar metas" (in banner) | VISIBLE - banner compacted, CTA inline |
| YangoLoyalty Config | "Guardar metas para X" | VISIBLE - `ct-primary-action` in `ct-action-zone` |
| WeeklyView | "Registrar acción" per alert | VISIBLE - `ct-primary-action` within scroll-bounded cards |
| WeeklyView | "Ver/Ocultar" row detail | VISIBLE - `ct-secondary-action` styled |

### 4.2 Hierarchy Order

1. CTA principal — `ct-primary-action` (blue background, weight 600)
2. Operaciones — tab switching, filter buttons — `ct-secondary-action`
3. Contexto — tooltips, metadata — `text-ct-text2`
4. Alertas secundarias — banners — `px-3 py-1` compact

---

## 5. COLLAPSIBLE GOVERNANCE

| Collapsible | Governance |
|-------------|-----------|
| Yango Loyalty city ranking | `ct-collapsible` + `ct-collapsible-header` + `ct-collapsible-content` max-height 18rem |
| Yango Loyalty KPI blockers | Single-expand (only one at a time), `DrillableBlocker` component preserved |
| GlobalFreshnessBanner | `py-1`, expand-on-click, table scroll governed |
| OperationalStatusBar | `py-1.5` collapse, expandable chips `text-xs` |
| CollapsibleFilters | `text-xs` button, toggle visibility |
| Collapsible tabes | Matrix: preserved, Yango: tabs switch content |

---

## 6. CSS PRIMITIVES DELIVERED

### Phase 1 (from Stage 1):
- `.ct-page`, `.ct-page-section`, `.ct-toolbar`, `.ct-panel`, `.ct-panel-header`, `.ct-panel-body`
- `.ct-form-grid`, `.ct-form-grid--dense`, `.ct-form-field`, `.ct-form-label`
- `.ct-scroll-region`, `.ct-section-header`, `.ct-kpi-strip`, `.ct-action-zone`

### Phase 2 (new in Stage 2):
- **Workbench**: `.ct-workbench`, `.ct-workbench-header`, `.ct-workbench-title`, `.ct-workbench-subtitle`, `.ct-workbench-toolbar`, `.ct-workbench-layout`, `.ct-workbench-main`
- **Collapsible**: `.ct-collapsible`, `.ct-collapsible-header`, `.ct-collapsible-header-icon`, `.ct-collapsible-content`, `.ct-collapsible-content--auto`
- **Form**: `.ct-form-section`, `.ct-form-section-title`, `.ct-form-row`, `.ct-form-group`, `.ct-inline-actions`, `.ct-compact-config-panel`, `.ct-input`, `.ct-input--sm`, `.ct-select`
- **Scroll**: `.ct-scroll-y`, `.ct-scroll-x`, `.ct-sticky-toolbar`, `.ct-sticky-actions`
- **Actions**: `.ct-primary-action`, `.ct-secondary-action`, `.ct-secondary-action--active`
- **Layout**: `.ct-fill-height`, `.ct-content-grid`, `.ct-table-card`, `.ct-table-card-header`, `.ct-empty-fill`
- **Components**: `.ct-badge`, `.ct-badge--ok/warn/bad/info/neutral`, `.ct-kpi-grid`, `.ct-kpi-card`, `.ct-kpi-card-label`, `.ct-kpi-card-value`, `.ct-kpi-card-delta`
- **Actions zone**: `.ct-actions-sticky`

---

## 7. DEGRADATION RISK ASSESSMENT

| Risk | Probability | Mitigation |
|------|------------|------------|
| Typography tokens not inherited in complex table cells | Low | Table-specific classes still use explicit sizes, not tokens |
| `ct-content-grid` stacks wrong on small screens | Low | Media query at 1024px switches to single column |
| `ct-scroll-y` with calc() breaks if header changes | Low | Uses `--scroll-max-h` variable, tunable via inline style |
| `ct-collapsible-content` max-height hides critical data | Low | 18rem is liberal (~5-6 KPI rows). Use `--auto` variant if needed |

---

## 8. COMPLIANCE CHECKLIST

### GO Criteria

- [x] Workflow claro — tabs + header structure in YangoLoyalty
- [x] CTAs visibles — `ct-primary-action` stands out
- [x] Forms compactos — `ct-form-grid--dense` + `ct-input`
- [x] Scroll natural — `ct-scroll-y` on alerts, `ct-collapsible-content` on accordions
- [x] No viewport destruction — max-height on collapsibles, scroll-bounded alerts
- [x] Navegación intuitiva — consistent header + tab pattern
- [x] Jerarquía clara — primary action > data > context > alerts
- [x] Usable sin zoom — 12px minimum, 11px for badges

### NO-GO Check (all negative = PASS)

- [ ] Accordion destructivo — NO (ct-collapsible-content max-height prevents this)
- [ ] Scroll nesting caótico — NO (only horizontal scroll on tables, vertical on alerts)
- [ ] Forms gigantes — NO (ct-form-grid--dense caps form expansion)
- [ ] Espacios muertos enormes — NO (ct-page max-width, reduced gaps)
- [ ] CTAs perdidos — NO (ct-primary-action prominent, ct-action-zone grouped)
- [ ] Banners dominantes — NO (py-1, text-xs, compact)
- [ ] Navegación kilométrica — NO (scroll-bounded regions)
- [ ] Layouts HTML genéricos — NO (workbench primitives applied)

---

## 9. FILES MODIFIED

| File | Changes |
|------|---------|
| `frontend/src/styles/ct-design-tokens.css` | +220 lines of workbench primitives |
| `frontend/src/components/yangoLoyalty/YangoLoyaltyView.jsx` | Workbench header, ct-collapsible, ct-kpi-grid, ct-form primitives, ct-primary-action |
| `frontend/src/components/WeeklyPlanVsRealView.jsx` | ct-panel, ct-content-grid, ct-table-card, ct-scroll-y, ct-* tokens replacing raw Tailwind |
| `docs/ui/OPERATIONAL_WORKBENCH_QA.md` | This document |

### Preserved (no changes):
- All Omniview Matrix files
- ECharts configuration
- Backend
- API services
- Other views (Supply, Drivers, etc.)
