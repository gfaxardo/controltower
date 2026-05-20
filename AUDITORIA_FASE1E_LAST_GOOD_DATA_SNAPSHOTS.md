# Fase 1E — Last Good Data / Snapshots / Serving Stability

**Fecha**: 2026-05-19
**Estado**: **GO** — Snapshots operativos, serving views funcionando

---

## 1. Problema resuelto

Antes de Fase 1E, si un refresh fallaba, quedaba parcial o se bloqueaba, los facts podían quedar incompletos y la UI podía mostrar datos rotos sin advertencia. No existía copia estable de periodos cerrados.

Ahora:
- Periodos locked tienen **snapshot** estable e inmutable
- La serving view decide automáticamente: locked → snapshot, open → working fact
- Si un refresh falla, el snapshot activo no se modifica
- El usuario puede saber qué fuente está viendo (`serving_source`, `data_status`)

---

## 2. Objetos creados

| Objeto | Tipo | Schema |
|--------|------|--------|
| `ops.real_business_slice_month_snapshot` | Tabla | ops |
| `ops.v_real_business_slice_month_serving` | Vista | ops |
| `last_good_data_service.py` | Service | app/services |
| `GET /ops/serving/status` | Endpoint | ops_refresh |
| `GET /ops/serving/snapshots` | Endpoint | ops_refresh |

---

## 3. Arquitectura

```
working_fact (refresh update)
    │
    ├──> create_snapshot_for_period() → snapshot table (immutable)
    │
    └──> v_real_business_slice_month_serving
           │
           ├── periodo locked + snapshot active → sirve snapshot
           └── periodo open / sin snapshot → sirve working_fact
```

---

## 4. Política de serving

| Periodo Status | Snapshot | Serving Source | Data Status |
|---------------|:---:|----------------|-------------|
| open | N/A | working_fact | open |
| locked | active | snapshot | locked_snapshot |
| locked | missing | working_fact | locked_no_snapshot |

---

## 5. Abril 2026 — snapshot creado

| Métrica | Valor |
|---------|-------|
| Snapshot version | 1 |
| Rows | 23 |
| Checksum | `1123bf21a454446c` |
| Serving source | snapshot |
| Data status | locked_snapshot |
| Fact total | 829,118 |
| Snapshot total | 829,118 |
| Match | ✓ |

---

## 6. Mayo 2026 — working fact

| Métrica | Valor |
|---------|-------|
| Serving source | working_fact |
| Data status | open |
| Total | 472,468 |

---

## 7. Endpoints

```bash
# Estado de serving
curl http://localhost:8000/ops/serving/status?grain=monthly&period=2026-04
# → serving_source: snapshot, data_status: locked_snapshot

# Snapshots disponibles
curl http://localhost:8000/ops/serving/snapshots?grain=monthly&period=2026-04
# → version: 1, checksum: 1123bf..., row_count: 23
```

---

## 8. Bogotá + Barranquilla (sin cambios)

| Ciudad | Slice | Trips |
|--------|-------|-------|
| Bogotá | Carga | 2,801 |
| Bogotá | Delivery moto | 188 |
| Barranquilla | Taxi Moto | 12,483 |
| Barranquilla | Auto regular | 9,764 |
| Barranquilla | Delivery moto | 1,406 |

---

## 9. Riesgos pendientes

| Riesgo | Estado |
|--------|--------|
| CT_PERIOD_CLOSURE_DRY_RUN=true en producción | Activar false |
| Snapshots para day/week facts | Fase 1F |
| Integrar Omniview a serving views | Fase 1F |
| Refresh scoped por ciudad | Fase 1F |
| Resolved view >120s | Índices nocturnos |

---

## 10. Siguiente fase

**Fase 1F — Omniview Serving Integration + Performance Hardening**
- Migrar Omniview a `v_real_business_slice_month_serving`
- Snapshots para day/week
- Activar `CT_PERIOD_CLOSURE_DRY_RUN=false`
- Índices nocturnos para resolved view
