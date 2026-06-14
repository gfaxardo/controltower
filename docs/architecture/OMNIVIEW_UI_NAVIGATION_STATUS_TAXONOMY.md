# OMNIVIEW UI — NAVIGATION STATUS TAXONOMY

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** ACTIVE GOVERNANCE RULE
**Applies to:** Any Omniview UI change touching navigation, routes, menus, or labels.

---

## 0. Executive Decision

**GO: NAVIGATION STATUS TAXONOMY ADDED TO UI GOVERNANCE**

All future Omniview UI changes must validate navigation clarity, route status, naming consistency, and operator orientation. This taxonomy replaces ad-hoc route management.

---

## 1. Problem

Omniview V1 and V2 coexist. Routes include:
- V2 Professional (default)
- V2 Shadow (fallback)
- V2 Sandbox (dev)
- V1 Matrix (legacy, hidden from menu)
- V1 Reports (preserved pending V2 equivalent)

Without explicit status taxonomy, an operator may open V1 thinking it is V2, miss the certified experience, or encounter ambiguous route names.

---

## 2. Status Taxonomy

| Status | Color | Label | Usage |
|--------|-------|-------|-------|
| `DEFAULT_CERTIFIED` | Green | `Default` / `Certified` | Main operational experience, ready for use |
| `ACTIVE_BUILD` | Amber | `Active` / `In build` | Module under active implementation |
| `LEGACY_FALLBACK` | Gray | `Legacy` / `Fallback` | Previous view preserved for safety |
| `BLOCKED_DO_NOT_USE` | Red | `Blocked` / `Do not use` | Unsafe or unavailable for operations |
| `DEV_SANDBOX` | Blue/Purple | `Dev` / `Sandbox` | Internal testing, not for operations |

**Rules:**
- Never communicate status with color alone. Always pair with text label.
- Red is reserved for blocked/unsafe. Do not use for functional legacy.
- Gray is for legacy/fallback. Functional but superseded.
- Amber is for active builds. Not yet certified.
- Green is for default/certified. The primary experience.
- Dev/sandbox must not be visible to end operators.

---

## 3. Naming Contract

| Route | Canonical Name | Badge | Visibility |
|-------|---------------|-------|------------|
| `/operacion/omniview-v2-professional` | Omniview V2 | `Default` | Menu (primary) |
| `/operacion/omniview-v2-shadow` | Omniview V2 Shadow | `Fallback interno` | URL only |
| `/operacion/omniview-v2-matrix-sandbox` | Omniview V2 Sandbox | `Dev` | Hidden from operator |
| `/operacion/omniview-matrix` | Omniview V1 Matrix | `Legacy fallback` | URL only |
| `/operacion/omniview` | Omniview V1 | `Legacy` | URL only |
| `/operacion/reportes` | Reportes | `Legacy temporal` | Menu (until V2 equivalent) |

**Rules:**
- Single canonical name for the operation tab: `Operación`
- No duplicate or near-duplicate tab names
- Default version always labeled with version number
- Legacy always marked with badge and hidden from menu when possible

---

## 4. Precheck Additions

Every future Omniview UI prompt must answer:

1. Which route is the default visible to the operator?
2. Are legacy routes visible in the menu?
3. Are fallback routes visible or URL-only?
4. Are dev/sandbox routes visible to the operator?
5. Are there duplicate or ambiguous route names?
6. Is there accent/naming inconsistency (e.g., `Operación` vs `Operacion`)?
7. Does each visible route/tab have an explicit status label?
8. Is status communicated with text AND color?
9. Does the color match the status taxonomy?
10. Could the operator mistakenly use V1 thinking it is V2?
11. Is the legacy route hidden or clearly marked?
12. Is the fallback preserved without being default?
13. Is there a navigation rollback plan?
14. Has the navigation been validated in a real browser?

---

## 5. Omniview Route Application

| Route | Status | Color | Label | Menu? |
|-------|--------|-------|-------|-------|
| V2 Professional | DEFAULT_CERTIFIED | Green | Default | YES |
| V2 Shadow | LEGACY_FALLBACK | Gray | Fallback interno | NO |
| V2 Sandbox | DEV_SANDBOX | Purple | Dev | NO |
| V1 Matrix | LEGACY_FALLBACK | Gray | Legacy fallback | NO |
| V1 Reports | ACTIVE_BUILD | Amber | Legacy temporal | YES |

---

## 6. Validation Rules

Before declaring any navigation change complete:
1. Open all routes in browser
2. Verify no error boundaries or stack traces
3. Verify each route shows its status label
4. Verify no dev route is in the main menu
5. Verify default route is the certified experience
6. Verify no duplicate/ambiguous tab names
7. Verify rollback path exists

---

## 7. Rollback

- Restore menu entries to previous state
- Restore route labels to previous state
- No backend, DB, or data changes needed

---

## 8. Next Phase

`OV2-UI-V1A Navigation Clarity + Status Taxonomy Implementation` — apply labels, badges, and visibility rules per this taxonomy.