# FASE 2.6 — Hard Enforcement Scan

## 1. Qué enforcement ya existe

| Mecanismo | Estado |
|-----------|--------|
| `ServingPolicy` dataclass | Declarada en 5 servicios; no conectada a ejecución de queries |
| `FORBIDDEN_SERVING_SOURCES` (5 fuentes) | Definido; solo validado si alguien llama `assert_serving_source` manualmente |
| `assert_serving_source` | Existe; llamado solo en 1 path (fallback de `_fetch_resolved_period_totals`) |
| `trace_source_usage` | Llamado en 2 servicios (omniview, control_loop); importado pero no usado en 3 servicios |
| `SERVING_REGISTRY` (18 features) | Pasivo: diagnostica pero no actúa como gate |
| `assert_feature_registered` | Existe; nadie lo llama en serving normal |
| `register_policy` | No existe |
| `execute_serving_query` wrapper | No existe |
| Script `check_serving_enforcement.py` | Existe; valida estáticamente |

## 2. Qué paths de query siguen pudiendo saltarse guardrails

| Servicio | Query path | Source | Guardrail aplicado |
|----------|-----------|--------|-------------------|
| `real_lob_service.get_real_lob_monthly` | `cur.execute` directo | `MV_MONTHLY` | Ninguno |
| `real_lob_service.get_real_lob_weekly` | `cur.execute` directo | `MV_WEEKLY` | Ninguno |
| `real_lob_service_v2.get_real_lob_monthly_v2` | `cur.execute` directo | `MV_MONTHLY_V2` | Ninguno |
| `real_lob_service_v2.get_real_lob_weekly_v2` | `cur.execute` directo | `MV_WEEKLY_V2` | Ninguno |
| `real_lob_v2_data_service.get_real_lob_v2_data` | `cur.execute` directo | `MV_MONTHLY`/`MV_WEEKLY` | Ninguno |
| `omniview._fetch_fact_slice_rows` | `cur.execute` directo | fact table | Ninguno (trace en orquestador) |
| `omniview._fetch_fact_rollup_by_country` | `cur.execute` directo | fact table | Ninguno |
| `omniview._fetch_monthly_fact_rows` | `cur.execute` directo | `FACT_MONTHLY` | Ninguno |

## 3. Features con policy declarada pero sin gate real

- Real LOB monthly (`_SERVING_POLICY` declarada, `trace_source_usage` importado pero nunca llamado)
- Real LOB monthly v2 (idem)
- Real LOB v2 data (idem)

## 4. Punto de interceptación recomendado

Crear `execute_serving_query()` en `serving_guardrails.py` que:
- Exija registry entry + policy
- Valide forbidden sources
- Ejecute el SQL
- Trace el uso
- Devuelva `list[dict]`

Aplicarlo en los `cur.execute` principales de los 5 servicios críticos.

## 5. Partes que NO se tocarán

- Endpoints públicos (contratos intactos)
- Frontend
- Build/rebuild/backfill paths
- Drill/audit paths
- Supply, driver lifecycle, territory services
- connection.py (context managers intactos)
