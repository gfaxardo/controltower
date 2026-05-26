# OPERATIONAL SCAN SPEED — QA

**Date**: 2026-05-25
**Mode**: Vs Proyección

---

## 1. WORST-IN-ROW

| Check | Status |
|---|---|
| Visible sin leer todas las celdas | ✅ `ring-2 ring-red-300/55 border-l-2 border-red-400/70 shadow-[inset...]` |
| No heatmap agresivo | ✅ Solo 1 celda por fila, autolimitante |
| No compite con último cierre | ✅ Guard: `!isCurrentPeriod` |
| No compite con seleccionada | ✅ Guard: `!isSelected` |

## 2. DELTA READABILITY

| Check | Status |
|---|---|
| Delta domina visualmente | ✅ Coloreado, bold, L2 |
| No se confunde con gap/YTD | ✅ Gap/YTD solo en tooltip |
| Sin attainment en celda con momentum | ✅ Eliminado "Avance X%" cuando hay comparable |

## 3. CELL LINE REDUCTION

| Check | Status |
|---|---|
| Menos ruido interno | ✅ Solo L0 badge + L1 real + L2 delta + status |
| Sin attainment redundante | ✅ Solo en planFallback |
| Información en tooltip | ✅ Tooltip tiene plan/expected/YTD/confidence |

## 4. HEADER RHYTHM

| Check | Status |
|---|---|
| Último cierre con más contraste | ✅ Header usa `currentPeriodKey` (operational anchor) para highlight azul |
| Header no compite con celdas | ✅ Altura conservada |

## 5. TEMPORAL GRADIENT

| Check | Status |
|---|---|
| Futuro más tenue | ✅ `opacity-35 grayscale-[40%]` |
| Pasado más degradado | ✅ Steps ampliados (daily 90, weekly 52, monthly 36) |
| Último cierre sigue dominante | ✅ Emerald glow intacto |
| Parcial no domina | ✅ Badge ámbar sin glow |

## 6. BUILD

| Check | Status |
|---|---|
| Build PASS | ✅ 818 módulos, 5.13s |
| No nuevos endpoints | ✅ |
| No Evolution wiring | ✅ |
| Sticky/Fullscreen/Drill intactos | ✅ |

---

## VERDICT: PASS
