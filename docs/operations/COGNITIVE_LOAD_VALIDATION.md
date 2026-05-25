# COGNITIVE LOAD VALIDATION

**Date**: 2025-05-25
**Purpose**: Assess whether the Control Tower interface is operationally scannable

---

## 1. COGNITIVE LOAD SCALE

| Level | Description | Operator experience |
|---|---|---|
| 1 | **Instant clarity** — I know what's wrong immediately | Ideal |
| 2 | **Quick scan** — I find the problem in < 10 seconds | Acceptable |
| 3 | **Moderate effort** — I need to read labels and think | Needs improvement |
| 4 | **High effort** — I feel overwhelmed, scrolling a lot | Problem |
| 5 | **Overload** — I give up and close the tab | Critical failure |

---

## 2. ELEMENTS TO EVALUATE

### Command Header
| Element | Cognitive weight | Question |
|---|---|---|
| Mode selector (Evolución / Vs Proyección) | Low | Clear toggle — understood? |
| Grain selector (Mensual / Semanal / Diario) | Low | Intuitive? |
| Operational mode selector | Medium | Do operators use Executive/Operational/Diagnostic modes? |
| Freshness badges | Medium | Understood or ignored? |
| Trust indicators | Medium | Do they change operator behavior? |

### Priority Strip
| Element | Cognitive weight | Question |
|---|---|---|
| Status label "Momentum" | Low | Clear? |
| Severity chips (!! / ! / ↓) | Medium | Intuitive? Too subtle? |
| City names + percentage | Low | Scannable? |
| "No deteriorations" empty state | Low | Clear? |

### Matrix
| Element | Cognitive weight | Question |
|---|---|---|
| City/Línea rows | Medium | Too many rows? Collapse default helps? |
| Period columns | High (daily) | Too many columns on daily? Weekday focus used? |
| Momentum row (DoD/WoW/MoM) | Low-Medium | Clear vs attainment row? |
| Attainment % + dot | Medium | Two color systems (momentum + attainment) confusing? |
| Gap value | Low | Useful or noise? |
| Projected value | Low | Read or skipped? |
| Trust overlays (ring on cell) | Medium | Understood? |

### Drill Panel
| Element | Cognitive weight | Question |
|---|---|---|
| Plan vs Real / Momentum toggle | Low-Medium | Discoverable? Used? |
| Gap summary | Medium | Useful? |
| Root cause analysis | High | Understood by non-technical operators? |
| Control loop history | High | Table of historical data — useful? |
| Curve confidence | Medium | Understood? |

### Behavioral MVP Panel
| Element | Cognitive weight | Question |
|---|---|---|
| Summary badges | Low | Clear at a glance? |
| Driver list with status chips | Medium | Too many drivers (100)? |
| Trips/day metric | Low | Makes sense? |
| Delta % | Low | Color-coded correctly? |
| Signal gaps footer | Low | Read or ignored? |

---

## 3. FIRST-SCAN TEST

Give operator 10 seconds. Ask:

1. "What's the biggest problem right now?" → Expected: Priority strip top item
2. "Which city needs attention?" → Expected: City with red/momentum-down cell
3. "How many drivers are at risk?" → Expected: Behavioral panel summary number

**Target**: 2/3 correct in 10 seconds.

---

## 4. CLICK-COUNT TEST

Count clicks to complete common tasks:

| Task | Ideal clicks | Actual (fill) |
|---|---|---|
| Find today's worst city | 0 (priority strip) | _ |
| Understand why city X is declining | 2 (click cell → read drill) | _ |
| See only Friday columns | 1 (click VIE chip) | _ |
| Compare plan vs real for city X | 3 (switch mode → click cell → read drill) | _ |
| See behavioral diagnosis for country | 0 (if panel open) | _ |
| Export matrix | 1 | _ |

**Target**: No task requires > 4 clicks.

---

## 5. INFORMATION NEVER USED

During sessions, note what operators NEVER interact with:

| Element | Ever used? (Y/N) |
|---|---|
| Zoom control | _ |
| Density toggle | _ |
| Focus mode (dimming) | _ |
| Insight mode (vs Data mode) | _ |
| FACT tables button | _ |
| Fullscreen matrix | _ |
| Operational mode (Executive/Diagnostic) | _ |
| Subfleet toggle | _ |
| Week scope toggle (año completo) | _ |

If >2 features never used across 3+ sessions → candidates for removal or redesign.

---

## 6. LANGUAGE / LABEL AUDIT

| Label | Problem? |
|---|---|
| "Vs Proyección" vs "Evolución" | Clear distinction? |
| "DoD" / "WoW" / "MoM" | Spanish operators understand English acronyms? |
| "attainment" / "avance" | Correct term? |
| "gap" | Understood? |
| "consistency_score" | Technical — should it be "Consistencia"? |
| "dominant_factor" | Technical — should it be "Factor principal"? |

---

## Validation Matrix (to be filled)

| Metric | Session 1 | Session 2 | Session 3 | Target |
|---|---|---|---|---|
| Cognitive load (1-5) | _ | _ | _ | ≤ 2 |
| First-scan accuracy (0-3) | _ | _ | _ | ≥ 2 |
| Avg clicks per task | _ | _ | _ | ≤ 3 |
| Unused features (count) | _ | _ | _ | ≤ 2 |
| Confusion points | _ | _ | _ | ≤ 2/session |
