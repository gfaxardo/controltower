# OV2-MVP.2 — OPERATIONAL ACCEPTANCE CHECKLIST

> **Fase:** OV2-MVP.2 — UX Hardening + Operational Acceptance Prep
> **Sub-document:** Acceptance Checklist
> **Fecha:** 2026-06-12

---

## CAN AN OPERATOR WORK A FULL DAY USING ONLY V2?

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | View Trips (orders) | **PASS** | day/week/month, all business slices |
| 2 | View Active Drivers | **PASS** | day/week/month |
| 3 | View Revenue (PEN) | **PASS** | revenue_yego_final |
| 4 | View GMV | **PASS** | gmv_total from Yango source |
| 5 | View Commission % | **PARTIAL** | Shows N/A — data pipeline pending |
| 6 | Filter by Country | **PASS** | Peru / Colombia dropdown |
| 7 | Filter by City | **PASS** | Lima, Trujillo, Arequipa, etc. |
| 8 | Filter by Park | **PASS** | Lima, Trujillo, Arequipa, Pro, TukTuk |
| 9 | Filter by Business Slice | **PASS** | Auto Regular, Delivery, PRO, TukTuk, Carga |
| 10 | Change grain (day/week/month) | **PASS** | Dropdown + smart date range |
| 11 | Change date range | **PASS** | Date inputs from/to |
| 12 | Check data freshness | **PASS** | Status bar: FRESH/STALE/CRITICAL |
| 13 | Check data source | **PASS** | Source badge: CT/YANGO/SHADOW |
| 14 | Check fallback status | **PASS** | Fallback indicator in status bar |
| 15 | See signal colors on cells | **PASS** | Green/red/gray left border |
| 16 | See delta arrows | **PASS** | ▲▼→ with direction colors |
| 17 | See source badge on cells | **PASS** | CT/YAN badge in corner |
| 18 | Inspect cell details | **PASS** | Click cell → drawer |
| 19 | Use fullscreen mode | **PASS** | [F] Fullscreen button + Esc exit |
| 20 | Sticky headers work | **PASS** | CSS position: sticky |
| 21 | No double scroll | **PASS** | overflow: hidden outer + auto body |
| 22 | Business slices visible | **PASS** | 6 slices in matrix rows |
| 23 | Status bar collapsible | **PASS** | Toggle button + detail view |
| 24 | Navigate from sidebar | **PASS** | "Omniview V2 MVP" in Operacion tab |
| 25 | V1 still accessible | **PASS** | V1 untouched, still default |

---

## SCORE: 24/25 PASS, 1 PARTIAL

**Acceptance rate: 96%**

### Outstanding

| # | Issue | Priority | Action |
|---|-------|----------|--------|
| 1 | Commission % shows N/A | P1 | Data pipeline fix required — not a V2 code issue |
