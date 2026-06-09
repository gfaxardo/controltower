# CT-GOV-043 — Runtime Certification Standard

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. PURPOSE

Every module in Control Tower must expose its runtime identity to enable:
- Traceability of which code version produced data
- Correlation of bugs to specific deployments
- Rollback safety
- Audit trail for governance certification

---

## 2. REQUIRED FIELDS

Every module's `/identity` or `/health` endpoint MUST return:

```json
{
  "module": "lima_growth",
  "version": "2.0.0",
  "git_hash": "a1b2c3d",
  "build_time": "2026-06-08T00:00:00Z",
  "backend_instance": "lima-growth-worker-1",
  "runtime": "python-3.13",
  "environment": "production",
  "source_system": "YANGO_API_LIVE"
}
```

### Field Definitions

| Field | Required | Description |
|-------|:---:|-------------|
| `module` | YES | Module name (lima_growth, omniview, loyalty, etc.) |
| `version` | YES | Semantic version from build |
| `git_hash` | YES | Short commit hash of deployed code |
| `build_time` | YES | ISO 8601 timestamp of build |
| `backend_instance` | YES | Unique instance identifier |
| `runtime` | YES | Language + version |
| `environment` | YES | dev / staging / production |
| `source_system` | YES | Canonical data source |

---

## 3. MODULE REGISTRY

| Module | Endpoint | Status |
|--------|----------|:---:|
| Lima Growth | `/yego-lima-growth/health` or `/` | PARTIAL (no git_hash) |
| Omniview | `/ops/omniview-v2/backend-identity` | EXISTS |
| Loyalty | `/yango-loyalty/...` | UNKNOWN |
| Core API | `/` | EXISTS (version only) |

---

## 4. DATA LINEAGE TAG

Every data generation event (pipeline run, refresh, snapshot build) must record:

```json
{
  "run_id": "<uuid>",
  "git_hash": "a1b2c3d",
  "build_time": "2026-06-08T00:00:00Z",
  "module": "lima_growth",
  "trigger": "scheduler_tick | manual | catch_up",
  "source_system": "YANGO_API_LIVE"
}
```

### Where to record

| Operation | Table | Column |
|-----------|-------|--------|
| Pipeline run | `pipeline_run_log` | git_hash column (add) |
| Refresh run | `refresh_run_log` | git_hash column (add) |
| Serving fact gen | `serving_fact` | source_run_id (exists) |
| Tick log | `scheduler_tick_log` | raw_result_json (exists) |
| History snapshot | `driver_list_history` | evidence_json (exists) |

---

## 5. COMPLIANCE CHECKLIST

| Check | Lima Growth | Omniview |
|-------|:---:|:---:|
| Version exposed | YES (`/` returns 2.0.0) | PARTIAL |
| Git hash exposed | NO | NO |
| Build time exposed | NO | NO |
| Backend instance exposed | NO | PARTIAL |
| Source system exposed | YES (YANGO_API_LIVE) | PARTIAL (CT_TRIPS_2026) |
| Run ID in pipeline logs | YES | YES |
| Git hash in data generation | NO (gap) | NO (gap) |

---

## FIRMA

```
CT-GOV-043 RUNTIME CERTIFICATION STANDARD
Date: 2026-06-08
Status: CANONICAL — gaps documented
```
