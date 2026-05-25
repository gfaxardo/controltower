# OPERATIONAL INFORMATION DENSITY GOVERNANCE

**Date**: 2026-05-25
**Motor**: Control Foundation
**Phase**: UX Hardening Stage 3

---

## 1. DENSITY PHILOSOPHY

Control Tower is an **operational decision terminal**, not a dashboard gallery.

**Density rule**: maximize actionable information per viewport pixel without sacrificing scanability.

The UI must enable:
1. Situation understanding in <3 seconds
2. Deviation detection in <1 second
3. Operational action initiation immediately upon detection

---

## 2. DENSITY MODES

### Three modes (via data-density attribute or class)

| Mode | Class | Multiplier | Use Case |
|------|-------|-----------|----------|
| Comfortable | `.ct-density-comfortable` | 1.0× | External presentations, new user onboarding |
| Compact | `.ct-density-compact` | 0.625× | Standard operational views |
| Operational | `.ct-density-operational` | 0.5× | Matrix views, terminal-like operation |

### Density variables
```css
--density-pad:     1;    /* Padding multiplier */
--density-gap:     1;    /* Gap multiplier */
--density-row-h:   1;    /* Row height multiplier */
--density-font-kpi: var(--ct-font-2xl);  /* KPI font size */
```

---

## 3. CARD GOVERNANCE RULES

### When to use a Card (`.ct-panel`)
- Contains multiple related data elements that form a semantic unit
- Requires a distinct visual boundary from neighboring content
- Has at least 3 lines of content (header + 2 data rows)
- Is interactive (expandable, drillable, has CTAs)

### When NOT to use a Card
- Single metric with label (use `ct-kpi-inline` or `ct-kpi-mini`)
- Informational message (use `ct-alert-inline` or `ct-info-row`)
- Filter controls (use `ct-filter-inline` or `ct-toolbar`)
- Section headers (use `ct-section-label` or `ct-visual-divider`)
- Empty states or placeholders (use inline text, minimal padding)
- "This feature is not ready" messages (use `ct-alert-compact--info`)

### Anti-patterns (PROHIBITED)
- Card inside card (double border + double padding = double waste)
- Card wrapping a single `<p>` tag
- `p-6` or `p-8` on any operational card (max `p-4`)
- Full card chrome (border + round + shadow + bg) for status messages

---

## 4. SPACING RULES

### Maximum values
| Property | Operational Max | Comfortable Max |
|----------|----------------|-----------------|
| Card padding | `p-4` (16px) | `p-6` (24px) |
| Section gap | `gap-3` (12px) | `gap-4` (16px) |
| Card grid gap | `gap-2` (8px) | `gap-3` (12px) |
| Top margin between views | `mt-2` (8px) | `mt-4` (16px) |
| Bottom margin after sections | `mb-3` (12px) | `mb-4` (16px) |
| Banner padding | `py-1` (4px) | `py-1.5` (6px) |

### NEVER use
- `mt-8`, `mb-8` (32px) — excessive dead air
- `space-y-6` (24px) — use `space-y-4` max, prefer `3`
- `p-8` (32px) — loading/empty states don't need this
- `px-6 py-6` for empty states — use `p-4` max

---

## 5. KPI DISPLAY RULES

### Hierarchy (from most compact to most spacious)

| Component | Height | Use case | Padding:Content ratio |
|-----------|--------|----------|----------------------|
| `ct-kpi-mini` | ~20px | Inline KPI in text flow | 20% |
| `ct-kpi-inline` | ~28px | Horizontal KPI strip | 30% |
| `ct-kpi-cluster` | ~40px | Related KPIs in one container | 35% |
| `ct-kpi-card` | ~64px | Standalone KPI with delta | 25% |
| Full KPI card (legacy) | ~88px | Non-compact legacy | 27% |

### Rules
1. If showing 1-2 KPIs: use `ct-kpi-inline` or `ct-kpi-mini`
2. If showing 3-6 related KPIs: use `ct-kpi-cluster`
3. If showing isolated KPIs with deltas: use `ct-kpi-card`
4. **NEVER** use the legacy KPI card in new views
5. Revenue/country-specific KPIs use `ct-kpi-cluster` grouping

---

## 6. TABLE DENSITY RULES

### Compact table (`.ct-table--compact`)
```css
thead th: py-1 text-2xs
tbody td: py-1 text-xs
```

