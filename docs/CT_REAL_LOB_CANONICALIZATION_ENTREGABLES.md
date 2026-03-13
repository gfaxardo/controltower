# CT-REAL-LOB-CANONICALIZATION — Entregables y validación

## 1. Mapa del sistema afectado

Ver **docs/CT_REAL_LOB_CANONICALIZATION_MAP.md** (fuentes, vistas, servicios, endpoints, componentes UI, queries de diagnóstico).

---

## 2. Decisión canónica

- **Lista final de categorías canónicas (service_type_norm):** economico, comfort, comfort_plus, tuk_tuk, minivan, premier, standard, start, xl, economy, delivery, cargo, moto, taxi_moto, UNCLASSIFIED.
- **Tabla raw → canonical:** En la sección 11 del mapa (y tabla en mismo doc).
- **Criterio:** Una sola función `canon.normalize_real_tipo_servicio(raw)`: unaccent, lower, trim, +→_plus, espacios/guiones→_; luego mapeo a clave canónica. Variantes equivalentes colapsan a una clave; lookup en `canon.dim_real_service_type_lob` para lob_group.

---

## 3. Archivos tocados

| Área | Archivo | Cambio |
|------|---------|--------|
| Backend | `alembic/versions/080_real_lob_canonical_service_type_unified.py` | **Nuevo:** migración que redefinde canon.normalize_real_tipo_servicio, upsert dim canónica, sincroniza map, desactiva claves antiguas. |
| Backend | `app/services/real_service_type_normalizer.py` | Añadido canonical_service_type() y _CANONICAL_MAP alineados con SQL; documentación 080. |
| Docs | `docs/CT_REAL_LOB_CANONICALIZATION_MAP.md` | **Nuevo:** mapa técnico, fuentes, vistas, servicios, endpoints, tabla raw→canonical, pasos post-migración. |
| Docs | `docs/CT_REAL_LOB_CANONICALIZATION_ENTREGABLES.md` | **Nuevo:** este entregable (resumen cambios, validación, riesgos). |

**No se modificó:** data_contract.py (TIPO_SERVICIO_MAPPING sigue para flujos Plan; REAL usa solo canon). Frontend: sin cambios (no había hotfix; usa valores del API).

---

## 4. Cambios implementados (resumen por archivo)

- **080_real_lob_canonical_service_type_unified.py**
  - `canon.normalize_real_tipo_servicio(raw)`: reescrita con unaccent, +→_plus, espacios/guiones→_, y CASE a claves canónicas (economico, comfort, comfort_plus, tuk_tuk, delivery, etc.).
  - `canon.dim_real_service_type_lob`: INSERT de filas canónicas (canonical_080) con ON CONFLICT DO UPDATE.
  - `canon.map_real_tipo_servicio_to_lob_group`: rellenada desde dim para legacy.
  - Filas antiguas (confort, confort+, tuk-tuk, mensajería, express, expres, envios) desactivadas con notes "reemplazado por canonical_080".
  - Downgrade: restaura función 070, reactiva filas desactivadas, borra filas con mapping_source = 'canonical_080'.

- **real_service_type_normalizer.py**
  - `canonical_service_type(raw)`: nueva función Python que replica la lógica canónica para uso en tests o helpers.
  - `_CANONICAL_MAP`: mapeo clave normalizada → clave canónica.
  - Comentarios actualizados indicando alineación con migración 080.

---

## 5. Validación E2E

### Queries usadas (ejecutar tras `alembic upgrade head` y refresh MVs)

