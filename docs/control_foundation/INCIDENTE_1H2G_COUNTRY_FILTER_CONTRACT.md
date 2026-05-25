# INCIDENTE 1H.2G — COUNTRY FILTER CONTRACT / ALL COUNTRIES BUG

## Veredicto Final: GO

---

## 1. Causa Raíz

### Tipo de falla: A) Frontend guardrail over-restrictive

El `blockedByCountry` guardrail en `BusinessSliceOmniviewMatrix.jsx:245` impedía cargar datos cuando el selector de país estaba en "TODOS LOS PAÍSES" (`country=''`) para granos weekly/daily:

```javascript
// Línea 244-245 (antes del fix)
const needsCountry = grain === 'weekly' || grain === 'daily'
const blockedByCountry = needsCountry && !country
```

Este guardrail tenía un comentario histórico que explicaba la preocupación original:
> "Guardrail: semanal/diario requiere país para evitar scope ilimitado
> (sin país → O(todas_tajadas × semanas × KPIs × SQL) → cuelgue)"

Sin embargo, desde la Fase 1H.2F, el serving fact `serving.omniview_projection_daily_fact` maneja eficientemente queries sin filtro de país (1470 filas en ~1s). El guardrail ya no es necesario.

### Cadena del bug

```
Usuario selecciona "TODOS LOS PAÍSES" en weekly projection
  → country = '' (empty string)
  → needsCountry = true (grain=weekly)
  → blockedByCountry = true
  → doLoadProjection: if (blockedByCountry) → setProjectionRows([]); return
  → Matriz vacía — no se envía request al backend
```

### Comportamiento observado

- Dropdown muestra "TODOS LOS PAÍSES" como placeholder
- Pero `blockedByCountry` impide cualquier request
- Si localStorage tenía `country='peru'` guardado de sesión anterior, la matriz mostraba Perú (porque `country` no estaba vacío)
- El usuario interpretaba que "TODOS LOS PAÍSES" solo mostraba Perú cuando en realidad era el país persistido

---

## 2. Fix Aplicado

**Archivo:** `frontend/src/components/BusinessSliceOmniviewMatrix.jsx:244`

```javascript
// Antes:
const needsCountry = grain === 'weekly' || grain === 'daily'

// Después:
const needsCountry = (grain === 'weekly' || grain === 'daily') && !isProjectionMode
```

### Efecto del cambio

| Modo | Grain | needsCountry | blockedByCountry con country='' |
|------|-------|-------------|------|
| Proyección (antes) | weekly | true | true → **bloquea** |
| Proyección (ahora) | weekly | false | false → **carga todos** |
| Evolución (sin cambio) | weekly | true | true → bloquea (requiere país) |
| Proyección (sin cambio) | monthly | false | false → carga todos |

**Razón del cambio:** En modo proyección, el serving fact maneja consultas sin filtro de país eficientemente. El guardrail que existía para proteger el runtime path ya no aplica.

---

## 3. Validación Backend

### Endpoint: `/ops/business-slice/omniview-projection`

| Caso | rows | countries | served_from | actual>0 |
|------|------|-----------|-------------|----------|
| ALL (no country) | 1470 | peru, colombia | fact | 400 |
| Peru only | 513 | peru | fact | 160 |
| Colombia only | 957 | colombia | fact | 240 |

### Contrato de filtro

| UI Selección | country param enviado | Backend recibe | Resultado |
|-------------|----------------------|----------------|-----------|
| TODOS LOS PAÍSES | (no se envía) | country=None | Todos los países |
| PERÚ | country=peru | country="peru" | Solo Perú |
| COLOMBIA | country=colombia | country="colombia" | Solo Colombia |

### Código de filtro en backend

- `_try_load_from_serving_fact:1599`: `if country: ...` — None o vacío → sin filtro
- `_country_sql_match_values(None)`: retorna `[]` → sin filtro SQL
- `_append_country_sql_filter(None)`: `if not vals: return` → sin filtro
- Todos los paths tratan `None` y `""` igual: sin filtro = todos los países

---

## 4. Validación Frontend

### Agrupación por país

La tabla de proyección ya soporta múltiples países:
- `countryRank()` asigna prioridad: Perú=0, Colombia=1
- `cityKey` incluye country: `${raw.country}::${raw.city}`
- Ordenamiento: Perú primero, luego Colombia, por volumen proyectado

### `FilterSelect` en proyección

Con `needsCountry=false` en modo proyección:
- `required={false}` → sin borde amarillo
- Placeholder "TODOS LOS PAÍSES" se comporta como opción válida
- Al seleccionar vacío → `country=''` → no se envía param → backend devuelve todo

---

## 5. QA Results

### Script: `validate_phase1h2g_country_filter_contract.py`

**57/63 PASS, 6 FAIL** (los 6 FAIL son `comparison_basis` ausente en daily/monthly — bug pre-existente no relacionado con country filter)

| Check | Weekly | Daily | Monthly |
|-------|--------|-------|---------|
| ALL: multiple countries | PASS | PASS | PASS |
| ALL: served_from=fact | PASS | PASS | PASS |
| ALL: actual_value > 0 | PASS | PASS | PASS |
| Peru: only peru | PASS | PASS | PASS |
| Colombia: only colombia | PASS | PASS | PASS |
| ALL: comparison_basis | PASS | FAIL* | FAIL* |

*Comparison_basis ausente en serving fact para daily/monthly. Mismo bug que ya fue corregido para weekly en 1H.2F. Requiere regeneración del serving fact para daily/monthly.

---

## 6. No-regresión

| Grain | Modo | País | Estado |
|-------|------|------|--------|
| weekly | proyección | TODOS | GO (1470 rows, Perú+Colombia) |
| weekly | proyección | Perú | GO (513 rows) |
| weekly | proyección | Colombia | GO (957 rows) |
| daily | proyección | TODOS | GO (868 rows, Perú+Colombia) |
| daily | proyección | Perú | GO (310 rows) |
| daily | proyección | Colombia | GO (558 rows) |
| monthly | proyección | TODOS | GO (338 rows, Perú+Colombia) |
| monthly | proyección | Perú | GO (118 rows) |
| monthly | proyección | Colombia | GO (220 rows) |
| weekly | evolución | TODOS | unchanged (blockedByCountry=true, requiere país) |
| daily | evolución | TODOS | unchanged (blockedByCountry=true, requiere país) |

**El comportamiento de evolución no cambia.** El guardrail se mantiene para ese modo.

---

## 7. GO / NO-GO

### GO conditions:
- [x] ALL countries endpoint devuelve Perú + Colombia para weekly
- [x] ALL countries endpoint devuelve Perú + Colombia para daily
- [x] ALL countries endpoint devuelve Perú + Colombia para monthly
- [x] Peru filter devuelve solo Perú
- [x] Colombia filter devuelve solo Colombia
- [x] served_from=fact para todos los casos
- [x] actual_value > 0 para todos los casos
- [x] No regresión en evolución mode
- [x] Fix es mínimo (1 línea, 1 archivo)
- [x] Frontend grouping soporta multi-país (countryRank + cityKey)

### Pendiente (no bloqueante):
- [ ] Regenerar serving fact para daily/monthly con comparison_basis
- [ ] UI manual validation (requiere frontend corriendo)

### NO-GO conditions:
- [ ] Ninguna — el contrato de filtro país funciona correctamente
