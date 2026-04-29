# Refresh System - YEGO Control Tower

Sistema de auditoría y refresh automático de materialized views.

---

## Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   run_refresh   │────▶│ refresh_service │────▶│  bi.refresh_  │
│    _job.py      │     │    .py          │     │    audit      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         │              ┌────────▼────────┐              │
         │              │ bi.refresh_lock │              │
         │              └─────────────────┘              │
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                    PostgreSQL (ops schema)
```

---

## Scripts

### 1. run_refresh_job.py

Ejecuta refresh **único** con todas las protecciones:
- Lock anti-concurrencia
- Retry automático (3 intentos)
- Registro granular por dataset

```bash
# Refresh todos los datasets
python scripts/run_refresh_job.py

# Refresh dataset específico
python scripts/run_refresh_job.py --dataset mv_real_trips_monthly
```

### 2. run_refresh_loop.py

Loop **continuo** que ejecuta refresh cada 30 minutos:
- Maneja excepciones (nunca termina)
- Logs con timestamps
- Puede detenerse con Ctrl+C

```bash
python scripts/run_refresh_loop.py
```

---

## Configuración de Cron / Scheduler

### Opción 1: Linux CRON (Recomendado)

Editar crontab:
```bash
crontab -e
```

Agregar línea para ejecutar cada 30 minutos:
```cron
*/30 * * * * cd /ruta/al/proyecto/backend && python scripts/run_refresh_job.py >> logs/refresh.log 2>&1
```

O usar el script de loop (corre en foreground, ideal para systemd):
```bash
# Systemd service
sudo nano /etc/systemd/system/yego-refresh.service
```

Contenido:
```ini
[Unit]
Description=YEGO Refresh Loop
After=network.target

[Service]
Type=simple
User=yego
WorkingDirectory=/ruta/al/proyecto/backend
ExecStart=/usr/bin/python scripts/run_refresh_loop.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable yego-refresh
sudo systemctl start yego-refresh
sudo systemctl status yego-refresh
```

### Opción 2: Docker

Dockerfile adicional (scheduler):
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/ .
RUN pip install -r requirements.txt

# Usar script de loop
CMD ["python", "scripts/run_refresh_loop.py"]
```

O usar cron dentro del contenedor:
```dockerfile
RUN apt-get update && apt-get install -y cron
RUN echo "*/30 * * * * cd /app && python scripts/run_refresh_job.py >> /var/log/refresh.log 2>&1" | crontab -
CMD ["cron", "-f"]
```

### Opción 3: Windows Task Scheduler

1. Abrir Task Scheduler (`taskschd.msc`)
2. Crear Basic Task
3. Trigger: Daily, cada 30 minutos
4. Action: Start a program
   - Program: `python`
   - Arguments: `scripts/run_refresh_job.py`
   - Start in: `C:\ruta\al\proyecto\backend`
5. Habilitar "Run whether user is logged on or not"

### Opción 4: PM2 (Node.js style)

Si tienes PM2 instalado:
```bash
pm2 start scripts/run_refresh_loop.py --name yego-refresh --interpreter python
pm2 save
pm2 startup
```

---

## Monitoreo

### Endpoint HTTP

```bash
# Ver estado del último refresh
curl http://localhost:8002/ops/refresh-status

# Ver historial
curl http://localhost:8002/ops/refresh-history?limit=20

# Ejecutar manualmente
curl -X POST http://localhost:8002/ops/refresh-run
```

### SQL Queries

```sql
-- Último refresh por dataset
SELECT * FROM bi.refresh_audit
ORDER BY created_at DESC
LIMIT 10;

-- Datasets stale (> 2 horas)
SELECT 
    dataset_name,
    last_refresh_at,
    EXTRACT(EPOCH FROM (NOW() - last_refresh_at)) / 60 as minutes_since
FROM bi.refresh_audit
WHERE status = 'success'
AND EXTRACT(EPOCH FROM (NOW() - last_refresh_at)) / 60 > 120
ORDER BY last_refresh_at ASC;

-- Estado del lock
SELECT * FROM bi.refresh_lock;
```

---

## Troubleshooting

### "Another refresh is running"
- Normal: hay otro proceso ejecutándose
- Verificar: `SELECT * FROM bi.refresh_lock;`
- Si es zombie (> 2 horas): se auto-resetea
- Forzar reset: `UPDATE bi.refresh_lock SET is_running = FALSE;`

### Dataset no existe
- Verificar que la función SQL existe: `SELECT ops.refresh_real_trips_monthly();`
- Agregar a KNOWN_REFRESH_DATASETS en refresh_service.py

### Falla después de 3 retries
- Revisar logs: `logs/refresh.log`
- Verificar conectividad a DB
- Revisar estado de la MV: `SELECT * FROM pg_stat_activity WHERE query LIKE '%refresh%';`

---

## Tablas de Auditoría

### bi.refresh_audit
- id (PK)
- dataset_name
- last_refresh_at
- status (success/failed)
- duration_seconds
- error_message
- created_at

### bi.refresh_lock
- id (PK)
- lock_name (unique)
- is_running (boolean)
- started_at
- updated_at

---

## Seguridad

- NO expone credenciales (usa get_db existente)
- Lock anti-concurrencia integrado
- No rompe startup de FastAPI
- Logs limpios (no PII)

---

## Changelog

- v1.0: Sistema básico de auditoría
- v1.1: Lock anti-concurrencia + retry
- v1.2: Registro granular por dataset
