-- Cross-app comparison: per-app themes of one type grouped into shared topics by the LLM.
CREATE TABLE compare_groups (
  id SERIAL PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('pain','positive','request')),
  label TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE compare_group_themes (
  group_id INTEGER NOT NULL REFERENCES compare_groups(id) ON DELETE CASCADE,
  theme_id INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
  PRIMARY KEY (group_id, theme_id)
);
CREATE INDEX compare_group_themes_theme_idx ON compare_group_themes (theme_id);

-- Comparison runs are logged too; they span apps, so app_id is NULL for them.
ALTER TABLE analysis_runs DROP CONSTRAINT analysis_runs_kind_check;
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_kind_check
  CHECK (kind IN ('fetch','extract','cluster','compare'));
