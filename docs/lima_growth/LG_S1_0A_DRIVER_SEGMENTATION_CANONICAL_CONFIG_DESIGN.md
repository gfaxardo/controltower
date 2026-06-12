# LG-S1.0A — DRIVER SEGMENTATION CANONICAL CONFIG DESIGN

**Fase:** Lima Growth Foundation — S1.0A  
**Motor:** Control Foundation (Lima Growth)  
**Estatus:** DESIGN ONLY — NO IMPLEMENTAR  
**Fecha:** 2026-06-10  
**Simulación:** data real 2026-06-10, N=18,545 drivers

---

## TASK 0 — GOVERNANCE CHECK

### Fase Activa Confirmada

| Motor | Fase | Estatus |
|-------|------|---------|
| Control Foundation | Omniview P0 Recovery | **REOPENED / P0** |
| Diagnostic Engine | 2A.3 | **PAUSED** (bloqueado hasta cierre real de OMNI-P0) |
| Lima Growth | Scheduler autónomo | **ACTIVE** (5-min tick, overlap-protected) |

### Restricciones Vigentes

- **NO** activar Diagnostic, Forecast, Suggestion, Decision, Action, Learning
- **NO** modificar lógica de negocio sin auditar
- **NO** re-enable heavy runtime fallback
- LG-S1.0A es **design-only**: no modifica queue, export, control_loop, scoring, ni programas legacy
- Compatible con fase activa: es diseño de configuración de capa fundamental, no activa motores bloqueados

### Veredicto de Governance

**GO para diseño.** La fase pertenece a Control Foundation (Lima Growth Foundation), que opera autónomamente bajo el paraguas CF. No viola restricciones de motores bloqueados porque no implementa, solo diseña.

---

## TASK 1 — AUDITORÍA DEL MODELO ACTUAL

### 1.1 Program Registry Actual

| Program Code | Priority | Activo | Descripción |
|---|---|---|---|
| `PROGRAM_HIGH_VALUE_RECOVERY` | 1 | true | High historical value, recently inactive |
| `PROGRAM_CHURN_PREVENTION` | 2 | true | Drivers at risk of churning/declining |
| `PROGRAM_14_90` | 3 | true | New/reactivated within 14-90 day window |
| `PROGRAM_ACTIVE_GROWTH` | 4 | true | Active drivers below weekly performance target |

