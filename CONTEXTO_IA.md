# Contexto completo para IAs: YEGO Control Tower

Este documento sirve para **compartir con ChatGPT u otras inteligencias artificiales** y para **dar mejores indicaciones a Cursor**. Incluye qué es el proyecto, fuentes de datos, reglas críticas y guías para que las IAs implementen cambios de forma segura y coherente.

---

## 1. ¿Qué es YEGO Control Tower?

**Propósito:** Sistema de **control de gestión operativa** que compara **Plan** (proyecciones) con **Real** (operación) para dar visibilidad, alertas accionables y accountability.

**Dominio:** Operaciones de YEGO (viajes completados, conductores, revenue, líneas de negocio LOB, territorios país/ciudad/parque, segmentos B2B/B2C).

**En una frase:** Dashboard web que une Plan vs Real mensual/semanal, alertas, acciones correctivas y visibilidad del universo LOB para tomar decisiones operativas.

---

## 2. Stack tecnológico

| Capa        | Tecnología |
|------------|------------|
| Backend    | Python 3.11, FastAPI 2.x, Uvicorn, Pydantic v2, psycopg2, pandas, openpyxl, Alembic |
| Frontend   | React 18, Vite 5, Axios, Tailwind CSS |
| Base de datos | PostgreSQL (`yego_integral`) |
| APIs       | REST; documentación en `/docs` cuando el backend está en marcha |

---

## 3. Estructura del proyecto (rutas clave)

```
YEGO CONTROL TOWER/
├── backend/
│   ├── app/
│   │   ├── main.py              # App FastAPI, CORS, routers, startup
│   │   ├── settings.py          # Configuración (Pydantic, .env)
│   │   ├── db/
│   │   │   ├── connection.py    # Pool PostgreSQL, get_db(), esquemas plan/bi
│   │   │   └── schema_verify.py # Verificación columnas mínimas al inicio
│   │   ├── contracts/
│   │   │   └── data_contract.py # Mapeo métricas, LOB, revenue, normalización
│   │   ├── adapters/
│   │   │   ├── plan_repo.py     # Lectura/escritura plan.*
│   │   │   ├── real_repo.py     # Lectura bi.*, dim.*
│   │   │   └── lob_universe_repo.py
│   │   ├── services/            # Lógica de negocio (ver sección 7)
│   │   ├── routers/             # Endpoints (plan, real, core, ops, phase2b, phase2c, ingestion, health)
│   │   └── models/
│   │       └── schemas.py       # Modelos Pydantic (request/response)
│   ├── alembic/versions/        # Migraciones de esquema
│   ├── scripts/                # Ingesta Plan Ruta 27, refresh MVs, etc.
│   ├── sql/                    # SQL y documentación de reglas
│   └── exports/                # CSVs de catálogos
├── frontend/
│   └── src/
│       ├── App.jsx             # Tabs: Real LOB, Legacy, Phase2B, Phase2C, LOB Universe
│       ├── services/api.js      # Cliente Axios y funciones por endpoint
│       └── components/         # KPICards, Filters, MonthlySplitView, etc.
├── docs/                       # Documentación (contracts, drill, etc.)
├── README.md                   # Instalación, endpoints, reglas
└── CONTEXTO_IA.md              # Este archivo
```

---

## 4. Fuentes de datos

### Base de datos PostgreSQL (`yego_integral`)

**Real (canónico):**
- **`public.trips_all`**: Viajes; filtro canónico `condicion = 'Completado'`.
- **`ops.mv_real_trips_monthly`**: Vista materializada agregada por (country, city, city_norm, lob_base, segment, month). Métricas: trips_real_completed, active_drivers_real, avg_ticket_real, revenue_real_proxy / revenue_real_yego, etc. Se refresca con `ops.refresh_real_trips_monthly()` o scripts.

