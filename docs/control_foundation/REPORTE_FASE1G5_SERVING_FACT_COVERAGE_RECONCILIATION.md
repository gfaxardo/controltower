# REPORTE FASE 1G.5 — SERVING FACT COVERAGE RECONCILIATION

## Veredicto: ✅ GO

---

## 1. Auditoría de Cobertura — Final

| Grain | Countries | Cities | Slices | Periods | Rows | served_from |
|-------|-----------|--------|--------|---------|------|-------------|
| daily | 2 (peru, colombia) | 9 | 8 | 365 | 10,287 | fact |
| weekly | 2 (peru, colombia) | 9 | 8 | 53 | 1,487 | fact |
| monthly | 2 (peru, colombia) | 9 | 8 | 12 | 338 | fact |

### Ciudades: 9 (arequipa, barranquilla, bogota, bucaramanga, cali, cucuta, lima, medellin, trujillo)

### Tajadas: 8 (Auto regular, Carga, Delivery, Moto, PRO, Tuk Tuk, YMA, YMM)

---

## 2. Faltantes Detectados y Corregidos

| Faltante | Causa | Corrección |
|----------|-------|------------|
| Daily solo tenía peru (1 país, 3 ciudades) | Refresh se ejecutó sin country=colombia | `--country colombia` → 6,696 rows |
| Monthly no existía en serving fact | CHECK constraint solo permitía daily/weekly | ALTER TABLE → agregado 'monthly' al CHECK |
| Monthly: year=NULL en filas insertadas | `_extract_row()` no derivaba year desde period_key para monthly | Fix: extraer year desde period_key como fallback |
| Monthly: 0 rows en API pese a 338 en DB | year=NULL no matcheaba `year = 2026` en WHERE | Clean + fix: `year = %s OR year IS NULL` en query |
| Weekly: refresh aceptaba solo daily/weekly | Script con choices=["daily","weekly"] | Agregado "monthly" a choices |

---

## 3. Correcciones Aplicadas

| Archivo | Cambio |
|---------|--------|
| **DB** | `ALTER TABLE serving.omniview_projection_daily_fact DROP CONSTRAINT ... ADD CONSTRAINT ... CHECK (grain = ANY (ARRAY['daily','weekly','monthly']))` |
| `backend/scripts/refresh_omniview_projection_facts.py` | choices=["daily","weekly","monthly"]; extraer year desde period_key |
| `backend/app/services/projection_expected_progress_service.py` | serving fact intentado para monthly también; `year = %s OR year IS NULL` |
| `backend/sql/phase1g3_omniview_projection_serving_layer.sql` | (implícito — el ALTER TABLE ya aplica) |

---

## 4. Refreshes Ejecutados

| Comando | Rows | Tiempo |
|---------|------|--------|
| `--grain daily --year 2026` (peru — ya existía) | 3,591 | 9s |
| `--grain daily --year 2026 --country colombia` | 6,696 | 42s |
| `--grain weekly --year 2026` | 1,487 | 7s |
| `--grain monthly --year 2026` | 338 | 152s |

---

## 5. Validación Endpoints — Final

| Endpoint | Rows | served_from | Tiempo |
|----------|------|-------------|--------|
| `omniview-projection?grain=daily&year=2026` | 10,287 | fact | 5,526ms |
| `omniview-projection?grain=weekly&year=2026` | 1,487 | fact | 2,342ms |
| `omniview-projection?grain=monthly&year=2026` | 338 | fact | 1,765ms |

---

## 6. Comparación UI Filters vs Serving Facts

| Dimensión | UI permite | Serving fact tiene | Coverage |
|-----------|-----------|--------------------|----------|
| Countries | peru, colombia | peru, colombia | 100% |
| Cities | 9 | 9 (todas) | 100% |
| Slices | 7-8 | 8 (todas) | 100% |
| Grains | monthly, weekly, daily | monthly, weekly, daily | 100% |
| Year | 2026 | 2026 | 100% |

---

## 7. GO/NO-GO

**✅ GO** — Serving fact coverage completa para todos los grains, países, ciudades y tajadas que la UI permite filtrar. Los 3 endpoints devuelven `served_from=fact` con `projection_exists=True`.
