# LoopControl Reactivation Checklist — LG-C1.3B

**Date:** 2026-06-05
**Phase:** LG-C1.3B → LG-C1.4
**Current Status:** NEEDS CONFIG

---

## Bloqueantes (deben completarse antes de reactivar)

- [ ] **Paso 1** — Obtener `LOOPCONTROL_INTEGRATION_KEY` real
  - Responsable: Miguel / Admin plataforma
  - Fuente: Miguel (call center operator) o dashboard `api-betaleads.yego.pro`
  - Acción: Solicitar key o regenerar si está perdida

- [ ] **Paso 2** — Resolver import roto `yego_lima_loopcontrol_result_sync`
  - Responsable: Developer
  - Archivo: `backend/app/main.py` lines 8, 138
  - Acción: Crear placeholder router o comentar import

- [ ] **Paso 3** — Configurar `.env` con la key real
  - Responsable: DevOps
  - Variable: `LOOPCONTROL_INTEGRATION_KEY=<key_real>`
  - Archivo: `backend/.env`

- [ ] **Paso 4** — Verificar `LOOPCONTROL_ENABLED=true` en `.env`
  - Responsable: DevOps
  - Ya está `true`, solo confirmar

- [ ] **Paso 5** — Reiniciar backend
  - Responsable: DevOps
  - Verificar que arranca sin errores

---

## No bloqueantes (validación post-reactivación)

- [ ] **Paso 6** — `GET /yego-lima-growth/loopcontrol/config`
  - Esperado: `{"enabled": true, "base_url_configured": true, "integration_key_configured": true, "mode": "LIVE", "issues": []}`

- [ ] **Paso 7** — Export test limit=5
  - `POST /yego-lima-growth/loopcontrol/export-draft`
  - Body: `{"opportunity_date": "2026-06-05", "program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "limit": 5}`
  - Esperado: `export_status: "exported"`, `campaign_id_external: <número>`

- [ ] **Paso 8** — Verificar `campaign_id_external != null`
  - Si es null → la key o URL no son válidas

- [ ] **Paso 9** — Verificar en DB
  - `SELECT * FROM growth.yango_lima_loopcontrol_campaign_export ORDER BY exported_at DESC LIMIT 1;`
  - Esperado: `export_status = 'exported'`, `contacts_inserted > 0`

- [ ] **Paso 10** — (Opcional) Activar auto-export job
  - `LOOPCONTROL_AUTO_EXPORT_ENABLED=true`
  - `LOOPCONTROL_EXPORT_HOUR=8`

---

## Ready Next: LG-C1.4 Result Sync Certification

Una vez que LG-C1.3B esté reactivado y generando `campaign_id_external`:

1. Coordinar con Miguel endpoint para recibir resultados de campaña
2. Implementar `yego_lima_loopcontrol_result_sync` router/service
3. Poblar `growth.yango_lima_loopcontrol_campaign_result`
4. Conectar con LimaGrowthDashboard (ya tiene UI placeholder)
