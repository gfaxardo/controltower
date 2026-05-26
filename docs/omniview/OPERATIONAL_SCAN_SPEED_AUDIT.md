# OPERATIONAL SCAN SPEED AUDIT

**Date**: 2026-05-25
**Mode**: Vs Proyección

---

## EVALUACIÓN DE ESCANEABILIDAD

### Must Fix

| Issue | Severity | Fix |
|---|---|---|
| Worst-in-row apenas se distingue de severity normal | HIGH | Endurecer `worstEmphasis`: ring más opaco, shadow sutil |
| Línea "Avance X%" es ruido visual en todas las celdas | MEDIUM | Solo mostrar attainment en planFallback. En modo momentum, mover a tooltip. |
| Delta texto compite con real value en celdas no-current | LOW | Asegurar delta tiene suficiente peso en celdas normales |

### Should Tune

| Issue | Fix |
|---|---|
| Headers no diferencian closed de partial | Badge en header de columna para "CERRADO" / "PARCIAL" |
| Futuro es demasiado visible | Endurecer futureDim: `opacity-35` |
| Pasado cercano tiene mismo peso que pasado lejano | Degradación más agresiva para pasado lejano |
| Celda seleccionada compite con worst-in-row | La selección ya domina (ring blue), OK |

### Preserve

| Item | Razón |
|---|---|
| Delta comparable dominance | Momentum es el foco visual correcto |
| Último cierre emerald authority | Dominancia temporal correcta |
| Severity emphasis | Autolimitante, no heatmap |
| Sticky headers/columns | Navegación espacial OK |
| Single scroll | Sin regresiones |

### Do Not Touch

| Item | Razón |
|---|---|
| Backend APIs | Sin necesidad |
| Evolution mode | Fuera de scope |
| Momentum calculations | Core lógico |
| Projection calculations | Core lógico |
