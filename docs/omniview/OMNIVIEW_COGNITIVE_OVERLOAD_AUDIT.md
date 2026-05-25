# OMNIVIEW COGNITIVE OVERLOAD AUDIT

**Date**: 2026-05-25

---

## CURRENT STATE: Everything visible simultaneously

| Element | Category | Cognitive Load |
|---------|----------|---------------|
| Command header (mode, period, health dots, attention counts) | always visible | LOW — compact, contextual |
| MatrixExecutiveBanner (trust status, confidence, impact, playbook, suggestions) | conditional | HIGH — multiline, dense text |
| Filter controls (8 dropdowns/toggles: grain, country, city, KPI, sort, plan version, compact, week focus) | always visible | HIGH — 8 interactive elements |
| Matrix table (100s-1000s of cells with signal colors) | always visible | VERY HIGH — primary content |
| Inspector panel (cell detail, trust info, deltas, SQL) | on click | HIGH — technical detail |
| Projection drill panel (KPI evolution, root cause, recommendations) | on click | VERY HIGH — complex panel |
| Priority panel (underperforming cells, top deviations) | expandable | HIGH — alert data |
| Insight panel (AI-detected patterns, configurable) | expandable | MEDIUM — optional |

## CLASSIFICATION

### Always visible (6 elements)
1. Command header — KEEP (essential context)
2. MatrixExecutiveBanner — **SHOULD BE MODE-DEPENDENT** (diagnostic info)
3. Filter controls — KEEP but compact
4. Matrix table — KEEP (primary)
5. Priority panel toggle — KEEP
6. Insight panel toggle — KEEP

### Mode dependent (can be shown/hidden per mode)
7. Playbook text in banner — DIAGNOSTIC mode only
8. Confidence score details — EXECUTIVE + DIAGNOSTIC
9. Root cause breakdown — DIAGNOSTIC only
10. Plan vs Real variance emphasis — COMPARATIVE mode
11. WoW/MoM deltas — COMPARATIVE mode
12. Degradation trends — DIAGNOSTIC mode
13. Top deviations list — EXECUTIVE mode

### Drill only (never in main view)
14. Cell inspector — on click
15. Projection drill — on click
16. SQL trace — drill only
17. Fact layer status — metadata

### Excessive noise
18. Filter count (8 visible) — reduce via mode: show 4 essential + "More filters" expand
19. MatrixExecutiveBanner multiline expansion — compact by default

## WHAT COMPETES VISUALLY

| Competition | Issue |
|-------------|-------|
| Command header vs Filter controls | Similar visual weight → resolved by tuning (filters are now ct-toolbar) |
| Banner vs Matrix | Banner can dominate when multiline → should compact per mode |
| Priority panel vs Matrix | Panel competes for attention → keep collapsed by default |
| Signal dots on cells vs attention header | Redundancy — fine, complementary |

## WHAT GENERATES COGNITIVE FATIGUE

1. "What should I pay attention to?" — Currently EVERYTHING. Need mode-guided attention.
2. "Is this operational or diagnostic?" — Mixed. Need mode to clarify intent.
3. "Where's the comparison?" — Buried in cell deltas. COMPARATIVE mode would emphasize this.
4. "What's degrading?" — Not surfaced prominently. DIAGNOSTIC mode would elevate this.
