# LG — Operational Refresh Contract

**Date:** 2026-06-06
**Phase:** LG-INFRA-R1.2 — CANONICAL CONTRACT

---

## CYCLE A: DAILY CLOSED PIPELINE

**Frequency:** Once per day, after operational data close (~00:01 Lima time or when prior day data becomes available).

**Input:** `closed_operational_data_date` from Yango API.

**Responsible for:**
- eligible_universe
- driver_360 daily
- driver_state_snapshot
- program_eligibility
- prioritized_opportunities (base list for the day)
- base assignment queue
- serving facts (8 types)
- Today Action Plan for the day

**Idempotency:** Can be re-run safely. Does not mutate exported records. Replaces only draft/base layers for the target date.

**Trigger:** Manual (POST /scheduler/run-daily-closed) or auto-detected by scheduler when new closed date appears.

---

## CYCLE B: LIVE 5-MIN MONITORING

**Frequency:** Every 5 minutes throughout the day.

**Input:** Current timestamp, recent Yango API data (orders, supply_hours).

**Responsible for:**
- Yango API incremental ingestion
- raw_yango MVs refresh
- Activity/trip/supply detection post-action
- Result signal updates (optional, backlog)
- Freshness/governance heartbeat
- Campaign/batch status tracking

**NOT responsible for:**
- NO eligibility rebuild
- NO prioritization rebuild
- NO queue rebuild
- NO program recalculation
- NO campaign export
- NO Action Engine
- NO list reordering

---

## SEPARATION RULES

| Operation | Daily Closed | Live 5-Min |
|-----------|:---:|:---:|
| Build eligible_universe | YES | NO |
| Build driver_360 | YES | NO |
| Build snapshot | YES | NO |
| Build eligibility | YES | NO |
| Build prioritized | YES | NO |
| Build base queue | YES | NO |
| Generate serving facts | YES | NO |
| Ingest Yango API | — | YES |
| Refresh raw_yango MVs | — | YES |
| Monitor action results | — | YES |
| Update governance | YES | YES |
| Maintain freshness | — | YES |

---

## PRE-WARM CONTRACT

The live 5-min loop maintains Yango API data fresh throughout the day. When midnight arrives:

- raw_yango is already fresh (last ingestion < 5 min ago)
- MVs are already fresh
- Activity cache is warm

The Daily Closed Pipeline only needs to build operational layers — it never re-ingests history that was already maintained during the day.

---

## MIDNIGHT + 1 CONTRACT

At 00:01 Lima time:

1. Create new `today_action_date`
2. Detect latest `closed_operational_data_date`
3. If data is available: run Daily Closed Pipeline
4. If data is not available: status = WAITING_FOR_CLOSED_DATA, retry each tick
5. When data appears: auto-run Daily Closed Pipeline
6. Today Action Plan becomes OPERABLE

---

## ENDPOINTS

| Method | Path | Mode |
|--------|------|------|
| GET | /scheduler/status | Both |
| POST | /scheduler/start | Both |
| POST | /scheduler/stop | Both |
| POST | /scheduler/tick | Live Monitoring |
| POST | /scheduler/run-daily-closed | Daily Pipeline |
| POST | /scheduler/run-live-monitoring | Live Monitoring |
