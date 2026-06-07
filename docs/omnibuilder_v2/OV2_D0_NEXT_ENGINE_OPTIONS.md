# OV2-D.0 — NEXT ENGINE OPTIONS

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Roadmap Decision
> **Status:** OPTIONS EVALUATED

---

## OPTION A — Slice Governance Certification

| Attribute | Value |
|-----------|-------|
| **Objective** | Map Yango park to CT business slices for slice-level comparison |
| **Value** | High — enables true cost-per-slice analysis, cross-source slice validation |
| **Risk** | Medium — mapping may be approximate (park ≠ slice 1:1) |
| **Dependencies** | CT slice data active. Yango raw data active. No new APIs needed. |
| **Premature?** | No — this is Control Foundation work |
| **Effort** | Medium — 1 backend service + 1 migration |
| **GO/NO-GO** | **GO** — highest-value Control Foundation gap |

---

## OPTION B — Plan vs Real V2 Integration

| Attribute | Value |
|-----------|-------|
| **Objective** | Integrate Plan vs Real into Omniview V2 for CT source |
| **Value** | High — essential operational capability |
| **Risk** | Low — CT plan tables exist and are populated |
| **Dependencies** | CT day/week/month ready (done). Plan tables accessible. |
| **Premature?** | No — PvR is Control Foundation |
| **Effort** | Medium — extend matrix to include plan values + delta |
| **GO/NO-GO** | **GO** — second priority after Slice Governance |

---

## OPTION C — Multi-Park API Expansion

| Attribute | Value |
|-----------|-------|
| **Objective** | Add credentials and ingestion for additional Yango parks |
| **Value** | Medium — enables fleet-wide Yango data, not just Lima |
| **Risk** | Low — existing pipeline scales |
| **Dependencies** | Credentials for other parks (business decision, not technical) |
| **Premature?** | Yes — blocked on business providing credentials |
| **Effort** | Low once credentials available |
| **GO/NO-GO** | **WAITING** — blocked on credentials |

---

## OPTION D — Hourly Serving Activation

| Attribute | Value |
|-----------|-------|
| **Objective** | Activate CT hour grain (table exists, 0 rows) and create Yango hour MV |
| **Value** | Medium — hour-level operational visibility |
| **Risk** | Low for CT (table exists), medium for Yango (new MV) |
| **Dependencies** | CT hour_fact needs data ingestion. Yango needs new MV migration. |
| **Premature?** | Partially — CT hour has 0 rows. Yango hour requires MV creation. |
| **Effort** | Medium |
| **GO/NO-GO** | **CONDITIONAL** — CT hour only when data available. Yango hour deferred. |

---

## OPTION E — Human-in-the-loop UX QA

| Attribute | Value |
|-----------|-------|
| **Objective** | Gonzalo reviews Omniview V2 Shadow in browser, validates usability |
| **Value** | **CRITICAL** — prevents OMNI-P0 repeat (false GO without human validation) |
| **Risk** | High if skipped — same as OMNI-P0 false GO |
| **Dependencies** | Dev servers running. Gonzalo availability. |
| **Premature?** | No — this is the most urgent gap. Must happen before any further GO. |
| **Effort** | Low — 30-60 min review session |
| **GO/NO-GO** | **GO — MUST BE FIRST** |

---

## OPTION F — Source Canonical Decision

| Attribute | Value |
|-----------|-------|
| **Objective** | Decide whether Yango API can become canonical source |
| **Value** | Very high — unlocks operational decisions on API data |
| **Risk** | **CRITICAL** — premature canonicalization is the #1 architectural risk |
| **Dependencies** | ≥30 days Yango data, ≥99.5% coverage, delta <3% vs CT, slice mapping, revenue certification |
| **Premature?** | **YES** — none of the prerequisites are met |
| **Effort** | Governance decision, not code |
| **GO/NO-GO** | **NO-GO — PREMATURE** |

---

## COMPARISON MATRIX

| Option | Value | Risk | Premature? | Priority |
|--------|-------|------|------------|----------|
| E — Human QA | CRITICAL | High if skipped | NO | **1st** |
| A — Slice Governance | HIGH | Medium | NO | **2nd** |
| B — Plan vs Real V2 | HIGH | Low | NO | **3rd** |
| D — Hourly Serving | MEDIUM | Low/Medium | Partially | 4th |
| C — Multi-Park | MEDIUM | Low | Yes (creds) | Waiting |
| F — Canonical Decision | VERY HIGH | **CRITICAL** | **YES** | **DEFERRED** |
