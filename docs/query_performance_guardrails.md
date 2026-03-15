# Guardrails de performance para queries y vistas

**CT-REAL-LOB-ROOT-CAUSE-FIX — FASE F**

Reglas obligatorias para evitar reintroducir problemas de performance (Seq Scan masivos, filtros que no usan índices) en migraciones, vistas, MVs y consultas ad-hoc.

---

## 1. Filtros por columnas de fecha (alto volumen)

- **No** usar en predicados de alto volumen:
  - `DATE(columna_fecha) >= ...`
  - `CAST(columna_fecha AS date) >= ...`
  - `columna_fecha::date >= ...` cuando la columna ya es tipo date/timestamp y el índice está sobre la columna tal cual
  - Cualquier función que envuelva la columna indexada en el lado del predicado (ej. `timezone(...)` sobre la columna)
- **Sí** usar condiciones que permitan index use:
  - `columna_fecha >= CONSTANTE` o `columna_fecha >= CURRENT_DATE - INTERVAL 'N days'`
  - Mantener la columna “sola” en un lado de la comparación.

## 2. Dónde aplicar el filtro de fecha

- **Empujar** el filtro de ventana (ej. últimos 120 días) **lo más arriba posible** en la cadena de vistas/CTEs.
- Si la consulta final filtra por fecha, pero la vista intermedia hace `UNION` / `Append` + `ORDER BY` / `DISTINCT` **sin** filtrar por fecha en cada rama, el planner no podrá usar índices por fecha en las tablas base.
- Preferir: vistas o CTEs dedicadas que ya restrinjan por fecha en cada rama (ej. `v_trips_real_canon_120d`) en lugar de aplicar un solo `WHERE fecha >= ...` sobre una vista que devuelve todo el histórico.

## 3. Orden de operaciones

- **No** hacer `GROUP BY` / `ORDER BY` / `DISTINCT` (o `DISTINCT ON`) sobre un conjunto completo si luego se filtra por fecha; el filtro debe poder aplicarse **antes** de esas operaciones para reducir volumen.
- Si es inevitable un `DISTINCT ON` o `ORDER BY` global, considerar una capa intermedia que ya restrinja por fecha (vista “windowed”) para que el scan en tablas base sea por índice.

## 4. Nuevas MVs sobre tablas grandes

Cualquier nueva MV que se alimente de tablas de viajes (o tablas con volumen similar) debe:

- **a)** Declarar de forma explícita su **ventana de cálculo** (ej. “últimos 120 días”) en comentario o documentación.
- **b)** Justificar o reutilizar **índices en tablas fuente** que permitan restringir por esa ventana (ej. índice sobre `fecha_inicio_viaje`).
- **c)** Incluir una **validación mínima del plan** (EXPLAIN) en la migración o en un runbook, para comprobar que no se introduce un Seq Scan masivo.

## 5. Migraciones que crean vistas o MVs sobre viajes

- Cualquier migración que cree o modifique vistas/MVs que lean de `trips_all`, `trips_2026` o tablas análogas debe incluir un **chequeo de performance mínimo**:  
  ejecutar `EXPLAIN` sobre la consulta representativa (ventana de fecha acotada) y comprobar que no aparece un Seq Scan sobre toda la tabla sin restricción por fecha.
- Si la vista usa `UNION`/`Append`, el filtro de fecha debe estar **en cada rama** del UNION (o en una vista intermedia “windowed”) para que el planner pueda usar índices por fecha.

## 6. Columna de fecha como restricción principal

- Si una columna de fecha es la **restricción principal** para acotar el volumen (ej. “solo últimos N días”), debe existir un **índice** sobre esa columna (o un índice compuesto que la lleve) o una **justificación documentada** de por qué no se usa índice (ej. tabla pequeña, otro criterio dominante).

## 7. Uso de este documento

- Enlazar esta guía desde runbooks, docs de arquitectura y, cuando exista, desde el checklist de migraciones (`docs/migration_performance_checklist.md`).
- Revisar estas reglas en code reviews de migraciones y cambios que toquen vistas/MVs sobre viajes o tablas de alto volumen.
