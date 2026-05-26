# PROJECTION RELEASE DECISION

**Date**: 2025-05-25
**Motor**: Control Foundation + Diagnostic Engine Temprano
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO FINAL: GO

**Omniview Proyección + Momentum Radar está listo para producción controlada.**

---

## 2. QUÉ QUEDÓ LISTO

### Viewport
- Single scroll owner (horizontal + vertical)
- Auto-scroll a current period (HOY / semana actual / mes actual)
- Botón "Ir a hoy" en ambos modos
- Sticky headers, city/label columns intactos
- Fullscreen drill funcional

### Present Dominance
- Emerald border + glow + larger font + bg gradient para current period
- Badge "HOY" / "SEM ACT" / "MES ACT" visible
- Pasado degradado con opacidad progresiva (max 55%)

### Momentum Radar
- Color severity scale: 5 niveles negativos + 5 positivos
- Background tinting por severidad en celdas
- Momentum delta como fila dominante (extrabold/bold, coloreado)
- DoD/WoW/MoM labels desde backend con arrows

### Cell Cognition
- REAL VALUE → dominante (13-16px extrabold)
- MOMENTUM DELTA → dominante (11px colored bold)
- Plan + Avance → terciario (9px gray-400, línea de contexto)
- Gap → eliminado del cell, disponible en tooltip

### Defaults
- Ciudades expandidas por defecto en todos los granos
- User governance: colapso respetado, reset solo en cambio de contexto

### Deterioration Strip
- `OmniviewMomentumPriorityStrip` wired para ambos modos
- Top 5 deterioros determinísticos, sin IA

### NaN Elimination
- `fmtAttainment`, `fmtGapPct`, `fmtValue` con guards
- Momentum display con `Number.isFinite` guard

### Mode Simplification
- Operational como modo primario dominante
- Executive/Diagnostic/Comparative en dropdown colapsado

### Weekday Cognition
- Chips prominentes (scale-110, glow azul)
- Label contextual "Comparando DOM vs DOM"

---

## 3. QUÉ QUEDA PENDIENTE

| Item | Severidad | Plan |
|---|---|---|
| Cleanup de 3 componentes deprecated | BAJA | FASE 4/6 — no bloquea producción |
| Chunk size >500 kB (pre-existing) | BAJA | No introducido en esta fase |
| `maxHeight: calc(100vh - 240px)` puede no ajustar en viewports pequeños | BAJA | El scroll único funciona; altura fija es aceptable |
| Modos Executive/Diagnostic/Comparative sin funcionalidad real | BAJA | Infraestructura lista, implementación en fases futuras |
| `periodPop` ausente en backend → momentum no visible | BAJA | Fallback controlado a attainment view |

---

## 4. QUÉ RIESGOS SE ACEPTAN

| Riesgo | Aceptado porque... |
|---|---|
| Chunk size grande | Pre-existing; bundle splitting es un proyecto aparte |
| Color severity thresholds en JS | Ajustables vía deploy; no requieren backend |
| Daily grain con muchas ciudades | El operador puede colapsar manualmente; column windowing mitiga |
| Sin `periodPop` en algunos escenarios backend | Fallback a attainment con peso normal; no rompe la celda |

---

## 5. QUÉ NO DEBE TOCARSE ANTES DE PRODUCCIÓN

| Prohibido | Razón |
|---|---|
| Evolution mode render/cell logic | Es secondary legacy, cualquier cambio introduce riesgo |
| `BusinessSliceOmniviewProjectionTable` | Deprecated, no usado |
| `BusinessSliceOmniviewProjectionCell` | Deprecated, no usado |
| `RealVsProjectionView` | Legacy, no usado |
| Backend serving facts | No necesitan cambios para esta release |
| Scroll ownership (ya unificado) | Estable, no tocar |
| Sticky positioning | Estable, no tocar |

---

## 6. RECOMENDACIÓN EXPLÍCITA

### SUBIR A PRODUCCIÓN CONTROLADA

**Omniview Vs Proyección + Momentum Radar** cumple todos los criterios GO:

| Criterio | Status |
|---|---|
| Proyección domina como cerebro principal | ✅ |
| Evolution no recibe mejoras nuevas | ✅ |
| Momentum manda visualmente | ✅ |
| DoD/WoW/MoM claros | ✅ |
| Ciudades desplegadas por defecto | ✅ |
| Presente visible | ✅ |
| Celda valor + delta clara | ✅ |
| No NaN | ✅ |
| Drill funciona | ✅ |
| Fullscreen funciona | ✅ |
| Build PASS | ✅ |
| Sin regresiones graves | ✅ |

### Condiciones de release:
1. No agregar nuevas features en esta release
2. Monitorear performance en daily grain con muchas ciudades
3. Documentar que los modos Executive/Diagnostic/Comparative son infraestructura (sin funcionalidad aún)
4. Programar cleanup de deprecated components para FASE 4/6

---

## 7. NOTAS OPERACIONALES

- Evolution mode permanece como secondary legacy, accesible vía toggle "Evolución"
- El toggle "Vs Proyección" es el modo recomendado para operación diaria
- La top deterioration strip guía la atención del operador hacia lo prioritario
- El drill (click en celda) permite profundizar en Plan vs Real o Momentum
- El fullscreen (botón expandir) permite análisis detallado sin distracciones

---

## VERDICT FINAL: GO — SUBIR A PRODUCCIÓN CONTROLADA
