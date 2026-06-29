-- BUN-1139: meta-polity hierarchy levels
-- Additive + reversible. Adds a self-referential parent link plus convenience
-- flags so the frontend can walk leaf -> meta -> meta-of-meta (depth 1-3).
--
-- Reversal (if needed):
--   ALTER TABLE polities DROP COLUMN IF EXISTS parent_id;
--   ALTER TABLE polities DROP COLUMN IF EXISTS is_meta;
--   ALTER TABLE polities DROP COLUMN IF EXISTS depth;
--   DROP INDEX IF EXISTS idx_polities_parent_id;

ALTER TABLE polities
ADD COLUMN IF NOT EXISTS parent_id BIGINT;

ALTER TABLE polities
ADD COLUMN IF NOT EXISTS is_meta BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE polities
ADD COLUMN IF NOT EXISTS depth INTEGER NOT NULL DEFAULT 0;

-- parent_id points at another polity (the immediate meta level above this one).
CREATE INDEX IF NOT EXISTS idx_polities_parent_id ON polities(parent_id);
