# Live LoopControl Export Report — 20260605

**Phase:** LG-C1.3E Live Smoke Test
**Date:** 2026-06-05 16:37:13

## Export Summary

| Field | Value |
|-------|-------|
| campaign_id_external | **120** |
| campaign_name | SMOKE_TEST_LC_5 |
| program_code | PROGRAM_CHURN_PREVENTION |
| opportunity_date | 2026-06-02 |
| contacts_sent | 5 |
| contacts_inserted | **5** |
| contacts_skipped | 0 |
| export_status | **exported** |
| mode | LIVE |
| HTTP response | 200 OK |
| LoopControl URL | api-betaleads.yego.pro |

## GO Criteria

- [x] campaign_id_external != null (value: 120)
- [x] contacts_inserted > 0 (value: 5)
- [x] contacts_skipped == 0
- [x] export_status == "exported"
- [x] HTTP 200 from LoopControl
- [x] LEDGER record created
- [x] Phones reales (+51 format)
- [x] Channels validos (BOT)

## Trace: 5 Contactos Exportados

1. 6a49ba1806f848d7bd8c — Franco Ismael — +51918****
2. 2b13da5c4c1a46d391d7 — Gonzalo Eduardo Cahu — +51975****
3. 8d07c3b020574995b887 — Guimarey Fernandez C — +51958****
4. 4e569aec6f4749b7bb10 — Medina Pimentel Darw — +51968****
5. 77076813bb39478d8bb4 — Paredes Zambrano — +51978****

## Verdict

**GO** — Live export successful. LoopControl integration operational.
