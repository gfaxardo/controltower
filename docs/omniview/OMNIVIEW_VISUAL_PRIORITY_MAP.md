# OMNIVIEW VISUAL PRIORITY MAP

**Date**: 2026-05-25

---

## VISUAL WEIGHT PER MODE

```
WEIGHT:  ███ = Maximum  ██ = High  █ = Medium  ░ = Low  · = Hidden
```

### EXECUTIVE

| Element | Weight | Why |
|---------|--------|-----|
| Health dots (freshness, trust, coverage) | ███ | First thing operator checks |
| Attention counts (blocked/critical) | ███ | What needs action |
| Priority panel (top deviations) | ██ | Default expanded |
| Banner status (OK/WARNING/BLOCKED) | ██ | Overall health |
| Matrix table | █ | Compact summary, not full detail |
| Filter controls | ░ | Essential only |
| Cell deltas | · | Hidden |
| Explanation text | · | Hidden |

### OPERATIONAL (default)

| Element | Weight | Why |
|---------|--------|-----|
| Matrix table | ███ | Primary work surface |
| Command header | ██ | Context always visible |
| Filter controls | ██ | Full controls needed |
| Cell signal colors | █ | Normal emphasis |
| Attention counts | █ | Reference only |
| Banner | ░ | Compact |
| Priority panel | ░ | Collapsed |
| Explanation | · | On drill only |

### DIAGNOSTIC

| Element | Weight | Why |
|---------|--------|-----|
| Dominant factor per row | ███ | "Why is this critical?" |
| Banner (full diagnostic text) | ██ | Root cause overview |
| Explanation badges | ██ | Per-row explanation |
| Matrix table | ██ | Data context |
| Severity badges | █ | Per cell |
| Filter controls | █ | Full |
| Priority panel | · | Not the focus |
| Variance | · | Not relevant |

### COMPARATIVE

| Element | Weight | Why |
|---------|--------|-----|
| Variance emphasis (red/green cells) | ███ | "What changed?" |
| Deltas (WoW, MoM, YTD) | ██ | Comparison columns |
| Plan vs Real side-by-side | ██ | Direct comparison |
| Matrix table | ██ | Data context |
| Command header | █ | Reference |
| Filter controls | █ | Full (period selection key) |
| Severity | ░ | Secondary to variance |
| Explanation | · | Not in comparison mode |
| Banner | · | Not in comparison mode |
