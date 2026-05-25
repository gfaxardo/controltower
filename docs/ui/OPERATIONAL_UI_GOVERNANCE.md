# OPERATIONAL UI GOVERNANCE — YEGO Control Tower

**Fuente oficial UX. Fecha: 2026-05-25**
**Motor: Control Foundation**
**Versión: 1.0.0**

---

## 1. PRINCIPIO RECTOR

La UX de YEGO Control Tower es una **interfaz operacional**, no un dashboard cosmético.

**Jerarquía visual operacional:**
1. Acción principal y datos operacionales críticos
2. Información de soporte y contexto
3. Navegación
4. Alertas secundarias y metadatos

**Objetivo de rendimiento UX:**
- Operable en laptop estándar (1366x768)
- Legible a 100% zoom sin pérdida de información
- Funcional a 110% y 125% zoom
- Mínimo scroll horizontal (solo en matrix que lo requiere)
- CTA siempre visible y accesible

---

## 2. TYPOGRAPHY RULES

### Escala operacional

| Token CSS | Tamaño | Tailwind | Uso |
|-----------|--------|----------|-----|
| `--ct-font-micro` | 10px | — | **SOLO matrix cell data interna.** Prohibido fuera de Matrix |
| `--ct-font-2xs` | 11px | `text-2xs` | Badges, hints operacionales, metadata no crítica |
| `--ct-font-xs` | 12px | `text-xs` | **Mínimo para UI chrome.** Labels, botones, filtros |
| `--ct-font-sm` | 13px | `text-sm` | Texto secundario, tooltips, descripciones |
| `--ct-font-md` | 14px | `text-base` | Texto de lectura, tablas, párrafos |
| `--ct-font-lg` | 16px | `text-lg` | Headers de sección |
| `--ct-font-xl` | 18px | `text-xl` | Títulos de vista |
| `--ct-font-2xl` | 20px | `text-2xl` | KPIs primarios |
| `--ct-font-3xl` | 24px | `text-3xl` | KPIs destacados |

### Reglas de hierro

1. **NUNCA** usar `text-[6px]`, `text-[7px]`, `text-[8px]` fuera de matrix cells.
2. **NUNCA** usar `text-[9px]` en UI chrome nuevo.
3. `text-[10px]` → reemplazar con `text-xs` (12px) o `text-2xs` (11px).
4. `text-2xs` (antes 10px, ahora 11px) es el **mínimo operacional** para UI chrome.
5. El contraste de texto DEBE cumplir WCAG AA (4.5:1 para texto normal).

### Excepción: Omniview Matrix

La matrix requiere densidad extrema. Se permite:
- `text-[9px]` a `text-[11px]` en celdas (cálculo dinámico por modo compact/normal)
- `text-[8px]` en tooltips y badges internos de matrix
- Estos tamaños son **exclusivos** de `BusinessSliceOmniviewMatrix*` y `OmniviewProjectionDrill`

---

## 3. SPACING RULES

### Escala operacional

| Token CSS | Valor | Tailwind | Uso |
|-----------|-------|----------|-----|
| `--ct-space-1` | 4px | `gap-1` / `p-1` | Entre íconos, badges |
| `--ct-space-2` | 8px | `gap-2` / `p-2` | Entre chips, label-input |
| `--ct-space-3` | 12px | `gap-3` / `p-3` | Entre secciones, padding panel |
| `--ct-space-4` | 16px | `gap-4` / `p-4` | Padding de contenido |
| `--ct-space-6` | 24px | `gap-6` / `p-6` | Separación mayor |
| `--ct-space-8` | 32px | `gap-8` / `p-8` | Separación de vistas |

### Reglas

1. **Padding de banner**: máximo `py-1` (4px) para banners colapsados.
2. **Gap entre secciones**: consistente `gap-2` o `gap-3`.
3. **Padding de página**: `px-4 py-2`.
4. No usar `space-y-*` sin consistencia. Preferir `gap` con flex/grid.
5. No usar `px` arbitrarios como `px-3.5` o `px-7`.

---

## 4. DENSITY RULES

### Modos

| Modo | Cuándo usar |
|------|------------|
| `--ct-density-normal` (1) | UI estándar, formularios, vistas generales |
| `--ct-density-compact` (0.75) | Modo compacto de matrix, toolbars densas |
| `--ct-density-sparse` (1.25) | Vistas ejecutivas, presentaciones |

### Reglas

1. Cada vista debe funcionar en densidad normal.
2. El modo compacto es un override opcional, no el default.
3. La matrix soporta ambos modos (toggle compact/normal).
4. No aplicar densidad compact a formularios operacionales.

---

