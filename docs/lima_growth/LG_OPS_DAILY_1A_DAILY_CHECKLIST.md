# LG-OPS-DAILY-1A — DAILY OPERATING CHECKLIST

**Phase:** Data Accumulation Period
**Status:** ACTIVE

---

## DAILY CHECKLIST (5 MINUTES)

### 1. Scheduler Health
- [ ] Scheduler running: `GET /growth/health` → scheduler_status = RUNNING
- [ ] Tick count increasing: verify `tick_count` increments from previous day
- [ ] No CRITICAL errors in scheduler logs

### 2. Data Freshness
- [ ] `driver_state_snapshot`: fresh to today
- [ ] `program_eligibility`: fresh to today
- [ ] `lifecycle_daily`: max date within 2 days
- [ ] `taxonomy_v2`: max date within 2 days
- [ ] `movement_fact`: snapshot count increasing

### 3. RNA Priority
- [ ] Run `POST /yego-lima-growth/rna-priority/build` (if not automated)
- [ ] HOT/WARM/COLD counts available: `GET /yego-lima-growth/rna-priority/summary`

### 4. Pilot Measurement
- [ ] Run `POST /yego-lima-growth/rna-pilot/build` (if new contact data)
- [ ] Data quality distribution visible

### 5. Dashboard
- [ ] `http://localhost:5173/lima-growth/intelligence` loads
- [ ] FreshnessBanner shows HEALTHY or WARNING (not CRITICAL)
- [ ] 7 tabs render
- [ ] No console errors (JS)
- [ ] No network errors (4xx/5xx)

### 6. Export
- [ ] `POST /yego-lima-growth/export` works (test with 1 row if possible)
- [ ] Audit log records new export

### 7. Build (if changes)
- [ ] `python -m compileall app` — PASS
- [ ] `npm run build` — PASS

---

## WEEKLY CHECKLIST (15 MINUTES)

### 1. Movement Accumulation
- [ ] Movement snapshots: count days since last build
- [ ] Coverage % trending up

### 2. Effectiveness Trend
- [ ] Scorecard: net_effect per program
- [ ] Improvements / declines trending

### 3. RNA Pilot
- [ ] Contact outcomes from LoopControl
- [ ] Conversion rates by band

### 4. Backlog Review
- [ ] No new P0 issues
- [ ] LG-OPS-1A (DB stability) still contained
- [ ] LG-PERF-1A (health latency) still acceptable

---

## INCIDENT LOG

| Date | Incident | Impact | Resolution |
|------|----------|--------|-----------|
| | | | |
