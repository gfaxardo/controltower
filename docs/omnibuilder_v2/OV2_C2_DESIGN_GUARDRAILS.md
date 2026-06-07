# OV2-C.2 — DESIGN GUARDRAILS

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture

---

## 1. VISUAL LIMITS

| Rule | Limit | Reason |
|------|-------|--------|
| Executive KPIs | Max 5 | OV2-C.2 V1 problem: 12 KPIs caused information overload |
| Alert strip visible alerts | Max 3 | Show most critical. "Show all (N)" for overflow. |
| Inspector width | 320-400px | Enough for content, doesn't cover matrix |
| Modal depth | 1 level | Inspector + modal never simultaneously open |
| Matrix min height | 300px | Below this, hide matrix and show "Select data" state |
| Compare panel | 2 sources | Only CT vs Yango currently |

---

## 2. COLOR SYSTEM

| Semantic | Hex | Usage |
|----------|-----|-------|
| OK / CANONICAL | #22c55e (green-500) | Status badges, coverage≥95%, OK cells |
| WARNING | #f59e0b (amber-500) | Warning badges, coverage<95%, delta>3% |
| BLOCKED | #ef4444 (red-500) | Blocked sections, revenue unavailable, coverage<50% |
| NOT_READY / UNKNOWN | #9ca3af (gray-400) | Not yet implemented sections |
| SHADOW / NOT CANONICAL | #6366f1 (indigo-500) | YANGO_API_RAW source badge |
| ESTIMATED / PROXY | #a855f7 (purple-500) | Derived values, proxy revenue |
| Background OK cell | #ffffff (white) | Default cell background |
| Background WARNING cell | #fffbeb (amber-50) | Subtle warning tint |
| Background BLOCKED cell | #fef2f2 (red-50) | Subtle error tint |
| Text primary | #111827 (gray-900) | Normal values |
| Text muted | #9ca3af (gray-400) | Unavailable values, "—" |

---

## 3. BADGES

Every badge must be:

### 3.1 Always visible when applicable
| Badge | When | Color |
|-------|------|-------|
| CANONICAL | source canonical_ready=true | Green |
| SHADOW / NOT CANONICAL | source canonical_ready=false | Indigo |
| PARTIAL COVERAGE | coverage < 95% | Amber |
| SHORT SERIES | < 7 days of data | Amber |
| REVENUE WARNING | revenue delta > 5% | Amber |
| REVENUE BLOCKED | revenue unavailable | Red |
| ESTIMATED | is_estimated=true | Purple |
| PARTIAL PERIOD | period_status=PARTIAL | Amber |
| FUTURE PERIOD | period_status=FUTURE | Gray |

### 3.2 Badge locations
- **Source badge:** Command header, every section card header
- **Coverage badge:** Command header, Operational Coverage section
- **Period badge:** Every matrix cell
- **Revenue badge:** Revenue KPI card, Revenue Integrity section
- **Estimated badge:** Affected KPI card, cell tooltip

---

## 4. LAYOUT RULES

| # | Rule |
|---|------|
| 1 | Header is always at top. Never scrolls away. |
| 2 | Matrix is below sections. Never side-by-side. |
| 3 | Inspector slides from right. Never covers header. |
| 4 | Compare panel opens as modal overlay. |
| 5 | No orphan scrollbars. Exactly one scroll context per zone. |
| 6 | Desktop-first. Min width 1024px. No mobile layout yet. |
| 7 | Font: system font stack. Monospace for numbers in cells. |
| 8 | Cell width: min 80px, max 120px for daily grain. |
| 9 | Row height: 40px. Consistent across all rows. |
| 10 | Gap between cards: 16px. Consistent. |

---

## 5. RESPONSIVE NOTES

| Breakpoint | Behavior |
|-----------|----------|
| >= 1280px | Full layout: header + exec + sections + matrix |
| 1024-1279px | Cards stack 2 per row. Matrix reduces columns. |
| < 1024px | NOT SUPPORTED in OV2-C.2. Show "Desktop required" message. |

---

## 6. ACCESSIBILITY BASELINE

| Requirement | Implementation |
|-------------|---------------|
| Keyboard navigation | Tab through sources, grains, cells. Enter to select. Escape to close. |
| Color not sole indicator | Status text accompanies color badges. |
| Focus visible | Outline on focused elements. |
| Screen reader labels | aria-label on all interactive elements. |

---

## 7. FORBIDDEN PATTERNS

| Pattern | Reason |
|---------|--------|
| Inline calculations in JSX | Must be pre-computed by backend |
| useEffect for derived state | Use computed/derived values |
| Multiple scroll containers | Single scroll per zone |
| localStorage without version key | Schema changes break persistence |
| Hardcoded colors outside constants | Consistency enforcement |
| Direct DOM manipulation | Use React state |
| setTimeout for UI timing | Use CSS transitions/animations |
| Double data fetching | Cache shell response, don't re-fetch for inspector |
