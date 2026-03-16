# Memo y checklist: coherencia estructural REAL

## Resumen de cambios

1. **Error 500 en drill por park:** Corregido en `get_drill_children`: las dos queries que usan `cancelled_trips` están envueltas en try/except; si fallan por columna inexistente se hace `conn.rollback()` y se re-ejecutan sin `cancelled_trips`, rellenando `cancelaciones = 0`.
2. **Etiqueta canónica de park:** Definida como `{park_name} — {city} — {country}`. Aplicada en:
   - `get_drill_parks`: cada ítem incluye `park_label`.
   - `get_drill_children` (desglose=PARK): cada fila incluye `park_label` y `country`.
   - `get_real_lob_filters`: cada park incluye `park_label`.
   - Frontend: dropdown de Park y subfilas del drill usan `park_label` (o construyen nombre — ciudad — país si no viene).
3. **Dimensión canónica:** Documentado que la fuente oficial para drill es `real_drill_dim_fact`; el dropdown del drill usa solo GET /ops/real-lob/drill/parks (mismo universo que el drill).
4. **Reconciliación y auditoría:** Script `audit_real_coherence.py` para discrepancias LOB vs park vs service_type, parks solo en drill vs solo en MVs, y etiquetas duplicadas.

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| docs/REAL_COHERENCE_FASE0_SCAN.md | Scan FASE 0 + FASE 3–4 documentadas |
| docs/REAL_COHERENCE_MEMO_AND_CHECKLIST.md | Este memo y checklist |
| backend/app/services/real_lob_drill_pro_service.py | Fallback cancelled_trips en get_drill_children; park_label en get_drill_parks y en filas PARK de children |
| backend/app/services/real_lob_filters_service.py | park_label en lista de parks |
| frontend/src/components/RealLOBDrillView.jsx | Dropdown y subfilas usan park_label (nombre — ciudad — país) |
| backend/scripts/audit_real_coherence.py | Reconciliación y coherencia parks/drill/MVs |
| backend/tests/test_real_coherence.py | Tests get_drill_parks y get_drill_children PARK |

---

## Checklist de validación manual

### 1. Drill por park sin 500
- [ ] Abrir pestaña Real → Drill (semanal/mensual).
- [ ] Desglose = **Park** (sin filtrar por un park concreto).
- [ ] Cargar datos; no debe aparecer error 500.
- [ ] Expandir una fila (clic en una fila de país/periodo); debe cargar el desglose por park sin 500.
- [ ] Probar con **un park concreto** seleccionado en el dropdown y desglose Park o Tipo de servicio; no debe dar 500.

### 2. Etiqueta completa en dropdown y subfilas
- [ ] En el dropdown **Park**, cada opción debe verse como `Nombre — Ciudad — País` (no solo nombre ni solo id).
- [ ] Al expandir una fila con desglose **Park**, cada subfila debe mostrar la misma etiqueta (nombre — ciudad — país).

### 3. Semanal vs mensual
- [ ] Mismo país: cambiar entre **Mensual** y **Semanal** y comprobar que los totales por periodo son coherentes (misma base de datos, distinto grain).

### 4. Reconciliación por desglose
- [ ] Para un mismo periodo y país, anotar total de viajes con desglose **LOB**.
- [ ] Mismo periodo/país con desglose **Park**: la suma de viajes de las subfilas debe coincidir con el total de la fila (y con el total por LOB).
- [ ] Idem con desglose **Tipo de servicio**: misma suma.

### 5. Parks en filtro vs drill
- [ ] Ejecutar `python -m scripts.audit_real_coherence --weeks 4`.
- [ ] Revisar salida: “Parks solo en drill” y “Parks solo en MV”. Si hay muchos en una lista y no en la otra, puede haber desalineación de ventana o de refresh (populate vs refresh MVs).

### 6. Cancelaciones
- [ ] Con migración 103 aplicada y populate ejecutado, las filas del drill deben mostrar columna de cancelaciones (y WoW si aplica).
- [ ] Sin migración 103 o sin populate: el drill debe seguir funcionando (sin 500) y mostrar 0 o “—” en cancelaciones.

---

## Comandos útiles

```bash
# Auditoría de coherencia (reconciliación + parks drill vs MVs)
cd backend && python -m scripts.audit_real_coherence --weeks 4 --months 3

# Tests de coherencia REAL
cd backend && python -m pytest tests/test_real_coherence.py -v
```

---

## Criterios de éxito

- Drill por park (con y sin filtro park, con y sin columna cancelled_trips) no devuelve 500.
- Parks se muestran siempre con formato **nombre — ciudad — país** en dropdown y en subfilas del drill.
- Filtro y drill usan el mismo universo de parks para el dropdown del drill (get_drill_parks).
- Semanal y mensual son dos rollups del mismo dataset (real_drill_dim_fact).
- Existe script de reconciliación y auditoría y tests mínimos para drill/parks y park_label.