**Dimensiones:**
- **`dim.dim_park`**: park_id, city, country, default_line_of_business (requerido por schema_verify).
- **`bi.real_monthly_agg`**, **`bi.real_daily_enriched`**: Agregados mensuales/diarios (orders_completed, year, month, etc.).

**Plan:**
- **`plan.plan_long_raw`**, **`plan.plan_long_valid`**, **`plan.plan_long_out_of_universe`**, **`plan.plan_long_missing`**: Plan formato long (period, country, city, line_of_business, metric, plan_value).
- **`ops.plan_trips_monthly`**: Tabla canónica Plan versionado (Ruta 27): plan_version, country, city, park_id, lob_base, segment, month, projected_trips, projected_drivers, projected_ticket, projected_revenue, etc. Append-only por versión.
- **`staging.plan_projection_raw`**, **`staging.plan_projection_realkey_raw`**: Staging para uploads.

**Operativo y comparación:**
- Vistas: **`ops.v_plan_trips_monthly_latest`**, **`ops.v_real_trips_monthly_latest`**, **`ops.v_plan_vs_real_monthly_latest`**, **`ops.v_plan_vs_real_realkey_final`**, **`ops.v_plan_vs_real_alerts_monthly_latest`**.
- **`ops.phase2b_actions`**: Acciones Fase 2B (week_start, country, city_norm, lob_base, segment, alert_type, root_cause, action_type, owner_role, due_date, status).
- **`bi.ingestion_status`**: Estado de ingesta (dataset_name, max_year, max_month, last_loaded_at).

**LOB:** Vistas/MVs de Real por LOB (homologación, tipo_servicio, lob_group, segment), drill mensual/semanal, estrategia (ej. `ops.mv_real_lob_drill_agg`, `ops.v_real_lob_resolved_final`).

### Archivos (ingesta)
- **Plan**: Subida por UI (CSV/Excel plantilla simple) o CSV Ruta 27 vía `POST /plan/upload_ruta27` y script `backend/scripts/ingest_plan_from_csv_ruta27.py`. Contrato de columnas en README y en `app/contracts/data_contract.py`.

---

## 5. Fases del sistema (2A, 2B, 2C, 2C+)

| Fase | Descripción |
|------|-------------|
| **2A** | Plan vs Real mensual, universo operativo, deltas y comparison_status (NOT_COMPARABLE, NO_REAL_YET, COMPARABLE). |
| **2B** | Plan vs Real semanal, alertas accionables y registro de acciones en `ops.phase2b_actions`. |
| **2C** | Scoreboard, backlog, breaches de SLA, snapshot. |
| **2C+** | Universo LOB, mapeo Plan → Real, viajes sin mapeo. |

---

## 6. Endpoints API (resumen)

| Prefijo | Archivo | Uso principal |
|---------|---------|----------------|
| `/plan` | `routers/plan.py` | upload_simple, upload_ruta27, summary/monthly, out_of_universe, missing |
| `/real` | `routers/real.py` | summary/monthly |
| `/core` | `routers/core.py` | summary/monthly (Plan+Real+deltas+comparison_status) |
| `/ops` | `routers/ops.py` | universe, plan-vs-real/monthly y alerts, real/monthly, plan/monthly, compare/overlap-monthly, real-lob (mensual/semanal, v2, drill, filters), real-drill, real-strategy, territory-quality |
| `/phase2b` | `routers/phase2b.py` | weekly/plan-vs-real, weekly/alerts, actions (CRUD, mark-missed) |
| `/phase2c` | `routers/phase2c.py` | scoreboard, backlog, breaches, run-snapshot, lob-universe, lob-universe/unmatched |
| `/ingestion` | `routers/ingestion.py` | status?dataset_name=... |
| `/health` | `routers/health.py` | healthcheck |

---

## 7. Servicios clave (lógica de negocio)

