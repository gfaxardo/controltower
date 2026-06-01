# REFRESH REMEDIATION POLICY — Omniview Serving Facts

**Motor:** Control Foundation  
**Prioridad:** Crítica  
**Fecha:** 2026-05-31  
**Versión:** 1.0.0  

---

## 1. Propósito

Definir la política de recuperación cuando el RAW (datos fuente `trips_2026`) está fresco pero las serving facts de Omniview (`day_fact`, `week_fact`, `month_fact`, `projection_daily_fact`) están desactualizadas, resultando en estado **BLOCKED** en Freshness Governance.

---

## 2. Diagnóstico del Estado BLOCKED

Freshness Governance detecta BLOCKED cuando:

| Capa | Condición | Umbral |
|------|-----------|--------|
| Daily fact | `lag_days > 3` | >3 días sin refrescar |
| Weekly fact | `lag_days > 10` | >10 días desde último week_start |
| Monthly fact | `month_start < mes anterior` | Mes anterior o más atrás |
| Projection daily | `lag_days > 3` | >3 días sin refrescar |

**Señal típica de BLOCKED:** RAW tiene datos de hoy/ayer, pero las serving facts tienen 4+ días de atraso. Esto ocurre cuando el pipeline de refresh (APScheduler o script manual) no se ejecutó.

---

## 3. Por Qué APScheduler No Basta en Dev

### 3.1 Comportamiento en Desarrollo

- APScheduler es un `BackgroundScheduler` en proceso. Solo vive mientras el backend está corriendo.
- En desarrollo (`ENVIRONMENT=dev`), el backend se inicia y detiene frecuentemente.
- `CT_SCHEDULER_ENABLED` está en `False` por defecto (ver `settings.py:193-196`).
- Aunque `OMNIVIEW_REAL_REFRESH_ENABLED=True` por defecto, el scheduler maestro no arranca si `CT_SCHEDULER_ENABLED=False`.
- Si el backend está apagado durante la ventana programada (04:00 UTC), el refresh simplemente no ocurre.
- No hay persistencia de jobs: si el backend se reinicia, el scheduler vuelve a empezar sin "catch-up".

### 3.2 Consecuencia

En dev, si el backend está apagado 24h+, las serving facts quedan sin refrescar aunque RAW se actualice por ingesta externa. Al iniciar el backend, Freshness Governance reporta BLOCKED y **no hay remediación automática**.

---

## 4. Diferencia Dev / Prod

| Aspecto | Dev | Prod |
|---------|-----|------|
| **Scheduler** | APScheduler en proceso (frágil) | Cron / systemd timer / job externo |
| `CT_SCHEDULER_ENABLED` | `False` (default) | `True` (explícito) |
| **Refresh al iniciar** | NUNCA automático | NUNCA automático (misma política) |
| **Remediación** | Manual vía endpoint `/ops/omniview/refresh` o UI | Externo vía job programado |
| **Health check startup** | Ligero: solo log + alerta visible | Ligero: solo log + alerta al sistema de monitoreo |
| **Garantía de refresh** | No garantizada (aceptable en dev) | Job externo persistente |

---

## 5. Cuándo Correr Refresh Manual

Ejecutar `POST /ops/omniview/refresh` (o `--force` desde CLI) cuando:

1. **Freshness Governance muestra BLOCKED** y se va a usar Omniview para decisiones.
2. **Después de un periodo prolongado sin backend** (>12h en dev, >1h en prod si falló el job externo).
3. **Antes de una demo, QA, o release candidate** para asegurar datos frescos.
4. **Después de ingesta masiva de RAW** que requiere reflejo inmediato en serving.

**NO correr refresh manual:**
- Durante ventanas de alto tráfico en prod (el refresh consume DB resources).
- Si el RAW está vacío o corrupto (verificar con health check primero).
- Concurrentemente (el advisory lock protege, pero genera skip innecesario).

---

## 6. Cuándo Bloquear Omniview

Omniview debe mostrarse como **BLOCKED** (rojo, sin datos engañosos) cuando:

1. **Daily fact lag > 3 días:** la ventana operativa más reciente no está disponible.
2. **Cualquier capa está en ERROR:** fallo de consulta o datos corruptos.
3. **DB no responde:** el health check de startup falló en tier bloqueante.

