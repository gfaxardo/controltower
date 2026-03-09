# Period Semantics — Visibilidad en Frontend

**Objetivo:** Dejar claro qué componente renderiza qué, qué ruta/tab lo muestra y qué endpoints alimentan cada bloque, para que la implementación sea comprobable en UI.

---

## 1. Flujo al entrar a Real LOB

- **App.jsx:** Tab principal "Real LOB" → renderiza `<RealLOBDrillView />` (línea ~141).
- **RealLOBDrillView** es el único componente que se monta cuando el usuario hace clic en la pestaña "Real LOB".

---

## 2. Subtabs visibles al entrar (desde 2026-03)

En la parte superior de Real LOB se muestran **siempre** dos botones:

- **Drill (semanal/mensual)** — Vista timeline por país con períodos semanales o mensuales (comportamiento anterior).
- **Vista diaria** — Nueva vista con selector de día, baseline (D-1, mismo día semana pasada, promedio 4 mismos días), KPIs diarios y tabla por LOB.

No hay que buscar un enlace escondido: ambas opciones están en la primera fila bajo el título "Real LOB".

---

## 3. Bloque "Períodos (semántica cerrada / abierta)"

- **Dónde:** Dentro de la vista **Drill**, debajo de los botones de periodo (Mensual/Semanal) y **siempre visible** (no depende de que el drill haya terminado de cargar).
- **Qué muestra:**
  - Última semana cerrada: `S{nn}-{año} — Cerrada`
  - Semana actual (parcial): `S{nn}-{año} — Abierta (parcial)`
  - Último mes cerrado: `{Mes} {año} — Cerrado`
  - Mes actual (parcial): `{Mes} {año} — Abierto (parcial)`
- **Fuente de datos:** `GET /ops/period-semantics`. Se llama en montaje del componente (useEffect sin dependencias del drill). Si la petición falla, se muestra "Cargando semántica temporal…".
- **Componente:** `RealLOBDrillView.jsx`, estado `periodSemantics`, caja con fondo verde claro (`bg-emerald-50`).

---

## 4. Bloque "Comparativo WoW" / "Comparativo MoM"

- **Dónde:** En la vista **Drill**, debajo del bloque de semántica temporal. **Siempre visible** (no condicionado a tener datos).
- **Qué muestra:**
  - Título: "Comparativo WoW (última semana cerrada vs anterior)" o "Comparativo MoM (último mes cerrado vs anterior)" según el botón Periodo elegido (Semanal / Mensual).
  - Estados posibles: "Cargando comparativo…", mensaje de error, "Sin datos para períodos cerrados…" o la lista de países (PE, CO) con métricas y delta % (↑/↓/→).
- **Fuente de datos:** `GET /ops/real-lob/comparatives/weekly` o `GET /ops/real-lob/comparatives/monthly` según el periodo seleccionado. Se llama al montar y al cambiar entre Semanal/Mensual.
- **Componente:** `RealLOBDrillView.jsx`, estado `comparative` y `comparativeLoading`, caja azul (`bg-blue-50`).

---

## 5. Vista diaria

- **Dónde:** Al hacer clic en el botón **"Vista diaria"** en la parte superior de Real LOB.
- **Qué muestra:**
  - Texto explicativo del selector de día y baseline.
  - **Selector de día:** input tipo date (por defecto: último día cerrado).
  - **Selector de baseline:** D-1 (vs día anterior), Mismo día semana pasada (WoW), Promedio últimos 4 mismos días.
  - Línea de contexto: "Día consultado: YYYY-MM-DD · Baseline: …"
  - KPIs por país (PE, CO): viajes, margen total, margen/trip, km prom, B2B %.
  - Bloque "Comparativo diario (vs baseline seleccionado)" con deltas % o mensaje de error/vacío.
  - Tabla por LOB para el día seleccionado (o mensaje "Sin filas para este día").