### Dense table (`.ct-table--dense`) — Matrix ONLY
```css
tbody td: py-px line-height: 1.3
```

### Rules
1. Standard tables: minimum `text-sm` cells, 32px row height
2. Operational tables: `text-xs` cells, 28px row height
3. Matrix tables: governed by their own density system (no overrides)
4. **NEVER** use raw `p-2` or `p-3` on table cells — use density classes

---

## 7. FILTER BAR RULES

### Compact filter (`.ct-filter-inline`)
- Single horizontal strip, not a card
- Labels: `text-2xs uppercase` 
- Inputs/selects: `ct-select` or `ct-input` in the filter context (automatically compact)
- Maximum height: 32px per row
- Wrapping: allowed but each row max 36px

### Anti-patterns
- Filters inside `p-4 rounded-lg shadow-sm` cards
- "Filtros" section header consuming a line
- 2-row grid with `gap-4` for 4 fields

---

## 8. ALERT DENSITY RULES

### Three levels

| Level | Component | Size | Use |
|-------|-----------|------|-----|
| Inline | `ct-alert-inline` | 22px | Non-critical info, metadata hints |
| Compact | `ct-alert-compact` | 32px | Operational warnings, status changes |
| Standard | banner pattern | 36px | Critical errors, fresh alerts |

### Rules
1. Non-critical persistence info → `ct-alert-inline`
2. Operational warnings → `ct-alert-compact`
3. Critical blocking → standard banner (not inside a card wrapper)
4. **NEVER** use a full card for an alert message

### Severity visual system
- Dot only (`.ct-severity-dot`) for inline indicators
- Colored left border for compact alerts
- Full background + border for standard alerts

---

## 9. INFORMATION LAYERING (Progressive Disclosure)

### Three layers

| Layer | Component | Visibility | Content |
|-------|-----------|-----------|---------|
| 1 — Overview | `ct-layer-overview` | Always visible | Key KPIs, status, anomalies |
| 2 — Detail | `ct-layer-detail` | On click/toggle | Table rows, KPI breakdowns, context |
| 3 — Drill | `ct-layer-drill` | Modal/sidebar | Raw data, SQL, root cause |

### Rules
1. **NEVER** show Layer 3 content in the main view
2. Layer 2 content collapses by default for non-primary operations
3. Layer 1 must fit in <40% of viewport height on 1366x768
4. Use `.ct-detail-toggle` for Layer 2 expansion

---

## 10. VISUAL SCAN PRIORITY

The eye must flow:
1. **Anomaly flags** (`.ct-anomaly-flag`) — red/warning signals
2. **Primary KPIs** (largest values, bold)
3. **Trends** (`.ct-trend-indicator`) — up/down arrows
4. **Actions** (`.ct-primary-action`, `.ct-secondary-action`)
5. **Context** (`.ct-meta-bar`, `.ct-info-row`)

### Rules
- Anomalies MUST be the first thing the eye catches
- Never give context the same visual weight as data
- Never place actions below the fold without a sticky alternative
- Use `.ct-visual-divider` instead of card borders for lighter separation

---

## 11. COMPLIANCE CHECKLIST

### For every new view/component:
- [ ] Uses appropriate density mode (comfortable/compact/operational)
- [ ] No card wrapping another card
- [ ] No `p-6`, `mt-8`, `mb-8`, `space-y-6`
- [ ] KPIs use the appropriate compression level
- [ ] Tables use compact styling
- [ ] Filters are in a horizontal strip, not a card
- [ ] Alerts use the appropriate density level
- [ ] Information is layered (no Layer 3 in main view)
- [ ] Visual scan follows the priority order
- [ ] Anomalies are immediately visible

---

## 12. MIGRATION PATH

Existing views should progressively adopt:

### Quick (1-2 lines per file):
- Replace `space-y-6` → `space-y-4` or `space-y-3`
- Replace `p-6` → `p-4` on cards
- Replace `mt-8` → `mt-2` or remove

### Medium (per-view refactor):
- Replace `bg-white p-4 rounded-lg shadow` cards with `.ct-panel`
- Group KPI cards into `.ct-kpi-cluster`
- Replace alert banners with `.ct-alert-compact`

### Full (design pass):
- Adopt density modes for the entire view
- Restructure information layering
- Apply `.ct-layer-overview` / `.ct-layer-detail` pattern
