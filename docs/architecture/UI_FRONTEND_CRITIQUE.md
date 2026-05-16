# YEGO Control Tower — Crítica Constructiva de UI/Frontend

**Fecha:** 2026-05-15
**Tipo:** Diagnosis de experiencia de usuario y autoridad visual
**Alcance:** Omniview Matrix, sistema de navegación global, jerarquía visual

---

## Resumen Ejecutivo

La UI del Control Tower tiene **buena densidad de datos** pero sufre tres problemas estructurales
que degradan la experiencia del operador:

1. **Los paneles de drill nunca liberan el espacio horizontal** — la matriz de datos nunca ocupa el ancho completo.
2. **No existe modo pantalla completa** — el operador no puede expandir la matriz para sesiones de análisis profundo.
3. **La autoridad visual es débil** — todo compite por la misma jerarquía, nada tiene peso visual claro.

Los tres se pueden resolver con cambios quirúrgicos sin tocar lógica de negocio.

---

## 1. El Drill de Proyección No Se Puede Cerrar

### Diagnóstico

```
┌──────────────────────────────────────────────┬──────────────────┐
│ MATRIZ (flex-1 min-w-0)                      │ DRILL (w-[25rem])│
│ ← solo ocupa ~60% del viewport               │ ← siempre ocupa  │
│                                              │    25rem fijos   │
│                                              │                  │
│                                              │  ┌──────────────┐│
│                                              │  │ "Click en una ││
│                                              │  │  celda..."   ││
│                                              │  │  (placeholder)││
│                                              │  └──────────────┘│
└──────────────────────────────────────────────┴──────────────────┘
```

**Archivos:** `OmniviewProjectionDrill.jsx:25-44`, `BusinessSliceOmniviewInspector.jsx:56-75`

**Causa raíz:** Ambos componentes renderizan un `<aside>` fijo incluso cuando `selection === null`.
Cuando el usuario cierra el drill (click en X o click en la misma celda), `setSelection(null)` se
ejecuta correctamente, pero el componente retorna un `<aside>` placeholder vacío con `w-[25rem]`.
El layout `flex gap-3` siempre asigna ese espacio al panel, aunque no tenga contenido.

**Impacto:** La matriz de Proyección vs Real solo dispone de `~60%` del viewport.
El operador **nunca ve los datos a ancho completo**. En pantallas ≤1366px, la tabla requiere
scroll horizontal constante incluso para ver 4 columnas.

### Solución (no implementada — propuesta)

```jsx
// OmniviewProjectionDrill.jsx — cambio quirúrgico
export default function OmniviewProjectionDrill ({ selection, ... }) {
  // En lugar de renderizar aside vacío, retornar null
  if (!selection) return null

  return (
    <aside className={...}>
      <DrillContent ... />
    </aside>
  )
}
```

**Lo mismo para `BusinessSliceOmniviewInspector`.** Cuando no hay selección, no debe ocupar espacio.

**Resultado:** El `<div className="flex-1 min-w-0">` de la matriz ocuparía el 100% del ancho
cuando el drill está cerrado. Al hacer clic en una celda, el drill aparece y la matriz se adapta.
El operador gana ~40% más de espacio de lectura por defecto.

---

## 2. Ausencia de Modo Pantalla Completa

### Diagnóstico

La Omniview Matrix compite con tres barras fijas antes de llegar a los datos:

```
┌─────────────────────────────────────────────┐ ← viewport 100vh
│ HEADER: YEGO Control Tower + user + admin  │    56px (h-14)
├─────────────────────────────────────────────┤
│ MAIN NAV: tabs (Performance, Drivers...)    │    44px
├─────────────────────────────────────────────┤
│ SUB NAV: Omniview Matrix | Control Loop...  │    40px
├─────────────────────────────────────────────┤
│ Omniview Controls: grain, filtros, modo...  │    ~80px
├─────────────────────────────────────────────┤
│ Banners: integridad, YTD, oportunidades...  │    ~100px
├─────────────────────────────────────────────┤
│ MATRIZ DE DATOS                             │ ← solo ~55% del viewport
│ (con scroll horizontal + vertical)          │
└─────────────────────────────────────────────┘
```