- **Fuentes de datos:**
  - `GET /ops/period-semantics` — para mostrar último día cerrado por defecto.
  - `GET /ops/real-lob/daily/summary?day=...`
  - `GET /ops/real-lob/daily/comparative?day=...&baseline=...`
  - `GET /ops/real-lob/daily/table?day=...&group_by=lob`
- **Componente:** `RealLOBDailyView.jsx`, montado cuando `subView === 'daily'` en `RealLOBDrillView`.

---

## 6. Resumen de endpoints por bloque

| Bloque en UI                         | Endpoint(s)                                                                 |
|--------------------------------------|-----------------------------------------------------------------------------|
| Períodos (semántica cerrada/abierta) | `GET /ops/period-semantics`                                                 |
| Comparativo WoW / MoM                | `GET /ops/real-lob/comparatives/weekly` o `.../monthly`                     |
| Vista diaria (resumen + comparativo + tabla) | `GET /ops/period-semantics`, `.../daily/summary`, `.../daily/comparative`, `.../daily/table` |

---

## 7. Cambios de wiring realizados (cierre visible)

- **Semántica:** Ya no depende de la respuesta del drill. Se llama `getPeriodSemantics()` al montar y el banner se rellena en cuanto responde el backend (sin esperar al drill, que puede tardar minutos).
- **Comparativo WoW/MoM:** El bloque se renderiza siempre; se muestran estados de carga, error o "sin datos" si no hay `by_country`, en lugar de ocultar la sección.
- **Vista diaria:** Dejó de ser un enlace pequeño; es un **subtab** al mismo nivel que "Drill (semanal/mensual)", con el mismo estilo de botón (azul cuando está activo).
- **Vista diaria (dentro):** El bloque comparativo diario y la tabla se muestran siempre (con mensaje de error o "sin datos" cuando aplique). El baseline seleccionado se muestra en la línea de contexto y junto al desplegable.

---

## 8. Cómo comprobar en la UI

1. Abrir la app y hacer clic en la pestaña **Real LOB**.
2. Ver en la parte superior los dos botones: **Drill (semanal/mensual)** y **Vista diaria**.
3. En vista Drill, comprobar que aparece la caja verde **"Períodos (semántica cerrada / abierta)"** con las cuatro etiquetas (última semana cerrada, semana actual, último mes cerrado, mes actual).
4. Comprobar la caja azul **"Comparativo WoW"** o **"Comparativo MoM"** (según Mensual/Semanal): o bien datos con deltas %, o "Cargando…", error o "Sin datos…".
5. Clic en **Vista diaria**: comprobar selector de día, selector de baseline, línea de contexto, KPIs por país, bloque comparativo diario y tabla por LOB (o mensajes de vacío/error).

Si el backend no está en marcha o `real_rollup_day_fact` no tiene datos, seguirán viéndose los bloques y los mensajes de carga/error/sin datos, no pantallas en blanco.

---

## 9. Evidencia de respuestas de backend (sample)

**GET /ops/period-semantics** (no depende de BD):

```json
{
  "reference_date": "2026-03-09",
  "last_closed_day": "2026-03-08",
  "last_closed_week": "2026-03-02",
  "last_closed_week_label": "S10-2026 — Cerrada",
  "current_open_week": "2026-03-09",
  "current_open_week_label": "S11-2026 — Abierta (parcial)",
  "last_closed_month": "2026-02-01",
  "last_closed_month_label": "Feb 2026 — Cerrado",
  "current_open_month": "2026-03-01",
  "current_open_month_label": "Mar 2026 — Abierto (parcial)"
}
```

**GET /ops/real-lob/comparatives/weekly**: Devuelve `period_type`, `current_week_start`, `previous_week_start`, `comparative_type: "WoW"`, `metrics` (viajes, margen_total, margen_trip, km_prom, b2b_pct con value_current, value_previous, delta_abs, delta_pct, trend_direction), y `by_country` (array de { country, metrics }). Validado con datos reales: by_country con 2 países (PE, CO).
