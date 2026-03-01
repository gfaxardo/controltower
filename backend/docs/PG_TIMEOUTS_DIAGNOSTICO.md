# Diagnóstico de statement_timeout=15s

## Problema

La sesión Postgres arranca con `statement_timeout=15s`, lo que cancela el refresh de MVs driver lifecycle antes de completar.

## Causas posibles

| Origen | Cómo detectar | Solución sugerida |
|--------|---------------|-------------------|
| **ROL** | `diagnose_pg_timeouts` muestra "Está forzado por ROL" | `ALTER ROLE <rolname> SET statement_timeout TO '60min';` |
| **DB** | "Está forzado por DB" | `ALTER DATABASE <datname> SET statement_timeout TO '60min';` |
| **postgresql.conf** | source=configuration file en pg_settings | Editar postgresql.conf o usar ALTER ROLE/DB para override |
| **Cliente (PGOPTIONS)** | source=client | Quitar PGOPTIONS o usar `-c statement_timeout=3600000` (ms) |

## Script de diagnóstico

```powershell
cd backend
python -m scripts.diagnose_pg_timeouts
```

- **Exit 0**: SET aplicó correctamente (Antes: 15s → Después: 60min/1h)
- **Exit 2**: No se pudo aplicar; imprime recomendaciones según rol/db/config

## Corrección en check script

`check_driver_lifecycle_and_validate` usa `SET statement_timeout` (no SET LOCAL) con `autocommit=True` para evitar transacciones implícitas. Si el SET no aplica, aborta con exit 2 e indica ejecutar `diagnose_pg_timeouts`.
