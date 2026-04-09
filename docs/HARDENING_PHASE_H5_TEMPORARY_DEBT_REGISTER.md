# H5 — Registro de deuda temporal / clasificación

**Fecha:** 2026-04-08

## Leyenda

- **A** — Definitivo y correcto  
- **B** — Temporal aceptable (documentado, reversión clara)  
- **C** — Deuda a resolver antes de producción fuerte  
- **D** — Legacy descartable / solo compatibilidad  

## Registro

| Archivo | Lógica | Clase | Por qué existe | Cuándo remover | Severidad |
|---------|--------|-------|----------------|----------------|-----------|
| `app/db/real_data_coverage_sql.py` | `coverage_from_clause()` + subconsulta si vista ausente | **B** | Despliegues sin vista creada | Tras `alembic upgrade` a **129** en todas las BDs | Media |
| `app/db/schema_verify.py` | Inspección `bi.real_monthly_agg` legacy | **D** | Compatibilidad / auditoría | Cuando se retire del todo el BI legacy | Baja |
| `129_ensure_v_real_data_coverage.py` | `CREATE OR REPLACE VIEW` desde `real_rollup_day_fact` | **A** | Garantizar contrato | N/A (definitivo) | — |
| Infra: espacio disco PostgreSQL | (no código) | **C** | Volumen/tablespace | Liberar espacio en servidor DB | Alta |
| `business_slice` coverage queries | Full scan posible en `trips_unified` | **C** | Volumen datos | Índices/particionado evaluados por DBA con EXPLAIN | Alta bajo carga |

## Evaluación explícita del fallback inline

- **Mantener** solo como rama centralizada en `real_data_coverage_sql` (no re-esparcir SQL duplicado en servicios).  
- **Eliminar dependencia del fallback** cuando `to_regclass('ops.v_real_data_coverage')` sea siempre no nulo en todos los entornos (CI + staging + prod).