En un monitor 1080p (1920×1080), la matriz solo dispone de ~600px de altura vertical.
El operador tiene que hacer scroll para ver datos y perder el contexto de los banners.

### Solución (no implementada — propuesta)

Añadir un botón de "Pantalla completa" en la barra de controles de la matriz que:

1. Oculte el header, main nav y sub nav con `position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 50; background: white`.
2. Conserve solo los controles de la matriz (grain, filtros, modo, KPI focus) en una barra flotante mínima.
3. Muestre un botón "Salir de pantalla completa" o use la tecla `Escape`.
4. Sea toggleable con un ícono `⛶` en la esquina superior derecha de la matriz.

```jsx
// Propuesta de estado en BusinessSliceOmniviewMatrix.jsx
const [fullscreen, setFullscreen] = useState(false)

// En el JSX:
<div className={fullscreen
  ? 'fixed inset-0 z-50 bg-white overflow-auto p-4'
  : ''
}>
  {fullscreen && (
    <button onClick={() => setFullscreen(false)}
      className="fixed top-4 right-4 z-50 ...">
      Salir pantalla completa
    </button>
  )}
  {/* contenido de la matriz */}
</div>
```

---

## 3. Autoridad Visual Débil en Todo el Sistema

### Diagnóstico

El sistema sufre de **jerarquía visual plana**: todo tiene el mismo peso, nada guía la mirada.

#### Problemas específicos

| Problema | Ubicación | Impacto |
|----------|-----------|---------|
| **Tabs activos poco visibles** | `App.jsx:237-241` — `border-b-2 border-blue-600` sobre fondo blanco es muy sutil | El operador no identifica rápido en qué tab está |
| **Tamaños de fuente microscópicos** | Uso masivo de `text-[10px]`, `text-[11px]` en toda la UI | Fatiga visual; ilegible en monitores 1080p a distancia normal |
| **Header sin peso visual** | `App.jsx:253-264` — logo azul pequeño, texto YEGO gris, todo plano | No hay sensación de "aplicación enterprise" |
| **Contenedores sin sombra ni separación** | `bg-white border border-gray-200` repetido sin variación | Todo parece el mismo componente; el ojo no diferencia datos de chrome |
| **Sin color semántico estructural** | Solo azul (`blue-600`) para activo, gris para todo lo demás | Paleta monocromática; el color solo aparece en datos (verde/rojo/ámbar de KPIs) |
| **Banners que compiten con datos** | Banners de integridad, YTD, contexto, oportunidades — todos con border y bg | El ojo no sabe si mirar el banner o la matriz |
| **Matriz sin jerarquía de lectura** | `BusinessSliceOmniviewMatrixTable` — todas las celdas mismo peso | Las celdas de totales y subtotales no se distinguen de celdas individuales |

#### Ejemplo concreto: comparación de peso visual

```
ANTES (todo mismo peso):
┌────────────────────────────────────────────────────┐
│ [Banner Data Trust]            bg-slate-50, 10px   │ ← mismo peso
│ [Contexto: freshness, comp...] bg-slate-50, 10px   │ ← mismo peso
│ [Oportunidades: 12 detectadas] bg-white, 10px      │ ← mismo peso
│ ┌────────────────────────────────────────────────┐ │
│ │ MATRIZ DE DATOS              bg-white, 10-11px  │ │ ← mismo peso que los banners
│ └────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

### Solución (no implementada — propuesta)

#### A. Escala tipográfica funcional

| Rol | Tamaño actual | Tamaño propuesto | Uso |
|-----|--------------|-----------------|-----|
| Título de vista | `text-lg` (18px) | `text-xl font-bold` (20px) | "Omniview Matrix", "Real LOB Drill" |
| Encabezado de sección | `text-[10px] uppercase` | `text-xs font-semibold uppercase` (12px) | Banners, contexto |
| Dato principal (KPI) | `text-sm` o `text-xs` | `text-sm font-semibold tabular-nums` (14px) | Celdas de la matriz |
| Dato secundario (delta) | `text-[10px]` | `text-[11px]` (11px) | Deltas, comparativos |
| Metadato / chrome | `text-[10px]` | `text-[10px] text-slate-400` | Freshness, cobertura, período |

#### B. Distinguir datos de chrome

- **Datos** (matriz, KPIs): fondo blanco, `shadow-sm`, tipografía más grande, color negro/gris-800.
- **Banners/contexto** (no son datos): fondo gris muy claro `bg-slate-50/80`, sin sombra, tipografía pequeña, colapsables por defecto.
- **Navegación**: mantenerla mínima pero darle un indicador activo más visible (fondo azul suave `bg-blue-50` en tab activo en lugar de solo `border-b-2`).

#### C. Peso visual del header

```jsx
// Propuesta de mejora sutil
<header className="... bg-slate-900 text-white ...">
  <div className="w-7 h-7 rounded-lg bg-blue-500 ...">
  <span className="font-bold text-white">YEGO</span>
  <span className="text-slate-300">Control Tower</span>
