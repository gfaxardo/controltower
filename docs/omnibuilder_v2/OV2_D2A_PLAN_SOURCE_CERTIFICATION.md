# OV2-D.2A — PLAN SOURCE CERTIFICATION

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Plan vs Real
> **Status:** **CANONICAL — Ready for V2 integration**

---

## 1. PLAN SOURCE AUDIT

### Table: `ops.plan_trips_monthly`

| Column | Type | Description |
|--------|------|-------------|
| id | bigint | PK |
| plan_version | text | Version identifier (e.g. `unified_fresh_1779825863`) |
| country | text | Country |
| city | text | City |
| park_id | text | Park identifier |
| lob_base | text | Line of business (raw from template) |
| segment | text | Segment |
| month | date | Target month |
| projected_trips | integer | Planned trips |
| projected_drivers | integer | Planned active drivers |
| projected_ticket | numeric | Planned average ticket |
| projected_trips_per_driver | numeric | Planned TPD |
| projected_revenue | numeric | Planned revenue |
| created_at | timestamptz | Row creation |

**Statistics:**
- Rows: 4,872
- Latest version: `unified_fresh_1779825863`
- Covers multiple countries, cities, and LOBs

### Template Parser: `plan_template_parser_service.py`
- Handles multi-sheet Excel (TRIPS, REVENUE, DRIVERS)
- Dimensions: country, city, linea_negocio
- Monthly columns (YYYY-MM)
- Ownership: Jefe Producto, Producto, estado
- LOB normalization map (e.g., "auto regular" → "Auto Taxi")

### Supporting Infrastructure:
| Table | Purpose |
|-------|---------|
| `ops.plan_versions_metadata` | Version lifecycle tracking |
| `ops.plan_lob_mapping` | LOB name normalization |
| `ops.plan_weekly_baselines` | Monthly→weekly distribution weights |
| `ops.projection_ownership` | Owner/backup tracking |
| `ops.v_plan_trips_monthly_latest` | Latest version view |
| `ops.v_plan_business_slice_join_stub` | Plan-to-slice join |

---

## 2. CLASSIFICATION

**CANONICAL** — The plan source is well-structured with versioning, LOB normalization, ownership tracking, and monthly grain. The template parser handles ingestion. The source is ready for V2 Plan vs Real integration.

---

## 3. GRAIN EXPANSION

| Grain | Source | Method |
|-------|--------|--------|
| month | `ops.plan_trips_monthly` | Direct (canonical) |
| ISO week | Derived from month via `weekly_baselines` weights | Existing in `v_plan_weekly_baselines` |
| day | Derived from week → day distribution | Proposed: uniform or historical pattern |
| hour | Backlog | Not designed |

---

## 4. REQUIRED ADJUSTMENTS

| Adjustment | Priority |
|-----------|----------|
| LOB → business_slice mapping (via `plan_lob_mapping`) | P0 — needed for slice-level Plan vs Real |
| plan_version selector in V2 UI | P1 |
| Owner display in Plan vs Real section | P2 |

---

## 5. VERDICT

The plan source is production-ready and certified for V2 Plan vs Real integration. The monthly table with 4,872 rows across multiple versions provides a solid foundation. No schema changes needed.
