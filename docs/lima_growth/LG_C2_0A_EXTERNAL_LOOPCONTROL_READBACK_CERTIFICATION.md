# LG-C2.0A — External LoopControl Readback Certification

**Date:** 2026-06-08
**Motor:** Lima Growth Machine
**Phase:** LG-C2.0A
**Status:** EXTERNAL_READBACK_BLOCKED

---

## 1. EXECUTIVE SUMMARY

**EXTERNAL READBACK: BLOCKED.**

LoopControl external API is not configured. `LOOPCONTROL_BASE_URL` is empty, `integration_key` is not set, and `is_enabled` is false in the loopcontrol_config table. Manual result sync (C2.0) and controlled seed (C2.1B) work correctly. External readback requires LoopControl provider to expose a results endpoint and configuration to be activated.

---

## 2. CONFIGURATION AUDIT

| Setting | Value |
|---------|-------|
| `LOOPCONTROL_BASE_URL` (settings) | **EMPTY** |
| `LOOPCONTROL_INTEGRATION_KEY` (settings) | **NOT SET** |
| `loopcontrol_config.is_enabled` (DB) | **false** |
| `loopcontrol_config.base_url` (DB) | **EMPTY** |
| `loopcontrol_config.integration_key_configured` | **false** |

---

## 3. ENDPOINT PROBES

**NOT EXECUTED.** No base URL available to probe. All external API calls would fail with connection errors.

### Expected endpoint patterns (from export code):

```
POST {base_url}/callcenter/campaigns/external       — Export (exists in code)
GET  {base_url}/callcenter/campaigns/{id}/results    — Readback (to be verified)
GET  {base_url}/callcenter/campaigns/{id}/contacts   — Readback (to be verified)
GET  {base_url}/callcenter/campaigns/{id}            — Campaign detail (to be verified)
```

---

## 4. WHAT EXISTS

| Capability | Status |
|-----------|:---:|
| Manual sync (C2.0) | **WORKING** — POST /loopcontrol/results/sync |
| Controlled seed (C2.1B) | **WORKING** — 5/5 matched, idempotent |
| Browser visibility (C2.1) | **WORKING** — campaign selector, cards, table |
| External readback | **BLOCKED** — no API URL configured |

---

## 5. RECOMMENDED NEXT STEPS

When LoopControl provider enables API:

1. Set `LOOPCONTROL_BASE_URL` and `LOOPCONTROL_INTEGRATION_KEY` in .env
2. Enable `is_enabled` in `loopcontrol_config`
3. Probe results endpoints
4. Build mapping from external response to internal payload
5. Create readback service and endpoint
6. Test with campaign 121

---

## 6. READBACK SERVICE (Stub)

```python
def readback_results(campaign_id_external):
    if not base_url or not key:
        return {"error": "BLOCKED_EXTERNAL_READBACK_NOT_AVAILABLE"}
    
    resp = requests.get(
        f"{base_url}/callcenter/campaigns/{campaign_id_external}/results",
        headers={"X-Integration-Key": key}, timeout=10
    )
    if resp.status_code == 200:
        results = normalize_results(resp.json())
        return sync_results({"campaign_id_external": campaign_id_external, "results": results})
```

---

## 7. FINAL VERDICT

```
EXTERNAL_READBACK_BLOCKED
```

### Reason

LoopControl external API URL and credentials are not configured. Manual sync and controlled seed work. Browser visibility works. The infrastructure is ready. External readback is blocked by provider configuration.

### Impact

- Manual result sync (POST /loopcontrol/results/sync) continues to work
- Controlled sync via internal endpoint is fully functional
- Browser visibility shows all synced results
- No data loss risk

### GO for next phase

**APPROVED.** External readback is a provider dependency, not an application gap. Manual sync path is fully certified (C2.0 + C2.1B).
