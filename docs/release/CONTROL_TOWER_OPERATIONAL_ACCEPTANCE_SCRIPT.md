# CONTROL TOWER OPERATIONAL ACCEPTANCE SCRIPT

**Date**: 2025-05-25
**Para**: Operador / QA

---

## PREPARACIÓN

1. Abrir navegador (Chrome/Firefox/Edge)
2. Navegar a la URL de Control Tower
3. Ir a `/operacion/omniview-matrix`

---

## PASO 1 — MODO PROYECCIÓN

- [ ] Seleccionar "Vs Proyección" en el toggle de modo
- [ ] Seleccionar una versión de plan en el dropdown
- [ ] La matriz debe cargar con ciudades expandidas

## PASO 2 — PRESENTE VISIBLE

- [ ] La columna actual (HOY / SEM ACT / MES ACT) debe tener:
  - [ ] Borde verde (emerald)
  - [ ] Fondo con brillo suave
  - [ ] Badge "HOY" / "SEM ACT" / "MES ACT"
  - [ ] Fuente más grande que el resto

## PASO 3 — TOP DETERIORATIONS

- [ ] Arriba de los filtros debe aparecer la tira "Momentum"
- [ ] Debe mostrar chips rojos/ámbar con los peores deterioros
- [ ] Si no hay deterioros, la tira está oculta (normal)

## PASO 4 — CELL READING

- [ ] Hacer clic en cualquier celda con datos de proyección
- [ ] La celda debe mostrar:
  - [ ] **Valor real** (grande, negrita)
  - [ ] **Delta** (flecha + porcentaje coloreado)
  - [ ] Línea pequeña de contexto (plan + avance)
- [ ] No debe aparecer "NaN", "undefined", ni "null"

## PASO 5 — MOMENTUM

- [ ] Cambiar a grano **Diario** → debe aparecer DoD
- [ ] Cambiar a grano **Semanal** → debe aparecer WoW
- [ ] Cambiar a grano **Mensual** → debe aparecer MoM
- [ ] Los colores del delta deben variar con la severidad:
  - [ ] Rojo intenso para caídas grandes
  - [ ] Verde intenso para subidas grandes

## PASO 6 — WEEKDAY FOCUS (Diario)

- [ ] Activar chips DOM/LUN/MAR/MIÉ/JUE/VIE/SÁB
- [ ] El chip activo debe verse más grande y con brillo azul
- [ ] La label debe decir "Comparando [DÍA] vs [DÍA]"
- [ ] Desactivar → volver a "Todos los días"

## PASO 7 — EXPAND/COLLAPSE

- [ ] Verificar que las ciudades están desplegadas
- [ ] Colapsar una ciudad (clic en la fila de ciudad)
- [ ] La ciudad debe ocultar sus líneas
- [ ] Volver a expandirla
- [ ] Cambiar de país → las ciudades deben re-expandirse

## PASO 8 — DRILL

- [ ] Hacer clic en una celda de proyección
- [ ] Debe abrirse el panel lateral derecho
- [ ] Alternar entre pestañas "Plan vs Real" y "Momentum"
- [ ] Cerrar con Escape o X

## PASO 9 — FULLSCREEN

- [ ] Clic en "Pantalla completa" (ícono expandir)
- [ ] La matriz debe ocupar toda la pantalla
- [ ] El drill debe seguir visible
- [ ] Salir con Escape o "Salir (Esc)"

## PASO 10 — SCROLL

- [ ] Verificar que solo hay UNA barra horizontal
- [ ] Verificar que solo hay UNA barra vertical
- [ ] Usar botón "Ir a hoy" (esmeralda) → debe centrar el presente
- [ ] El footer debe mostrar "Mostrando columnas X-Y de Z"

## PASO 11 — BEHAVIORAL MVP (si aplica)

- [ ] Navegar a la sección de Behavioral MVP
- [ ] Verificar que carga sin errores
- [ ] Revisar dimensiones y gaps

---

## FEEDBACK

Registrar:
- ¿Qué se entendió en < 2 segundos?
- ¿Qué confundió?
- ¿Qué faltó?
- ¿Qué sobró?
- ¿El color comunica correctamente la severidad?