</header>
```

Un header oscuro ancla visualmente la aplicación y hace que el contenido (blanco) se lea como
"área de trabajo". Es un patrón estándar en dashboards enterprise (Grafana, Datadog, Retool).

#### D. Totales con peso visual

En `BusinessSliceOmniviewMatrixTable`, las filas de totales deben tener:
- Fondo `bg-slate-100` o `bg-blue-50/30`
- Tipografía `font-bold`
- Separador visual (`border-t-2 border-slate-300`) antes de la fila de totales

---

## 4. Grid Resistiva de Proyección vs Real

### Diagnóstico

La tabla de proyección (`BusinessSliceOmniviewMatrixTable mode="projection"`) tiene columnas
para múltiples períodos (semanas/días del mes). En granularidad diaria con mes completo son
~30 columnas. Con el drill ocupando 25rem fijos, se ven ~4 columnas sin scroll.

Además, la tabla no tiene:
- **Sticky columns** para la columna de ciudad/Línea (se pierde al hacer scroll horizontal).
- **Resize de columnas** (todas tienen ancho fijo).
- **Indicador visual de columna actual** (¿qué período es "hoy" o "esta semana"?).

### Solución (no implementada — propuesta)

- Hacer sticky la primera columna (ciudad/línea) con `position: sticky; left: 0; z-index: 2; bg-white`.
- Marcar la columna del período actual con un sutil `bg-blue-50/30` o un indicador `▾` en el header.
- Liberar el drill (sección 1) es el mayor ganador de espacio horizontal.

---

## 5. Prioridades de Corrección

| # | Problema | Severidad | Esfuerzo | Archivos |
|---|----------|-----------|----------|----------|
| 1 | Drill no se cierra (retornar null sin selection) | **Crítico** | 15 min | `OmniviewProjectionDrill.jsx`, `BusinessSliceOmniviewInspector.jsx` |
| 2 | Modo pantalla completa | **Alto** | 2-3h | `BusinessSliceOmniviewMatrix.jsx` |
| 3 | Sticky column ciudad/línea en matriz | **Alto** | 1-2h | `BusinessSliceOmniviewMatrixTable.jsx` |
| 4 | Header con autoridad visual | **Medio** | 1h | `App.jsx` |
| 5 | Escala tipográfica funcional | **Medio** | 3-4h | `tailwind.config.js` + barrido de componentes |
| 6 | Separar datos de chrome visualmente | **Medio** | 2-3h | Varios componentes de Omniview |
| 7 | Totales con peso visual | **Bajo** | 1h | `BusinessSliceOmniviewMatrixTable.jsx` |
| 8 | Resize de columnas | **Bajo** | 3-4h | `BusinessSliceOmniviewMatrixTable.jsx` |

---

## Conclusión

La UI tiene una base sólida de datos. Los problemas no son de arquitectura de información
(ya resueltos en la limpieza anterior), sino de **experiencia de lectura**: el operador
no puede ver los datos con comodidad porque el espacio está mal distribuido y la jerarquía
visual no guía la mirada hacia lo importante.

**La corrección #1 (drill colapsable) es trivial y tiene el mayor impacto inmediato.**
Recomiendo implementarla ya. Las demás son mejoras progresivas que no rompen nada existente.
