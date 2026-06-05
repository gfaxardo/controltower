# LoopControl Export — LC-1

## Overview

Control Tower exports prioritized driver opportunities as DRAFT campaigns to LoopControl (call center dialer).

**Status: LC-1 COMPLETE — Production Ready**

---

## .env Configuration

```env
LOOPCONTROL_ENABLED=true
LOOPCONTROL_BASE_URL=https://api-betaleads.yego.pro/api
LOOPCONTROL_INTEGRATION_KEY=<key>
LOOPCONTROL_DEFAULT_SCHEDULE_DAYS=12345
```

`LOOPCONTROL_ENABLED=false` → DRY_RUN mode (no external HTTP calls).

---

## Endpoints

### Export Draft Campaign

```
POST /yego-lima-growth/loopcontrol/export-draft
Content-Type: application/json

{
  "opportunity_date": "2026-06-02",
  "program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
  "limit": 50,
  "campaign_name": "HV_REAL_50"
}
```

### Get Export History

```
GET /yego-lima-growth/loopcontrol/exports?limit=20
```

### Get Export Detail

```
GET /yego-lima-growth/loopcontrol/exports/{export_id}
```

### Validate Config

```
GET /yego-lima-growth/loopcontrol/config
```

---

## Payload Sent to LoopControl

### Campaign-level

| Field | Value |
|---|---|
| `name` | campaign_name (from request or auto-generated) |
| `description` | "Lima Growth {program} — {date} — {n} drivers" |
| `dialer_mode` | "predictive" |
| `max_concurrent` | 10 |
| `max_attempts` | 3 |
| `ring_timeout` | 30 |
| `schedule_start` | "09:00" |
| `schedule_end` | "18:00" |
| `schedule_days` | `"12345"` (string, NOT array) |
| `script` | Auto-generated descriptive text |

### Contact-level

| Field | Source |
|---|---|
| `external_id` | `_short_external_id(driver_profile_id)` — first 20 alphanumeric chars |
| `contractor_id` | Same as external_id |
| `phone` | `public.drivers.phone` (100% coverage) |
| `name` | `public.drivers.full_name` |
| `city` | `dim.dim_park.city` via `public.drivers.park_id` |
| `park_id` | `public.drivers.park_id` |
| `metadata` | JSON with: driver_profile_id, program, lifecycle, performance, orders_week, best_week, orders_30d, score, rank, bucket |

---

## Contact Source

### SQL Query

```sql
SELECT o.driver_profile_id, ..., d.phone, d.full_name, d.park_id, dp.city
FROM growth.yango_lima_prioritized_opportunity_daily o
LEFT JOIN public.drivers d ON d.driver_id = o.driver_profile_id
LEFT JOIN dim.dim_park dp ON dp.park_id = d.park_id
WHERE o.opportunity_date = ?
  AND o.is_actionable_today = true
  AND o.selected_program_code = ?
ORDER BY o.final_rank ASC
LIMIT ?
```

### Coverage

| Field | Coverage |
|---|---|
| phone | 100% (156K+ drivers) |
| name | 100% |
| city | 100% (all Lima) |
| park_id | 100% |

---

## Critical Fixes Applied

### 1. Schedule Days Format (LC-1.5)
`schedule_days` MUST be string `"12345"`, NOT array `["MON","TUE",...]`.
Array format causes LoopControl error: `value too long for type character varying(20)`.

### 2. Campaign ID Parsing (LC-1.6)
LoopControl nests the campaign ID: `response["data"]["campaign"]["id"]`.
Must parse nested path, not flat `response["id"]`.

### 3. Phone Resolution (LC-1.8)
Phones were hardcoded as empty string `""`. Now resolved via JOIN to `public.drivers`.
Before: `contacts_skipped = 10`. After: `contacts_skipped = 0`.

### 4. JSON Serialization (LC-1.2)
`make_json_safe()` converts Decimal → float, date/datetime → isoformat before POST.

### 5. Field Length Sanitization (LC-1.3)
`_sanitize_contact_fields()` enforces: external_id ≤ 20, contractor_id ≤ 20, document ≤ 20, phone ≤ 20, name ≤ 120, park_id ≤ 50, city ≤ 50.

---

## GO Criteria

- [x] `export_status = "exported"`
- [x] `campaign_id_external != null`
- [x] `contacts_inserted > 0`
- [x] `contacts_skipped = 0`

---

## Known Gaps (LC-2 Pending)

### Anti-Duplication
Exporting the same campaign_name + date creates a **new** campaign in LoopControl with duplicate contacts. No deduplication logic exists. Drivers could receive duplicate calls.

**Required:** Check if a campaign was already exported for the same date+program before allowing re-export.

### Result Sync
LoopControl campaign results (calls made, answered, outcomes) are not synced back to Control Tower.

**Required:** Endpoint from Miguel to pull campaign results → write to `growth.yango_lima_loopcontrol_campaign_result`.

### Campaign Name Convention
Current auto-generated name may exceed LoopControl limits for very long program names. Manual `campaign_name` parameter recommended.

### Document Field
`document` (DNI/ID) is not available in current data sources. Sent as empty. LoopControl may skip contacts without document.

---

## Files Modified

- `backend/app/services/yego_lima_loopcontrol_export_service.py` — Core export logic
- `backend/app/routers/yego_lima_loopcontrol_export.py` — API router
- `backend/.env` — Configuration

---

## Last Validated

2026-06-04 — Export test HV_REAL_50: 50 contacts inserted, 0 skipped, campaign ID 115.
