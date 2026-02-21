# Real LOB Strategy — Módulo de expansión y dirección

Módulo estratégico de Real LOB v2: KPIs ejecutivos, forecast automático (solo país y LOB_GROUP), índices estratégicos y ranking territorial. **No toca Plan vs Real REALKEY.**

---

## 1. Alcance del forecast

- **Niveles con forecast:** solo **País** y **LOB_GROUP** dentro de país. No hay forecast por ciudad ni por park.
- **Modelo:** momentum ponderado 3 meses:
  - `Forecast_next_month = (0.5 × Mes_Actual) + (0.3 × Mes_-1) + (0.2 × Mes_-2)`
  - Si no hay 3 meses completos: promedio simple disponible.
  - Si solo hay 1 mes: forecast = ese mismo valor.
- **Horizonte:** no se proyecta más de 2 meses hacia adelante (en la práctica se expone 1 mes de forecast).
- **Etiqueta:** siempre mostrar: *"Proyección basada en tendencia histórica, no considera eventos externos."*

---

## 2. Fórmulas

### Forecast próximo mes (país y LOB_GROUP)

```
Con 3 meses:  forecast = 0.5×M0 + 0.3×M(-1) + 0.2×M(-2)
Con 2 meses:  forecast = (M0 + M(-1)) / 2
Con 1 mes:    forecast = M0
```

### Crecimiento MoM (month-over-month)

```
growth_mom = (trips - trips_prev) / trips_prev
```

### Índice de aceleración

```
acceleration_index = avg_growth_last_2_months - avg_growth_last_6_months
```

- **Positivo:** la tendencia reciente acelera respecto al promedio de 6 meses (verde).
- **Negativo:** desaceleración (amarillo).

### Índice de expansión (ciudades)

```
expansion_index = growth_city / growth_country
```

- **> 1:** la ciudad crece más que el país (expansión relativa).
- **< 1:** la ciudad crece menos que el país.

### Concentración (país)

```
concentration_index = (viajes top 3 ciudades) / (viajes total país)
```

- Indica cuánto del volumen del país se concentra en las 3 principales ciudades.

### Momentum score (LOB)

- Crecimiento ponderado reciente; en la implementación se usa `growth_mom` del último mes como proxy de momentum.

### Participación LOB

```
participation_pct = (viajes LOB / viajes total país) × 100
```

---

## 3. Vistas SQL (backend)

| Vista | Descripción |
|-------|-------------|
| `ops.v_real_country_month` | Agregado mensual por país: trips, trips_prev, growth_mom, b2b_trips, b2b_ratio, max_trip_ts. |
| `ops.v_real_country_month_forecast` | Igual que la anterior + forecast_next_month, forecast_growth, acceleration_index. |
| `ops.v_real_country_lob_month` | Por país y LOB_GROUP: trips, growth_mom, forecast_next_month. |
| `ops.v_real_country_city_month` | Por país y ciudad: trips, growth_mom, expansion_index. |

**Fuente:** `ops.mv_real_lob_month_v2`. Índices añadidos para consultas por `(country, month_start)` y `(country, city, month_start)`.

---

## 4. Endpoints

| Método | Ruta | Parámetros | Descripción |
|--------|------|------------|-------------|
| GET | `/ops/real-strategy/country` | `country` (requerido), `year_real`, `segment_tag`, `period_type` | KPIs país, tendencia 12 meses, forecast, ranking ciudades. |
| GET | `/ops/real-strategy/lob` | `country` (requerido), `year_real`, `segment_tag`, `lob_group`, `period_type` | Distribución LOB: viajes, participación, MoM, forecast, momentum. |
| GET | `/ops/real-strategy/cities` | `country` (requerido), `year_real`, `segment_tag`, `period_type` | Ranking ciudades: viajes, MoM, % país, expansion_index. |

- **Default:** último mes disponible.
- **Orden:** `month_start DESC`, luego por volumen (trips DESC).

---

## 5. KPIs por endpoint

### País (`/ops/real-strategy/country`)

- `total_trips_ytd`: viajes acumulados año en curso.
- `growth_mom`: crecimiento mes a mes.
- `b2b_ratio`: proporción B2B.
- `forecast_next_month`: proyección próximo mes.
- `forecast_growth`: crecimiento proyectado vs mes actual.
- `acceleration_index`: aceleración reciente vs 6 meses.
- `concentration_index`: peso de las top 3 ciudades.

### LOB (`/ops/real-strategy/lob`)

- `trips`, `participation_pct`, `growth_mom`, `forecast_next_month`, `momentum_score`.

### Ciudades (`/ops/real-strategy/cities`)

- `city`, `trips`, `growth_mom`, `pct_country`, `expansion_index`.

---

## 6. Validaciones

1. **Forecast:** solo se muestra si existen al menos 2 meses reales.
2. **Horizonte:** no se proyecta más de 2 meses.
3. **Sin mezcla con Plan:** el módulo usa solo datos Real (v2); no modifica ni lee Plan vs Real REALKEY.
4. **Datos insuficientes:** si no hay datos para el filtro, se devuelve estructura vacía y mensaje claro en frontend.

---

## 7. Performance y refresh

- Las vistas de estrategia son **vistas normales** que leen de `ops.mv_real_lob_month_v2`.
- Para que Strategy esté al día, hay que refrescar esa MV (y la semanal si se usara en el futuro).
- **Script recomendado (refresh diario):**
  ```bash
  cd backend && python -m scripts.refresh_real_strategy_mvs
  ```
  Equivalente a refrescar `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2`.

Si en el futuro las vistas por país o por LOB resultan pesadas, se pueden convertir en materialized views y añadir su refresh a este script.

---

## 8. Advertencia sobre el forecast

El forecast es **mecánico** (momentum de 3 meses). No incorpora:

- Eventos externos (festivos, campañas, cambios regulatorios).
- Estacionalidad explícita.
- Otros drivers de demanda.

Siempre debe mostrarse la leyenda: *"Proyección basada en tendencia histórica, no considera eventos externos."*

---

## 9. Ejemplos de interpretación

- **Aceleración positiva (verde):** el crecimiento de los últimos 2 meses es mayor que el promedio de los últimos 6 → tendencia al alza.
- **Aceleración negativa (amarillo):** el crecimiento reciente es menor que el de 6 meses → posible desaceleración.
- **Expansion_index > 1 en una ciudad:** esa ciudad está creciendo más que el país → foco de expansión.
- **Concentration_index alto:** el país depende mucho de pocas ciudades; útil para diversificación territorial.
