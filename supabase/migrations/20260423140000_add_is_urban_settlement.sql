ALTER TABLE cities
ADD COLUMN IF NOT EXISTS is_urban_settlement BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_cities_urban ON cities(is_urban_settlement);
