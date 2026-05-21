# AUTOCOBRO ELIGIBILITY POLICY — V1 PREVIEW

**Policy Version:** `autocobro_v1_preview`  
**Status:** Preview-only. NO ejecuta acciones reales.  
**Created:** FASE 1F-8 — Autocobro Eligibility Readiness  
**Rationale:** Determinar qué conductores son elegibles para autocobro usando exclusivamente señales antifraude determinísticas. Esta política NO prende ni apaga autocobro real.

---

## 1. PROPÓSITO

Definir una política determinística, trazable y auditable que clasifique a cada conductor en uno de 4 estados de elegibilidad para autocobro:

| Estado | Significado |
|--------|-------------|
| `eligible` | Conductor apto para autocobro por señales antifraude |
| `review_required` | Requiere revisión manual antes de decidir |
| `restricted` | NO elegible para autocobro (señales de riesgo) |
| `unknown` | Datos insuficientes para clasificar |

---

## 2. FUENTES DE DATOS

Todas las señales provienen exclusivamente de tablas del esquema `fraud`:

| Fuente | Tabla | Señales usadas |
|--------|-------|---------------|
| Trust snapshot | `fraud.driver_trust_snapshot` | `trust_tier`, `total_completed_trips`, `first_completed_trip_at` |
| Risk snapshot | `fraud.driver_risk_snapshot` | `behavioral_profile_class`, `behavioral_confidence_score`, `recommended_action`, `risk_score`, `severity` |
| Open cases | `fraud.risk_cases` | `status`, `severity`, `recommended_action`, `case_confidence_score` |
| Identity clusters | `fraud.payment_identity_source` | `is_synthetic`, `bank_cluster_flags` |
| Trip features | `fraud.trip_risk_features` | `short_trip_farming_flag`, `card_amount_flags` |

**NO se usan APIs externas. NO se usa data bancaria sintética. NO se usa IA.**

---

## 3. REGLAS DE CLASIFICACIÓN

### 3.1 ELIGIBLE

Un conductor es `eligible` si cumple **TODAS** las siguientes condiciones:

| # | Condición | Fuente |
|---|-----------|--------|
| E1 | `trust_tier = 'trusted'` | `driver_trust_snapshot` |
| E2 | `total_completed_trips >= 50` | `driver_trust_snapshot` |
| E3 | `behavioral_profile_class IN ('normal', 'watchlist')` | `driver_risk_snapshot` |
| E4 | No `open` high/critical cases | `risk_cases` |
| E5 | `case_confidence_score` máximo < 60 O no tiene casos | `risk_cases` |
| E6 | No `identity_flags` que indiquen identidad sintética | `payment_identity_source` |
| E7 | No `short_trip_farming` candidate reciente (D-30) | `trip_risk_features` |
| E8 | No `high_card_amount_new_driver` flag | `trip_risk_features` |
| E9 | `recommended_action` NOT IN `restrict_driver_review`, `disable_autocobro`, `hold_bonus_review` | `driver_risk_snapshot` |

### 3.2 REVIEW_REQUIRED

Un conductor es `review_required` si cumple **AL MENOS UNA** de:

| # | Condición | Fuente |
|---|-----------|--------|
| R1 | `trust_tier = 'new_or_unproven'` pero `total_completed_trips >= 30` | `driver_trust_snapshot` |
| R2 | `behavioral_profile_class = 'suspicious'` | `driver_risk_snapshot` |
| R3 | Tiene casos `open` con severidad `medium` y `case_confidence_score` entre 30-59 | `risk_cases` |
| R4 | Es `fraud_candidate` (tiene candidate flags) pero sin casos `high/critical` abiertos | `driver_risk_snapshot` |
| R5 | `behavioral_profile_class IS NULL` pero `total_completed_trips >= 50` y `trust_tier = 'trusted'` | `driver_risk_snapshot` + `driver_trust_snapshot` |

### 3.3 RESTRICTED

Un conductor es `restricted` si cumple **AL MENOS UNA** de:

| # | Condición | Fuente |
|---|-----------|--------|
| X1 | `behavioral_profile_class IN ('high_risk', 'critical_pattern')` | `driver_risk_snapshot` |
| X2 | Tiene al menos un caso `open` con severidad `high` o `critical` | `risk_cases` |
| X3 | `recommended_action IN ('restrict_driver_review', 'disable_autocobro', 'hold_bonus_review')` | `driver_risk_snapshot` |
| X4 | `case_confidence_score >= 60` en cualquier caso `open` | `risk_cases` |
| X5 | `short_trip_farming` confirmed (D-30, > 3 viajes cortos/día) | `trip_risk_features` |
| X6 | `high_card_amount_new_driver` confirmed | `trip_risk_features` |
| X7 | `trust_tier = 'restricted'` | `driver_trust_snapshot` |

### 3.4 UNKNOWN

Un conductor es `unknown` si:

| # | Condición |
|---|-----------|
| U1 | `trust_tier IS NULL` (no existe en `driver_trust_snapshot`) |
| U2 | `trust_tier = 'unknown'` |
| U3 | `total_completed_trips < 3` (datos insuficientes para perfil conductual) |
| U4 | Error de datos (driver_id inválido, datos corruptos) |

---

## 4. REGLAS DE PRIORIDAD

El orden de evaluación es:

1. **UNKNOWN** — se evalúa primero (datos insuficientes)
2. **RESTRICTED** — se evalúa segundo (señales de bloqueo)
3. **REVIEW_REQUIRED** — se evalúa tercero (señales ambiguas)
4. **ELIGIBLE** — caso por defecto si pasa todos los filtros

Un conductor solo puede tener UN estado final.

---

## 5. TRAZABILIDAD

Cada clasificación genera un `eligibility_reason` (JSONB) con:

```json
{
  "status": "eligible",
  "matched_rules": ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9"],
  "signals": {
    "trust_tier": "trusted",
    "total_completed_trips": 245,
    "behavioral_profile_class": "normal",
    "behavioral_confidence_score": 15.2,
    "open_high_cases": 0,
    "max_case_confidence": null,
    "recommended_action": "monitor",
    "synthetic_identity": false,
    "short_trip_farming": false,
    "high_card_new_driver": false
  },
  "computed_at": "2026-05-21T12:00:00Z",
  "policy_version": "autocobro_v1_preview"
}
```

---

## 6. LO QUE ESTA POLÍTICA NO HACE

- NO prende ni apaga autocobro real
- NO modifica `driver_trust_snapshot` ni `driver_risk_snapshot`
- NO llama APIs externas
- NO usa data bancaria sintética
- NO usa IA/ML para decidir
- NO bloquea pagos
- NO desconecta drivers
- NO toca Omniview ni Plan vs Real

---

## 7. VERSIONAMIENTO

Cada cambio de política se versiona:

| Version | Cambio | Fecha |
|---------|--------|-------|
| `autocobro_v1_preview` | Versión inicial — preview | 2026-05-21 |

La tabla `fraud.autocobro_eligibility_policy` almacena el histórico de versiones.

---

## 8. INTERPRETACIÓN DE RESULTADOS

- **eligible:** El conductor pasa todos los filtros antifraude. El sistema de autocobro PUEDE considerarlo apto (decisión externa).
- **review_required:** Hay señales ambiguas. Se recomienda revisión manual antes de habilitar autocobro.
- **restricted:** El conductor tiene señales de riesgo que desaconsejan el autocobro. NO habilitar sin resolver los casos abiertos.
- **unknown:** No hay datos suficientes. Recolectar más historial de viajes antes de evaluar.
