# Definición canónica: hueco de margen en fuente (REAL)

## Reglas de negocio (obligatorias)

1. **Viaje CANCELADO** → no se exige comisión/margen. Cancelado + margen NULL = **normal**, no alertar.
2. **Viaje COMPLETADO** → debe existir comisión/margen en fuente. Completado + margen NULL = **anomalía real de fuente**.
3. **Cancelado + margen presente** = **anomalía secundaria** de consistencia (no es hueco de fuente, pero es incoherente).
4. No inventar ni imputar margen faltante en REAL.

---

## Métricas

| Métrica | Definición |
|---------|------------|
| **completed_trips** | Viajes con condición Completado (o trip_outcome_norm = 'completed'). |
| **completed_trips_with_margin** | Completados con comisión/margen presente: `comision_empresa_asociada IS NOT NULL` (y opcional `!= 0` si se considera 0 como "sin margen"). Por defecto: IS NOT NULL. |
| **completed_trips_without_margin** | Completados con `comision_empresa_asociada IS NULL`. **Métrica principal de anomalía.** |
| **completed_without_margin_pct** | `completed_trips_without_margin / completed_trips` (0 si completed_trips = 0). |
| **cancelled_trips** | Viajes cancelados (condicion = 'Cancelado' o ILIKE '%cancel%'). |
| **cancelled_trips_with_margin** | Cancelados que sí tienen comisión/margen (IS NOT NULL). **Anomalía secundaria.** |
| **cancelled_with_margin_pct** | `cancelled_trips_with_margin / cancelled_trips` (0 si cancelled_trips = 0). |
| **margin_coverage_pct** | `completed_trips_with_margin / completed_trips` (porcentaje de completados con margen; 100% = cobertura completa). |

---

## Dimensiones de análisis (mínimas)

- **fecha** (día, o semana si grain = week)
- **país**
- **LOB** (lob_group)
- **park** (park_id o park_name)
- **tipo_servicio** (tipo_servicio_norm)
- **segmento** (solo si ya existe de forma natural en el flujo, p. ej. B2B/B2C)

---

## Reglas de severidad (anomalía principal: completados sin margen)

| Severidad | Condición |
|-----------|-----------|
| **INFO** | completed_without_margin_pct > 0 |
| **WARNING** | completed_without_margin_pct > 0.5% |
| **CRITICAL** | completed_without_margin_pct > 2% |
| **CRITICAL inmediato** | Días recientes con completed_trips > 0 y completed_trips_with_margin = 0 (cobertura 0% en periodo reciente). |

Umbrales configurables (constantes en código o env):  
`MARGIN_GAP_PCT_WARNING = 0.5`, `MARGIN_GAP_PCT_CRITICAL = 2.0`.

---

## Anomalía secundaria (cancelados con margen)

- **WARNING** si cancelled_with_margin_pct > umbral (p. ej. 5%).
- **CRITICAL** si cancelled_with_margin_pct > umbral alto (p. ej. 10%) o si cancelled_trips_with_margin > N absoluto.
- Umbral documentado: **CANCELLED_WITH_MARGIN_PCT_WARNING = 5.0**, **CANCELLED_WITH_MARGIN_PCT_CRITICAL = 10.0**.

---

## Códigos de alerta

- **REAL_MARGIN_SOURCE_GAP_COMPLETED** — Completados sin margen en fuente (anomalía principal).
- **REAL_CANCELLED_WITH_MARGIN** — Cancelados con margen presente (anomalía secundaria de consistencia).

---

## Fuente de datos para el cálculo

- **Recomendado para agregados por día y dimensión:** `ops.v_real_trip_fact_v2` (ya tiene trip_outcome_norm, margin_total = comision_empresa_asociada, país, LOB, park, tipo_servicio_norm). Ventana: `fecha_inicio_viaje::date >= current_date - N` (60/90 días).
- **Alternativa solo por día (sin LOB/park):** `ops.v_trips_real_canon_120d` con join a parks para país; menos dimensiones.
