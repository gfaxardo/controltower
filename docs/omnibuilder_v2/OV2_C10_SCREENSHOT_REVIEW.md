# OV2-C.10 — SCREENSHOT REVIEW

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Visual Closure
> **Status:** SCRIPT READY — execution needs dev servers

---

## 1. SCREENSHOT SCENARIOS

| # | File | Route | Source | Expected |
|---|------|-------|--------|----------|
| 1 | `01_ct_day_default.png` | `/operacion/omniview-v2-shadow` | CT_TRIPS_2026 | CANONICAL badge, 6-slice matrix, shell sections |
| 2 | `02_yango_day_shadow.png` | `/operacion/omniview-v2-shadow` | YANGO_API_RAW | SHADOW badge, safety banner, single fleet row |
| 3 | `03_sandbox_ct_day.png` | `/operacion/omniview-v2-matrix-sandbox` | CT (mock) | 6 slices × 7 days, scenario selector |
| 4 | `04_sandbox_yango_day.png` | `/operacion/omniview-v2-matrix-sandbox` | Yango (mock) | Single row × 5 days, SHADOW badge |
| 5 | `05_v1_omniview_matrix.png` | `/operacion/omniview-matrix` | V1 CT | Production V1 matrix intact |

---

## 2. EXPECTED VISUAL ELEMENTS PER SCREENSHOT

### 2.1 CT Day Default (01)
- [ ] Command header with "OV2 Shadow" label
- [ ] CANONICAL badge (green)
- [ ] Source selector showing "CT Trips 2026"
- [ ] Grain selector showing "Daily"
- [ ] Date pickers
- [ ] Coverage badge
- [ ] Executive KPI strip (max 5 cards)
- [ ] Alert strip (visible if warnings exist)
- [ ] Section shell cards (10 sections)
- [ ] MatrixShell with 6 rows (slices)
- [ ] Matrix columns showing dates
- [ ] No MATRIX_FALLBACK_ACTIVE banner
- [ ] No SHADOW MODE banner

### 2.2 Yango Day Shadow (02)
- [ ] SHADOW badge (indigo)
- [ ] "SHADOW MODE — Yango API is NOT canonical" banner (amber)
- [ ] Source selector showing "Yango API (Shadow)"
- [ ] Single row (Lima Fleet)
- [ ] Warnings in alert strip
- [ ] Some sections showing BLOCKED (Plan vs Real, Slice Readiness)
- [ ] No MATRIX_FALLBACK_ACTIVE banner

### 2.3 Sandbox CT Day (03)
- [ ] Scenario dropdown with "CT Day" selected
- [ ] Source badge CANONICAL
- [ ] 6 rows × 7 columns
- [ ] WARNING/OK/BLOCKED/SHADOW colored cells
- [ ] Delta indicators in bottom-left of cells
- [ ] ESTIMATED badges

### 2.4 Sandbox Yango Day (04)
- [ ] SHADOW / NOT CANONICAL badge
- [ ] Single row
- [ ] Cells showing WARNING status
- [ ] Safety banner

### 2.5 V1 Omniview Matrix (05)
- [ ] Production V1 matrix renders
- [ ] V1 header visible
- [ ] V1 filter controls
- [ ] Data cells populated
- [ ] No OV2 visual elements

---

## 3. FUNCTIONAL ASSERTIONS (in-browser)

| # | Action | Expected | Result |
|---|--------|----------|--------|
| B1 | Load `/operacion/omniview-v2-shadow` | Page renders without errors | PENDING |
| B2 | Switch source to YANGO_API_RAW | Source changes, SHADOW badge appears | PENDING |
| B3 | Switch grain to week (CT) | Matrix re-renders with week columns | PENDING |
| B4 | Switch grain to month (CT) | Matrix re-renders with month columns | PENDING |
| B5 | Switch grain to week (Yango) | Empty state with GRAIN_NOT_SUPPORTED | PENDING |
| B6 | Click matrix cell | Cell inspector opens on right | PENDING |
| B7 | Close inspector (X button) | Inspector closes, cell deselected | PENDING |
| B8 | Close inspector (backdrop click) | Inspector closes | PENDING |
| B9 | Close inspector (Escape key) | Inspector closes | PENDING |
| B10 | Load V1 route | V1 renders correctly | PENDING |

---

## 4. EXECUTION COMMANDS

```bash
# 1. Start backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Start frontend (separate terminal)
cd frontend
npm run dev

# 3. Run visual tests
cd frontend
node tests/omniview-v2-shadow-visual.mjs

# 4. Review screenshots
ls backend/exports/audits/omniview_v2_visual/
```

---

## 5. REVIEW STATUS

Screenshots not yet captured — dev servers required for execution. All code-level checks pass (see OV2-C.9 report). Screenshot review will be updated when servers are available.
