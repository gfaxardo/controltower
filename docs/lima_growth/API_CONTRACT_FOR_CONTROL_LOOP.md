# API Contract for Control Loop — YEGO Lima Growth Tower

## Fase PP-0 — Production Pilot Handoff for Miguel

---

## A. Daily Flow

Every day the system generates a fresh list of actionable opportunities. Miguel's workflow:

```
1. Opportunities generated automatically (or POST /pipeline/run-daily)
2. GET /opportunities/daily → see today's list
3. For each driver: contact → register action → confirm
4. At end of day: close unmanaged with POST /opportunities/close-unmanaged
5. Build impact: POST /control-loop/build-daily-impact
6. Review: GET /executive/summary
```

---

## B. Key Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/opportunities/daily?opportunity_date=HOY&limit=50` | Get today's action list |
| POST | `/control-loop/actions` | Register an agent action |
| GET | `/control-loop/actions?action_owner=miguel` | View your actions |
| PATCH | `/control-loop/actions/{id}/status` | Update action status |
| POST | `/opportunities/close-unmanaged` | Close unmanaged from previous day |
| POST | `/control-loop/build-daily-impact` | Build impact metrics |
| GET | `/control-loop/agent-performance-summary` | View your performance |
| GET | `/control-loop/driver-impact-timeline/{id}` | View driver history |
| GET | `/executive/summary` | View overall dashboard |

---

## C. Opportunity Types

### OPPORTUNITY_14_90
Early-life drivers: new or recently reactivated, still within 14/90 day window.
**Goal**: Activate and accelerate new drivers.

### OPPORTUNITY_ACTIVE_GROWTH
Underperforming drivers: LOW or MEDIUM performance, below weekly target.
**Goal**: Increase trips to reach target.

### OPPORTUNITY_CHURN_PREVENTION
At-risk drivers: declining performance, churn risk flags active.
**Goal**: Retain, prevent churn.

---

## D. Management Statuses

| Status | Meaning | When |
|--------|---------|------|
| `PENDING_ACTION` | No action taken yet | Start of day |
| `ACTION_CONFIRMED` | Agent contact confirmed successful | After successful contact |
| `ACTION_ATTEMPTED` | Agent tried but couldn't confirm | After attempted contact |
| `ACTION_NOT_CONFIRMED` | Explicitly not confirmed | Driver declined |
| `NO_ACTION` | Closed without action | End of day, auto-close |
| `DISMISSED` | Manually dismissed | Agent decision |

---

## E. Registering an Action

```
POST /yego-lima-growth/control-loop/actions
```

```json
{
  "driver_profile_id": "0693351ce23d43db8ff0d5a691fbaaf7",
  "action_date": "2026-06-02",
  "action_type": "WHATSAPP_CALL",
  "source_segment_snapshot_date": "2026-06-02",
  "list_date": "2026-06-02",
  "list_type": "LEALTAD_2_ACTIVE_GROWTH",
  "action_channel": "WHATSAPP",
  "action_owner": "miguel",
  "action_status": "attempted",
  "action_confirmed": true,
  "confirmation_source": "WHATSAPP_REPLY",
  "action_reason": "low_trips_this_week",
  "campaign_code": "PILOT_W1",
  "notes": "Driver committed to do 15+ trips this week"
}
```

Response:
```json
{
  "ok": true,
  "action_id": "a1b2c3d4-..."
}
```

---

## F. Closing Unmanaged Items

At end of day, any PENDING_ACTION items become NO_ACTION:

```
POST /yego-lima-growth/opportunities/close-unmanaged
```

```json
{
  "opportunity_date": "2026-06-02"
}
```

Response:
```json
{
  "ok": true,
  "opportunity_date": "2026-06-02",
  "items_closed": 25
}
```

---

## G. Consulting Impact

After actions are registered:

```
POST /yego-lima-growth/control-loop/build-daily-impact
```

```json
{
  "impact_date": "2026-06-02"
}
```

Then view driver timeline:

```
GET /yego-lima-growth/control-loop/driver-impact-timeline/{driver_profile_id}?limit=10
```

---

## H. Consulting Agent Performance

```
GET /yego-lima-growth/control-loop/agent-performance-summary?date_from=2026-06-01&date_to=2026-06-02&action_owner=miguel
```

Returns: assigned items, confirmed, attempted, confirmation rate, avg delta orders, moved segments, reactivated count.

---

## I. Opportunity Types Reference

### OPPORTUNITY_14_90
```json
{
  "driver_profile_id": "abc123...",
  "opportunity_type": "OPPORTUNITY_14_90",
  "program_code": "PROGRAM_14_90",
  "lifecycle_state": "EARLY_LIFE",
  "completed_orders_week": 5,
  "distance_to_weekly_target": 45,
  "management_status": "PENDING_ACTION"
}
```

### OPPORTUNITY_ACTIVE_GROWTH
```json
{
  "driver_profile_id": "def456...",
  "opportunity_type": "OPPORTUNITY_ACTIVE_GROWTH",
  "program_code": "PROGRAM_ACTIVE_GROWTH",
  "lifecycle_state": "ESTABLISHED",
  "performance_state": "LOW",
  "completed_orders_week": 12,
  "distance_to_weekly_target": 38,
  "management_status": "PENDING_ACTION"
}
```

### OPPORTUNITY_CHURN_PREVENTION
```json
{
  "driver_profile_id": "ghi789...",
  "opportunity_type": "OPPORTUNITY_CHURN_PREVENTION",
  "program_code": "PROGRAM_CHURN_PREVENTION",
  "retention_state": "CHURN_RISK",
  "lifecycle_state": "ESTABLISHED",
  "completed_orders_week": 3,
  "distance_to_weekly_target": 47,
  "management_status": "PENDING_ACTION"
}
```

---

## J. Quick Start Commands

```bash
# Get today's full list
curl -s "http://localhost:8000/yego-lima-growth/opportunities/daily?opportunity_date=2026-06-02&limit=10" | python -m json.tool

# Get active growth opportunities only
curl -s "http://localhost:8000/yego-lima-growth/opportunities/daily?opportunity_date=2026-06-02&opportunity_type=OPPORTUNITY_ACTIVE_GROWTH&limit=5" | python -m json.tool

# Register a confirmed action
curl -s -X POST "http://localhost:8000/yego-lima-growth/control-loop/actions" \
  -H "Content-Type: application/json" \
  -d '{"driver_profile_id":"...","action_date":"2026-06-02","action_type":"WHATSAPP_CALL","source_segment_snapshot_date":"2026-06-02","list_date":"2026-06-02","list_type":"LEALTAD_2_ACTIVE_GROWTH","action_owner":"miguel","action_status":"attempted","action_confirmed":true,"confirmation_source":"WHATSAPP_REPLY","campaign_code":"PILOT_W1"}' | python -m json.tool

# See executive summary
curl -s "http://localhost:8000/yego-lima-growth/executive/summary?date=2026-06-02" | python -m json.tool

# Check your performance
curl -s "http://localhost:8000/yego-lima-growth/control-loop/agent-performance-summary?date_from=2026-06-01&date_to=2026-06-02&action_owner=miguel" | python -m json.tool
```
