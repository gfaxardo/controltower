# CT-GOV-043 — Global Waterfall Contract

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. UNIVERSAL WATERFALL

```
                    ┌─────────────────────────┐
                    │      RAW SOURCE           │
                    │  Yango API / trips_2026   │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │      NORMALIZED / MV       │
                    │  orders_raw / day_fact      │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │        HISTORY             │
                    │  driver_history_weekly     │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │        SNAPSHOT            │
                    │  driver_state_snapshot     │
                    │  serving_snapshot          │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │     OPERATIONAL LAYERS     │
                    │  eligibility / prioritized │
                    │  queue / day_fact          │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │      SERVING FACTS         │
                    │  serving_fact (8 types)    │
                    │  matrix / shell            │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │           UI               │
                    │  Lima Growth / Omniview    │
                    └───────────────────────────┘
```

---

## 2. VALIDATION RULES PER TRANSITION

### RAW → NORMALIZED

```
Rule: raw date >= normalized date
Violation: normalized has data that raw doesn't → data fabrication risk
```

### NORMALIZED → HISTORY

```
Rule: history source date >= normalized max date
Violation: history was built from a different source → lineage break
```

### HISTORY → SNAPSHOT

```
Rule: snapshot layer_date >= history max date
Rule: snapshot effective_source_date = history max date
Violation: STALE_PROPAGATED — snapshot built from stale history
```

### SNAPSHOT → OPERATIONAL

```
Rule: eligibility date = snapshot date
Rule: prioritized date >= eligibility date
Violation: layers out of sync
```

### OPERATIONAL → SERVING

```
Rule: serving fact_date = max operational date
Rule: serving generated_at >= last pipeline success
Violation: serving facts stale
```

### SERVING → UI

```
Rule: UI reads from serving (serving-first)
Rule: UI shows effective_source_date, not layer_date
Violation: UI shows false freshness (layer_date > effective_source_date)
```

---

## 3. CROSS-DOMAIN CONSISTENCY

| Check | Omniview | Lima Growth |
|-------|:---:|:---:|
| RAW layer defined | trips_2026 | orders_raw |
| Normalization defined | day_fact | normalizer |
| Snapshot defined | serving_snapshot | driver_state_snapshot |
| Serving facts defined | matrix/shell | 8 fact types |
| UI reads from serving | YES | YES (4 of 7) |
| Effective source date exposed | NO (gap) | YES (R3.0E) |
| STALE_PROPAGATED detection | NO (gap) | YES |

---

## 4. MINIMUM CERTIFICATION

Before any GO:

- [ ] All 6 waterfall transitions validated
- [ ] No transition shows parent.stale > child.fresh
- [ ] All effective_source_dates traceable to raw source
- [ ] No hidden fallbacks (explicit defaults only)
- [ ] Serving facts exist for latest operational date

---

## FIRMA

```
CT-GOV-043 GLOBAL WATERFALL CONTRACT
Date: 2026-06-08
Status: CANONICAL
```
