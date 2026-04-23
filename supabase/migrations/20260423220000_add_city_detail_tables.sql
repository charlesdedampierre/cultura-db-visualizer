CREATE TABLE IF NOT EXISTS city_individuals_cache (
    city_id TEXT NOT NULL,
    wikidata_id TEXT NOT NULL,
    name_en TEXT,
    occupations_en TEXT,
    sitelinks_count INTEGER,
    impact_date_raw INTEGER,
    impact_date INTEGER,
    is_birth SMALLINT NOT NULL,
    is_death SMALLINT NOT NULL,
    PRIMARY KEY (city_id, wikidata_id)
);

CREATE INDEX IF NOT EXISTS idx_cind_city     ON city_individuals_cache(city_id);
CREATE INDEX IF NOT EXISTS idx_cind_city_sl  ON city_individuals_cache(city_id, sitelinks_count DESC);
CREATE INDEX IF NOT EXISTS idx_cind_city_impact ON city_individuals_cache(city_id, impact_date);

CREATE TABLE IF NOT EXISTS city_evolution_cache (
    city_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (city_id, year)
);

CREATE INDEX IF NOT EXISTS idx_cevo_city ON city_evolution_cache(city_id);

CREATE TABLE IF NOT EXISTS city_summary_cache (
    city_id TEXT PRIMARY KEY,
    name_en TEXT,
    lat REAL,
    lon REAL,
    n_individuals INTEGER NOT NULL,
    n_birth INTEGER NOT NULL,
    n_death INTEGER NOT NULL,
    n_both INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_csum_n ON city_summary_cache(n_individuals DESC);
