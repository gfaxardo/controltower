# Monitor de service_type no mapeados (Real LOB)

## Objetivo

Detectar **nuevos** `service_type` que caen en LOB UNCLASSIFIED sin esperar a que contaminen el dashboard. Priorizar candidatos a mapping por volumen y separar basura marginal de tipos de negocio legítimos.

## Objeto

**Vista:** `ops.v_real_service_type_unmapped_monitor`

- **Fuente:** `ops.v_real_trips_service_lob_resolved` (capa canónica).
- **Filtro:** `is_unclassified = true` y ventana últimos **90 días**.
- **Agregado:** por `(tipo_servicio_raw, tipo_servicio_norm)`.

## Columnas

| Columna | Tipo | Descripción |
|--------|------|-------------|
| `tipo_servicio_raw` | text | Valor crudo del viaje. |
| `tipo_servicio_norm` | text | Valor normalizado (clave para lookup en dim). |
| `trips` | bigint | Número de viajes en la ventana. |
| `first_seen_date` | date | Primera fecha vista en la ventana. |
| `last_seen_date` | date | Última fecha vista en la ventana. |
| `sample_lob_resolved` | text | Siempre `'UNCLASSIFIED'` en esta vista. |
| `is_unclassified` | boolean | Siempre `true`. |

## Uso

### Lista priorizada (candidatos a mapping)

```sql
-- Ordenar por volumen para priorizar
SELECT tipo_servicio_raw, tipo_servicio_norm, trips, first_seen_date, last_seen_date
FROM ops.v_real_service_type_unmapped_monitor
ORDER BY trips DESC
LIMIT 100;
```

### Filtrar basura marginal

- Tipos con pocos viajes (ej. &lt; 10) suelen ser basura (direcciones, productos, IDs).
- Tipos con nombres que parecen direcciones o texto sin sentido: dejar en UNCLASSIFIED.
- Tipos que parecen variantes de negocio (ej. otra forma de escribir "delivery", "taxi"): candidatos a añadir a `canon.dim_real_service_type_lob`.

### Añadir un nuevo mapping

1. Decidir el `lob_group` correcto (auto taxi, delivery, tuk tuk, taxi moto).
2. Insertar en la **fuente canónica** única:
   ```sql
   INSERT INTO canon.dim_real_service_type_lob (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at)
   VALUES ('nuevo_tipo_norm', 'lob_group', 'manual', true, 'Candidato desde unmapped monitor', now())
   ON CONFLICT (service_type_norm) DO UPDATE SET lob_group = EXCLUDED.lob_group, updated_at = now();
   ```
3. (Opcional) Repoblar backfill para que el drill refleje el cambio en el rango deseado.

## Coste

La vista agrega sobre `v_real_trips_service_lob_resolved` con filtro de 90 días; el coste depende del volumen de viajes en esa ventana. Si fuera alto en producción, se puede sustituir por una tabla refreshable rellenada por script o job (misma estructura), documentando el script y la frecuencia de refresh.

## Creación

La vista se crea en la migración **071_real_service_type_unmapped_monitor** (depende de 070 capa canónica).
