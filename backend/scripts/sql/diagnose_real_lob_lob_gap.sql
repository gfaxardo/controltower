-- Diagnóstico brecha service_type -> LOB (Real LOB).
-- Ejecutar en DB con esquemas ops y canon.
-- Ref: docs/real_lob_lob_gap_diagnosis.md

-- A) Residual UNCLASSIFIED en service_type y LOB (drill)
SELECT 'A) UNCLASSIFIED en drill (service_type y lob)' AS paso;
SELECT
  breakdown,
  dimension_key AS breakdown_value,
  SUM(trips) AS trips
FROM ops.real_drill_dim_fact
WHERE breakdown IN ('service_type','lob')
  AND dimension_key = 'UNCLASSIFIED'
GROUP BY breakdown, dimension_key
ORDER BY breakdown;

-- B) Qué validated_service_type cae en LOB UNCLASSIFIED (vista por viaje = v_real_trips_with_lob_v2)
SELECT 'B) Top validated_service_type en LOB UNCLASSIFIED' AS paso;
SELECT
  real_tipo_servicio_norm AS validated_service_type,
  COUNT(*) AS trips
FROM ops.v_real_trips_with_lob_v2
WHERE lob_group = 'UNCLASSIFIED'
GROUP BY real_tipo_servicio_norm
ORDER BY trips DESC
LIMIT 200;

-- C) Cruzado service_type -> LOB
SELECT 'C) Cruzado validated_service_type x lob_group' AS paso;
SELECT
  real_tipo_servicio_norm AS validated_service_type,
  lob_group,
  COUNT(*) AS trips
FROM ops.v_real_trips_with_lob_v2
GROUP BY real_tipo_servicio_norm, lob_group
ORDER BY trips DESC
LIMIT 500;

-- D) Totales para % residual
SELECT 'D) Total viajes (vista) y UNCLASSIFIED LOB' AS paso;
SELECT
  COUNT(*) AS total_trips,
  SUM(CASE WHEN lob_group = 'UNCLASSIFIED' THEN 1 ELSE 0 END) AS unclassified_lob_trips,
  ROUND(100.0 * SUM(CASE WHEN lob_group = 'UNCLASSIFIED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS pct_unclassified_lob
FROM ops.v_real_trips_with_lob_v2;
