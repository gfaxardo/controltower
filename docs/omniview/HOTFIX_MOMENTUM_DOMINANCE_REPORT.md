# HOTFIX MOMENTUM DOMINANCE — REPORTE FINAL

**Date**: 2025-05-25
**Motor**: Control Foundation + Diagnostic Engine Temprano
**Foco**: Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Status |
|---|---|
| Build | ✅ PASS (814 modules, 9.27s) |
| DoD/WoW/MoM visibles | ✅ Forzados cuando `periodPop` tiene valor |
| Momentum domina visualmente | ✅ Display model canónico |
| Plan queda secundario | ✅ Muted attainment o context line |
| Drill abre Momentum por defecto | ✅ `selectionHasMomentum` |
| Top strip usa momentum | ✅ Sequential deltas |
| No NaN | ✅ |
| Evolution intacto | ✅ Cero cambios |

## 2. CAUSA RAÍZ

`hasMomentum` requería tres condiciones simultáneas (`periodPopComparable && periodPopLabel && periodPop != null`). El backend no siempre envía `comparable` o `label`, ocultando momentum incluso con datos válidos. El attainment/fulfillment ocupaba el espacio visual dominante.

## 3. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `projectionCellDisplayModel.js` | **NUEVO** — canonical display helper |
| `BusinessSliceOmniviewMatrixCell.jsx` | Usa display model; render simplificado |
| `OmniviewProjectionDrill.jsx` | Default a momentum tab si existe |

## 4. DISPLAY MODEL

`buildProjectionCellDisplay(delta, grain, kpiKey)`:

- Si `periodPop` tiene valor numérico → momentum domina (label de grain, color de severity)
- Si no → fallback a attainment, marcado visualmente como secundario
- Contexto mínimo: "avance 47.3%" cuando hay momentum, "Plan 59.6K · 47.3%" en fallback

## 5. CÓMO SE PRIORIZA MOMENTUM

1. `periodPop` con valor finito → momentum inmediatamente, sin chequear banderas
2. Label derivado de grain si backend no lo provee
3. Color por severity scale (5 niveles)
4. Plan/attainment relegado a línea de contexto 9px gray-400

## 6. DRILL DEFAULT

`selectionHasMomentum(selection)` → si true, abre `momentum` tab. Si no, abre `plan_vs_real`.

## 7. RIESGOS

| Riesgo | Severidad |
|---|---|
| Label derivado puede no coincidir con backend label | BAJA (información contextual) |
| `periodPop` nulo en datos del backend | BAJA (controlled fallback to attainment) |

## VERDICT FINAL: GO — Momentum restaurado como lectura dominante