## 5. MAX HEIGHTS & SCROLL REGIONS

### Alturas operacionales

| Elemento | Altura | Nota |
|----------|--------|------|
| Toolbar | 36px (`--ct-toolbar-height`) | Estándar |
| Banner colapsado | 40px máximo (`--ct-banner-max-height`) | Incluye padding |
| Table header | 36px (`--ct-table-header`) | Sticky |
| Table row | 32px (`--ct-table-row`) | 24px compact |
| KPI card | 80px mínimo (`--ct-kpi-card-min`) | Altura fija |

### Scroll regions

**PROHIBIDO** usar `calc(100vh - Npx)` con N hardcodeado. En su lugar:

1. Usar CSS custom properties:
   ```css
   .ct-scroll-region {
     height: var(--scroll-height, calc(100vh - var(--header-height, 64px) - var(--toolbar-height, 36px)));
   }
   ```

2. La matrix es la excepción — su `calc(100vh - 240px)` debe mantenerse pero documentarse como deuda temporal.

3. Todo panel lateral usa `max-h-[85vh]` máximo.

4. Las modales usan `max-h-[90vh]` con `overflow-y-auto`.

---

## 6. FORM RULES

### Grid de formulario

```css
.ct-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  max-width: 768px; /* --ct-page-narrow */
}
```

### Reglas

1. **Labels**: mínimo `text-xs` (12px), uppercase, color `text-ct-text2`.
2. **Inputs/Selects**: altura mínima 36px (`--ct-input-height`).
3. **Select nativos**: usar `border border-gray-200 rounded-md text-sm px-2.5 py-1.5`.
4. **NUNCA** hacer formularios full-width con 2 campos — usar `ct-form-grid`.
5. **CTAs**: agrupar en zona de acciones con `ct-action-zone` (borde superior, `pt-3`).
6. **Dropdowns/Selects**: mantener nativos hasta que se requiera biblioteca. Sin hacks de posicionamiento.

### Validación

- Campos requeridos: `*` rojo junto al label.
- Estado de error: borde `border-red-400` + fondo `bg-red-50`.
- Estado de éxito: borde `border-emerald-300`.

---

## 7. BANNER RULES

### Jerarquía visual (de mayor a menor)

1. **CTAs y acciones** (primaria)
2. **Datos operacionales** (secundaria)
3. **Banners contextuales** (terciaria)

### Reglas

1. Banner colapsado: `px-3 py-1 text-xs`. Altura máxima ~32px.
2. Banner expandible: mantener el patrón de toggle (click para expandir).
3. Color por severidad:
   - OK/Emerald → `bg-emerald-50 border-emerald-300 text-emerald-800`
   - Warning/Amber → `bg-amber-50 border-amber-300 text-amber-800`
   - Error/Red → `bg-red-50 border-red-300 text-red-800`
4. **NUNCA** apilar más de 2 banners visibles simultáneamente.
5. Los banners NO deben contener tablas completas — solo resumen + expandir.
6. Texto de banner: `text-xs` (12px) mínimo.

### Componentes gobernados

| Componente | Regla |
|-----------|-------|
| `GlobalFreshnessBanner` | `py-1`, `text-xs`, tabla expandible |
| `MatrixExecutiveBanner` | `py-1`, `text-xs`, contenido colapsado |
| `OperationalStatusBar` | `py-1.5` collapse, chips `text-xs` |
| `RealMarginQualityCard` | `py-2`, `text-sm` — aceptable |

---

## 8. TABLE RULES

### Legibilidad operacional

1. Altura mínima de fila: 32px (estándar), 24px (compacto).
2. Header sticky: `sticky top-0 z-20 bg-slate-800 text-white`.
3. Columnas izquierdas sticky: `sticky left-0 z-10`.
4. Texto de celda: mínimo `text-sm` para tablas estándar, `text-xs` para tablas densas.
5. Scroll horizontal: solo en tablas anchas (matrix), con indicador de posición.
6. Totales row: siempre visible (sticky).

### Omniview Matrix (excepción)

La matrix opera con densidad extrema. Las reglas de tamaño no aplican a sus celdas. El toggle compact/normal permite elegir entre:
- **Normal**: 13px-14px en celdas, 78-100px de ancho de columna
- **Compact**: 9px-11px en celdas, 58-78px de ancho de columna

---

## 9. VIEWPORT CONTRACTS

### Breakpoints operacionales

| Viewport | Comportamiento |
|----------|---------------|
| < 768px | Navegación colapsada, tablas con scroll horizontal |
| 768-1024px | Layout funcional, paneles laterales sobre contenido |
| 1024-1366px | Layout completo, matrix con scroll |
| > 1440px | Layout completo, sin cambios |

