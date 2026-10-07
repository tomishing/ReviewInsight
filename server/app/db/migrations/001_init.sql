CREATE TABLE apps (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  play_id TEXT UNIQUE,
  appstore_id TEXT UNIQUE,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE reviews (
  id SERIAL PRIMARY KEY,
  app_id INTEGER REFERENCES apps(id) ON DELETE CASCADE,
  store TEXT NOT NULL CHECK (store IN ('play','appstore')),
  store_review_id TEXT NOT NULL,
  rating SMALLINT CHECK (rating BETWEEN 1 AND 5),
  title TEXT,
  body TEXT NOT NULL,
  app_version TEXT,
  country TEXT,
  review_date TIMESTAMPTZ,
  fetched_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (store, store_review_id)
);

CREATE TABLE review_analysis (
  review_id INTEGER PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
  sentiment TEXT NOT NULL CHECK (sentiment IN ('positive','neutral','negative')),
  pain_points JSONB NOT NULL DEFAULT '[]',
  positives JSONB NOT NULL DEFAULT '[]',
  requests JSONB NOT NULL DEFAULT '[]',
  model TEXT NOT NULL,
  analysed_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE themes (
  id SERIAL PRIMARY KEY,
  app_id INTEGER REFERENCES apps(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('pain','positive','request')),
  label TEXT NOT NULL,
  description TEXT,
  review_count INTEGER NOT NULL DEFAULT 0,
  example_review_ids INTEGER[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE analysis_runs (
  id SERIAL PRIMARY KEY,
  app_id INTEGER REFERENCES apps(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('fetch','extract','cluster')),
  items INTEGER DEFAULT 0,
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'running',
  error TEXT,
  started_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ
);
