# Checklist de performance para migraciones

**CT-REAL-LOB-ROOT-CAUSE-FIX — FASE F**

Checklist reutilizable para migraciones y cambios que afecten vistas, MVs o consultas sobre tablas grandes (en particular viajes).

---

## Antes de crear o modificar una vista / MV

- [ ] **Ventana de datos:** Si la vista/MV debe representar solo un subconjunto temporal (ej. últimos 120 días), ¿el filtro por fecha está aplicado **en** la definición (en cada rama de UNION si aplica) y no solo “fuera” de una vista que devuelve todo?
- [ ] **Predicados index-friendly:** Los filtros sobre columnas de fecha no usan `DATE(columna)`, `CAST(columna AS date)` ni otras funciones que impidan el uso del índice.
- [ ] **Índices fuente:** Las tablas base sobre las que se filtra por fecha tienen índice sobre esa columna (o se ha creado en la misma migración / está justificado en el diagnóstico).
- [ ] **Orden de operaciones:** No hay `DISTINCT` / `ORDER BY` / agregación global sobre el conjunto completo antes de aplicar el filtro de fecha; si lo hay, se ha valorado una capa “windowed” que filtre por fecha antes.

## En la migración

- [ ] **Índices:** Si se añaden índices sobre tablas grandes, se documenta si se usa `CREATE INDEX` normal o `CREATE INDEX CONCURRENTLY` (y en qué entorno/runbook se ejecuta CONCURRENTLY si aplica).
- [ ] **EXPLAIN:** Si la migración introduce una vista/MV sobre tablas de viajes (o análogas), se incluye en el mensaje de commit o en un runbook la instrucción para ejecutar `EXPLAIN` sobre la consulta representativa y el criterio de éxito (no Seq Scan masivo, uso de índice por fecha cuando corresponda).

## Después de aplicar la migración

- [ ] **Plan de ejecución:** Se ha ejecutado `diagnose_real_lob_mv_cost.py` (o el EXPLAIN equivalente) y se ha comprobado que el plan es aceptable (ver `docs/real_lob_execution_plan_validation.md`).
- [ ] **Bootstrap/refresh:** Si la migración crea MVs vacías que se rellenan por script (bootstrap o refresh), se ha comprobado que el tiempo de la primera población es razonable (no horas) o que el script usa la capa index-friendly (ej. vista _120d) cuando exista.

## Referencias

- **Causa raíz y diagnóstico:** `docs/real_lob_root_cause_diagnosis.md`
- **Validación del plan:** `docs/real_lob_execution_plan_validation.md`
- **Reglas de performance:** `docs/query_performance_guardrails.md`
- **Script de diagnóstico:** `backend/scripts/diagnose_real_lob_mv_cost.py`
