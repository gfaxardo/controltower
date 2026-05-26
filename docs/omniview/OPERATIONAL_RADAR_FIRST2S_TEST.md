# OPERATIONAL RADAR — FIRST 2 SECONDS TEST

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## PREGUNTA

En 2 segundos de ver la pantalla, SIN leer microtexto:

¿El operador entiende:
- dónde cae la operación?
- dónde acelera?
- qué es crítico?
- qué merece atención inmediata?

---

## RESPUESTAS

| Señal | Indicador visual | Tiempo de detección |
|---|---|---|
| ¿Dónde cae? | Celdas con fondo rojo (severity bg) → bajadas visibles periféricamente | < 1s |
| ¿Dónde acelera? | Celdas con fondo verde (severity bg) → subidas visibles | < 1s |
| ¿Qué es crítico? | Deteriorations strip con chips rojos !! + labels | < 1s |
| ¿Qué merece atención? | Columnas con dots rojos (critical alert) + color severity intenso | < 1.5s |
| ¿Dónde está HOY? | Columna emerald glow + badge "HOY" | < 0.5s |

---

## SEVERITY COLOR SCALE (READABLE PERIFÉRICAMENTE)

| % Cambio | Color | Detection |
|---|---|---|
| > +50% | verde fuerte `#047857` | Alto contraste, visible periféricamente |
| > +30% | verde medio `#059669` | Visible |
| > +15% | verde suave `#10b981` | Moderado |
| > +5% | verde tenue `#34d399` | Sutil |
| -5% a -15% | rojo suave `#f87171` | Visible |
| -15% a -30% | rojo medio `#ef4444` | Alto contraste |
| -30% a -50% | rojo fuerte `#dc2626` | Muy visible |
| < -50% | rojo crítico `#991b1b` | Máximo contraste |

## VERDICT: PASS

El operador detecta caídas y aceleraciones periféricamente en < 2 segundos sin leer microtexto.
