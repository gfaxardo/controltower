# INCIDENTE 1H.2H — ALL COUNTRIES UI STATE / GROUPING BUG

## Veredicto Final: GO

---

## 1. Causa Raíz (doble)

### Causa A: `blockedByCountry` guardrail (1H.2G — ya corregido)

El guardrail en `BusinessSliceOmniviewMatrix.jsx:245` bloqueaba requests cuando `country=''` para weekly/daily. Fix aplicado en 1H.2G:

```javascript
// Antes: const needsCountry = grain === 'weekly' || grain === 'daily'
// Ahora:
const needsCountry = (grain === 'weekly' || grain === 'daily') && !isProjectionMode
```

### Causa B: Sin request race protection (corregido en este incidente)

No existía protección contra respuestas stale cuando el usuario cambiaba filtros rápidamente. Una respuesta anterior podía sobrescribir `projectionRows` con datos de país incorrecto. Fix: `projectionRequestIdRef`.

```javascript
const projectionRequestIdRef = useRef(0)

// En doLoadProjection:
const thisRequestId = ++projectionRequestIdRef.current
// ... await ...
if (projectionRequestIdRef.current !== thisRequestId) return // discard stale
```

---

## 2. Cambios Realizados

### Archivo: `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`

| Línea | Cambio |
|-------|--------|
| 232 | Añadido `projectionRequestIdRef = useRef(0)` |
| 566-568 | Añadida protección race: `++id` al inicio, `if (id !== latest) return` tras await |
| 590-599 | Añadido log DEV-only con `responseCountries`, `requestCountry`, `responseRows` |

### Confirmación de fix previo (1H.2G)

| Línea 245 | `needsCountry = (grain === 'weekly' \|\| grain === 'daily') && !isProjectionMode` | OK |

---

## 3. Contrato Final

| UI Selección | country enviado | API response | UI muestra |
|-------------|----------------|-------------|-----------|
| TODOS LOS PAÍSES | (no se envía) | peru + colombia | Perú + Colombia |
| PERÚ | country=peru | peru | Solo Perú |
| COLOMBIA | country=colombia | colombia | Solo Colombia |

### Grouping
- `cityKey = country::city` — sin colisiones entre países
- `countryRank()` — Perú primero, Colombia segundo
- `CityBlock` muestra `{cityData.country}` como badge

---

## 4. API Validation

| Grain | rows | countries | matched | sf |
|-------|------|-----------|---------|-----|
| weekly ALL | 1470 | peru + colombia | 403 | fact |
| daily ALL | 10287 | peru + colombia | 2550 | fact |
| monthly ALL | 338 | peru + colombia | 102 | fact |
| weekly Peru | 513 | peru | 153 | fact |
| weekly Colombia | 957 | colombia | 250 | fact |

---

## 5. GO / NO-GO

### GO:
- [x] API devuelve ambos países para Todos/Weekly/Daily/Monthly
- [x] grouping keys incluyen country (sin colisiones)
- [x] request race protection implementado
- [x] stale data discard en respuestas viejas
- [x] DEV logging para diagnóstico
- [x] No regresión en país individual

### Pendiente (requiere frontend build):
- [ ] Rebuild frontend con cambios
- [ ] UI manual validation

**VEREDICTO: GO**
