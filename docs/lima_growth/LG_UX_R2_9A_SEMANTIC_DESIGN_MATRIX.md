# LG-UX-R2.9A — Semantic Design Matrix

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9A Semantic UX Audit
**Scope:** Inventory of all visual tokens across Lima Growth V2.

---

## STATUS BADGES

| Concept | Color | Badge Class | Icon | Used In |
|---------|-------|-------------|------|---------|
| READY | `bg-green-100 text-green-700` | `StatusBadge` | — | Queue, Programs |
| HELD | `bg-yellow-100 text-yellow-700` | `StatusBadge` | — | Queue |
| EXPORTED | `bg-purple-100 text-purple-700` | Legacy inline | — | Queue (legacy), V2 falls to gray default |
| EXPORTED (lowercase) | `bg-green-100 text-green-800` | `StatusBadge` | — | Export history |
| DRAFT | `bg-gray-100 text-gray-600` | `StatusBadge` | — | LoopControl |
| DRAFT_DRY_RUN | `bg-blue-100 text-blue-800` | `StatusBadge` | — | LoopControl |
| LIVE (LoopControl) | `bg-green-100 text-green-800` | `StatusBadge` | — | Config |
| DRY_RUN (LoopControl) | `bg-yellow-100 text-yellow-800` | `StatusBadge` | — | Config |
| FAILED | `bg-red-100 text-red-800` | `StatusBadge` | — | Export |
| ACTIVE (program) | `bg-blue-100 text-blue-700` | Inline | — | Programs |
| EMPTY (program) | `bg-gray-100 text-gray-500` | Inline | — | Programs |
| STALE (program) | `bg-red-100 text-red-700` | Inline | — | Programs |
| UNKNOWN (program) | `bg-gray-100 text-gray-400` | Inline | — | Programs |
| BLOCKED | `bg-red-100 text-red-700` | Inline | — | Programs |
| ACTIVE (policy) | `bg-green-100 text-green-700` | Inline | — | Policy Panel |
| DRAFT (policy) | `bg-yellow-100 text-yellow-700` | Inline | — | Policy Panel |
| RETIRED (policy) | `bg-gray-100 text-gray-500` | Inline | — | Policy Panel |

---

## OPERATIONAL STATUSES (Today's Action Plan)

| Status | Color | Icon |
|--------|-------|------|
| QUEUE_NOT_BUILT | `bg-red-100 text-red-700` | ⛔ |
| QUEUE_EMPTY | `bg-gray-100 text-gray-600` | ○ |
| READY_TO_EXPORT | `bg-green-100 text-green-700` | ✓ |
| READY_WITH_BLOCKERS | `bg-yellow-100 text-yellow-700` | ⚠ |
| ALL_HELD | `bg-red-100 text-red-700` | ⊘ |
| ALL_EXPORTED | `bg-blue-100 text-blue-700` | → |
| IDLE | `bg-gray-100 text-gray-500` | — |

---

## FRESHNESS BADGES

| Status | Dot | Background |
|--------|-----|------------|
| FRESH | `bg-green-400` | `bg-green-50 text-green-700` |
| WARNING | `bg-yellow-400` | `bg-yellow-50 text-yellow-700` |
| STALE | `bg-red-400` | `bg-red-50 text-red-700` |
| UNKNOWN | `bg-gray-300` | `bg-gray-50 text-gray-500` |

---

## CHANNEL BADGES

| Channel | Color |
|--------|-------|
| CALL_CENTER | `bg-blue-50 text-blue-700` |
| SAC | `bg-purple-50 text-purple-700` |
| BOT | `bg-cyan-50 text-cyan-700` |
| UNASSIGNED | `bg-red-50 text-red-700` |

---

## ALLOCATION MODES

| Mode | Color |
|------|-------|
| STRICT_PRIORITY | `bg-blue-50 text-blue-700` |
| PROPORTIONAL | `bg-purple-50 text-purple-700` |
| HYBRID | `bg-green-50 text-green-700` |

---

## SECTION CARD BORDER COLORS

| Section | Border |
|--------|--------|
| Today's Action Plan header | `#06244a → #0d3b7a` gradient |
| Pipeline Operacional | `#06244a → #0d3b7a` gradient |
| Top Priorities | `#7c3aed` |
| Bloqueadores | `#dc2626` |
| Observaciones | `#0891b2` |
| Acciones Recomendadas | `#059669` |
| Program Operations | `#059669` |
| Estado del Conductor | `#1a56db` |
| Politica de Oportunidades | `#1a56db` |
| LoopControl Integration | `#7c3aed` |
| Capacidad Operativa | `#0891b2` |
| Capacity Allocation Trace | `#d97706` |
| Program Capacity Policy | `#059669` |
| Execution Queue | `#d97706` |
| Backlog No Certificado | `#9ca3af` |

---

## ACTION BUTTON COLORS

| Action | Color |
|--------|-------|
| Build Queue | `#d97706` (amber) |
| Export READY | `#7c3aed` (purple) |
| Save Config | `#0891b2` (cyan) |
| Edit Config (link) | `#0891b2` (cyan) |
| Cancel | `text-gray-400` |
| Retry | `#06244a` underline |

---

## KPI CARD STYLES

| Type | Accent | Background | Value Style |
|------|--------|------------|-------------|
| MetricCard | Top border 3px | `bg-white` | `text-2xl font-bold text-gray-800` |
| KpiBlock | None | `bg-gray-50` | `text-xl font-bold {color}` |
| ConfigItem | None | `bg-gray-50` | `font-medium text-gray-700` |
| StatusKpi | None | Transparent on dark bg | `text-xl font-bold {accent}` |

---

## BANNER / ALERT COLORS

| Type | Border | Background | Text |
|------|--------|------------|------|
| Error | `border-red-200` | `bg-red-50` | `text-red-600/700` |
| Warning | `border-yellow-200` | `bg-yellow-50` | `text-yellow-700/800` |
| Success | `border-green-200` | `bg-green-50` | `text-green-600/700` |
| Info / Remediation | `border-blue-200` | `bg-blue-50` | `text-blue-800` |
| Guardrails | `border-yellow-200` | `bg-yellow-50` | `text-yellow-800` |

---

## HEALTH INDICATORS

| Status | Dot Color | Label |
|--------|-----------|-------|
| Operativo | `bg-green-400` | "Operativo" |
| Degradado | `bg-yellow-400` | "Degradado" |
| Caido | `bg-red-400` | "Caido" |

---

## KEY INCONSISTENCIES

| # | Issue | Impact |
|---|-------|--------|
| 1 | `EXPORTED` badge missing from V2 StatusBadge — falls to gray | MISSING — queue records with EXPORTED status show gray |
| 2 | Program ACTIVE = blue in V2, green in legacy | MISMATCH — same concept, different colors |
| 3 | ExplainabilityTooltip only on MetricCard, not on TodayActionPlan or Queue | COVERAGE GAP |
| 4 | Freshness badge missing from Driver State sub-section | COVERAGE GAP |
| 5 | `decisionColors.js` unused in V2 | DEAD CODE |
| 6 | Export history `exported` vs `EXPORTED` case mismatch risk | POTENTIAL BUG |
| 7 | `draft_dry_run` (blue) ≈ `STRICT_PRIORITY` (blue) — similar tones, different concepts | AMBIGUITY |
