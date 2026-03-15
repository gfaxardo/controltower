# Contrato esperado: plantilla Excel de proyección

**Objetivo:** Definir el contrato esperado para la carga de la proyección (Excel/CSV) sin hardcodear valores hasta que exista la plantilla real.

---

## 1. Contrato genérico (placeholder)

Cuando el usuario entregue la plantilla de proyección, este documento se actualizará con:

- **Formato:** Excel (.xlsx) o CSV; encoding y separador.
- **Columnas obligatorias sugeridas:**
  - **Dimensión tiempo:** period (YYYY-MM o YYYY-MM-DD), period_type (month/week).
  - **Dimensiones geográficas:** country, city (o equivalentes con nombres a mapear).
  - **Dimensiones de negocio:** line_of_business / vertical / LOB / service_type / categoría (según nomenclatura del Excel).
  - **Métricas de plan/proyección:** drivers_plan, trips_plan, revenue_plan, avg_ticket_plan (o nombres equivalentes).
- **Métricas derivadas en carga (opcional):** avg_trips_per_driver_plan = trips_plan / drivers_plan si no viene.
- **Reglas de validación:** no nulos en claves; valores numéricos >= 0 donde aplique.
- **Mapping:** qué columnas del Excel se mapean a `country`, `city`, `lob_base`, `segment`, etc. en el sistema (vía `ops.projection_dimension_mapping`).

---

## 2. Tabla de staging (ya preparada)

- **ops.projection_upload_staging:** columnas flexibles para recibir filas crudas (period, period_type, raw_country, raw_city, raw_lob, raw_segment, drivers_plan, trips_plan, revenue_plan, avg_ticket_plan, source_file_name, uploaded_at, etc.). Los nombres exactos de columnas “raw_*” se ajustarán al contrato final del Excel.

---

## 3. Parser esperado (backend)

- Endpoint o script: **POST /ops/real-vs-projection/upload** (o script `load_projection_from_excel.py`) que:
  1. Acepte archivo (Excel/CSV).
  2. Valide contra el contrato (columnas mínimas, tipos).
  3. Inserte en `ops.projection_upload_staging`.
  4. Opcional: dispare sugerencias de mapping para `projection_dimension_mapping` (valores distintos en raw_* que no tengan canonical).

---

## 4. Riesgos pendientes

- Si la proyección viene por **mes** y el sistema expone **semana**, hará falta agregar o desagregar (documentar decisión).
- Si las dimensiones del Excel no tienen equivalente canónico, la vista por segmentación proyección será parcial hasta completar mapping manual.
