# LG-EXP-1A — SAFE COLUMNS POLICY

**Date:** 2026-06-12

---

## EXPORTABLE COLUMNS

| # | Column | Sensitive? | Justification |
|---|--------|:---:|------|
| 1 | driver_id | NO | Opaque internal ID |
| 2 | driver_name | LOW | Required for operator identification |
| 3 | phone | MEDIUM | Required for contact operations |
| 4 | city | NO | Operational segmentation |
| 5 | park | NO | Operational segmentation |
| 6 | lifecycle | NO | Operational status |
| 7 | segment | NO | Operational segment |
| 8 | activity_status | NO | Activity classification |
| 9 | value_tier | NO | Value percentile |
| 10 | momentum | NO | Trend indicator |
| 11 | program | NO | Program assignment |
| 12 | movement_status | NO | Movement status |
| 13 | rna_status | NO | RNA flag |
| 14 | contactability | LOW | Has phone? Boolean |
| 15 | last_activity | LOW | Date only, no PII |
| 16 | trips_7d | NO | Aggregate count |
| 17 | trips_30d | NO | Aggregate count |
| 18 | explanation_summary | NO | Text explanation |

## FORBIDDEN COLUMNS

- Credentials / passwords
- Internal audit trails (full evidence_json)
- Raw financial data
- Personal documents / ID numbers (beyond phone)
- System logs / tokens

## ENFORCEMENT

- Backend whitelists columns via `SAFE_COLUMNS` constant
- Only columns in the whitelist are included in CSV output
- Unknown columns are silently dropped