### Contract

1. En 1366x768, el contenido operacional debe ser visible sin scroll vertical excesivo.
2. El header sticky total (nav + sub-nav + maturity) no debe exceder 90px.
3. Los CTAs deben ser visibles sin scroll en vistas principales.
4. NINGÚN componente debe requerir zoom > 125% para ser legible.

---

## 10. ZOOM CONTRACTS

| Zoom | Expectativa |
|------|------------|
| 100% | Todo legible. Mínimo operacional. |
| 110% | Todo legible. Layout funcional. |
| 125% | Contenido principal legible. Posible scroll en vistas densas. |
| > 150% | Layout puede degradarse. Prioridad: legibilidad > layout. |

---

## 11. Z-INDEX GOVERNANCE

### Registry

| Capa | z-index | Uso |
|------|---------|-----|
| Content | 1 | Contenido normal |
| Sticky column | 10 | Columnas izquierdas fijas en tablas |
| Sticky totals | 18 | Fila de totales sticky |
| Sticky header | 20 | Headers de tabla sticky |
| Overlay | 30 | Overlays de contenido |
| Header | 40 | Navegación principal |
| Panel | 50 | Paneles laterales, sidebars |
| Modal | 80 | Modales |
| Fullscreen | 100 | Vistas fullscreen |
| Max | 999 | Emergencias |

### Reglas

1. Usar solo estos valores. NO inventar `z-[15]`, `z-[25]`, etc.
2. Referenciar `--ct-z-*` en custom properties si es necesario.
3. Cada capa DEBE documentarse en qué componente se usa.

---

## 12. LAYOUT PRIMITIVES

### Clases reutilizables (de `ct-design-tokens.css`)

| Clase | Uso |
|-------|-----|
| `.ct-page` | Contenedor máximo de contenido (1440px, centrado) |
| `.ct-page-section` | Agrupación vertical con gap consistente |
| `.ct-toolbar` | Barra de herramientas horizontal |
| `.ct-panel` | Panel con borde y fondo card |
| `.ct-panel-header` | Header de panel |
| `.ct-panel-body` | Cuerpo de panel |
| `.ct-form-grid` | Grid de formulario operacional |
| `.ct-form-field` | Wrapper de campo con label |
| `.ct-scroll-region` | Región scrolleable |
| `.ct-section-header` | Header de sección |
| `.ct-kpi-strip` | Tira horizontal de KPIs |
| `.ct-action-zone` | Zona de acciones/CTAs |

### Reglas

1. Toda nueva página DEBE usar `.ct-page` como wrapper.
2. Todo nuevo formulario DEBE usar `.ct-form-grid`.
3. Todo nuevo panel DEBE usar `.ct-panel`.
4. Las CTAs DEBEN estar en `.ct-action-zone`.

---

## 13. ENFORCEMENT

### CI/CD

- El build DEBE pasar sin errores.
- PRs que introduzcan `text-[6px]`, `text-[7px]`, `text-[8px]` fuera de matrix → rechazados en review.
- PRs que introduzcan `px` arbitrarios sin token → requieren justificación.

### Code Review Checklist

- [ ] ¿Usa los tokens CSS definidos?
- [ ] ¿Texto >= `text-xs` (excepto matrix)?
- [ ] ¿Banner <= 40px colapsado?
- [ ] ¿Formulario usa grid, no full-width?
- [ ] ¿Scroll usa custom properties, no valores hardcodeados?
- [ ] ¿z-index usa los valores del registry?
- [ ] ¿Funciona en 1366x768 a 100% zoom?

---

## 14. DEBT REGISTER (conocido, aceptado temporalmente)

| Ítem | Archivo | Razón | Plan |
|------|---------|-------|------|
| `calc(100vh - 240px)` hardcodeado | `BusinessSliceOmniviewMatrixTable.jsx` | Complejidad matrix | Migrar a `--scroll-height` cuando se refactorice matrix |
| Tamaños 7px-9px en matrix | `BusinessSliceOmniviewMatrixCell.jsx`, etc. | Densidad operacional requerida | Evaluar en refactor de matrix |
| z-index hardcodeados en matrix | Varios archivos matrix | Complejidad de capas | Migrar a `--ct-z-*` en refactor |
| `text-2xs` heredado | Varios archivos | Legado previo al hardening | Eliminar progresivamente, reemplazar con `text-xs` |

---

## 15. VERSION HISTORY

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2026-05-25 | Creación inicial. Tipografía mínima 11px (chrome), 12px (contenido). Tokens CSS. Layout primitives. Z-index registry. Viewport contracts. Banner sizing. Form rules. |
