# Migration tab — Weekly grouped drilldown (fix final)

## 1. Archivos modificados

- **`frontend/src/components/SupplyView.jsx`**
  - Añadido estado `migrationExpandedWeeks` (Set) y `toggleMigrationWeek` para expandir/colapsar bloques por semana.
  - Añadido `useMemo` **`migrationWeeksGrouped`**: agrupa `migrationWeeklySummary` por `week_label` y enriquece con `summary` (upgrades, downgrades, revivals, stable) y `transitions` por semana a partir de `migration`.
  - Sustituida la tabla plana "Nivel 1" por bloques semanales colapsables: cabecera con semana + Up/Down/Revival/Stable; al expandir: tabla de resumen por segmento + tabla de transiciones (From → To) con tipos en color y acción "Ver drivers".
  - Añadida leyenda de segmentos (panel superior) usando `SEGMENT_LEGEND_MINIMAL`.
  - Import añadido: `useMemo`.

No se modificó backend ni contratos de API.

---

## 2. Explicación del fix

- **Problema:** La pestaña Migration mostraba una tabla plana (una fila por semana + segmento), sin jerarquía semanal ni transiciones agrupadas por semana.
- **Solución:** La estructura agrupada se construye en el **frontend** a partir de los mismos datos:
  - **Resumen semanal:** de `migrationWeeklySummary` se agrupa por `week_label` y se obtienen los segmentos por semana.
  - **Totales por semana (Up/Down/Revival/Stable):** se calculan filtrando el array `migration` por semana (`week_display` o `formatIsoWeek(week_start)`).
  - **Transiciones por semana:** mismo array `migration` filtrado por semana y excluyendo `lateral`.
- Cada semana se muestra como un **bloque colapsable**: cabecera con etiqueta de semana y totales; al expandir, tabla de segmentos (Drivers, WoW Δ, WoW %, Upgrades, Downgrades) y tabla de transiciones (From, To, Tipo, Drivers, Rate, Acción "Ver drivers").
- Los tipos de transición se etiquetan con color: **upgrade** = verde, **downgrade** = rojo, **revival** = azul, **drop** = rojo claro.
- La leyenda de segmentos (Dormant, Occasional, Casual, PT, FT, Elite, Legend y sus rangos) se muestra en un panel superior reutilizando `SEGMENT_LEGEND_MINIMAL`.

---

## 3. Ejemplo de estructura renderizada

```
Leyenda: Dormant (0 viajes/semana), Occasional (1–4), Casual (5–29), PT (30–59), FT (60–119), Elite (120–179), Legend (180+)

[S11-2026]  Up 6425 · Down 8462 · Revival 3084 · Stable 19838                    ▶
─────────────────────────────────────────────────────────────────────────────
(Si se expande:)
  Resumen por segmento
  | Segmento | Drivers | WoW Δ | WoW % | Upgrades | Downgrades |
  | CASUAL   | 652     | -406  | ...   | 120      | 89         |
  | OCCASIONAL| ...    | ...   | ...   | ...      | ...        |
  ...

  Transiciones (From → To)
  | From   | To        | Tipo      | Drivers | Rate | Acción      |
  | CASUAL | OCCASIONAL| downgrade | 349     | 12%  | Ver drivers |
  | PT     | FT        | upgrade   | 120     | 5%   | Ver drivers |
  ...

[S10-2026]  Up 5800 · Down 8200 · Revival 2900 · Stable 19500                    ▼
  (contenido expandido: segmentos + transiciones)
```

---

## 4. Confirmación

- La UI **agrupa por semana**: cada bloque corresponde a una semana (`week_label`), ordenada por fecha descendente.
- **Expandir/colapsar:** cada cabecera de semana es un botón que muestra/oculta resumen por segmento y transiciones.
- **Resumen por segmento** y **transiciones (From → To)** se muestran dentro de cada semana expandida.
- **Upgrade/downgrade/revival** se distinguen por color en la tabla de transiciones.
- El **drilldown a drivers** se mantiene mediante el botón "Ver drivers" en cada fila de transición (abre el modal existente con `openMigrationDrilldown(row)`).
- Los **filtros** (semana, segmento) se aplican: al filtrar por semana solo se muestra ese bloque; al filtrar por segmento se filtran segmentos y transiciones dentro de cada bloque.

---

## Fase 1 — Trazado del pipeline (referencia)

| Elemento | Ubicación |
|----------|-----------|
| Componente | `frontend/src/components/SupplyView.jsx` (tab Migration) |
| API resumen semanal | `GET /ops/supply/migration/weekly-summary` (params: park_id, from, to) |
| API transiciones | `GET /ops/supply/migration` |
| Backend | `backend/app/routers/ops.py`, `backend/app/services/supply_service.py` |
| Vista SQL (resumen) | `ops.v_driver_segments_weekly_summary` |

Los datos de resumen semanal llegan como **filas planas** (una por semana + segmento). La agrupación por semana se hace en frontend con `migrationWeeksGrouped`.
