# OV2-D.3B — SCOPE LOCK

> **Date:** 2026-06-08
> **Status:** DEFINED

## IN SCOPE

| Feature | Status |
|---------|--------|
| Matrix layout (already built) | ✅ existing |
| KPI/grain/mode selector (already built) | ✅ existing |
| Cell Inspector connected to `/drill/cell` | ✅ backend endpoint exists |
| Lineage badges (READY/PARTIAL) | ✅ add to inspector |
| Park breakdown in inspector | ✅ drill returns parking data |
| Driver top-N in inspector | ✅ drill returns drivers |
| Freshness observatory connection | ✅ endpoint exists |
| Advancement status badges | ✅ advancement_log exists |

## OUT OF SCOPE

| Feature | Why |
|---------|-----|
| Heatmaps | Deferred to D.3C |
| Fleet drill full | PARTIAL — needs bridge fleet columns |
| Raw trip drill full | PARTIAL — needs trips_2026 scan |
| Yango reconciliation | PARTIAL — endpoint not built |
| New KPI types | No feature expansion |
| V1 visual changes | V1 frozen |

---

*End of Scope Lock*
