# DEFAULT EXPANDED CITIES — DECISION LOG

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## PROBLEMA

Las ciudades aparecían colapsadas por defecto en grano `daily` (introducido en FASE 1H.2 como protección de DOM). Esto rompía el primer vistazo operacional — el operador debía expandir manualmente para ver datos.

## DECISIÓN

### Antes
- `grain === 'daily'` → todas las ciudades colapsadas por defecto (Set completo)
- Otros granos → expandido por defecto (Set vacío)
- Cada cambio de `grain` o `cities` → reset al default

### Después
- Todos los granos → **expandido por defecto** (Set vacío inicial)
- El usuario puede colapsar manualmente ciudades individuales
- `expandAll` / `collapseAll` disponibles en la barra de herramientas
- El estado de colapso **solo se resetea** cuando cambia el conjunto de ciudades (filtros/país/grano/plan version)
- El usuario **nunca pelea** con el sistema: su preferencia se respeta hasta que cambie el contexto

## GOVERNANCE

| Evento | Comportamiento |
|---|---|
| Carga inicial | Todas expandidas |
| Usuario colapsa una ciudad | `userToggledRef = true`, estado respetado |
| Cambio de filtro (país, ciudad, grano) | `prevCityKeys !== currentKeys` → reset a expandido |
| Cambio de modo (Evolución ↔ Proyección) | Reset a expandido |
| Cambio de plan version | Reset a expandido |
| Cambio de KPI focus mode | NO reset |
| Scroll / zoom / densidad | NO reset |

## IMPLEMENTACIÓN

```js
const [collapsed, setCollapsed] = useState(() => new Set())
const userToggledRef = useRef(false)
const prevCityKeysRef = useRef(null)

useEffect(() => {
  const currentKeys = [...cities.keys()].sort().join('|')
  const prevKeys = prevCityKeysRef.current
  prevCityKeysRef.current = currentKeys
  if (prevKeys === null || prevKeys !== currentKeys) {
    setCollapsed(new Set())
    userToggledRef.current = false
  }
}, [cities])

const toggleCity = (ck) => {
  userToggledRef.current = true
  // ... toggle logic
}
```

## RENDIMIENTO

| Escenario | Riesgo |
|---|---|
| Daily con 30+ ciudades × 7 líneas × 90 columnas | MILES de celdas en DOM |
| Mitigación | El operador puede colapsar manualmente; el sistema no re-expande |
| Virtualización | La windowing de columnas (`visibleColRange`) sigue activa |

La colapsación manual es la herramienta del operador para escenarios de alta densidad. El sistema no impone colapso automático.
