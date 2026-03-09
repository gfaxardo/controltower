# Pipeline Real LOB – service_type y LOB

## Flujo service_type (breakdown "Tipo de servicio")

```
public.trips_all.tipo_servicio (raw, ej. "Económico", "confort+", "tuk-tuk")
    │
    ▼
ops.v_trips_real_canon (vista unión trips_all + trips_2026)
    │
    ▼ backfill_real_lob_mvs.py — CTE with_country
ops.validated_service_type(tipo_servicio)
    = ops.normalized_service_type() si pasa validación, si no UNCLASSIFIED
    │
    ▼ normalized_service_type():
    │   unaccent → lower → trim → + → _plus → espacios/guiones → _ → solo [a-z0-9_]
    │   Económico → economico, confort+ → confort_plus, tuk-tuk → tuk_tuk
    │
    ▼ validated_service_type():
    │   UNCLASSIFIED si: NULL/vacío, contiene coma, >30 chars, >3 palabras
    │
    ▼ tipo_servicio_norm (alias en CTE)
    │
    ▼ INSERT INTO ops.real_drill_dim_fact (dimension_key = tipo_servicio_norm, breakdown = 'service_type')
    │
    ▼ ops.mv_real_drill_dim_agg (vista = SELECT * FROM real_drill_dim_fact)
    │
    ▼ real_lob_drill_pro_service.py — get_drill_children()
    │   row["service_type"] = row["dimension_key"]
    │
    ▼ Frontend: RealLOBDrillView.jsx
```

## Flujo LOB (breakdown "LOB")

```
tipo_servicio_norm (de arriba)
    │
    ▼ LEFT JOIN canon.map_real_tipo_servicio_to_lob_group
    │   ON real_tipo_servicio = tipo_servicio_norm
    │
    ▼ COALESCE(lob_group, 'UNCLASSIFIED') AS lob_group
    │
    ▼ INSERT INTO ops.real_drill_dim_fact (dimension_key = lob_group, breakdown = 'lob')
    │
    ▼ ops.mv_real_drill_dim_agg
    │
    ▼ get_drill_children() → row["lob_group"] = row["dimension_key"]
```

## Objetos SQL clave

| Objeto | Tipo | Uso |
|--------|------|-----|
| `ops.real_drill_dim_fact` | Tabla | Fact principal del drill |
| `ops.mv_real_drill_dim_agg` | Vista | = SELECT * FROM real_drill_dim_fact |
| `ops.v_trips_real_canon` | Vista | trips_all + trips_2026, filtrado |
| `ops.normalized_service_type(text)` | Función | Normalización canónica |
| `ops.validated_service_type(text)` | Función | Validación + normalización |
| `canon.map_real_tipo_servicio_to_lob_group` | Tabla | Mapping tipo→LOB |
| `ops.v_audit_service_type` | Vista | Auditoría raw→normalized→validated |
| `ops.v_audit_breakdown_sum` | Vista | Validación breakdown sum |
