# Migración 064 y Drill Real LOB — Error DiskFull (No space left on device)

## Causa

La creación de las MVs de Real LOB y las consultas del **Real LOB Drill** son operaciones pesadas que usan archivos temporales en `base/pgsql_tmp/` para ordenar y agregar millones de filas. Si el disco del servidor PostgreSQL se llena durante la ejecución, aparece:

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

---

## Plan B: Mover TEMP a tablespace con más espacio (solo si hay superuser)

Si el host Windows tiene espacio libre pero PostgreSQL (Linux/WSL/Docker) usa un disco lleno para `pgsql_tmp`, puedes redirigir los archivos temporales a un path con espacio (ej. `/mnt/c/` en WSL).

### Requisitos

- Rol con privilegio `CREATE TABLESPACE`
- Path con espacio suficiente (ej. `C:\pg_temp_ts` en Windows → `/mnt/c/pg_temp_ts` en WSL)

### Pasos

1. **Crear carpeta en el host con espacio:**

   ```bash
   # En WSL
   mkdir -p /mnt/c/pg_temp_ts
   chmod 700 /mnt/c/pg_temp_ts
   ```

2. **Crear tablespace y configurar PostgreSQL:**

   ```sql
   -- Conectar como superuser
   CREATE TABLESPACE pg_temp_ts LOCATION '/mnt/c/pg_temp_ts';

   -- Configurar uso de tablespace para temp
   ALTER SYSTEM SET temp_tablespaces = 'pg_temp_ts';

   -- Recargar configuración (no requiere restart)
   SELECT pg_reload_conf();
   ```

3. **Verificar:**

   ```sql
   SHOW temp_tablespaces;
   -- Debe mostrar: pg_temp_ts
   ```

4. **Revertir (si hace falta):**

   ```sql
   ALTER SYSTEM RESET temp_tablespaces;
   SELECT pg_reload_conf();
   DROP TABLESPACE pg_temp_ts;
   ```

**Nota:** Si el rol no tiene `CREATE TABLESPACE`, omitir Plan B y usar el modo incremental (ventana reciente + backfill por chunks).
