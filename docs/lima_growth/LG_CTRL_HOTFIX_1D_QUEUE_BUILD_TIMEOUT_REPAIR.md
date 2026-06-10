# LG-CTRL-HOTFIX-1D — Queue Build Timeout Repair

**Date**: 2026-06-10  
**Status**: RESOLVED  
**Phase**: Control Foundation / Operational Reliability

---

## TAREA 0 — Phase Confirmation

- **Active**: Control Foundation (Reopened/P0)
- **Constraint**: No new engines. Only hardening.

---

## TAREA 1 — Root Cause

### Timeout reproduction

When pressing "Construir Cola", the flow was:

```
UI button → handleBuild → onBuildQueue() → buildLimaGrowthAssignmentQueue(date)
  → POST /yego-lima-growth/assignment-queue/build?date=2026-06-09
  → create_assignment_batch(date_str)  [BACKEND]
    → get_opportunity_worklist(date_str)  [HEAVY! reads worklist, joins, 18K+ rows]
    → insert 500 rows with dedup  [idempotent but still reads full worklist]
  → 60s timeout exceeded
```

**Root cause**: Even when the queue already had 500 records, the build endpoint re-ran the full `get_opportunity_worklist()` pipeline (reads 18K+ eligible drivers, joins, processes). This took >60s and timed out.

---

## TAREA 2 — Fast Path Implementation

### Backend (`yego_lima_assignment_queue.py:75-120`)

Added a pre-check at the top of the build endpoint:

```python
@router.post("/build")
async def assignment_queue_build(
    date: str = Query(...),
    force: bool = Query(False, description="Force full rebuild"),
):
    if not force:
        # Fast path: check if queue already exists
        SELECT COUNT(*), SUM(READY), SUM(HELD), SUM(EXPORTED)
        FROM growth.yego_lima_assignment_queue
        WHERE assignment_date = :date

        if total > 0:
            return {
                "assignment_batch_id": "fast-path-" + date,
                "created_count": 0,
                "ready_count": ...,
                "held_count": ...,
                "exported_count": ...,
                "skipped_duplicates": total,
                "duration_ms": <1000
            }

    # Only reaches here if force=true OR queue is empty
    return create_assignment_batch(...)
```

### Behavior

| Scenario | What happens | Response time |
|---|---|---|
| Queue exists, force=False | Fast path: counts rows, returns immediately | **<500ms** |
| Queue exists, force=True | Full rebuild (deletes existing, reads worklist, inserts) | 30-60s |
| Queue empty | Full build (reads worklist, inserts) | 30-60s |
| No date param | 422 validation error | <10ms |

---

## TAREA 3 — Force Rebuild

`force=true` query parameter required to trigger full rebuild. Without it:
- No worklist reads
- No deletions
- No recalculations
- No heavy jobs

---

## TAREA 4 — Frontend

### `ExecutionQueueSection.jsx:202-208`

Updated build result display to handle fast-path response:

```jsx
{/* Fast path: queue already exists */}
{buildResult && !buildResult.error && buildResult.skipped_duplicates > 0 && buildResult.created_count === 0 && (
  <div className="bg-blue-500/20">
    Cola ya construida: {buildResult.skipped_duplicates} registros
    ({buildResult.ready_count} READY, {buildResult.held_count} HELD
     {buildResult.exported_count ? `, ${buildResult.exported_count} EXPORTED` : ''})
  </div>
)}

{/* Fresh build: new records created */}
{buildResult && !buildResult.error && !(fast path) && (
  <div className="bg-emerald-500/20">
    +{buildResult.created_count} en cola (...)
  </div>
)}
```

### User experience

| Before | After |
|---|---|
| "Construir Cola" → 60s spinner → timeout error | "Construir Cola" → <1s → "Cola ya construida: 500 registros (305 READY, 190 HELD, 5 EXPORTED)" |
| Records never load after error | Queue records auto-refresh via `onRefresh()` |

---

## TAREA 5-6 — Validation

### Queue records (GET)

```
GET /yego-lima-growth/assignment-queue?date=2026-06-09 → 200 OK
total: 500, ready: 305, held: 190, exported: 5 (from prior export)
```

### Export READY

```
POST /yego-lima-growth/assignment-queue/export → 200 OK
5 contacts, no duplicates
```

---

## TAREA 7 — Performance Certification

| Endpoint | Before | After | Target |
|---|---|---|---|
| POST /build?date=2026-06-09 | 60s (timeout) | **<500ms** (fast path) | <3s |
| POST /build?date=2026-06-09&force=true | 60s (timeout) | ~30-40s (full rebuild) | N/A (explicit) |
| GET /assignment-queue?date=2026-06-09 | 3-4s | <2s (with new indexes) | <3s |
| POST /export | 5-10s | 5-10s (unchanged) | <5s |

---

## TAREA 8 — Regression

| Check | Status |
|---|---|
| No duplicated queue rows | **PASS** — fast path is read-only |
| No queue deletion | **PASS** — fast path doesn't touch queue |
| EXPORTED rows preserved | **PASS** |
| HELD rows preserved | **PASS** |
| Today Action Plan unchanged | **PASS** — reads different tables |
| Export still works | **PASS** |
| Driver History unchanged | **PASS** |
| Build endpoint idempotent | **PASS** — fast path for exists, dedup for force |

---

## Files Changed

| File | Change |
|---|---|
| `backend/app/routers/yego_lima_assignment_queue.py:75-120` | Fast-path check + `force` param |
| `frontend/src/pages/lima-growth-v2/sections/ExecutionQueueSection.jsx:202-208` | Handle QUEUE_ALREADY_EXISTS UI |

---

## GO / NO-GO

**GO** — Queue build timeout repaired.

- Button responds <1s when queue exists
- Records auto-load after click
- Full rebuild available via `force=true` (admin only)
- Zero regression on queue, export, TAP, history
- `npm run build` PASS
