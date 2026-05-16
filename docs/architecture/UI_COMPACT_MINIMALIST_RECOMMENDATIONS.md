# YEGO Control Tower — Hacia una UI Compacta y Minimalista

**Fecha:** 2026-05-15
**Tipo:** Recomendaciones de diseño sin pérdida funcional

---

## Principio

> **Cada píxel de chrome es un píxel robado a los datos.** La UI debe desaparecer cuando el operador mira los números, y aparecer solo cuando necesita actuar.

---

## 1. Fusión Header + Nav en una sola barra

### Antes (3 barras, ~140px)
```
┌────────────────────────────────────────────┐ 56px
│ [YEGO] Control Tower    usuario  Admin ⚙  │
├────────────────────────────────────────────┤ 44px
│ Performance │ Drivers │ Riesgo │ Operación │
├────────────────────────────────────────────┤ 40px
│ Omniview Matrix │ Ctrl Loop │ Reportes ... │
├────────────────────────────────────────────┤
│ DATOS                                      │
```

### Propuesta (1 barra, ~48px)
```
┌────────────────────────────────────────────┐ 48px
│ [Y] Operación ▾  │ Omniview Matrix · LOB · Oport  │ usuario ⚙│
└────────────────────────────────────────────┘
```

- El logo se reduce a `[Y]` o un ícono de 24px.
- El tab principal + subtab se fusionan en un breadcrumb o dropdown: `Operación ▾ > Omniview Matrix`.
- Los subtabs secundarios se colapsan bajo un `···` o se muestran como pestañas pequeñas inline.
- El botón Admin y el usuario se mueven a la derecha, compactos.
- **Ganancia: ~92px verticales liberados para datos.**

---

## 2. Controles de Matriz Colapsables por Defecto

### Situación actual

Los controles de la Omniview Matrix ocupan ~130px incluso antes de que el operador los toque:

```
┌────────────────────────────────────────────┐
│ Grano [Mensual|Semanal|Diario]             │
│ País [▾] Ciudad [▾] Tajada [▾] Flota [▾] │
│ Año [▾] Mes [▾] Subflotas ☐              │
├────────────────────────────────────────────┤
│ Vista [Evolución|Vs Proyección] [Compacto] │
│ KPI focus [Trips|Revenue|Drivers|...]      │
│ Exportar CSV · Cargar datos · Versión ▾    │
└────────────────────────────────────────────┘
```

### Propuesta

Barra de herramientas flotante de una línea, contexto-dependiente:

```
┌────────────────────────────────────────────┐
│ Mensual ▾ │ Lima ▾ │ 2026 ▾ │ 🔍 Filtros  │ ← solo 40px
└────────────────────────────────────────────┘
```

- **Grano, país, año y mes** visibles en una sola fila horizontal compacta.
- **Ciudad, tajada, flota, KPI focus, subflotas** colapsados detrás del botón `🔍 Filtros` que abre un drawer o popover.
- **Vista (Evolución/Vs Proyección) y densidad (Compacto)** movidos a un menú `···` en la esquina.
- **"Cargar datos"** solo visible en modo lazy-load; si ya está cargado, desaparece.
- **Ganancia: ~90px verticales liberados.**

---

## 3. Banners que No Compitan con los Datos

### Situación actual

Los banners (integridad, YTD, contexto, oportunidades) usan `rounded-lg border shadow-sm px-4 py-2` — mismo lenguaje visual que las tarjetas de datos. El ojo no sabe diferenciar "esto es un aviso" de "esto es un dato".

### Propuesta: Sistema de notificaciones inline

```
┌────────────────────────────────────────────┐
│ 🟢 Data fresca · Cobertura 98% · 3 oportunidades →  │ ← 24px, solo texto
└────────────────────────────────────────────┘
```

- **Una sola línea de estado** (24-28px) que consolida: freshness + cobertura + oportunidades + integridad.
- Solo el estado `warning` o `broken` muestra un banner visible con fondo de color.
- El estado `ok` se muestra como texto gris discreto en la barra de estado.
- Al hacer hover o clic, se expande un tooltip con detalle.
- **Los banners de YTD, contexto e integridad se fusionan en esta barra de estado.**
- **Ganancia: ~100px verticales cuando todo está OK.**

