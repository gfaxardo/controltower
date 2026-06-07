# OV2-CX.2 — OPERATING DATE GOVERNANCE & SERVING PERFORMANCE

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Operating Date
> **Status:** **IMPLEMENTED**

---

## 1. EXECUTIVE SUMMARY

Omniview V2 now opens by default on `latest_closed_date` instead of today. A lightweight `/operating-date` endpoint (<500ms) provides the latest date with data. The default for 2026-06-06 is 2026-06-05 (the last day with CT data).

---

## 2. WHAT WAS DONE

| Task | Status |
|------|--------|
| `/ops/omniview-v2/operating-date` endpoint | Created — <500ms, single DB query |
| Frontend default date fix | On mount, fetches operating-date and sets date_from/date_to to latest_closed_date |
| Operating-date info bar | Shows "Latest closed: YYYY-MM-DD" when today has no data |
| Performance audit | Shell: 6.5s (reduced from 11s in CX.1E) |
| Serving Snapshot Design | Documented in OV2_CX2_SERVING_SNAPSHOT_DESIGN.md |

---

## 3. ENDPOINT: GET /ops/omniview-v2/operating-date

```json
{
  "latest_closed_date": "2026-06-05",
  "current_processing_date": "2026-06-06",
  "max_available_date": "2026-06-05",
  "has_today_data": false,
  "default_date": "2026-06-05",
  "source_system": "CT_TRIPS_2026",
  "freshness_status": "STALE"
}
```

---

## 4. FILES MODIFIED

| File | Change |
|------|--------|
| `omniview_v2.py` | +`/operating-date` endpoint |
| `OmniviewV2ShadowPage.jsx` | useEffect fetches operating-date on mount, sets default date |
| `api.js` | +`getOmniviewV2OperatingDate()` |
| `OV2_CX2_OPERATING_DATE_CONTRACT.md` | Created |
| `OV2_CX2_SERVING_SNAPSHOT_DESIGN.md` | Created |
| `OV2_CX2_RUNTIME_PERFORMANCE_AUDIT.md` | Created |

---

## 5. DEFAULT DATE BEHAVIOR

| Scenario | Default Date |
|----------|-------------|
| Today has data | Today |
| Today has no data | latest_closed_date (2026-06-05) |
| latest_closed_date changed | Info bar visible: "Latest closed: YYYY-MM-DD" |

---

## 6. PERFORMANCE

| Metric | Before | After |
|--------|--------|-------|
| Shell | 11s | 6.5s |
| Matrix | 0.8s | 0.8s |
| Operating-date | — | <500ms |
| Frontend load (default date) | Opens on empty date | Opens on latest_closed_date |

---

## 7. BUILD

| Check | Result |
|-------|--------|
| Frontend build | PASS (7.7s) |
| Backend py_compile | PASS |
| V1 intact | All chunks present |

---

## 8. DECISION

**GO** — Default date is latest_closed_date, page opens with data, operating-date endpoint <500ms.
