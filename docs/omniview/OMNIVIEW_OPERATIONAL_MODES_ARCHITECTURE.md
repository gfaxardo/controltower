# OMNIVIEW OPERATIONAL MODES — Architecture

**Date**: 2026-05-25
**Status**: DEFINED — Implementation pending

---

## 4 MODES

### EXECUTIVE — "What's the status?"
**Purpose**: Quick situational awareness.  
**Priority**: Blocked, critical, health, top deviations, freshness.  
**Minimizes**: Detail, raw data, technical info.

### OPERATIONAL — "What's happening?"
**Purpose**: Daily operational monitoring.  
**Priority**: Full matrix, comparability, tracking, active slices.  
**Default**: This is the primary mode.

### DIAGNOSTIC — "Why is this happening?"
**Purpose**: Explanation and degradation analysis.  
**Priority**: Dominant factors, explanations, trend deterioration, severity decomposition.  
**NO recommendations**: This is diagnostic, not prescriptive.

### COMPARATIVE — "How does this compare?"
**Priority**: WoW, MoM, YTD, Plan vs Real, variance focus, ranking comparative.

---

## MODE RESPONSIBILITY MATRIX

| Capability | EXECUTIVE | OPERATIONAL | DIAGNOSTIC | COMPARATIVE |
|-----------|-----------|-------------|------------|-------------|
| Matrix table | Compact summary rows | Full matrix | Full matrix + explanation overlay | Full matrix + variance highlight |
| Command header | Full health strip | Full | Full | Full |
| Banner | Top-level status only | Full | Dominant factors | Hidden/minimal |
| Filter controls | Essential only (grain, country) | Full | Full | Full |
| Attention strip | Prominent | Visible | Visible | Subtle |
| Severity badges | Per row as dot | Per cell as dot | Per row as badge + explanation | Per cell as variance |
| Explanation text | None | None | Dominant factor per row | None |
| Variance emphasis | None | Subtle | None | Prominent |
| Deltas (WoW/MoM) | None | Subtle cell delta | Degradation-only emphasis | Full delta columns |
| Priority panel | Expanded by default | Collapsed | Collapsed | Collapsed |

---

## VISUAL GOVERNANCE

### What's STABLE across all modes
- Matrix table (position, scroll behavior, sticky headers)
- Command header (always present)
- Filter positioning (always above matrix)
- Cell click → drill behavior

### What CHANGES per mode
- Emphasis (what's bold/colored/prominent)
- Visibility (what's shown vs hidden)
- Default states (panel collapsed vs expanded)

### What NEVER changes
- Matrix calculation logic
- Data fetching
- Serving facts
- Cell dimensions
- Scroll mechanics