---

## 4. Sidebar de Navegación Colapsable

### Propuesta: Rail lateral al estilo VS Code

```
┌──┬─────────────────────────────────────────┐
│📊│ Omniview Matrix                          │
│🚗│                                          │
│⚠ │  ┌──────────────────────────────────┐   │
│📋│  │ MATRIZ DE DATOS                   │   │
│🏥│  │                                   │   │
│  │  └──────────────────────────────────┘   │
└──┴─────────────────────────────────────────┘
 48px
```

- **Rail izquierdo de 48px** con íconos por tab: 📊 Performance, 🚗 Drivers, ⚠ Riesgo, 📋 Operación, 🏥 Diagnósticos.
- Al hacer hover sobre un ícono, se despliega un flyout con los subtabs.
- Al hacer clic, se fija la navegación expandida (como VS Code).
- Esto libera ~100px horizontales y elimina la segunda barra de navegación.
- El breadcrumb superior muestra la ubicación actual: `Operación › Omniview Matrix`.

---

## 5. Modos de Densidad por Rol

No todos los usuarios necesitan la misma cantidad de información. La UI debería adaptarse:

| Modo | Para | Qué muestra |
|------|------|------------|
| **Ejecutivo** | Dirección | Solo KPIs agregados por país, sin drill. Tarjetas grandes, fuente 16px. |
| **Operador** (default) | Equipo de operaciones | Matriz completa con drill lateral. Fuente 12px. |
| **Analista** | Data/BI | Matriz expandida con inspector abierto por defecto, queries visibles, export. Fuente 11px. |
| **Compacto** | Monitores pequeños / tablet | Fuente 10px, sin banners, drill en modal en lugar de sidebar. |

Cada modo es un toggle en el perfil o en la barra de herramientas. No requiere cambios de código por vista — es un sistema de variables CSS/tailwind.

---

## 6. Lenguaje Visual Minimalista

### 6.1 Menos bordes, más espacio negativo

```
ANTES:                               DESPUÉS:
┌──────────────────────────┐         ┌──────────────────────────┐
│ ┌──────────────────────┐ │
│ │ bordered card        │ │            Card content
│ │ with shadow          │ │            separated by
│ └──────────────────────┘ │            whitespace only
│ ┌──────────────────────┐ │
│ │ another bordered     │ │
│ │ card                 │ │            No borders
│ └──────────────────────┘ │            unless interactive
└──────────────────────────┘         └──────────────────────────┘
```

- Eliminar `border` y `shadow-sm` de tarjetas internas que no son interactivas.
- Usar `border` solo en: tablas de datos, inputs, botones, paneles colapsables.
- Separar secciones con `gap` y padding, no con líneas `border-b`.

### 6.2 Escala de grises para chrome, color solo para datos

```
Chrome (navegación, controles, labels): slate-400 / slate-500
Datos (KPIs, números):                gray-800 / gray-900
Alertas (severidad):                  emerald / amber / red (solo en datos)
Acciones (CTAs):                      blue-600 (solo en botones)
```

Esto crea una jerarquía natural: lo gris es "sistema", lo negro es "información", lo colorido es "atención requerida".

### 6.3 Tipografía: menos tamaños, más contraste

| Actual | Propuesto |
|--------|-----------|
| 6 tamaños distintos por vista (`text-[10px]` a `text-lg`) | 3 tamaños: caption, body, heading |
| `text-[10px]` para datos | `text-xs` (12px) para metadatos, `text-sm` (14px) para KPIs |
| Uppercase tracking-wide en labels | Sentence case, sin tracking — igual de legible, menos ruido visual |

---

## 7. Tabla de la Matriz: Lectura Horizontal sin Fricción

### 7.1 Columnas con ancho adaptable

- Las columnas de períodos (semanas/días) deben tener ancho `minmax(80px, 1fr)`.
- La columna de ciudad/línea debe tener `sticky left: 0` con `min-width: 180px`.
- El usuario debería poder redimensionar columnas arrastrando el borde (pequeña librería o CSS `resize`).

