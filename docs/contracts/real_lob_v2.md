# Real LOB v2 — Contrato de API y columnas

Observabilidad de viajes REAL por LOB_GROUP y segmento B2B/B2C. Filtros por country, city, park_id. Sin Plan.

## Regla B2B (obligatoria)

- **segment_tag = 'B2B'** si `trips_all.pago_corporativo IS NOT NULL`
- **segment_tag = 'B2C'** en caso contrario
- segment_tag no afecta lob_group ni real_tipo_servicio; es un tag/filtro adicional.

## Fuente de datos

- **LOB_GROUP** desde tabla canónica `canon.map_real_tipo_servicio_to_lob_group` (real_tipo_servicio normalizado → lob_group).
- **real_tipo_servicio_norm**: normalización mínima de `trips_all.tipo_servicio` (económico→economico, mensajeria→mensajería, comfort→confort, exprés→express). Fallback **UNCLASSIFIED** si no está en el mapa.

## Endpoints

### GET /ops/real-lob/monthly-v2

**Query params:**

| Parámetro           | Tipo   | Descripción |
|---------------------|--------|-------------|
| country             | string | opcional. País (ej. co, pe). |
| city                | string | opcional. Ciudad normalizada. |
| park_id             | string | opcional. ID de park. |
| lob_group           | string | opcional. auto taxi, delivery, tuk tuk, taxi moto, UNCLASSIFIED. |
| real_tipo_servicio  | string | opcional. Tipo de servicio normalizado. |
| segment_tag         | string | opcional. B2B o B2C. |
| month               | string | opcional. YYYY-MM. Si no se envía ni year_real, default = último mes disponible. |
| year_real           | int    | opcional. Filtra meses del año (rango 01-01 a 12-31). |

**Respuesta:**

- `data`: array de objetos (ver columnas abajo).
- `total_records`: número.
- `last_available_month`: string YYYY-MM o null.
- `last_available_week`: string YYYY-MM-DD o null.
- `reason`: "no_data_for_filters" si data está vacío.

**Orden:** month_start ASC, trips DESC.

---

### GET /ops/real-lob/weekly-v2

**Query params:** mismos que monthly-v2, salvo:

- `week_start` (string, opcional): lunes de la semana YYYY-MM-DD. Si no se envía ni year_real, default = última semana disponible.
- Sin `month`.

**Orden:** week_start DESC, trips DESC.

---

## Columnas por fila (payload data)

| Campo                    | Tipo   | Descripción |
|--------------------------|--------|-------------|
| country                  | string | co, pe, etc. |
| city                     | string | Ciudad normalizada. |
| park_id                  | string | ID del park. |
| park_name                | string | Nombre del park (desde parks). |
| lob_group                | string | auto taxi, delivery, tuk tuk, taxi moto, UNCLASSIFIED. |
| real_tipo_servicio_norm  | string | Tipo de servicio normalizado. |
| segment_tag              | string | B2B o B2C. |
| month_start / week_start | date   | Periodo (según endpoint). |
| period_date              | string | Fecha en formato YYYY-MM-DD. |
| display_month / display_week | string | Para mostrar en UI (YYYY-MM o YYYY-MM-DD). |
| trips                    | number | Cantidad de viajes. |
| revenue                  | number | Suma de revenue (≥ 0). |
| currency                 | string | PEN (pe), COP (co) o null. |
| is_open                  | bool   | true si el periodo es el actual (mes/semana en curso). |

## Mapeo canónico (real_tipo_servicio → lob_group)

| real_tipo_servicio | lob_group  |
|--------------------|------------|
| economico          | auto taxi  |
| confort            | auto taxi  |
| confort+           | auto taxi  |
| minivan            | auto taxi  |
| premier            | auto taxi  |
| standard           | auto taxi  |
| start              | auto taxi  |
| express            | delivery   |
| cargo              | delivery   |
| mensajería         | delivery   |
| tuk-tuk            | tuk tuk    |
| moto               | taxi moto  |

Cualquier otro valor (o no encontrado en la tabla) → **UNCLASSIFIED**.

## Refresco de MVs

- **Script:** `backend/scripts/refresh_real_lob_mvs_v2.py`
- **Uso:** desde `backend/`: `python -m scripts.refresh_real_lob_mvs_v2`
- **Frecuencia recomendada:** diaria tras ingesta.

## Validación / Calidad

- **pct_unclassified:** por país/ciudad/park; warning si > 5%.
- **segment_tag:** filtrar por B2B debe devolver solo filas con segment_tag B2B.
- Queries acotadas por periodo (defaults último mes/semana) y lectura desde MVs para evitar timeouts.
