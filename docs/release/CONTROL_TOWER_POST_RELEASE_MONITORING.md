# CONTROL TOWER POST-RELEASE MONITORING PLAN

**Date**: 2025-05-25

---

## WHAT TO MONITOR

### Frontend Errors

| Signal | Tool | Threshold |
|---|---|---|
| Console errors in browser | Developer Tools / Error tracking | Any error → investigate |
| Network request failures | Network tab / API monitoring | > 5% failure rate → investigate |
| NaN appearing in cells | Visual inspection | Any NaN → fix formatter guard |
| Page freezes / hangs | User reports | Any report → investigate |

### API Performance

| Endpoint | Expected latency | Alert if |
|---|---|---|
| `omniview-projection` | < 10s | > 20s consistently |
| `omniview-momentum-drill` | < 5s | > 10s consistently |
| `matrix-operational-trust` | < 3s | > 5s consistently |
| `business-slice/filters` | < 2s | > 5s consistently |

### UX Signals

| Signal | How to detect |
|---|---|
| Operators using Evolution mode instead of Proyección | Mode toggle frequency (if tracked) |
| Operators collapsing many cities | Collapse button usage |
| Drill usage (do operators drill down?) | Cell click frequency |
| Confusion about momentum labels | Operator feedback |
| Cognitive overload | Operator report ("demasiada información") |

### Data Quality

| Signal | Check |
|---|---|
| False positives in deterioration strip | Compare vs actual operational events |
| Missing momentum data | Check if `periodPop` is null in backend response |
| Integrity broken warnings | `projectionMeta.integrity_status.status === 'broken'` |

---

## FEEDBACK COLLECTION (lightweight)

Without heavy analytics, capture:

1. **Operator verbal feedback** — record after each session
   - What was useful?
   - What was confusing?
   - What did you wish you could see?
   - What did you ignore?

2. **Screenshot capture** — at session start and after 2 minutes
   - Is the operator in Proyección or Evolution?
   - Is the current period visible?
   - Are cities expanded?

3. **Simple counter** (browser localStorage or backend log)
   - Mode toggle count (Proyección vs Evolution)
   - Drill open count
   - Fullscreen usage count

---

## FIRST 48 HOURS

| Time | Action |
|---|---|
| Hour 0 | Deploy, verify builds, confirm endpoints |
| Hour 1 | Operator acceptance script run-through |
| Hour 24 | Check for console errors, API latency, operator feedback |
| Hour 48 | Review feedback, decide if adjustments needed |

---

## FIRST WEEK

- Review all operator feedback
- Identify top 3 friction points
- Plan adjustments for next release cycle
- No new features — only fixes

---

## DECISION GATES

| After | Decision |
|---|---|
| 48 hours | Continue or rollback? |
| 1 week | GO for next phase? |
| 2 weeks | Begin next motor activation? |

## VERDICT: Monitoring plan documented — lightweight, no heavy analytics required
