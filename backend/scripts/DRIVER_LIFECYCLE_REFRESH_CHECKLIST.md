# Driver Lifecycle — Checklist de refresh y validación

El script `check_driver_lifecycle_and_validate` es **a prueba de timeouts**: aplica `SET statement_timeout` y `SET lock_timeout` en la conexión **antes** del refresh (no usa SET LOCAL). Si la sesión tiene 15s por defecto, el script lo cambia a 60min/5min según ENV.

## Comandos principales (PowerShell)

```powershell
cd backend

# Modo recomendado: el script impone statement_timeout y lock_timeout (no depende de PGOPTIONS)
python -m scripts.check_driver_lifecycle_and_validate

# Diagnóstico (locks, timeouts, pg_stat_activity, valores objetivo ENV) — no refresca
python -m scripts.check_driver_lifecycle_and_validate --diagnose

# Diagnóstico de timeouts (qué fuerza 15s: rol, db, config)
python -m scripts.diagnose_pg_timeouts

# Solo validaciones (sin refresh)
$env:DRIVER_LIFECYCLE_REFRESH_MODE="none"
python -m scripts.check_driver_lifecycle_and_validate

# Forzar nonc en ventana de mantenimiento
$env:DRIVER_LIFECYCLE_REFRESH_MODE="nonc"
python -m scripts.check_driver_lifecycle_and_validate

# Deploy completo
python -m scripts.apply_driver_lifecycle_v2
```

## Backup: PGOPTIONS (si el cliente impone timeout externo)

```powershell
# Valores en milisegundos: statement_timeout=3600000 (60min), lock_timeout=300000 (5min)
$env:PGOPTIONS="-c statement_timeout=3600000 -c lock_timeout=300000"
python -m scripts.check_driver_lifecycle_and_validate
```

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| DRIVER_LIFECYCLE_REFRESH_MODE | concurrently | concurrently \| nonc \| none |
| DRIVER_LIFECYCLE_TIMEOUT_MINUTES | 60 | Timeout por statement |
| DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES | 5 | Timeout para esperar locks |
| DRIVER_LIFECYCLE_FALLBACK_NONC | 1 | Si falla concurrently por timeout/lock → reintentar nonc |

## Antes del refresh

- [ ] Ejecutar diagnóstico: `scripts/sql/driver_lifecycle_refresh_diagnose.sql`
- [ ] Verificar que no haya otro REFRESH en curso (query 2 del diagnóstico)
- [ ] Opcional: `DRIVER_LIFECYCLE_REFRESH_MODE=nonc` para ventana de mantenimiento

## Aplicar hardening (una vez)

```bash
psql $DATABASE_URL -f sql/driver_lifecycle_refresh_hardening.sql
```

O tras `run_driver_lifecycle_build`: el build crea refresh básico; hardening añade duración por paso, fallback nonc y variante 3only.

## Validaciones post-refresh

- Conteos de cada MV (base, weekly_kpis, monthly_kpis, weekly_stats, monthly_stats, cohortes)
- Unicidad base: `COUNT(*) = COUNT(DISTINCT driver_key)`
- Freshness: `MAX(last_completed_ts)` si existe
- park_id NULL: % (WARNING si > 5%)

## Criterios DONE

- apply_driver_lifecycle_v2.py termina en OK
- consistency_validation devuelve 0 filas
- cohort_validation OK (si cohortes desplegadas)
- null_share reportado (warning si > 5%)
- Tiempos de refresh reportados
