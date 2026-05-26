# CONTROL TOWER RELEASE NOTES

**Date**: 2025-05-25
**Version**: 2.0.0 (Omniview Proyección + Momentum Radar)
**Motor**: Control Foundation

---

## QUÉ CAMBIA

### Omniview Proyección ahora es el cerebro principal

- **Momentum Radar**: DoD/WoW/MoM dominan visualmente con escala de color de 10 niveles de severidad. El ojo detecta deterioros/aceleraciones periféricamente.
- **Celda operacional**: solo 2 líneas dominantes — el valor real y el delta momentum. Todo lo demás (plan, gap, metadata) queda como contexto secundario o en tooltip.
- **Presente domina**: columna actual con spotlight emerald (borde, glow, fuente ampliada). El pasado se degrada progresivamente.

### Experiencia mejorada

- **Ciudades desplegadas por defecto**: todos los granos muestran todas las ciudades al abrir. El usuario puede colapsar sin que el sistema pelee.
- **Scroll único**: una sola barra horizontal + una vertical. Sin doble scroll confuso.
- **Auto-centrado**: el viewport aterriza automáticamente cerca de HOY/semana actual/mes actual.
- **Top deterioration strip**: los 5 peores deterioros visibles como chips rojos arriba de la matriz.
- **Weekday focus**: chips prominentes con label contextual ("Comparando DOM vs DOM").
- **Drill mejorado**: toggle entre Plan vs Real y Momentum en el inspector lateral. Fullscreen para análisis profundo.
- **NaN eliminado**: ningún valor muestra "NaN%" o texto roto.

---

## QUÉ NO CAMBIA

- **Cálculos base**: los serving facts y el backend no se modificaron.
- **Serving governance**: RAW → MV → FACTS → UI intacto.
- **Evolution mode**: disponible como modo legacy secundario, sin cambios.
- **Plan versions**: misma lógica de carga y selección.
- **Filtros**: país, ciudad, tajada, año, mes — mismos controles.
- **Export (CSV)**: misma funcionalidad.
- **Behavioral MVP**: mismo panel diagnóstico.

---

## RIESGOS CONOCIDOS

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Daily con muchas ciudades puede tener DOM pesado | Rendimiento | Colapsar manualmente; column windowing activo |
| Sin momentum data en algunos casos | Visual | Fallback a attainment view con peso normal |
| Modos Executive/Diagnostic/Comparative sin funcionalidad | Confusión | Documentado como infraestructura; solo Operational es funcional |

---

## NOVEDADES TÉCNICAS

- Color severity scale en `operationalMomentumEmphasis.js` (función pura, sin estado)
- Viewport centering engine en `projectionViewportFocusEngine.js`
- Single scroll owner via `overflow: clip`
- User collapse governance con `userToggledRef`

---

## CÓMO PROBAR

Ver `CONTROL_TOWER_OPERATIONAL_ACCEPTANCE_SCRIPT.md` para guía paso a paso.
