# Migración 064 — Error DiskFull (No space left on device)

## Causa

La creación de las MVs de Real LOB es una operación pesada que usa archivos temporales en `base/pgsql_tmp/` para ordenar y agregar millones de filas. Si el disco del servidor PostgreSQL se llena durante la ejecución, aparece:

```
psycopg2.errors.DiskFull: could not write to file "base/pgsql_tmp/pgsql_tmpXXXXX.X": No space left on device
```

## Pasos para resolver

### 1. Liberar espacio en disco (obligatorio)

El error ocurre en el **servidor donde corre PostgreSQL**, no necesariamente en tu máquina local.

**Si PostgreSQL está en tu PC:**
- Liberar espacio en el disco donde está instalado PostgreSQL (por defecto `C:\Program Files\PostgreSQL\...` o similar).
- Borrar logs antiguos, datos temporales, etc.

**Si PostgreSQL está en un servidor remoto:**
- Conectarte al servidor y liberar espacio en el disco de datos de PostgreSQL.
- Revisar `pg_stat_activity` y `pg_locks` por queries largas que puedan estar consumiendo recursos.

**Comandos útiles (en el servidor):**
```bash
# Ver espacio en disco
df -h

# En Windows PowerShell
Get-PSDrive C
```

### 2. Limpiar archivos temporales de PostgreSQL

Tras un fallo, pueden quedar archivos huérfanos en `base/pgsql_tmp/`. Si tienes acceso al directorio de datos de PostgreSQL:

```bash
# Ubicación típica (Linux)
# $PGDATA/base/pgsql_tmp/

# Borrar archivos temporales huérfanos (solo si PostgreSQL está detenido o no hay sesiones activas)
# rm -f $PGDATA/base/pgsql_tmp/pgsql_tmp*
```

**Precaución:** No borres archivos temporales mientras PostgreSQL está ejecutando queries.

### 3. Aumentar work_mem (opcional)

La migración ya incluye `SET work_mem = '256MB'` para reducir el uso de archivos temporales. Si tienes más RAM disponible, puedes subir el valor antes de ejecutar:

```sql
-- Ejecutar en la sesión antes de la migración, o modificar la migración
SET work_mem = '512MB';
```

### 4. Reintentar la migración

Tras liberar espacio:

```bash
cd backend
alembic upgrade head
```

Con DDL transaccional, el fallo hace rollback de toda la migración 064, así que puedes volver a ejecutarla sin problemas.

## Estrategia en 2 fases (desde 064)

La migración crea primero `ops.mv_real_drill_enriched` (1 fila por trip enriquecido) y luego `ops.mv_real_drill_dim_agg` (agregados). La fase 2 lee de la MV intermedia y usa menos espacio temporal (solo GROUP BY sobre tabla materializada). Si falla en la fase 1, libera espacio y reintenta.

## Requisitos aproximados de espacio

- **Archivos temporales:** varios GB durante la creación de `mv_real_drill_enriched` (depende del volumen de `trips_all` + `trips_2026`).
- **MV intermedia (enriched):** ~1 fila por trip completado en co/pe (varios GB).
- **MV final (dim_agg):** agregación por país/periodo/dimensión (mucho menor).

Se recomienda tener al menos **5–10 GB libres** en el disco de datos de PostgreSQL antes de ejecutar la migración.
