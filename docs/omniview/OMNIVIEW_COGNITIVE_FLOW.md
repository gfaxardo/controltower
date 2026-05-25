# OMNIVIEW COGNITIVE FLOW

**Date**: 2026-05-25
**Per mode**: First 3 seconds of operator attention

---

## EXECUTIVE MODE

### Second 0-1: Health strip
Sees: Green dots = OK, Red/Amber dots = problem
Understands: "System is healthy" or "Something is wrong"

### Second 1-2: Attention counts
Sees: "0 blocked, 1 critical"
Understands: "One thing needs attention"

### Second 2-3: Top deviation
Sees: Priority panel showing worst cell
Understands: "This is the priority"

---

## OPERATIONAL MODE (default)

### Second 0-1: Mode + period
Sees: "Omniview Operational · Mensual · 2025"
Understands: "I'm in monitoring mode"

### Second 1-2: Matrix overview
Sees: Green/yellow/red pattern across cells
Understands: "Most things are OK, some warnings"

### Second 2-3: Attention counts
Sees: Blocked/critical chip counts
Understands: "I need to investigate N items"

---

## DIAGNOSTIC MODE

### Second 0-1: Dominant factor strip
Sees: "Critical due to Freshness degraded. Lag: 5d"
Understands: "There's a data problem"

### Second 1-2: Explanation per row
Sees: DiagnosticDominantFactor per affected city
Understands: "City X is blocked due to Y"

### Second 2-3: Secondary factors
Sees: Contributing factors in tooltip
Understands: "Multiple things are degrading"

---

## COMPARATIVE MODE

### Second 0-1: Variance overview
Sees: More red cells (variance emphasis) vs normal
Understands: "Significant deviations exist"

### Second 1-2: Comparison context
Sees: Plan vs Real labels, WoW delta columns
Understands: "Comparing specific periods"

### Second 2-3: Ranking
Sees: Sorted by deviation magnitude
Understands: "Biggest gap is at the top"
