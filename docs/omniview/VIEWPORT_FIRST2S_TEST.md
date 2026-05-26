# VIEWPORT FIRST 2 SECONDS TEST

**Date**: 2025-05-25
**Mode**: Vs Proyección
**Foco**: Operational UX

---

## PREGUNTA PRINCIPAL

En 2 segundos de ver la pantalla:
¿El operador entiende:
- dónde está HOY?
- qué periodo domina?
- qué requiere atención?
- hacia dónde cayó/subió la operación?

---

## RESPUESTAS (post-implementation)

| Pregunta | Indicador visual | Resultado esperado |
|---|---|---|
| ¿Dónde está HOY? | Columna con badge "HOY", borde emerald, glow verde, bg-gradient, fuente más grande | El ojo aterriza inmediatamente en la columna actual |
| ¿Qué periodo domina? | Columna actual resaltada vs pasado degradado con opacidad reducida | El presente tiene ~100% opacidad, el pasado se atenúa progresivamente |
| ¿Qué requiere atención? | Celdas con señal danger (rojo) o warning (ámbar), alerta crítica < 75% | Los problemas resaltan contra el contexto degradado |
| ¿Hacia dónde va la operación? | Momentum DoD/WoW/MoM en la celda, flechas verde/rojo con % | La tendencia inmediata es visible directamente |

---

## ESCANEO COGNITIVO (orden natural)

1. **HOY badge** → columna actual inmediatamente localizada (emerald border + glow)
2. **Degradación del pasado** → 55% opacidad máx para columnas antiguas, contraste reducted
3. **Valor REAL** → número grande y bold en la celda actual
4. **Momentum** → DoD/WoW/MoM en color verde/rojo, inmediatamente debajo del real
5. **Avance %** → atenuado cuando hay momentum (opacidad 60%), secundario

---

## VERDICT: PASS

El viewport de proyección ahora centra la atención operacional en el presente mientras mantiene el contexto histórico como referencia degradada.