- **plan_parser_service**: Parseo plantilla simple; separación valid/out_of_universe/missing.
- **ops_universe_service**: Universo operativo desde bi.real_monthly_agg + dim.dim_park (actividad 2025); caché.
- **core_service**: Resumen mensual core (join Plan/Real, deltas, comparison_status).
- **plan_real_split_service**: Real/Plan mensual desde ops (mv_real_trips_monthly, vistas plan), overlap mensual.
- **plan_vs_real_service**: Plan vs Real mensual y alertas desde ops.v_plan_vs_real_realkey_final.
- **phase2b_weekly_service**: Plan vs Real semanal y alertas.
- **phase2b_actions_service**: CRUD y mark_missed sobre ops.phase2b_actions.
- **phase2c_accountability_service**: Scoreboard, backlog, breaches, snapshot.
- **lob_universe_service**: Universo LOB y viajes sin mapeo.
- **real_lob_service**, **real_lob_service_v2**: Real por LOB mensual/semanal (v2: lob_group, tipo_servicio, segment).
- **real_lob_filters_service**: Opciones de filtros (countries, cities, parks, lob_groups) con caché.
- **real_lob_v2_data_service**: Datos Real LOB v2 por niveles de agregación.
- **real_drill_service**, **real_lob_drill_pro_service**: Drill por país/LOB/park, totals, coverage, refresh MV.
- **real_strategy_service**: KPIs ejecutivos, forecast, rankings por país, LOB y ciudades.
- **territory_quality_service**: KPIs de mapeo territorial y parques sin mapear.

**Contrato de datos:** `app/contracts/data_contract.py` — mapeo métricas (trips→orders_completed, revenue dinámico), LOB, tipo_servicio, normalización país/ciudad, `resolve_lob_with_meta`. No inventar columnas; inspección dinámica cuando aplique.

---

## 8. Reglas críticas (NO saltarse)

- **NO exportar** CSV, Excel, Google Sheets ni archivos descargables desde el sistema sin requisito explícito.
- **Real solo desde Postgres**: bi.real_*, dim.dim_park, ops.mv_real_trips_monthly; no inventar datos.
- **Plan**: desde Excel/CSV → plan.plan_long_* u ops.plan_trips_monthly según flujo.
- **NO inventar columnas**: siempre inspeccionar schema o usar data_contract.
- **Si falta revenue real**: dejar null, nunca inventar.
- **Universo operativo manda**: no inventar ciudad/línea; validar contra ops_universe.
- **Delta solo si comparable**: year_real == year_plan y existe real; comparison_status debe respetarse en UI.
- **Revenue Plan**: en Ruta 27 es `projected_revenue` (input); no confundir con GMV ni calcular como trips×ticket sin indicación explícita.

---

## 9. Cómo dar mejores indicaciones a Cursor (y a cualquier IA)

### 9.1 Incluir contexto concreto
- **Mal:** "Arregla el plan."
- **Bien:** "En el endpoint GET /ops/plan/monthly, cuando no hay datos para un mes, devolver 0 en projected_trips en lugar de omitir el mes. El frontend espera siempre 12 meses en MonthlySplitView."

### 9.2 Indicar archivos o capas
- **Mal:** "Cambia el cálculo de revenue."
- **Bien:** "En backend/app/services/plan_vs_real_service.py, el delta de revenue debe usar revenue_real_yego si existe, si no revenue_real_proxy. Mantener data_contract para no inventar columnas."

### 9.3 Mencionar reglas del dominio
- **Ejemplo:** "Añade un filtro por segment (B2B/B2C) en la vista Real LOB, sin mezclar monedas cuando no hay país seleccionado (igual que en Fase 2A)."

### 9.4 Especificar contrato API cuando toques endpoints
- **Ejemplo:** "El nuevo endpoint GET /ops/real-lob/v2/data debe aceptar query params: country, city, lob_group, year, month. La respuesta debe seguir el mismo formato que /ops/real/monthly para reutilizar la tabla del frontend."

### 9.5 Pedir una cosa por mensaje (para cambios grandes)
- Para cambios grandes, dividir: primero "añadir campo X al schema y migración", luego "usar X en el servicio Y", luego "mostrar X en el componente Z".

