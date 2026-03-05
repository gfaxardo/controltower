# Driver Lifecycle — Secuencia GO (verificación completa)

Todos los scripts usan la misma conexión (`app.db`: DATABASE_URL o DB_* desde `.env`).

## Orden de ejecución

```bash
cd backend

# 1) Build: crea MVs y vistas
python -m scripts.run_driver_lifecycle_build

# 2) Fix vista: build recrea v_driver_lifecycle_trips_completed; asegurar que lea de trips_unified
python scripts/fix_view_trips_unified.py

# 3) Check: refresca MVs y valida
python -m scripts.check_driver_lifecycle_and_validate

# 4) Auditoría: sanity checks
python -m scripts.audit_trips_unified_and_driver_lifecycle
```

## Verificación de consistencia

Cada script imprime al inicio:
- **Config:** `db=X user=Y host=H:port` (debe ser **idéntico** en los 4)
- **DB / user / schema:** `current_database()`, `current_user`, `current_schema()`
- **to_regclass:** `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`

Si `Config` o `DB` difieren entre scripts → revisar:
- `.env` en `backend/` (ruta del `env_file` en settings)
- Variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` en `.env`
- El pool usa siempre `DB_*` (misma fuente que settings). `DATABASE_URL` se usa para SQLAlchemy/alembic.

## Estado GO esperado

| Script | Salida esperada |
|--------|-----------------|
| run_driver_lifecycle_build | OK en build, refresh y validaciones |
| fix_view_trips_unified | `OK: v_driver_lifecycle_trips_completed ahora lee de public.trips_unified` |
| check_driver_lifecycle_and_validate | `MVs driver lifecycle en ops: [lista]` (no "ninguna") |
| audit_trips_unified_and_driver_lifecycle | `ops.mv_driver_lifecycle_base (matview): EXISTE` |

## Si check dice "ninguna" pero build reportó OK

1. Comprobar que **Config** es igual en build y check.
2. Si `to_regclass` devuelve oid pero `pg_matviews` está vacío → posible `search_path` o visibilidad de schema.
3. Revisar que no haya varios `.env` (proyecto, home, etc.) con distintos `DATABASE_URL`/`DB_*`.
