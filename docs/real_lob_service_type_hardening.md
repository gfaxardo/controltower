# Hardening Real LOB – service_type (Versión final)

**Proyecto:** Yego Control Tower  
**Fecha:** 2026-03-09

---

## 1. Problema detectado

- UNCLASSIFIED absorbía **66% de service_type** y **74% de LOB**.
- Causa: `validated_service_type()` aplicaba regex `^[a-z0-9_\-]+$` ANTES de quitar tildes → `Económico` (77% de viajes PE) fallaba el regex.
- Duplicados: `tuk-tuk` / `tuk_tuk` / `tuk tuk` coexistían como categorías distintas.
- `confort+` → UNCLASSIFIED porque `+` no pasaba el regex.
- `mensajería`, `Exprés`, `Envíos` → UNCLASSIFIED por tildes.

## 2. Causa raíz

La función `validated_service_type()` validaba el raw SIN normalizar primero. Los valores reales del upstream tienen tildes (`Económico`), signos (`confort+`), mayúsculas, espacios y guiones que el regex rechazaba.

## 3. Regla final de normalización canónica

**Función SQL:** `ops.normalized_service_type(raw_value)`

```
unaccent(raw_value) → LOWER → TRIM → '+' → '_plus' → espacios/guiones → '_' → solo [a-z0-9_]
```

Ejemplos:
- `Económico` → `economico`
- `confort+` → `confort_plus`
- `tuk-tuk` → `tuk_tuk`
- `mensajería` → `mensajeria`
- `Exprés` → `expres`
- `Envíos` → `envios`

## 4. Regla final de validación

**Función SQL:** `ops.validated_service_type(raw_value)`

UNCLASSIFIED solo si:
- NULL o vacío
- Contiene coma `,`
- Longitud > 30 caracteres
- Más de 3 palabras (frases descriptivas)

Todo lo demás → `normalized_service_type(raw_value)`.

**No se usa catálogo cerrado.** Cualquier tipo de servicio razonable del upstream se acepta.

## 5. Criterios UNCLASSIFIED / LOW_VOLUME / LOW SAMPLE

| Criterio | Regla | Dónde se aplica |
|---|---|---|
| UNCLASSIFIED | coma, >30 chars, >3 palabras, vacío | Función SQL + backfill |
| LOW_VOLUME | viajes < 20 por categoría | API drill (agrupación en respuesta) |
| LOW SAMPLE | viajes < 30: pct_b2b = null | API drill (KPIs) |

## 6. Resultados ANTES / DESPUÉS

### UNCLASSIFIED share en service_type

| Momento | UNCLASSIFIED trips | Total trips | % |
|---|---|---|---|
| Antes (071) | 17,060,163 | 25,819,333 | **66.08%** |
| Después (072) | 158 | 22,997,704 | **0.00%** |

### UNCLASSIFIED share en LOB

| Momento | UNCLASSIFIED trips | Total trips | % |
|---|---|---|---|
| Antes (071) | 17,060,163 | 22,975,209 | **74.25%** |
| Después (072) | 292,442 | 23,014,025 | **1.27%** |

### Duplicados eliminados

| Antes | Después |
|---|---|
| tuk-tuk (326k) + tuk_tuk (326k) | tuk_tuk (326k) |
| mensajería (48k) + mensajeria (250k) | mensajeria (250k) |
| envíos (4k) + envios (39k) | envios (39k) |
| focos led para auto, moto (2) | eliminado (UNCLASSIFIED) |

### Top service_type final

| dimension_key | trips |
|---|---|
| economico | 16,487,504 |
| moto | 3,292,324 |
| confort | 1,249,132 |
| standard | 766,448 |
| tuk_tuk | 326,189 |
| mensajeria | 249,926 |
| confort_plus | 235,440 |
| minivan | 113,529 |
| start | 91,096 |
| cargo | 84,668 |
| expres | 48,340 |
| envios | 38,794 |
| premier | 14,142 |
| UNCLASSIFIED | 158 |

## 7. Migraciones aplicadas

- **070:** Funciones + vistas auditoría (base).
- **071:** Relajación regex (insuficiente: no resolvía tildes).
- **072:** Normalización canónica con `unaccent` + mapping LOB expandido.

## 8. Backfill ejecutado

```bash
python -m scripts.cleanup_old_service_type  # limpiar filas service_type viejas
python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2026-04-01 --resume false
```

16 meses OK, 0 fallidos, ~2.5 horas.

## 9. Riesgos residuales

- **LOB UNCLASSIFIED (1.27%):** Tipos como `el_progreso` o IDs numéricos (6 categorías con 2 trips cada una) no tienen mapping LOB. Son irrelevantes en volumen.
- **Mapping LOB para `mensajeria`:** La tabla `canon.map_real_tipo_servicio_to_lob_group` tiene una fila con key `mensajería` (con tilde) que ya no matchea porque el backfill ahora guarda `mensajeria` (sin tilde). Se debe agregar la key `mensajeria` → `delivery`.

**Trazabilidad brecha service_type → LOB:** véase [real_lob_lob_gap_diagnosis.md](real_lob_lob_gap_diagnosis.md) (diagnóstico exacto, clasificación residual, backfill para re-sincronizar LOB).

## Pipeline y variantes

- **Raw:** `tipo_servicio` en `ops.v_trips_real_canon`. **Normalizado:** `ops.normalized_service_type` / `ops.validated_service_type`. **LOB:** `canon.map_real_tipo_servicio_to_lob_group`. **Drill:** breakdown=service_type usa **tipo_servicio_norm** (mismo que el mapping).
- Variantes con acento: **envíos** → delivery (además de `envios`). Cualquier otra variante con tilde en LOB UNCLASSIFIED debe añadirse al mapping.
- **ops.real_lob_residual_diagnostic:** agregado últimos 90 días; rellenar con `python scripts/populate_real_lob_residual_diagnostic.py`. No perseguir 0 % UNCLASSIFIED; el residual basura se deja en UNCLASSIFIED.
