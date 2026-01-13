-- Exportar DISTINCT park_id de trips_all con conteo de trips
-- Para identificar parks que aparecen en trips pero no tienen mapeo territorial

SELECT 
    t.park_id,
    COUNT(*) as trips_count,
    MIN(t.fecha_inicio_viaje) as first_trip_date,
    MAX(t.fecha_inicio_viaje) as last_trip_date
FROM public.trips_all t
WHERE t.park_id IS NOT NULL AND trim(t.park_id) != ''
GROUP BY t.park_id
ORDER BY trips_count DESC;
