# UX-H4A — OMNIVIEW SHELL CONTRACT

**Motor:** Control Foundation UX Hardening  
**Versión:** 1.0.0  
**Fecha:** 2026-05-31  

---

## OmniviewShell

Contenedor único para toda la superficie operacional de Omniview.

### Ámbito

El shell envuelve:
1. CommandHeader (modo, grano, periodo, stats)
2. MomentumPriorityStrip
3. Controls (filtros, grain, visualización, KPI selector)
4. Status bars y banners (freshness, proyección, YTD, integridad)
5. Priority Layer
6. Insights Panel
7. Matrix Table (viewport con scroll)

### Reglas

1. **Padding horizontal único:** `mx-3 sm:mx-4` en el wrapper exterior. El shell ocupa todo el ancho disponible dentro del margin.

2. **Border radius común:** `rounded-lg` en el shell. Ningún componente interno debe tener su propio `rounded-*`.

3. **Fondo común:** `bg-ct-surface` en el shell. Los componentes internos heredan el fondo o usan `bg-ct-surface` explícitamente.

4. **Divisores internos:** `divide-y divide-ct-border/40`. Los `space-y-*` gaps entre componentes están prohibidos — los divisores unen en lugar de separar.

5. **Borde común:** `border border-ct-border` en el shell. Ningún componente interno debe tener su propio borde completo. Se permiten bordes parciales: `border-l-[3px]` para accent, `border-t` solo para separación interna en sub-secciones.

6. **Matrix viewport:** Empieza alineado con el header. El scroll horizontal ocurre dentro del viewport, no rompe el shell. `overflow-hidden` en el shell contiene el scroll interno.

7. **Fullscreen:** Mantiene el contrato. El modal fullscreen (`fixed inset-0 bg-white overflow-y-auto`) reemplaza el shell. La tabla usa `isFullscreen={true}` para restablecer `overflow-y-auto` con `max-height`.

8. **Tokens:** Todos los componentes deben usar `ct-*` variables CSS. `bg-white`, `border-gray-*`, `rounded-lg` de Tailwind están prohibidos dentro del shell.

### Anti-patrones

```jsx
// PROHIBIDO — card independiente dentro del shell
<div className="rounded-lg border border-ct-border bg-white shadow-sm">

// PROHIBIDO — espacio entre secciones
<div className="space-y-2">
  <ComponentA />
  <ComponentB />
</div>

// CORRECTO — componente transparente que hereda del shell
<div className="px-4 py-2">
  <ComponentA />
</div>

// CORRECTO — divisores del shell
<div className="divide-y divide-ct-border/40">
  <ComponentA />
  <ComponentB />
</div>
```
