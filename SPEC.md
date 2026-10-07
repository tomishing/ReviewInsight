# SPEC.md — ReviewInsight

Detailed specification. Project rules, stack, and phases are in `CLAUDE.md`.

## Target apps (initial seed)

| App                      | Google Play ID                        | App Store ID               |
| ------------------------ | ------------------------------------- | -------------------------- |
| Monarch Money            | `com.monarchmoney.mobile` ✓           | `1459319842` ✓             |
| YNAB                     | `com.youneedabudget.evergreen.app` ✓  | `1010865877` ✓             |
| Money Manager (Realbyte) | `com.realbyteapps.moneymanagerfree` ✓ | `560481810` ✓              |
| Cashew                   | `com.budget.tracker_app` ✓            | `6463662930` ✓             |
| Yomio                    | `com.yomio.app` ✓                     | `6757447181` ✓             |
| Money Tracker            | `com.freeman.moneymanager` ✓          | TODO (may be Android-only) |

✓ = copied from a store URL (Canada store). Apps live in the DB; this table is only the seed list.

## Data sources — notes and limits

- **Google Play**: `google-play-scraper` (unofficial). Default `lang=en`, `country=ca`, sort newest, paginate with continuation token.
- **App Store**: `https://itunes.apple.com/{country}/rss/customerreviews/page={1..10}/id={appId}/sortby=mostrecent/json` — max ~500 most recent reviews per country.
- Both are unofficial; one app failing must not stop the others.
- Personal research only — ≥1 s between page requests, do not redistribute raw review text.

## Database schema

Migrations are plain SQL in `server/app/db/migrations/`, run in filename order on server start (`001_init.sql`, `002_seed_apps.sql`, …). Each runs once in its own transaction and is recorded in `schema_migrations (filename, applied_at)`; a failing migration rolls back and stops the server. Never edit an applied migration — add a new file.

```sql
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
```

- Insert reviews with `ON CONFLICT (store, store_review_id) DO NOTHING`.
- Never re-analyse a review that already has a `review_analysis` row (saves API cost).
- Re-clustering replaces that app's `themes` rows in one transaction.

## Analysis pipeline

1. **Fetch** new reviews for an app → `reviews`.
2. **Extract** — send unanalysed reviews to Claude in batches of ~50. Strict JSON per review:
   `{ "review_id", "sentiment", "pain_points": [], "positives": [], "requests": [] }` — short English phrases, empty arrays allowed. Validate with Pydantic; retry once on invalid JSON.
3. **Cluster** — per app and type, merge similar phrases into themes (e.g. "crashes at login" + "closes on sign-in" → "Crashes during login") with counts → `themes`.
4. **Compare** — cross-app view: pain points shared by several competitors = opportunities for PopNickel.

All prompts live in `server/app/analysis/prompts.py`. Every run is logged in `analysis_runs` with token usage.

## API design

All responses use the `{ data, error }` envelope format.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness check (API + database) |
| GET | `/api/apps` | List apps with review counts and last fetch date |
| POST | `/api/apps` | Add app `{ name, play_id?, appstore_id?, notes? }` |
| PUT / DELETE | `/api/apps/{id}` | Edit / delete app (cascades) |
| POST | `/api/apps/{id}/fetch` | Fetch new reviews from both stores |
| POST | `/api/apps/{id}/analyse` | Extract + cluster unanalysed reviews |
| GET | `/api/apps/{id}/summary?from=&to=&store=` | Sentiment breakdown, rating trend by month, top themes |
| GET | `/api/themes/{id}/reviews` | Original reviews behind a theme |
| GET | `/api/compare?type=pain` | Theme × app matrix |
| GET | `/api/runs?app_id=` | Recent runs with token usage |
| GET | `/api/export/markdown?app_id=` | Markdown report for the Obsidian vault |

## Frontend pages

- **Apps** — list of target apps, add/edit, "Fetch" and "Analyse" buttons with progress and last-run status
- **App detail** — sentiment pie, monthly rating line chart, Play vs App Store filter, top pain points / positives / requests ranked by count (bar charts); click a theme → side panel with original reviews
- **Compare** — themes × apps table; highlight pain points shared by ≥2 competitors
- Every page: loading spinners, error states with retry, empty states with guidance

Sentiment colors: green = positive, gray = neutral, red = negative.
