-- Validaciones obligatorias para el sistema de mapeo territorial

-- 1) Conteo de trips_unknown y lista top park_id causantes
SELECT 
    'Trips con territory unknown' as metric,
    COUNT(*) as total_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM public.trips_all), 2) as pct_of_total
FROM ops.v_trip_territory_canonical
WHERE is_territory_unknown = true;

SELECT 
    'Top 20 park_id causantes de trips_unknown' as metric,
    park_id,
    COUNT(*) as trips_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ops.v_trip_territory_canonical WHERE is_territory_unknown = true), 2) as pct_of_unknown
FROM ops.v_trip_territory_canonical
WHERE is_territory_unknown = true
  AND park_id IS NOT NULL
GROUP BY park_id
ORDER BY trips_count DESC
LIMIT 20;

-- 2) Conteo parks_unmapped
SELECT 
    'Parks unmapped (en trips_all pero no en dim_park)' as metric,
    COUNT(DISTINCT park_id) as parks_unmapped,
    SUM(trips_count) as total_trips_unmapped
FROM (
    SELECT 
        t.park_id,
        COUNT(*) as trips_count
    FROM public.trips_all t
    WHERE t.park_id IS NOT NULL 
      AND trim(t.park_id) != ''
      AND NOT EXISTS (
          SELECT 1 FROM dim.dim_park dp WHERE dp.park_id = t.park_id
      )
    GROUP BY t.park_id
) unmapped;

-- 3) Verificar que weekly KPIs suman coherente
SELECT 
    'Verificación: Suma de trips semanales vs total' as metric,
    (SELECT total_trips FROM ops.v_territory_mapping_quality_kpis) as total_trips,
    (SELECT SUM(total_trips) FROM ops.v_territory_mapping_quality_kpis_weekly) as sum_weekly_trips,
    (SELECT total_trips FROM ops.v_territory_mapping_quality_kpis) - 
    (SELECT SUM(total_trips) FROM ops.v_territory_mapping_quality_kpis_weekly) as difference;

-- 4) Parks con country o city NULL
SELECT 
    'Parks en dim_park con country o city NULL/vacío' as metric,
    COUNT(*) as parks_with_null_territory
FROM dim.dim_park
WHERE country IS NULL OR trim(country) = '' OR city IS NULL OR trim(city) = '';

-- 5) Resumen general de KPIs
SELECT * FROM ops.v_territory_mapping_quality_kpis;
