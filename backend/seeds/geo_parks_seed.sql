-- =============================================================================
-- Seed: park_id -> city, country para dim.dim_geo_park
-- Ejecutar: psql $DATABASE_URL -f backend/seeds/geo_parks_seed.sql
-- O via: python -m scripts.apply_geo_parks_seed
-- =============================================================================
-- Overrides por park_id. Ajustar valores según operación.
-- Si dim.dim_park ya tiene city/country, el sync inicial los copia; este seed
-- permite sobrescribir o completar UNKNOWN.

-- Ejemplo (descomentar y ajustar):
-- UPDATE dim.dim_geo_park SET city = 'Cali', country = 'Colombia' WHERE park_id = 'xxx';
-- UPDATE dim.dim_geo_park SET city = 'Lima', country = 'Peru' WHERE park_id = 'yyy';

-- Sin overrides por defecto (dejar UNKNOWN hasta cargar mapeo).
SELECT 1 AS seed_applied;
