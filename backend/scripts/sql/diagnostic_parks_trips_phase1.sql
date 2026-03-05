-- FASE 1 — Diagnóstico rápido: parks, trips_all, joins.
-- Ejecutar contra la BD del Control Tower (ej. psql o desde scripts con get_db).
-- Objetivo: confirmar esquema para regla "no IDs en UI" (park_name, city, country; conductor_nombre como nombre legible).

-- 1) Confirmar parks (public.parks: id, name, city según contexto; puede tener semántica distinta)
SELECT id, name, city FROM public.parks ORDER BY 1 LIMIT 50;

-- 2) Confirmar trips_all: conteos park_id/conductor_id/conductor_nombre
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE park_id IS NULL) AS park_id_null,
  COUNT(*) FILTER (WHERE conductor_id IS NULL) AS driver_id_null,
  COUNT(*) FILTER (WHERE COALESCE(conductor_nombre::text,'') = '') AS conductor_nombre_blank
FROM public.trips_all;

-- 3) Join parks ↔ trips_all (match por id o por city=park_id según esquema; ajustar si falla)
SELECT
  COUNT(*) AS trips,
  COUNT(*) FILTER (WHERE p.id IS NOT NULL) AS matched,
  COUNT(*) FILTER (WHERE p.id IS NULL) AS unmatched
FROM public.trips_all t
LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '');
-- Si tu BD usa p.city = t.park_id (ver migración 029), usar: LEFT JOIN public.parks p ON p.city = t.park_id

-- 4) Ejemplos: park_id, park_name, city, driver, condicion
SELECT
  t.park_id,
  p.name AS park_name,
  p.city AS park_city,
  t.conductor_id AS driver_id,
  t.conductor_nombre,
  t.condicion,
  t.created_at
FROM public.trips_all t
LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
WHERE t.condicion = 'Completado'
ORDER BY t.created_at DESC NULLS LAST
LIMIT 20;
