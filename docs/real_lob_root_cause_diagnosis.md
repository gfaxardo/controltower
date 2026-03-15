# Real LOB — Diagnóstico causa raíz de performance

**CT-REAL-LOB-ROOT-CAUSE-FIX — FASE A**

## Cadena de dependencias

```
ops.mv_real_lob_month_v2 / ops.mv_real_lob_week_v2 (096)
  └─ CTE base: SELECT * FROM ops.v_real_trips_with_lob_v2 WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
       └─ ops.v_real_trips_with_lob_v2 (090)
            └─ ops.v_real_trips_service_lob_resolved (090)
                 └─ ops.v_trips_real_canon (064)
                      └─ public.trips_all (WHERE fecha_inicio_viaje IS NULL OR fecha_inicio_viaje < '2026-01-01')
                      └─ public.trips_2026 (WHERE fecha_inicio_viaje >= '2026-01-01')
                           UNION ALL → SELECT DISTINCT ON (id) ... ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC
```

## Cuello de botella exacto

1. **Tablas que hacen Seq Scan:**  
   `public.trips_all` y `public.trips_2026` aparecen en el plan como **Seq Scan** (Append de ~56M filas estimadas).

2. **Por qué el filtro de 120 días no ayuda en la práctica:**  
   El filtro `fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'` se aplica **fuera** de la vista canónica. La vista `ops.v_trips_real_canon` está definida como:
   - `UNION ALL` de dos ramas (trips_all y trips_2026) con filtros fijos por año (< 2026 y >= 2026).
   - Sobre ese resultado: `SELECT DISTINCT ON (id) ... ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST`.

   El planner **no** puede empujar un filtro externo (los 120 días) por debajo de ese `DISTINCT ON` + `ORDER BY`, porque son operaciones globales. Por tanto:
   - Primero se materializa (o se escanean) **todas** las filas del UNION.
   - Luego se ordena y se aplica DISTINCT ON.
   - Solo después se aplica el filtro de 120 días sobre ese resultado.

   En la práctica eso implica **Seq Scan completo** en ambas tablas y un **Sort** sobre decenas de millones de filas antes de filtrar.

3. **Índices existentes (064):**  
   - `ix_trips_all_real_lob_refresh` en (condicion, fecha_inicio_viaje) WHERE condicion = 'Completado'.  
   - `ix_trips_all_park_fecha` en (park_id, fecha_inicio_viaje) WHERE condicion = 'Completado'.  
   - Análogos para `trips_2026`.

   Esos índices no se usan para una consulta que solo restringe por **fecha** (ventana 120 días) a nivel de la vista canónica, porque:
   - La vista no filtra por `condicion` ni por `park_id` en las tablas base; esos filtros están más arriba (en v_real_trips_service_lob_resolved).
   - No existe un índice que lleve **solo** `fecha_inicio_viaje` para un range scan de la ventana.

4. **Expresiones que no rompen el índice (en este caso):**  
   El filtro en la MV usa `fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'` (sin `DATE()` ni `CAST` en la columna), por lo que no es una expresión que invalide el uso del índice. El problema no es la forma del predicado, sino **dónde** se aplica (después del UNION + DISTINCT ON + ORDER BY).

5. **Orden de operaciones problemático:**  
   - Append (Seq Scan trips_all + Seq Scan trips_2026).  
   - Sort (por id, source_priority, fecha_inicio_viaje).  
   - Unique (DISTINCT ON).  
   - **Después** se aplica el Filter de 120 días.

## Resumen

| Pregunta | Respuesta |
|----------|-----------|
| ¿Cuál es el cuello de botella? | Seq Scan completo en trips_all y trips_2026 + Sort masivo antes de aplicar el filtro de 120 días. |
| ¿Qué tablas hacen Seq Scan? | `public.trips_all`, `public.trips_2026`. |
| ¿Qué índice falta o no se usa? | Falta un índice **solo sobre fecha_inicio_viaje** (o que permita range scan por fecha) en ambas tablas; además, el filtro de 120 días debe aplicarse **en** la definición de la vista canónica (en cada rama del UNION) para que el planner pueda usar ese índice. |
| ¿Qué expresión rompe el índice? | Ninguna expresión en la columna de fecha; el problema es la **posición** del filtro (fuera del UNION/DISTINCT ON). |
| ¿Vista base, joins o ambos? | Sobre todo la **vista base** (v_trips_real_canon): el filtro de fecha no está “aguas arriba” en el UNION, por lo que el plan no puede reducir el volumen antes del Sort/DISTINCT ON. Los joins posteriores (parks, dim_service_type, dim_lob_group) son sobre un resultado ya enorme. |

## Solución aplicada (FASE B y C)

- **FASE B:** Índices en tablas fuente: `(fecha_inicio_viaje)` (o equivalente) en `trips_all` y `trips_2026` para range scan de la ventana.
- **FASE C:** Nueva capa “ventana 120 días” que aplica el filtro **dentro** del UNION:
  - `ops.v_trips_real_canon_120d`: mismas ramas que v_trips_real_canon pero con `fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'` en cada rama.
  - `ops.v_real_trips_service_lob_resolved_120d` y `ops.v_real_trips_with_lob_v2_120d`: misma semántica que las vistas existentes pero leyendo de `v_trips_real_canon_120d`.
  - Las MVs de Real LOB leen de `v_real_trips_with_lob_v2_120d` (sin WHERE adicional en la CTE base), de modo que el planner puede usar Index Scan (o plan razonable) sobre la ventana de 120 días.
