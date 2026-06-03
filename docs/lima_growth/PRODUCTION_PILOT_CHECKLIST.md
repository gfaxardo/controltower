# Production Pilot Checklist — YEGO Lima Growth Tower

## Fase PP-0 — Miguel Handoff

---

## 1. Required Environment Variables

| Variable | Default | Required | Notes |
|----------|---------|----------|-------|
| `DB_HOST` | localhost | Yes | PostgreSQL host |
| `DB_PORT` | 5432 | Yes | |
| `DB_NAME` | yego_integral | Yes | |
| `DB_USER` | - | Yes | |
| `DB_PASSWORD` | - | Yes | |
| `YANGO_LIMA_PARK_ID` | 08e20910... | Yes | Lima fleet park_id |
| `LIMA_GROWTH_WEEKLY_TRIPS_TARGET` | 50 | Yes | Target trips |
| `LIMA_GROWTH_API_CUTOVER_DATE` | 2026-06-01 | Yes | Historical cutover |
| `YANGO_API_ENABLED` | false | No | Only if using API pipeline |
| `CT_SCHEDULER_ENABLED` | false | **Must be false** | No auto scheduler |

---

## 2. Database Setup

```bash
cd backend
alembic upgrade head
```

Expected: `173_yego_lima_driver_360_stabilization` (or higher)

---

## 3. Backend Start

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:
- `/docs` loads Swagger UI
- `/health` returns `{"status": "ok"}`
- `/yego-lima-growth/executive/freshness` returns all layers

---

## 4. Pilot Scope

- **1 agent**: Miguel
- **1 list type**: OPPORTUNITY_ACTIVE_GROWTH (start simple)
- **5-10 drivers per day**: manageable batch
- **3 days**: pilot duration
- **Action channels**: WhatsApp, Llamada
- **Campaign**: `PILOT_W1`

---

## 5. Daily Pilot Routine

### Morning (9am)
```bash
# 1. Build today's opportunities
curl -X POST http://localhost:8000/yego-lima-growth/opportunities/build-daily \
  -H "Content-Type: application/json" \
  -d '{"opportunity_date":"2026-06-03"}'

# 2. Get today's list (5 drivers)
curl "http://localhost:8000/yego-lima-growth/opportunities/daily?opportunity_date=2026-06-03&opportunity_type=OPPORTUNITY_ACTIVE_GROWTH&limit=5"
```

### During Day (contact drivers)
```bash
# 3. Register action after contacting driver
curl -X POST http://localhost:8000/yego-lima-growth/control-loop/actions \
  -H "Content-Type: application/json" \
  -d '{"driver_profile_id":"DRIVER_ID","action_date":"2026-06-03","action_type":"WHATSAPP_CALL","source_segment_snapshot_date":"2026-06-03","list_date":"2026-06-03","list_type":"LEALTAD_2_ACTIVE_GROWTH","action_owner":"miguel","action_status":"attempted","action_confirmed":true,"confirmation_source":"WHATSAPP_REPLY","campaign_code":"PILOT_W1"}'
```

### Evening (5pm)
```bash
# 4. Close unmanaged from yesterday
curl -X POST http://localhost:8000/yego-lima-growth/opportunities/close-unmanaged \
  -H "Content-Type: application/json" \
  -d '{"opportunity_date":"2026-06-02"}'

# 5. Build impact
curl -X POST http://localhost:8000/yego-lima-growth/control-loop/build-daily-impact \
  -H "Content-Type: application/json" \
  -d '{"impact_date":"2026-06-03"}'

# 6. Review performance
curl "http://localhost:8000/yego-lima-growth/control-loop/agent-performance-summary?date_from=2026-06-01&date_to=2026-06-03&action_owner=miguel"
```

---

## 6. Rollback Plan

If issues arise:
1. Stop registering new actions
2. Existing data stays in DB (historical)
3. Can delete test data: `DELETE FROM growth.yango_lima_driver_action_registry WHERE campaign_code = 'PILOT_W1'`
4. Opportunity lists regenerate fresh each day (no stale state)

---

## 7. Smoke Test (Automated)

```bash
curl -X POST http://localhost:8000/yego-lima-growth/pilot/smoke-test \
  -H "Content-Type: application/json" \
  -d '{"run_date":"2026-06-03","max_drivers":50,"dry_run":false}'
```

Should return `overall_status: "success"` with all steps passing.

---

## 8. What NOT to Touch

- Omniview UI
- Plan vs Real
- week_fact
- business_slice
- trips_2026 in runtime (only for backfill)
- Dashboard (not built yet)
- Scheduler (manual only)

---

## 9. Success Criteria for Pilot

After 3 days:
- [ ] Opportunities generated each day
- [ ] At least 5 actions registered per day
- [ ] Confirmation rate > 30%
- [ ] Impact metrics available (delta orders vs baseline)
- [ ] Executive summary shows state_based source
- [ ] No errors in server logs
- [ ] No performance degradation in other endpoints
- [ ] Miguel can operate independently

---

## 10. API Map Reference

```
GET  /yego-lima-growth/pilot/api-map
```

Returns full endpoint catalog with descriptions, parameters, and examples.

---

## 11. Support Contacts

- Backend issues: Check `/health` and `/executive/freshness`
- Pipeline issues: Check `/pipeline/status` and run `/pipeline/consistency-check`
- Data issues: Run `/lab/history-continuity-check`
- Rebuild: `/lab/rebuild-history-until-cutover` (be careful)