### 7.2 Zebra sutil en lugar de bordes

```
ANTES: Cada celda con border                     DESPUÉS: Zebra cada 2 filas
┌──────┬──────┬──────┐                           ┌──────┬──────┬──────┐
│ Celda│ Celda│ Celda│                           │ Celda│ Celda│ Celda│
├──────┼──────┼──────┤                           │ Celda│ Celda│ Celda│  ← bg-slate-50
│ Celda│ Celda│ Celda│                           │ Celda│ Celda│ Celda│
├──────┼──────┼──────┤                           │ Celda│ Celda│ Celda│  ← bg-slate-50
```

Elimina ~50% del ruido visual de bordes. Solo mantener `border-b` entre filas.

---

## 8. Sistema de Notificaciones en Lugar de Banners

En lugar de banners que compiten con los datos, usar un centro de notificaciones:

```
┌────────────────────────────────────────────┐
│ 🔔 3                                      │ ← campana con badge
└────────────────────────────────────────────┘
```

Al hacer clic, despliega:

```
┌──────────────────────────┐
│ ⚠ Integridad de datos    │
│ ⚠ Oportunidades (12)     │
│ ✓ YTD consistente        │
└──────────────────────────┘
```

Solo los ítems `⚠` producen una notificación. Los `✓` se archivan automáticamente pero se pueden revisar.

---

## 9. Resumen Visual del Antes y Después

```
ANTES (~340px de chrome antes de los datos):
┌────────────────────────────────────────────┐ 56px header
├────────────────────────────────────────────┤ 44px main nav
├────────────────────────────────────────────┤ 40px sub nav
├────────────────────────────────────────────┤ 80px filtros
├────────────────────────────────────────────┤ 36px freshness banner
├────────────────────────────────────────────┤ 28px data trust banner
├────────────────────────────────────────────┤ 60px controles matriz
├────────────────────────────────────────────┤ ← DATOS (solo ~460px en 1080p)
└────────────────────────────────────────────┘

DESPUÉS (~96px de chrome antes de los datos):
┌────────────────────────────────────────────┐ 48px header + nav fusionado
├────────────────────────────────────────────┤ 24px barra de estado inline
├────────────────────────────────────────────┤ 40px filtros compactos (1 fila)
├────────────────────────────────────────────┤ ← DATOS (~700px en 1080p, +52%)
└────────────────────────────────────────────┘
```

---

## 10. Roadmap de Implementación

| Fase | Cambio | Impacto | Esfuerzo | Rompe algo? |
|------|--------|---------|----------|------------|
| **Fase 1** | Drill colapsable (ya hecho) | Alto | 15 min | No |
| **Fase 2** | Fusionar header + nav en 1 barra | Alto | 3-4h | App.jsx — cambio grande |
| **Fase 3** | Barra de estado inline (consolida 4 banners) | Alto | 2-3h | Solo renderizado condicional |
| **Fase 4** | Controles de matriz en 1 fila colapsable | Medio | 2h | OmniviewMatrix.jsx |
| **Fase 5** | Rail lateral de navegación | Medio | 4-5h | App.jsx — reemplaza nav horizontal |
| **Fase 6** | Modos de densidad | Medio | 3h | Context + CSS variables |
| **Fase 7** | Zebra + eliminar bordes internos | Bajo | 1h | Solo CSS |
| **Fase 8** | Centro de notificaciones | Bajo | 3h | Componente nuevo |

**Cada fase es independiente.** Se puede implementar en cualquier orden sin bloquear las demás.

---

## Conclusión

La UI actual tiene **exceso de chrome**: ~340px de barras, banners y controles antes de que el operador vea un solo dato. Las propuestas anteriores reducen eso a ~96px sin eliminar **ninguna** funcionalidad. Todo sigue accesible, solo que colapsado, fusionado o movido a una interacción secundaria (hover, clic, drawer).

El resultado es una interfaz donde los datos ocupan >85% del viewport en lugar del ~55% actual. El operador pasa de "navegar la UI" a "leer los datos".
