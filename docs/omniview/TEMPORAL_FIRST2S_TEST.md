# TEMPORAL AUTO-FOCUS — FIRST 2 SECONDS TEST

**Date**: 2026-05-25
**Purpose**: Validar que en los primeros 2 segundos el operador entiende dónde está HOY.

---

## TEST QUESTIONS

En 2 segundos, el operador debe identificar:

| # | Pregunta | Respuesta esperada |
|---|----------|-------------------|
| 1 | ¿Dónde está HOY? | La columna del día actual es inmediatamente visible, sin scroll horizontal necesario. |
| 2 | ¿Qué periodo es el actual? | El badge "HOY" / "SEMANA ACTUAL" / "MES ACTUAL" es visible y legible. |
| 3 | ¿Qué merece atención inmediata? | La celda del periodo actual tiene mayor peso visual: fuente más grande, fondo azul resaltado, borde sutil. |

---

## VISUAL LANDING CHECKLIST

### Daily grain
- [ ] El auto-scroll centra la columna de HOY al cargar
- [ ] El badge "HOY" en el header es visible (`text-[10px]`, azul sobre blanco)
- [ ] La columna HOY tiene fondo `bg-blue-950/90` con glow azul
- [ ] Las celdas de HOY tienen fuente más grande (`text-[16px]` vs `text-[14px]`)
- [ ] El Total row de HOY tiene fondo azul claro y texto `text-blue-900`
- [ ] El KPI del periodo actual usa `font-extrabold`

### Weekly grain
- [ ] El auto-scroll centra la semana actual
- [ ] Badge "SEMANA ACTUAL" visible en el header
- [ ] Misma jerarquía visual que daily

### Monthly grain
- [ ] El auto-scroll centra el mes actual
- [ ] Badge "MES ACTUAL" visible en el header
- [ ] Misma jerarquía visual que daily

---

## NO DISTRACTION CHECKLIST

- [ ] Las columnas históricas/distant no compiten visualmente con el periodo actual
- [ ] Los periodos cercanos (+/- 3 días, +/- 2 semanas) mantienen legibilidad normal
- [ ] Los periodos muy distantes (15+ días, 8+ semanas) no distraen
- [ ] El ojo aterriza naturalmente en la columna del periodo actual

---

## USER NAVIGATION RESPECT

- [ ] Después de scroll manual, no hay recentrado automático
- [ ] Cambiar filtro de ciudad/negocio NO recentra
- [ ] Cambiar grain SÍ recentra (nuevo contexto temporal)
- [ ] Cambiar a Proyección SÍ recentra (nuevo modo operativo)
- [ ] El botón "Ir a hoy" funciona en ambos modos (Evolución y Proyección)

---

## PERFORMANCE

- [ ] Sin scroll loops
- [ ] Sin jitter durante el auto-scroll
- [ ] Sin rerenders masivos al hacer scroll manual
- [ ] Sticky headers intactos
- [ ] Sticky left columns intactas
- [ ] Fullscreen drill sigue funcionando
- [ ] Weekday focus sigue funcionando

---

## VERDICT

El operador debe poder responder en 2 segundos:
- "El periodo actual está ahí" (señala la columna resaltada)
- "HOY tiene más peso visual"
- "Puedo navegar libremente a otros periodos"

Si no se cumple, revisar: intensidad del glow, tamaño de fuente del periodo actual, contraste del badge.