---

## 10. Cómo pueden interactuar mejor ChatGPT y Cursor

### 10.1 Flujo recomendado
1. **En ChatGPT:** Describir el objetivo de negocio o la funcionalidad deseada (sin necesidad de conocer la estructura del repo). Pedir que te devuelva un **prompt estructurado** para Cursor con: qué hacer, en qué capa (API, servicio, frontend), reglas que respetar (ver sección 8) y nombres de archivos si los conoces.
2. **Copiar este documento (CONTEXTO_IA.md)** en la conversación con ChatGPT y decir: "Usa este contexto para generar el prompt para Cursor."
3. **En Cursor:** Pegar el prompt generado (o el tuyo mejorado) y, si hace falta, adjuntar o citar `CONTEXTO_IA.md` o `README.md` para que Cursor tenga el contexto del proyecto.

### 10.2 Qué puede hacer ChatGPT con este contexto
- Redactar prompts que incluyan: capa (router/servicio/adapter/frontend), reglas críticas, y si aplica contrato de API o de datos.
- Proponer mensajes de commit o descripciones de PR alineadas con las fases (2A/2B/2C).
- Sugerir nombres de endpoints o de funciones coherentes con el resto del código (p. ej. plan-vs-real, real-lob, phase2b).

### 10.3 Qué hace mejor Cursor
- Editar archivos concretos del repo (backend/app/..., frontend/src/...).
- Respetar imports, convenciones y reglas ya existentes (data_contract, schema_verify, no inventar columnas).
- Ejecutar migraciones Alembic, scripts en backend/scripts, o comandos en el proyecto.

### 10.4 Ejemplo de prompt para Cursor generado con ayuda de ChatGPT
"En YEGO Control Tower, backend FastAPI + React. Necesito que las alertas mensuales (GET /ops/plan-vs-real/alerts) incluyan un campo 'severity' calculado así: si delta_trips_pct < -10% entonces 'high', si < -5% entonces 'medium', si no 'low'. Respeta que los deltas solo existen cuando comparison_status es COMPARABLE. Añade el campo en backend/app/services/plan_vs_real_service.py y en backend/app/models/schemas.py en el schema de respuesta de alertas. No inventar columnas en BD; solo lógica en el servicio."

---

## 11. Cómo implementar mejor las mejoras (buenas prácticas)

1. **Leer antes de escribir:** Revisar el servicio o router existente y el data_contract antes de añadir métricas o columnas.
2. **Un cambio, un ámbito:** Si tocas BD, haz migración Alembic; si tocas API, actualiza schemas Pydantic y, si aplica, el cliente en frontend/src/services/api.js.
3. **Nombres consistentes:** Usar snake_case en backend, mismo criterio que en ops.plan_trips_monthly y en las vistas (country, city_norm, lob_base, segment).
4. **Filtros y monedas:** Si un endpoint puede devolver varios países, documentar o mantener la convención de no mezclar monedas en un mismo total (como en Fase 2A).
5. **Tests y validación:** Si añades reglas de negocio nuevas (p. ej. severity), considerar tests o al menos verificar en /docs que el contrato de respuesta sea correcto.

---

## 12. Referencias rápidas

- **API docs (local):** http://localhost:8000/docs  
- **Frontend (dev):** http://localhost:5173  
- **Variables de entorno:** backend/.env (DB_*, ENVIRONMENT, CORS_ORIGINS); frontend: VITE_API_URL, VITE_CT_LEGACY_ENABLED  
- **Migraciones:** `cd backend && alembic upgrade head`  
- **Refresh Real mensual:** `SELECT ops.refresh_real_trips_monthly();` (o script en backend/scripts)

---

*Documento pensado para compartir con ChatGPT u otras IAs y para mejorar las indicaciones a Cursor. Actualizar cuando cambien fuentes de datos, reglas críticas o estructura del proyecto.*
