# CONTROL TOWER ROLLBACK PLAN

**Date**: 2025-05-25

---

## 1. CRITICAL FILES

### Frontend (modified in this release cycle)

| File | Risk | Rollback action |
|---|---|---|
| `BusinessSliceOmniviewMatrix.jsx` | Viewport + auto-scroll + displayProjMatrix | Revert to git hash before release |
| `BusinessSliceOmniviewMatrixTable.jsx` | Default expanded + overflow: clip | Revert |
| `BusinessSliceOmniviewMatrixCell.jsx` | Cell hierarchy + NaN + severity colors | Revert |
| `operationalMomentumEmphasis.js` | Severity color scale | Revert |
| `OmniviewModeSelector.jsx` | Mode simplification | Revert |
| `projectionViewportFocusEngine.js` | New file — viewport centering | Remove file + remove import in Matrix.jsx |

### Backend

No backend files were modified in this release cycle. Serving facts and core calculations unchanged.

## 2. HOW TO REVERT FRONTEND

```bash
# Option A: Git revert to pre-release hash
git checkout <pre-release-commit>

# Option B: Revert specific files
git checkout <pre-release-commit> -- frontend/src/components/BusinessSliceOmniviewMatrix.jsx
git checkout <pre-release-commit> -- frontend/src/components/BusinessSliceOmniviewMatrixTable.jsx
git checkout <pre-release-commit> -- frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx
git checkout <pre-release-commit> -- frontend/src/utils/operationalMomentumEmphasis.js
git checkout <pre-release-commit> -- frontend/src/components/omniview/command/OmniviewModeSelector.jsx
rm frontend/src/utils/projectionViewportFocusEngine.js

# Rebuild
cd frontend && npm run build
```

## 3. HOW TO REVERT BACKEND

No backend rollback needed for this release. If backend issues arise:
- Restart with previous deployment
- Serving facts are not affected by frontend changes

## 4. ENDPOINTS TO DISABLE IF THEY FAIL

| Endpoint | Action |
|---|---|
| `/ops/business-slice/omniview-projection` | Frontend shows SmartEmptyState; Evolution mode still works |
| `/ops/business-slice/omniview-momentum-drill` | Momentum drill tab shows empty; Plan/Real tab still works |

## 5. FEATURE FLAGS (if applicable)

No feature flags currently in use for Omniview. The `viewMode` toggle (Evolución ↔ Proyección) serves as an implicit fallback — if Proyección has issues, Evolution mode remains fully functional.

## 6. HOW TO RETURN TO PRE-RELEASE MODE

1. Toggle `viewMode` to `'evolucion'` via UI button — Evolution mode is completely untouched
2. Evolution mode has: matrix, deltas, insight engine, weekday focus, fullscreen, drill — all pre-existing
3. If UI is broken, redeploy frontend from previous build artifacts

## 7. WHAT NOT TO TOUCH DURING ROLLBACK

| Asset | Reason |
|---|---|
| `alembic/` migrations | No DB changes in this release |
| `requirements.txt` | No dependency changes |
| Serving fact tables (DB) | Frontend-only release |
| API routers | No backend changes |
| `api.js` frontend service | Pre-existing endpoints unchanged |

## 8. ROLLBACK DURATION

| Step | Time |
|---|---|
| Git revert + rebuild | ~5 min |
| Deploy previous build | ~2 min |
| Verify Evolution mode works | ~1 min |
| **Total** | **~8 min** |

## VERDICT: Rollback plan documented — quick (~8 min), Evolution mode serves as fallback