**Omniview NO debe bloquearse cuando:**
- Solo weekly o monthly están en WARNING (lag leve).
- La proyección está levemente atrasada pero daily/weekly están OK.
- El RAW está fresco pero el refresh está en curso (mostrar estado intermedio).

---

## 7. Flujo de Remediación

```
┌─────────────────────────────────────────────────────────────┐
│                  FRESHNESS GOVERNANCE                        │
│                                                              │
│  RAW fresco ✓   Daily ✗   Weekly ✗   Monthly ✗   Proj ✗   │
│  Status: BLOCKED                                             │
│                                                              │
│  ┌─────────────────────────────┐                             │
│  │  [Refrescar Omniview]      │  ← Botón visible en UI      │
│  └─────────────────────────────┘                             │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────────────┐                             │
│  │  POST /ops/omniview/refresh │  ← Endpoint admin          │
│  │  ?force=true                │                             │
│  └─────────────────────────────┘                             │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────────────────────────────────┐         │
│  │  run_business_slice_real_refresh_job(force=True) │         │
│  │  → day_fact + week_fact + month_fact             │         │
│  │  → mes actual + mes anterior                     │         │
│  │  → advisory lock                                 │         │
│  └─────────────────────────────────────────────────┘         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────────────┐                             │
│  │  Re-check Freshness          │                             │
│  │  GET /ops/omniview/freshness │                             │
│  └─────────────────────────────┘                             │
│           │                                                  │
│           ▼                                                  │
│  RAW fresco ✓   Daily ✓   Weekly ✓   Monthly ✓   Proj ✓    │
│  Status: OK                                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Prohibiciones (Do NOT)

| Acción | Motivo |
|--------|--------|
| Ejecutar backfill pesado automáticamente en startup | Bloquearía el inicio del backend, riesgo de timeout |
| Ocultar alerta de BLOCKED | El usuario debe saber que los datos no son confiables |
| Maquillar freshness (forzar OK artificial) | Falsa seguridad, decisiones sobre datos stale |
| Hacer fallback runtime en UI (mostrar RAW directo) | El frontend no debe consultar RAW; rompe la cadena de gobernanza |
| Escanear RAW desde frontend | Problemas de performance, seguridad, y arquitectura |
| Refresh sin advisory lock en prod | Riesgo de race condition multi-worker |

---

## 9. Recomendación para Producción

### 9.1 Scheduler Externo

Usar un scheduler externo al backend. Opciones:

**Opción A — Cron / systemd timer (Linux server):**
```cron
# /etc/cron.d/omniview-refresh
# Diario a las 05:00 UTC (después del cierre de datos D-1)
0 5 * * * cd /opt/controltower/backend && python -m scripts.refresh_omniview_real_slice --force >> /var/log/omniview-refresh.log 2>&1
```

**Opción B — GitHub Actions (si el entorno lo permite):**
```yaml
name: Omniview Daily Refresh
on:
  schedule:
    - cron: '0 5 * * *'  # 05:00 UTC
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run refresh
        run: |
          cd backend
          pip install -r requirements.txt
          python -m scripts.refresh_omniview_real_slice --force
```

**Opción C — APScheduler en worker dedicado:**
- Separar el scheduler en un proceso independiente (`scheduler_worker.py`) supervisado por systemd.
- No atado al ciclo de vida del backend API.

### 9.2 Health Check Posterior

Después de cada refresh programado, ejecutar verificación:
```bash
python -m scripts.check_omniview_serving_freshness
```
Si el check falla (status != ok), disparar alerta al sistema de monitoreo (Slack, PagerDuty, webhook configurado en `REAL_FRESHNESS_ALERT_WEBHOOK`).

### 9.3 Frecuencia

- **Diaria**, después del cierre de datos D-1 (raw poblado para el día anterior).
- Horario recomendado: 04:00–06:00 UTC (ventana de bajo tráfico).
- En entornos de alto volumen, considerar refresh cada 6h para day_fact solamente.

### 9.4 Alerta si Falla

Configurar `REAL_FRESHNESS_ALERT_WEBHOOK` con un endpoint que notifique al equipo de data si:
- El refresh falla (errores en el job).
- El health check post-refresh muestra BLOCKED.
- El RAW está vacío (posible problema de ingesta).