```sql
-- A) Valores distintos de real_tipo_servicio_norm en la vista (debe haber una sola entrada para comfort_plus, tuk_tuk, delivery)
SELECT real_tipo_servicio_norm, COUNT(*) AS trips
FROM ops.v_real_trips_with_lob_v2
WHERE fecha_inicio_viaje::date >= current_date - 90
GROUP BY real_tipo_servicio_norm
ORDER BY trips DESC;

-- B) Verificar que no aparezcan duplicados (no debe haber tanto 'confort+' como 'comfort_plus', ni 'tuk-tuk' y 'tuk_tuk')
-- Tras 080 solo deben verse claves canónicas: comfort_plus, tuk_tuk, delivery, etc.

-- C) Totales por lob_group (debe ser consistente; total viajes no debe cambiar)
SELECT lob_group, COUNT(*) AS trips
FROM ops.v_real_trips_with_lob_v2
WHERE fecha_inicio_viaje::date >= current_date - 90
GROUP BY lob_group ORDER BY trips DESC;
```

### Endpoints a probar

- GET `/ops/real-lob/filters` → `tipo_servicio` y `lob_groups` sin duplicados equivalentes.
- GET `/ops/real-lob/v2/data` → filas con `real_tipo_servicio_norm` canónico (comfort_plus, tuk_tuk, delivery).
- GET `/ops/real-lob/drill` y drill/children → dimension_key (lob / service_type) con valores canónicos.

### Pantallas a verificar

- **Real > Observabilidad (v2):** tablas y filtros por LOB / tipo servicio sin duplicados (confort+ y confort plus como una sola; tuk_tuk y tuk-tuk como una; express y mensajería como delivery).
- **Real > Drill:** desglose por LOB y por tipo de servicio con las mismas claves canónicas.
- Recarga, cambio de pestaña, cambio de filtros y nueva consulta: la corrección debe persistir (datos vienen del backend/MVs).

### Evidencia de persistencia

- Los datos provienen de `ops.v_real_trips_with_lob_v2` → `v_real_trips_service_lob_resolved` → `canon.normalize_real_tipo_servicio`. Tras refresh de MVs v2, la UI mostrará solo claves canónicas hasta el próximo refresh de datos. El backfill de drill rellena `real_drill_dim_fact` con la misma función; tras backfill, el drill también es persistente.

---

## 6. Riesgos / deuda técnica

- **MVs legacy (mv_real_trips_by_lob_month/week):** Siguen usando columna `lob` de otra fuente; si algún cliente usa solo esos endpoints, no verá la unificación. Los endpoints v2 y drill sí usan la capa canónica.
- **053 mv_real_lob_drill_agg:** Tiene CASE inline propio; si algún proceso la usa directamente (no el drill actual que usa real_drill_dim_fact), podría seguir mostrando variantes antiguas. El drill PRO usa `ops.mv_real_drill_dim_agg` (vista sobre real_drill_dim_fact), alimentado por backfill con canon.
- **Display label:** No implementado en API. Si se desea etiqueta amigable (ej. "Comfort Plus"), se puede añadir en `/ops/real-lob/filters` un array de { value, label } o formatear en frontend desde la clave canónica.
- **Dimensiones canónicas futuras:** Para consolidar dimensiones (dim_service_type / dim_lob / dim_lob_group) en un solo modelo de dimensiones, se puede extender `canon.dim_real_service_type_lob` con columnas display_label y orden, y exponer un único endpoint de catálogo.

---

## Criterios de aceptación (checklist)

- [x] Sistema escaneado antes de cambiar (mapa en CT_REAL_LOB_CANONICALIZATION_MAP.md).
- [x] Solución canónica y global (función única canon.normalize_real_tipo_servicio + dim).
- [ ] Vistas REAL dejan de mostrar duplicados por naming (verificar tras migración + refresh MVs).
- [ ] express y mensajería consolidados como delivery (verificar en filtros y tablas).
- [ ] confort+ y confort plus como una sola categoría (comfort_plus).
- [ ] tuk_tuk y tuk-tuk como una sola categoría (tuk_tuk).
- [ ] Filtros REAL sin categorías equivalentes duplicadas.
- [ ] Corrección persiste al recargar UI (datos desde backend).
- [ ] Total de viajes no cambia (solo redistribución entre categorías equivalentes).
- [x] Fix no hardcodeado en frontend.
- [x] Documentado qué se cambió y por qué.

(Items con [ ] requieren ejecutar migración, refresh MVs y comprobación manual o con queries anteriores.)
