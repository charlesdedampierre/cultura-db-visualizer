CREATE TABLE IF NOT EXISTS polities (
    id BIGINT PRIMARY KEY,
    name TEXT,
    type TEXT,
    wikipedia_url TEXT,
    wikidata_id TEXT,
    individuals_count INTEGER,
    display_mode TEXT DEFAULT 'both'
);

CREATE TABLE IF NOT EXISTS polity_periods (
    id BIGINT PRIMARY KEY,
    polity_id BIGINT REFERENCES polities(id),
    polity_name TEXT,
    from_year INTEGER,
    to_year INTEGER,
    area REAL,
    geometry TEXT
);

CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    name_en TEXT,
    lat REAL,
    lon REAL,
    iso_country_name TEXT
);

CREATE TABLE IF NOT EXISTS individuals_light (
    wikidata_id TEXT,
    name_en TEXT,
    occupations_en TEXT,
    sitelinks_count INTEGER,
    impact_date INTEGER,
    impact_date_raw INTEGER,
    polity_id BIGINT,
    birthcity_id TEXT,
    deathcity_id TEXT,
    PRIMARY KEY (wikidata_id, polity_id)
);

CREATE TABLE IF NOT EXISTS evolution_cache (
    polity_id BIGINT,
    year INTEGER,
    count INTEGER,
    PRIMARY KEY (polity_id, year)
);

CREATE TABLE IF NOT EXISTS top_cities_cache (
    polity_id BIGINT,
    city_id TEXT,
    city_name TEXT,
    lat REAL,
    lon REAL,
    individual_count INTEGER,
    PRIMARY KEY (polity_id, city_id)
);

CREATE INDEX IF NOT EXISTS idx_pp_polity ON polity_periods(polity_id);
CREATE INDEX IF NOT EXISTS idx_pp_years ON polity_periods(from_year, to_year);
CREATE INDEX IF NOT EXISTS idx_il_polity ON individuals_light(polity_id);
CREATE INDEX IF NOT EXISTS idx_il_polity_sitelinks ON individuals_light(polity_id, sitelinks_count DESC);
CREATE INDEX IF NOT EXISTS idx_il_polity_impact ON individuals_light(polity_id, impact_date);
