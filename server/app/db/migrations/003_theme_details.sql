-- Themes hold every review behind them (not just examples), the "generic" flag from
-- clustering (vague remarks like "great app", not ranked), and the most-used phrases.
ALTER TABLE themes RENAME COLUMN example_review_ids TO review_ids;
ALTER TABLE themes
  ADD COLUMN generic BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN example_phrases TEXT[] NOT NULL DEFAULT '{}';
CREATE INDEX themes_app_type_idx ON themes (app_id, type);
