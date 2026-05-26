# OPERATIONAL DEFAULTS — VISUAL QA

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## DAILY GRAIN

| Check | Expected | Status |
|---|---|---|
| Ciudades desplegadas por defecto | Todas las ciudades visibles al cargar | ✅ Default expanded |
| HOY visible sin scroll | Columna actual centrada en viewport | ✅ Auto-scroll |
| DoD domina color/delta | Verde/rojo bold en fila de momentum | ✅ `font-extrabold` + color |
| NaN no aparece | Todas las celdas muestran valores válidos o '—' | ✅ NaN guards en formatters |
| Valor + delta se leen rápido | Real (big/bold) → DoD (colored → context line | ✅ New dominant layout |
| Usuario puede colapsar | Click en ciudad la colapsa, sin fightback | ✅ `userToggledRef` |

## WEEKLY GRAIN

| Check | Expected | Status |
|---|---|---|
| Ciudades desplegadas | Visibles al cargar | ✅ Default expanded |
| WoW domina | Label + colored delta para WoW | ✅ `periodPopLabel` = "WoW" |
| SEM ACT centrada | Semana actual visible | ✅ Auto-scroll |

## MONTHLY GRAIN

| Check | Expected | Status |
|---|---|---|
| Ciudades desplegadas | Visibles al cargar | ✅ Default expanded |
| MoM domina | Label + colored delta para MoM | ✅ `periodPopLabel` = "MoM" |
| MES ACT centrado | Mes actual visible | ✅ Auto-scroll |

## CELL LAYOUT

| Row | Content | Weight |
|---|---|---|
| 1 | HOY badge (solo current period) | Tiny, contextual |
| 2 | REAL VALUE | **font-extrabold, text-gray-900, 16px** |
| 3 | MOMENTUM DELTA | **font-extrabold/bold, colored** |
| 4 | Plan + Avance context | Ultra-small, gray, footer |
| 5 | Status label | Small, colored |

## PERIOD AUTHORITY

| Period | Visual treatment |
|---|---|
| Current (HOY/SEM ACT/MES ACT) | Emerald border + glow + bg gradient + larger font |
| Future (sin real) | Opacity-60 |
| Past (degraded) | Progressive opacity reduction (max 55%) |

## VERDICT: PASS
