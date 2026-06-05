# OMNI-P0 — CLOSED / PARTIAL CLARITY RULES

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Estado:** REGLAS DEFINIDAS — PENDIENTE IMPLEMENTACIÓN EN VS PROY

---

## 1. PROBLEMA

Actualmente en Evolution, una celda puede mostrar "-30%" sin contexto de si ese periodo está cerrado (dato definitivo), parcial (dato incompleto, la caída puede recuperarse), o es el periodo actual en curso.

Vs Proy tiene mejor soporte (badges L0 como "ULTIMO CIERRE", "PARCIAL") pero no es uniforme cross-métrica.

---

## 2. REGLA CANÓNICA

**Toda celda con delta DEBE indicar claramente su `period_status`.**

Los estados definidos son:

| Estado | Significado | Badge UI | Color badge |
|--------|-------------|----------|-------------|
| **CLOSED** | Periodo finalizado, dato definitivo | "CERRADO" | Gris / Emerald |
| **PARTIAL** | Periodo en curso, dato incompleto | "PARCIAL" | Ámbar |
| **CURRENT** | Periodo actual (hoy/semana/mes activo) | "ACTUAL" | Azul (Present Focus ring) |
| **FUTURE** | Periodo que aún no comenzó | "FUTURO" | Gris claro |
| **NO_PLAN** | Sin plan cargado para este periodo | "SIN PLAN" | Gris |
| **NO_REAL** | Sin dato real (data loss / gap) | "SIN DATO" | Rojo claro |

---

## 3. CASO: -30% AUTO REGULAR

### Escenario A: CLOSED

```
Celda: "▼ -30% MoM" + Badge "CERRADO"
Tooltip: "Periodo cerrado. Real: 850 viajes. Anterior: 1,214 viajes. 
         Caída definitiva de -364 viajes (-30.0%). 
         Comparación: MoM (mayo 2024 vs mayo 2026)."
Color: Rojo severidad media-alta (#dc2626)
Interpretación: La caída es real y definitiva. No hay más datos por llegar.
```

### Escenario B: PARTIAL

```
Celda: "▼ -30% WoW ~" + Badge "PARCIAL"
Tooltip: "Periodo parcial. Real: 850 viajes (hasta día 4 de 7). 
         Equivalente anterior: 1,214 viajes (mismos 4 días de semana anterior).
         La caída puede recuperarse cuando lleguen los 3 días restantes.
         Completado vs mismo punto: -30.0%."
Color: Rojo con opacidad reducida (por parcialidad)
Interpretación: La caída es parcial. Faltan 3 días de datos. 
               Puede que el periodo cierre mejor.
```

### Escenario C: CURRENT (hoy)

```
Celda: "▼ -30% DoD" + Badge "ACTUAL" + Ring azul
Tooltip: "Hoy. Real: 850 viajes. Mismo día semana anterior: 1,214 viajes.
         Comparación: DoD (miércoles vs miércoles anterior)."
Color: Rojo
Interpretación: Comparación del día actual vs mismo día semana anterior.
               No es una caída mensual, es day-over-day.
```

---

## 4. IMPLEMENTACIÓN EN VS PROY

Vs Proy actualmente usa `projectionCellDisplayModel.js` con capas L0-L4:

- **L0**: Period badge ("ULTIMO CIERRE", "PARCIAL") — ya existe
- **L1**: Real value — ya existe
- **L2**: Comparable delta — ya existe (`buildComparableDelta`)
- **L3**: Context (attainment/plan) — ya existe
- **L4**: Status text — ya existe

### Lo que falta:

1. **L0 debe ser obligatorio para TODAS las métricas**, no solo trips/revenue/drivers.
2. **El badge L0 debe reflejar el `period_status` del contrato canónico**, no solo "ULTIMO CIERRE"/"PARCIAL".
3. **La opacidad del color de delta debe reducirse para PARTIAL** (indicar visualmente que el dato es incompleto).
4. **Tooltip debe incluir explícitamente el `period_status`** con explicación.

### Estados en el código actual de Vs Proy

En `projectionMatrixUtils.js`:
- `getProjectionStatusLabel()` retorna labels de estado
- `week_state` en el delta de proyección indica el estado de la semana

En `BusinessSliceOmniviewMatrixCell.jsx` (rama Vs Proy, L250-473):
- `comparisonStatus === 'missing_plan'` → "Sin plan"
- Periodos futuros → "Pendiente", "Sin ejecución"

---

## 5. REGLA DE CERTIFICACIÓN

Para certificar una celda como correcta:

```
cell.period_status DEBE estar definido
cell.display_badge DEBE ser visible
cell.tooltip_reason DEBE incluir el estado y su significado

Si delta_pct != null:
  - Si period_status === 'CLOSED' → color con severidad completa
  - Si period_status === 'PARTIAL' → color con opacidad reducida
  - Si period_status === 'CURRENT' → color normal + ring azul
  - Si period_status === 'NO_REAL' → overlay rojo claro
```

---

## 6. EJEMPLO DE CONTRATO DE CELDA (CASO REAL)

```json
{
  "real_value": 850,
  "plan_value": 1100,
  "projection_value": 1050,
  "delta_abs": -364,
  "delta_pct": -0.30,
  "comparison_label": "MoM",
  "period_status": "CLOSED",
  "freshness_status": "OK",
  "trust_status": "OK",
  "display_value": "850",
  "display_badge": "CERRADO",
  "color_rule": {
    "bg": "#fee2e2",
    "text": "#dc2626",
    "border": null,
    "severity": "alto_negativo"
  },
  "tooltip_reason": "Periodo cerrado. Caída definitiva de -30.0% vs mes anterior (-364 viajes). Real: 850. Plan: 1,100. Brecha vs plan: -22.7%."
}
```

---

**END OF CLOSED/PARTIAL RULES**
