-- One-shot: clear the partial city_individuals_cache load so the
-- upload script can fill it cleanly. TRUNCATE isn't subject to the
-- PostgREST statement timeout the way a big DELETE is.
TRUNCATE TABLE city_individuals_cache;