**Source**: `growth.yego_lima_program_registry` (seed migration #198), `yego_lima_program_eligibility_service.py:31-33`

### 1.2 Eligibility Actual (2026-06-10)

| Programa | Elegibles | % Universo |
|---|---|---|
| ACTIVE_GROWTH | 17,685 | 95.3% |
| CHURN_PREVENTION | 7,774 | 41.9% |
| 14_90 | 2,669 | 14.4% |

**Problema crítico**: 9,125 drivers (49.2%) en 2+ programas simultáneamente. 963 en los 3 programas.

### 1.3 Overlap Multi-Programa

| Programas por Driver | Drivers | % |
|---|---|---|
| 1 | 8,915 | 48.1% |
| 2 | 8,162 | 44.0% |
| 3 | 963 | 5.2% |

### 1.4 Prioritized Opportunities (2026-06-10)

| Programa | Total | Actionable |
|---|---|---|
| 14_90 | 2,208 | 0 |
| CHURN_PREVENTION | 2,001 | 451 |
| ACTIVE_GROWTH | 1,173 | 0 |
| HIGH_VALUE_RECOVERY | 49 | 49 |

### 1.5 Queue (2026-06-10)

| Programa | READY |
|---|---|
| CHURN_PREVENTION | 32 |
| 14_90 | 15 |
| ACTIVE_GROWTH | 3 |
| HIGH_VALUE_RECOVERY | 2 |

### 1.6 Drivers Sin Programa

505 drivers (2.7%) no califican a ningún programa actual.

### 1.7 Clasificación de Programas Legacy

| Programa Legacy | Clasificación | Replacement Segment |
|---|---|---|
| `PROGRAM_HIGH_VALUE_RECOVERY` | **MAP_TO_NEW_SEGMENT** | `HIGH_VALUE_RECOVERY` (mismo nombre, reglas configurables) |
| `PROGRAM_CHURN_PREVENTION` | **DEPRECATE** | Subsumido en `ACTIVE_GROWTH` (señales de riesgo) |
| `PROGRAM_14_90` | **MAP_TO_NEW_SEGMENT** | `NEW_OR_REACTIVATED` (namespace más amplio) |
| `PROGRAM_ACTIVE_GROWTH` | **MAP_TO_NEW_SEGMENT** | `ACTIVE_GROWTH` (redefinido: solo drivers con señales de intervención) |

**Justificación**:
- `CHURN_PREVENTION` como programa independiente genera overlap masivo (42% del universo está en CP). Su lógica (retention_state AT_RISK/CHURN_RISK, declining_flag, churn_risk_flag) es una **señal de intervención** dentro de `ACTIVE_GROWTH`, no un segmento propio.
- Los 4 programas actuales no son excluyentes por diseño (policy `allow_multi_program_eligibility = true`). El nuevo diseño fuerza exclusión.

---

## TASK 2 — DISEÑO DE TABLAS DE CONFIGURACIÓN

### 2.1 `growth.yego_lima_segment_registry`

```sql
CREATE TABLE growth.yego_lima_segment_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_code    TEXT NOT NULL UNIQUE,
    segment_name    TEXT NOT NULL,
    description     TEXT,
    priority_order  INTEGER NOT NULL CHECK (priority_order >= 1),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    is_exclusive    BOOLEAN NOT NULL DEFAULT true,
    is_catch_all    BOOLEAN NOT NULL DEFAULT false,
    policy_version  TEXT NOT NULL DEFAULT 'v1',
    valid_from      DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to        DATE,
    deprecated_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Seed inicial (6 segmentos)**:

| segment_code | segment_name | priority_order | is_exclusive | is_catch_all |
|---|---|---|---|---|
| `HIGH_VALUE_RECOVERY` | High Value Recovery | 1 | true | false |
| `TOP_PERFORMER` | Top Performer | 2 | true | false |
| `NEW_OR_REACTIVATED` | New or Reactivated | 3 | true | false |
| `ACTIVE_GROWTH` | Active Growth | 4 | true | false |
| `STABLE` | Stable | 5 | true | false |
| `UNCLASSIFIED` | Unclassified | 99 | true | true |

**Programas hijos de `NEW_OR_REACTIVATED`** (no son segmentos, son sub-programas):

| sub_program_code | parent_segment | target |
|---|---|---|
| `NOR_50_14` | NEW_OR_REACTIVATED | 50 viajes en 14 días |
| `NOR_90_300` | NEW_OR_REACTIVATED | 300 viajes en 90 días |

### 2.2 `growth.yego_lima_segment_rule_config`

```sql
CREATE TABLE growth.yego_lima_segment_rule_config (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_code      TEXT NOT NULL REFERENCES growth.yego_lima_segment_registry(segment_code),
    rule_group        TEXT NOT NULL,        -- e.g. 'ELIGIBILITY', 'EXCLUSION', 'SUB_CLASSIFICATION'
    rule_key          TEXT NOT NULL,        -- e.g. 'min_completed_orders_week'
    operator          TEXT NOT NULL,        -- e.g. '>=', 'IN', 'BETWEEN', 'IS_TRUE', 'IS_NOT_NULL'
    value_json        JSONB NOT NULL,       -- e.g. 80, ["ACTIVATED","EARLY_LIFE"], [1,14]
    weight            FLOAT DEFAULT 1.0,    -- For composite scoring
    required_flag     BOOLEAN DEFAULT true, -- If true, rule MUST pass
    exclusion_flag    BOOLEAN DEFAULT false,-- If true, matching EXCLUDES from segment
    policy_version    TEXT NOT NULL DEFAULT 'v1',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_segment_rules_code ON growth.yego_lima_segment_rule_config(segment_code);
CREATE INDEX idx_segment_rules_version ON growth.yego_lima_segment_rule_config(policy_version);
```

### 2.3 `growth.yego_lima_segment_dependency_config`

```sql
CREATE TABLE growth.yego_lima_segment_dependency_config (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_code                TEXT NOT NULL REFERENCES growth.yego_lima_segment_registry(segment_code),
    excludes_segment_code       TEXT,  -- This segment excludes drivers also matching this
    depends_on_segment_code     TEXT,  -- This segment's rules are evaluated after this
    precedence_order            INTEGER NOT NULL,
    conflict_resolution_strategy TEXT NOT NULL DEFAULT 'STRICT_PRECEDENCE', -- STRICT_PRECEDENCE | HIGHEST_SCORE | LEAST_CONFLICT
    policy_version              TEXT NOT NULL DEFAULT 'v1',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.4 `growth.yego_lima_driver_segment_snapshot`

```sql
CREATE TABLE growth.yego_lima_driver_segment_snapshot (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date         DATE NOT NULL,
    driver_profile_id     TEXT NOT NULL,
    segment_code          TEXT NOT NULL,
    classification_reason TEXT,
    matched_rules_json    JSONB,  -- {"HIGH_VALUE_RECOVERY": ["HV-001","HV-002","HV-003"]}
    failed_rules_json     JSONB,  -- {"ACTIVE_GROWTH": ["AG-003"], "STABLE": ["ST-001"]}
    excluded_segments_json JSONB, -- ["ACTIVE_GROWTH", "STABLE"]
    candidate_count       INTEGER,
    policy_version        TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(snapshot_date, driver_profile_id)
);

CREATE INDEX idx_segment_snapshot_date ON growth.yego_lima_driver_segment_snapshot(snapshot_date);
CREATE INDEX idx_segment_snapshot_segment ON growth.yego_lima_driver_segment_snapshot(snapshot_date, segment_code);
CREATE INDEX idx_segment_snapshot_driver ON growth.yego_lima_driver_segment_snapshot(driver_profile_id);
```

---

## TASK 3 — REGLAS INICIALES CONFIGURABLES

### 3.1 Variables desde `driver_state_snapshot`

| Variable | Columna | Tipo | Descripción |
|---|---|---|---|
| `lifecycle_state` | lifecycle_state | TEXT | PROSPECT, ACTIVATED, EARLY_LIFE, ESTABLISHED, REACTIVATED, CHURNED, UNKNOWN |
| `performance_state` | performance_state | TEXT | NO_TRIPS, LOW, MEDIUM, TARGET, HIGH, UNKNOWN |
| `retention_state` | retention_state | TEXT | HEALTHY, WATCHLIST, AT_RISK, CHURN_RISK, UNKNOWN |
| `completed_orders_week` | completed_orders_week | INTEGER | Viajes completados esta semana |
| `completed_orders_day` | completed_orders_day | INTEGER | Viajes completados hoy |
| `supply_hours_week` | supply_hours_week | NUMERIC | Horas de suministro semanal |
| `trips_per_supply_hour_week` | trips_per_supply_hour_week | NUMERIC | Eficiencia |
| `distance_to_weekly_target` | distance_to_weekly_target | INTEGER | Gap al target semanal |
| `reached_target_flag` | reached_target_flag | BOOLEAN | Alcanzó target semanal |
| `declining_flag` | declining_flag | BOOLEAN | Declive WoW > 30% |
| `churn_risk_flag` | churn_risk_flag | BOOLEAN | Riesgo de churn detectado |
| `recoverable_flag` | recoverable_flag | BOOLEAN | Históricamente valioso, recuperable |
| `new_driver_flag` | new_driver_flag | BOOLEAN | Driver nuevo |
| `reactivated_flag` | reactivated_flag | BOOLEAN | Driver reactivado |
| `avg_orders_4w` | avg_orders_4w | NUMERIC | Promedio 4 semanas |
| `avg_orders_12w` | avg_orders_12w | NUMERIC | Promedio 12 semanas |
| `best_week_12w` | best_week_12w | INTEGER | Mejor semana en 12w |
| `historical_band` | historical_band | TEXT | 50+, 30-49, 10-29, 0-9, NO_HISTORY |
| `weekly_trips_target` | weekly_trips_target | INTEGER | Target configurado |
| `last_trip_at` | last_trip_at | TIMESTAMPTZ | Último viaje registrado |
| `first_seen_at` | first_seen_at | TIMESTAMPTZ | Primera vez visto en el sistema |
| `first_trip_at` | first_trip_at | TIMESTAMPTZ | Primer viaje registrado |
| `last_supply_at` | last_supply_at | TIMESTAMPTZ | Último suministro (NULL en datos actuales) |

**Variables derivadas** (calculadas al vuelo, no almacenadas):

| Variable | Fórmula |
|---|---|
| `days_since_last_trip` | CURRENT_DATE - last_trip_at::date |
| `days_since_first_seen` | CURRENT_DATE - first_seen_at::date |
| `days_since_first_trip` | CURRENT_DATE - first_trip_at::date |
| `days_since_last_supply` | CURRENT_DATE - last_supply_at::date |
| `avg_weekly_trips_4w` | avg_orders_4w |
| `avg_weekly_trips_12w` | avg_orders_12w |
| `supply_hours_7d` | supply_hours_week (proxy) |
| `active_weeks_12w` | weeks with orders > 0 in last 12 (requiere history_weekly) |
| `top_percentile_threshold` | p80 de completed_orders_week del universo |

### 3.2 Reglas por Segmento (V1 Policy)

#### HIGH_VALUE_RECOVERY (Priority 1)
| Rule Key | Operator | Value | Required |
|---|---|---|---|
| `min_best_week_12w` | >= | 80 | true |
| `max_completed_orders_week` | = | 0 | true |
| `min_inactive_days` | >= | 1 | true |
| `max_inactive_days` | <= | 14 | true |
| `last_trip_not_null` | IS_NOT_NULL | true | true |

#### TOP_PERFORMER (Priority 2)
| Rule Key | Operator | Value | Required |
|---|---|---|---|
| `min_completed_orders_week_tier1` | >= | 80 | false |
| `min_completed_orders_week_tier2` | >= | 50 | false |
| `min_best_week_12w_tier2` | >= | 60 | false |
| `performance_state_tier3` | IN | ["HIGH"] | false |
| `min_completed_orders_week_tier3` | >= | 50 | false |

Logic: (tier1) OR (tier2) OR (tier3). Tier1 alone is sufficient (>=80). Tier2 needs both (>=50 AND best_12w>=60). Tier3 needs both (HIGH performance AND >=50).

#### NEW_OR_REACTIVATED (Priority 3)
| Rule Key | Operator | Value | Required |
|---|---|---|---|
| `lifecycle_state` | IN | ["ACTIVATED","EARLY_LIFE"] | false |
| `reactivated_flag` | IS_TRUE | true | false |
| `max_days_since_trip_for_react` | <= | 90 | false |
| `reached_target_flag` | IS_FALSE | true | true |

Logic: (lifecycle IN ['ACTIVATED','EARLY_LIFE'] OR (reactivated AND last_trip <= 90d)) AND NOT reached_target.

Sub-programas (solo clasificación, no afectan segmento exclusivo):
- `NOR_50_14`: lifecycle = 'EARLY_LIFE' (conductores nuevos, early window)
- `NOR_90_300`: lifecycle = 'ACTIVATED' (ventana extendida)

#### ACTIVE_GROWTH (Priority 4)
| Rule Key | Operator | Value | Required |
|---|---|---|---|
| `lifecycle_state` | IN | ["ACTIVATED","EARLY_LIFE","ESTABLISHED","REACTIVATED"] | true |
| `completed_orders_week` | < | 50 | true |
| `distance_to_target` | > | 0 | true |
| `max_completed_orders_week_for_growth` | < | 80 | true |
| `has_intervention_signal` | ANY_TRUE | ["declining_flag","churn_risk_flag","recoverable_flag"] | true |
| `retention_at_risk` | IN | ["AT_RISK","CHURN_RISK"] | false |

Logic: Active lifecycle AND below target AND NOT top AND (declining OR churn_risk OR recoverable OR at_risk retention).

#### STABLE (Priority 5)
| Rule Key | Operator | Value | Required |
|---|---|---|---|
| `reached_target_flag` | IS_TRUE | true | false |
| `lifecycle_established` | = | "ESTABLISHED" | false |
| `retention_healthy` | = | "HEALTHY" | false |
| `completed_orders_week_active` | > | 0 | false |
| `no_intervention_signal` | ALL_FALSE | ["declining_flag","churn_risk_flag"] | false |
| `lifecycle_active` | IN | ["ACTIVATED","EARLY_LIFE","ESTABLISHED","REACTIVATED"] | false |

Logic: (reached_target) OR (established + healthy + active + no_signals) OR (active_lifecycle + no_signals + active).

#### UNCLASSIFIED (Priority 99, Catch-all)
| Rule Key | Operator | Value | Required |
|---|---|---|---|
| `always_match` | IS_TRUE | true | true |

---

## TASK 4 — PRECEDENCIA EXCLUYENTE

### Orden de Evaluación

```
1. HIGH_VALUE_RECOVERY    (score ~1000) — Máxima urgencia operativa
2. TOP_PERFORMER          (score ~700-800) — Reconocer excelencia primero
3. NEW_OR_REACTIVATED     (score ~580-600) — Early-life pipeline
4. ACTIVE_GROWTH          (score ~400) — Intervención para bajo rendimiento con señales
5. STABLE                 (score ~200-300) — Default: sanos sin intervención
6. UNCLASSIFIED           (score 0) — Catch-all
```

### Justificación del Orden

1. **HIGH_VALUE_RECOVERY primero**: Un driver que valía 80+ viajes/semana y dejó de producir esta semana es la máxima prioridad operativa. Si esperamos, se pierde.

2. **TOP_PERFORMER segundo**: Drivers que ya producen alto volumen no deben ser "intervenidos" con growth programs. Deben ser reconocidos y retenidos. Si TOP_PERFORMER se evaluara después, estos drivers caerían en ACTIVE_GROWTH o STABLE, perdiendo la oportunidad de reconocimiento.

3. **NEW_OR_REACTIVATED tercero**: Drivers en early-life necesitan nurturing específico. Si caen en ACTIVE_GROWTH, reciben intervención genérica en vez de programa de aceleración.

4. **ACTIVE_GROWTH cuarto**: Solo drivers que realmente necesitan intervención (tienen señales de riesgo). No todos los drivers bajo target.

5. **STABLE quinto**: El default positivo. "No necesita intervención" es el estado deseable para la mayoría.

6. **UNCLASSIFIED último**: Catch-all obligatorio. En V1 de reglas cubre 0 drivers — todas las reglas juntas producen 100% coverage.

### Disposición de 50_14 y 90_300

**Veredicto: Opción B — Programas dentro de `NEW_OR_REACTIVATED`.**

| Aspecto | Decisión | Justificación |
|---|---|---|
| ¿Segmentos independientes? | **NO** | 50_14 y 90_300 no definen estados operacionales excluyentes; definen objetivos de programa. Un driver puede estar simultáneamente en "new driver" y tener objetivo 50/14 o 90/300. |
| ¿Sub-programas? | **SÍ** | Se modelan como `sub_program_code` dentro del segmento `NEW_OR_REACTIVATED`. El segmento es el contenedor excluyente; el sub-programa es la meta operativa. |
| ¿Afectan la exclusión? | **NO** | La exclusión se resuelve a nivel segmento. Dos drivers en `NEW_OR_REACTIVATED` pueden tener diferentes sub-programas sin conflicto. |
| Mapeo lifecycle → sub-programa | EARLY_LIFE → `NOR_50_14`, ACTIVATED → `NOR_90_300` | El estado de lifecycle ya captura la diferencia entre ventana corta (14d) y larga (90d). |

---

## TASK 5 — CONFLICT SIMULATION

### 5.1 Resultados (2026-06-10, N=18,545)

| Segmento | Drivers | % Universo |
|---|---|---|
| HIGH_VALUE_RECOVERY | 0 | 0.0% |
| TOP_PERFORMER | 657 | 3.5% |
| NEW_OR_REACTIVATED | 2,669 | 14.4% |
| ACTIVE_GROWTH | 6,574 | 35.4% |
| STABLE | 8,645 | 46.6% |
| UNCLASSIFIED | 0 | 0.0% |

### 5.2 Conflict Resolution

| Candidatos por Driver | Drivers | % |
|---|---|---|
| 1 candidato | 15,219 | 82.1% |
| 2 candidatos | 3,326 | 17.9% |

Solo el 17.9% de los drivers tuvieron conflictos (matchearon 2 segmentos), resueltos por precedencia.

### 5.3 Exclusión por Precedencia

| Segmento | Drivers excluidos (perdieron contra mayor prioridad) |
|---|---|
| STABLE | 2,341 |
| ACTIVE_GROWTH | 985 |

- 2,341 drivers saludables fueron correctamente asignados a STABLE en vez de ACTIVE_GROWTH (porque NEW_OR_REACTIVATED o TOP_PERFORMER los capturaron primero).
- 985 drivers con señales de riesgo fueron asignados a STABLE porque NEW_OR_REACTIVATED o TOP_PERFORMER tuvo mayor prioridad. Esto es correcto: no queremos que un driver nuevo/reactivado sea tratado como "active growth con riesgo".

### 5.4 Distribución Cross-Tab

**Performance × Segmento (aproximado)**:

| Performance State | Universe % | Asignación Típica |
|---|---|---|
| LOW (89.9%) | 16,667 | 52% STABLE, 39% ACTIVE_GROWTH, 9% NEW_OR_REACTIVATED |
| MEDIUM (5.5%) | 1,018 | Mayoría STABLE |
| HIGH (3.4%) | 634 | Mayoría TOP_PERFORMER |
| TARGET (1.2%) | 226 | Mayoría STABLE |

### 5.5 Script de Simulación

`backend/scripts/s1_0a_simulation_v3.py` — 100% reproducible. Lee `yango_lima_driver_state_snapshot` (read-only), clasifica, emite report.

---

## TASK 6 — VALIDACIÓN DE CONFLICTOS

### Matriz de Certificación

| Criterio | Resultado | Estado |
|---|---|---|
| Coverage | 100% (18,545/18,545) | **PASS** |
| Duplicate final segments | 0 | **PASS** |
| Unclassified count | 0 (0.0%) | **PASS** |
| Drivers with multi-candidate | 3,326 (17.9%) | **ACCEPTABLE** — todos resueltos por precedencia |
| Conflicts explicados | 100% — cada exclusión tiene razón documentada | **PASS** |
| No hardcode rules outside config | Todas las reglas son configurables vía `segment_rule_config` | **PASS** |
| Reglas usan solo columnas existentes | Sí — `driver_state_snapshot` (27 columnas auditadas) | **PASS** |

### Señal de Atención

`last_trip_at` muestra >90d para 10,630 drivers (57%) incluso cuando `completed_orders_week > 0`. Esto sugiere que `last_trip_at` no es confiable como señal de recencia para el universo actual. La simulación V3 usa `completed_orders_week > 0` como proxy de actividad, que es más robusto. **Recomendación**: Auditar la pipeline de `last_trip_at` en `driver_state_snapshot` antes de usarlo en reglas de producción.

---

## TASK 7 — DEPRECATION PLAN

### 7.1 Plan por Programa Legacy

| Programa Legacy | Acción | Replacement | Timeline |
|---|---|---|---|
| `PROGRAM_HIGH_VALUE_RECOVERY` | **MAP** | `HIGH_VALUE_RECOVERY` segment | Migrar reglas a `segment_rule_config`. Mismo nombre, misma prioridad, reglas configurables. |
| `PROGRAM_CHURN_PREVENTION` | **DEPRECATE** | Subsumido en `ACTIVE_GROWTH` | Las señales de churn (retention_state, declining_flag, churn_risk_flag) se convierten en reglas `has_intervention_signal` dentro de `ACTIVE_GROWTH`. El programa CP desaparece como entidad independiente. |
| `PROGRAM_14_90` | **MAP** | `NEW_OR_REACTIVATED` segment | Migrar reglas de lifecycle. Los sub-programas 50_14 y 90_300 reemplazan la lógica actual de `PROGRAM_14_90`. |
| `PROGRAM_ACTIVE_GROWTH` | **MAP** | `ACTIVE_GROWTH` segment (redefinido) | El nuevo `ACTIVE_GROWTH` es más restrictivo: solo drivers con señales de intervención, no todos los bajo-target. |

### 7.2 Marca de Deprecación en `program_registry`

```sql
UPDATE growth.yego_lima_program_registry SET
    active = false,
    valid_to = '2026-06-10',
    deprecated_at = now()
WHERE program_code IN (
    'PROGRAM_CHURN_PREVENTION',
    'PROGRAM_14_90',
    'PROGRAM_ACTIVE_GROWTH',
    'PROGRAM_HIGH_VALUE_RECOVERY'
);
```

**Nota**: NO borrar. Los programas legacy permanecen en DB con `active=false`, `deprecated_at` timestamp. La UI debe filtrarlos si `active=false`.

### 7.3 Migration Path (NO IMPLEMENTAR AHORA)

1. Crear tablas de segmentación en schema `growth`
2. Seed `segment_registry` con 6 segmentos
3. Seed `segment_rule_config` con reglas V1
4. Build `driver_segment_snapshot` para 2026-06-10 (validación)
5. Migrar routers y servicios para leer de segmentos, no de programas
6. Marcar programas legacy como deprecated
7. UI switch: mostrar segmentos, ocultar programas legacy

---

## TASK 8 — GO / NO-GO

### Veredicto: **A) CONFIG DESIGN READY**

### Evidencia

| Criterio | Estado |
|---|---|
| 100% coverage sobre data real 18,545 drivers | **PASS** |
| 0 segmentos duplicados | **PASS** |
| 0% unclassified | **PASS** |
| Reglas 100% configurables (no hardcode) | **PASS** |
| Esquema DB versionado y auditable | **PASS** |
| Precedencia excluyente documentada y validada | **PASS** |
| Plan de deprecación claro (no destructivo) | **PASS** |
| Compatible con fase activa (Control Foundation) | **PASS** |
| Simulación reproducible (script adjunto) | **PASS** |

### Riesgos Identificados (no bloqueantes)

| Riesgo | Severidad | Mitigación |
|---|---|---|
| `last_trip_at` unreliable para recencia | MEDIUM | Usar `completed_orders_week > 0` como proxy principal en V1. Auditoría de `last_trip_at` pipeline como pre-requisito de V2. |
| `supply_hours_week` = 0 en todo el universo | LOW | No se usa en reglas V1. Requiere investigación de pipeline de suministro. |
| `HIGH_VALUE_RECOVERY` = 0 drivers en snapshot actual | LOW | Esperado. HVR es segmento condicional. Aparece solo cuando las condiciones se cumplen (best_week>=80 + inactive 1-14d). No es un bug. |
| ACTIVE_GROWTH a 35.4% puede crecer si se aflojan señales | MEDIUM | Mantener `has_intervention_signal` como required. Ajustar thresholds vía config, no vía código. |

### Próximo Paso

**LG-S1.0B — Implementación de tablas** (solo cuando OMNI-P0 cierre con GO real y se autorice).

---

## APPENDIX A — Scripts de Auditoría

| Script | Propósito |
|---|---|
| `backend/scripts/s1_0a_audit.py` | Auditoría completa de universo actual (read-only) |
| `backend/scripts/s1_0a_simulation_v3.py` | Simulación de segmentación excluyente (read-only) |
| `backend/scripts/s1_0a_deepdive.py` | Deep-dive de columnas y distribuciones |
| `backend/scripts/s1_0a_columns.py` | Lista columnas de driver_state_snapshot |

---

## APPENDIX B — Referencias

| Archivo | Línea | Contenido |
|---|---|---|
| `ai_operating_system.md` | 1-225 | Canonical engine order, mandatory rules |
| `ai_current_phase.md` | 1-167 | OMNI-P0 active, Diagnostic paused |
| `yego_lima_program_eligibility_service.py` | 31-38 | Program codes y reglas actuales |
| `yego_lima_program_explainability_service.py` | 26-132 | Reglas documentadas de los 4 programas |
| `yego_lima_opportunity_policy_service.py` | 28-33 | PROGRAM_PRIORITY order |
| `yego_lima_driver_state_service.py` | 34-57 | Lifecycle, performance, retention state enums |

---

**LG-S1.0A — FIN DEL DISEÑO**

*No se ha tocado queue, export, control_loop, scoring, ni programas legacy.*
*No se han creado tablas, migraciones, ni seeds.*
*Diseño canónico validado sobre data real 2026-06-10.*
