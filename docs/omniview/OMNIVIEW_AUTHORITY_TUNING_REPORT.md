# OMNIVIEW AUTHORITY TUNING — REPORT

**Date**: 2026-05-25
**Status**: **GO**
**Build**: PASS (10.68s)

---

## 1. PROBLEMS FOUND

| Problem | Severity |
|---------|----------|
| Command header looks like generic card — no identity | HIGH |
| Inner strip has its own bg + border (redundant nesting) | MEDIUM |
| Banner children area visually heavy (bg + thick border) | MEDIUM |
| Filter toolbar is a full card with same visual weight as header | HIGH |
| Too many visual bands before matrix data (4) | HIGH |

## 2. CHANGES APPLIED

| Change | Effect |
|--------|--------|
| Left accent border (3px ct-accent) on header | **Identity** — command header now has a distinct visual signature |
| Removed inner bg/border from strip | **Unification** — strip reads as part of header, not nested card |
| Reduced banner area to py-1, lighter border | **Compaction** — banner feels integrated, not separate card |
| Filter toolbar: removed full card chrome | **Hierarchy** — filter toolbar is now lighter than command header |

## 3. BEFORE vs AFTER (band stack)

```
BEFORE (4 visual bands):
┌─ Card: Command Header (rounded-lg border bg-ct-card shadow-sm) ──┐
│  ┌─ Strip (bg-ct-surface border-b) ──┐                          │
│  └────────────────────────────────────┘                          │
│  ┌─ Children (bg-ct-surface/50 border-t py-1.5) ─┐              │
│  │  MatrixExecutiveBanner                          │              │
│  └────────────────────────────────────────────────┘              │
└───────────────────────────────────────────────────────────────────┘
┌─ Card: Filter Toolbar (rounded-lg border bg-ct-surface) ─────────┐
│  Filters...                                                       │
└───────────────────────────────────────────────────────────────────┘
Matrix...

AFTER (2 visual areas):
┌─ Header: Command Center (left-accent shadow-sm) ─────────────────┐
│  Mode | Evolution · Mensual · 2025 | Fresh | Trust | Cov | ● 2 ●1│
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
│  MatrixExecutiveBanner (conditional, py-1)                        │
└───────────────────────────────────────────────────────────────────┘
  Filters (light border + bg-ct-surface, reduced visual weight)...
Matrix...
```

## 4. WHAT WAS PRESERVED

- Matrix table (untouched)
- Sticky headers (untouched)
- Drill behavior (untouched)
- Projection logic (untouched)
- Data fetching (untouched)
- All calculations (untouched)

## 5. WHAT WAS NOT DONE

- Did not merge filter toolbar into header (would restructure 200+ lines of JSX → high risk, low reward)
- Did not create new alert stack component (existing: MatrixExecutiveBanner handles this role)
- Did not add hero section or executive summary strip (requires new data source)

## 6. VERDICT

**GO** — Command header now has distinct identity. Visual band stack reduced from 4 to 2 discrete areas. Filter toolbar no longer competes visually with the command header. Matrix preserved.
