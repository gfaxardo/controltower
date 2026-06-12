# LG-RNA-2A — RNA PRIORITY ENGINE CERTIFICATION

**Date:** 2026-06-12
**Phase:** LG-RNA-2A
**Status:** CERTIFIED

---

## 1. ARCHIVOS

| # | Archivo | Cambio |
|---|--------|--------|
| 1 | `backend/alembic/versions/217_yego_lima_rna_priority.py` | NUEVO — `growth.rna_priority_fact` |
| 2 | `backend/app/services/yego_lima_rna_priority_service.py` | NUEVO — Scoring engine + queries |
| 3 | `backend/app/routers/yego_lima_rna_priority.py` | NUEVO — 5 endpoints |
| 4 | `backend/app/main.py` | MODIFICADO — +1 import, +1 include_router |
| 5 | `frontend/src/pages/lima-growth-ui1a/sections/RNATab.jsx` | RESCRITO — Priority bands + HOT/WARM/COLD |

---

## 2. SCORING FORMULA (DETERMINISTIC, NO AI/ML)

| Signal | Weight | Description |
|--------|--------|-------------|
| contactable | +20 | Driver has phone — can be contacted |
| cancelled_signal | +15 | Previously cancelled — re-engagement potential |
| recent_activity | +15 | Had trips in last 7 days |
| high_value | +10 | Top 20% value tier |
| positive_momentum | +10 | Momentum is rising |
| has_program | +10 | Already assigned to a program |
| positive_movement | +5 | Recent positive movement score |
| trips_30d | +5 | Had trips in last 30 days (not 7d) |
| dormant_30d | −10 | No trips in 30+ days |
| churned_lifecycle | −15 | Lifecycle is CHURNED or DECLINING |

**Max possible score:** 85 | **Min possible score:** −25

---

## 3. PRIORITY BANDS

| Band | Score Range | Description |
|------|------------|-------------|
| HOT | ≥ 35 | High priority — contactable, recent activity, high value |
| WARM | 15–34 | Medium priority — some signals, moderate potential |
| COLD | < 15 | Low priority — dormant, churned, limited signals |

---

## 4. RNA PRIORITY FACT

**Table:** `growth.rna_priority_fact`

| Column | Description |
|--------|-------------|
| driver_profile_id | Unique per driver |
| rna_score | 0–85 numeric score |
| priority_band | HOT / WARM / COLD |
| contactable / cancelled_signal | Boolean signals |
| lifecycle / value_tier / momentum | From taxonomy |
| trips_7d / trips_30d | Activity data |
| days_since_last_trip | Recency |
| movement_score | From movement fact |
| program_code | From eligibility |
| signal_breakdown_json | Per-signal score breakdown (traceable) |

UPSERT on conflict — re-running `POST /build` updates existing scores.

---

## 5. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/yego-lima-growth/rna-priority/build` | Build/refresh all RNA priorities |
| `GET` | `/yego-lima-growth/rna-priority/summary` | HOT/WARM/COLD counts + bands |
| `GET` | `/yego-lima-growth/rna-priority/drivers?band=HOT` | Filtered drivers by band |
| `GET` | `/yego-lima-growth/rna-priority/driver/{id}` | Per-driver detail with signal breakdown |
| `GET` | `/yego-lima-growth/rna-priority/bands` | Band definitions + scoring weights |

---

## 6. EXPLAINABILITY

Every driver's score is traceable:
- `signal_breakdown_json` shows exactly which signals contributed
- `GET /driver/{id}` returns per-signal reasons
- `Why this priority score?` expandable section in RNA tab shows full formula

---

## 7. EXPORT INTEGRATION

"Export HOT" button in RNA tab filters HOT drivers. Reuses LG-EXP-1A export infrastructure.

---

## 8. BUILD

| Build | Result |
|-------|--------|
| Backend compile | PASS |
| Frontend `npm run build` | PASS (7.74s, 61 kB UI-1A, 7 tabs) |

---

## 9. VEREDICTO

### LG_RNA_2A_CERTIFIED

| Criterio | Status |
|----------|:---:|
| Scoring deterministic | PASS (10 rule-based signals) |
| Priority fact persisted | PASS (migration 217) |
| HOT/WARM/COLD visible | PASS (3-band display) |
| Signal breakdown traceable | PASS (signal_breakdown_json) |
| Export integrated | PASS |
| Explainability integrated | PASS |
| No AI / No ML | PASS |
| No runtime recalculation | PASS (persisted fact) |
| Build backend PASS | PASS |
| Build frontend PASS | PASS |

**LG-RNA-2A RNA Prioritization Engine: IMPLEMENTED AND CERTIFIED.**

---

## FIRMA

```
LG-RNA-2A RNA PRIORITY ENGINE CERTIFICATION
Date: 2026-06-12
Status: LG_RNA_2A_CERTIFIED
```
