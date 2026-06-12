# OV2-MVP.1B — OPERATIONAL SIGNAL CONTRACT

> **Fase:** OV2-MVP.1B — Operational Signal Layer
> **Sub-document:** Signal Contract
> **Fecha:** 2026-06-12

---

## 1. PRINCIPLE

La señal visual interpreta el estado operacional. NO explica causas. NO genera recomendaciones.

Cada señal opera con metadata existente de endpoints productivos:
- `/ops/omniview-v2/shell`
- `/ops/omniview-v2/matrix`
- `/ops/omniview-v2/health`
- `/ops/omniview-v2/operating-date`
- `/ops/omniview-v2/backend-identity`

Sin inventar confianza. Sin runtime pesado.

---

## 2. DELTA SIGNALS (variación vs periodo anterior)

| Signal | Condition | Icon | Color | CSS Token |
|--------|-----------|------|-------|-----------|
| **UP** | delta_value > 0 | ▲ | `#16a34a` (green-600) | `--sig-up` |
| **DOWN** | delta_value < 0 | ▼ | `#dc2626` (red-600) | `--sig-down` |
| **FLAT** | delta_value == 0 and real > 0 | → | `#6b7280` (gray-500) | `--sig-flat` |
| **NO_COMPARISON** | no delta available | — | `#d1d5db` (gray-300) | `--sig-missing` |

---

## 3. HEALTH SIGNALS (estado de datos)

| Signal | Condition | Badge | Color | CSS Token |
|--------|-----------|-------|-------|-----------|
| **HEALTHY** | freshness <= 1d, coverage >= 95% | OK | `#16a34a` | `--sig-healthy` |
| **WARNING** | freshness 1-3d or coverage 80-95% | WARN | `#f59e0b` (amber-500) | `--sig-warning` |
| **STALE** | freshness > 3d | STALE | `#dc2626` | `--sig-stale` |
| **MISSING** | value is None/NULL | N/A | `#9ca3af` (gray-400) | `--sig-missing` |
| **FALLBACK_USED** | canonical_ready=false | FALLBACK | `#f59e0b` | `--sig-fallback` |
| **NOT_CERTIFIED** | source_badge = SHADOW | SHADOW | `#6b7280` | `--sig-shadow` |

---

## 4. PLAN SIGNALS (ejecución vs plan)

| Signal | Condition | Icon | Color | CSS Token |
|--------|-----------|------|-------|-----------|
| **AHEAD** | attainment_pct >= 110% | ▲▲ | `#16a34a` | `--sig-ahead` |
| **ON_TRACK** | 90% <= attainment_pct < 110% | ✓ | `#16a34a` | `--sig-on-track` |
| **BEHIND** | attainment_pct < 90% | ▼▼ | `#dc2626` | `--sig-behind` |
| **NO_PLAN** | plan_status = MISSING | — | `#9ca3af` | `--sig-no-plan` |

---

## 5. SOURCE SIGNALS

| Signal | Condition | Badge Label | Color |
|--------|-----------|-------------|-------|
| **CT_BRIDGE** | source_system = CT_TRIPS_2026, canonical_ready = true | CT | `#16a34a` |
| **YANGO_API** | source_system = YANGO_API_RAW | YANGO | `#8b5cf6` (violet-500) |
| **SHARED** | metric uses blended sources | SHARED | `#3b82f6` (blue-500) |
| **FALLBACK_CT** | Yango unavailable, using CT fallback | CT* | `#f59e0b` |
| **NOT_AVAILABLE** | source not providing this metric | N/A | `#9ca3af` |

---

## 6. IMPLEMENTATION RULES

1. **All signals derived from existing API data** — no new endpoints.
2. **No signal when data insufficient** — show UNKNOWN badge, don't guess.
3. **Signal colors use CSS custom properties** (`--sig-*` tokens in `MatrixVisualSystem.css`).
4. **Delta values use `cell.comparison_status` and `cell.delta_value`** from MatrixResponse.
5. **Health uses `shell.coverage` + `operating_date.freshness_status`**.
6. **Plan uses `plan-real/monthly` response**.
7. **Source uses `cell.source_system` + `cell.canonical_ready` + `cell.source_badge`**.

---

## 7. CELL RENDERING ORDER

```
[SourceBadge] [TrustBadge]
[KPI Value] [DeltaArrow] [DeltaValue]
[PlanValue] [GapValue] [Attainment%] [PlanStatus]
[CoverageBadge] [FreshnessBadge] [FallbackBadge]
```

Compact mode (default matrix cell):
```
[Value] [DeltaArrow] [PlanStatusBadge]
```

Expanded mode (cell inspector):
```
Full rendering order
```
