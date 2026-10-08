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

The schema below is the current one (after all migrations). Migrations are plain SQL in `server/app/db/migrations/`, run in filename order on server start (`001_init.sql`, `002_seed_apps.sql`, …). Each runs once in its own transaction and is recorded in `schema_migrations (filename, applied_at)`; a failing migration rolls back and stops the server. Never edit an applied migration — add a new file.

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
  review_ids INTEGER[] NOT NULL DEFAULT '{}',        -- every review behind the theme
  generic BOOLEAN NOT NULL DEFAULT false,             -- vague remarks ("great app"), not ranked
  example_phrases TEXT[] NOT NULL DEFAULT '{}',       -- up to 3 most-used phrases
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE analysis_runs (
  id SERIAL PRIMARY KEY,
  app_id INTEGER REFERENCES apps(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('fetch','extract','cluster','compare')),  -- compare: app_id NULL
  items INTEGER DEFAULT 0,
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'running',
  error TEXT,
  started_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ
);

-- Cross-app comparison: per-app themes of one type grouped into shared topics
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
```

- Insert reviews with `ON CONFLICT (store, store_review_id) DO NOTHING`.
- Fetching is incremental: newest first, up to `count` per store. Once `count` reviews are stored for a store, it stops at the first page that is entirely stored; below that it keeps paging so a larger `count` reaches older reviews.
- A store returning no reviews when none are stored yet counts as an error (likely a wrong ID).
- `analysis_runs.status`: `running` → `ok` / `partial` (one store failed) / `error`. Runs left `running` by a server restart are marked `error` on the next start.
- Never re-analyse a review that already has a `review_analysis` row (saves API cost).
- Re-clustering replaces that app's `themes` rows in one transaction.

## Analysis pipeline

1. **Fetch** new reviews for an app → `reviews`.
2. **Extract** — send unanalysed reviews to Claude in batches of ~50. Strict JSON per review:
   `{ "review_id", "sentiment", "pain_points": [], "positives": [], "requests": [] }` — short English phrases, empty arrays allowed. Validate with Pydantic; retry once on invalid JSON.
3. **Cluster** — per app and type, merge similar phrases into themes (e.g. "crashes at login" + "closes on sign-in" → "Crashes during login") with counts → `themes`. Up to 250 distinct phrases: one call returns the themes with their phrase ids. More than that (listing every id would overflow the model's output): one call defines the themes, then phrases are assigned to them in batches of 250. Either way, phrases the model leaves out are assigned in a follow-up call, so none are dropped.
4. **Compare** — cross-app view: pain points shared by several competitors = opportunities for PopNickel. Per type, the clustering model groups every app's non-generic theme labels into shared topics (`compare_groups`); a theme left out becomes its own topic. Cell value = distinct reviews of that app in the topic ÷ the app's analysed reviews. The comparison is cached and marked stale when any theme is not in a group (e.g. after an app is re-clustered); rebuilding replaces that type's groups in one transaction.

All prompts live in `server/app/analysis/prompts.py`. Every run is logged in `analysis_runs` with token usage.

- Extraction saves each batch as it completes and updates the run's `items` / tokens, so progress can be polled via `/api/runs`; a failure keeps the batches already saved.
- Clustering runs on all analysed reviews of the app, only when extraction added reviews, the app has no themes yet, or `recluster` is set. Identical phrases (case-insensitive) are sent once. A failed clustering keeps the previous themes.
- Models: `EXTRACT_MODEL` (default `claude-haiku-4-5`), `CLUSTER_MODEL` (defaults to `EXTRACT_MODEL`).

## API design

All responses use the `{ data, error }` envelope format, except the Markdown export's file body.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness check (API + database) |
| GET | `/api/apps` | List apps with review counts per store, analysed count, last fetch date, last run |
| GET | `/api/apps/{id}` | One app, same fields as the list |
| POST | `/api/apps` | Add app `{ name, play_id?, appstore_id?, notes? }` — at least one store ID; App Store ID numeric (`id` prefix stripped); duplicate ID → 409 |
| PUT / DELETE | `/api/apps/{id}` | Edit (partial: only the fields sent) / delete app (cascades) |
| POST | `/api/apps/{id}/fetch` | Fetch new reviews from both stores. Optional body `{ count?: 1–2000 (default 500, per store), country? }`. Returns `{ run_id, status, inserted, stores: { play?, appstore?: { fetched, inserted, error } } }` |
| POST | `/api/apps/{id}/analyse` | Extract + cluster. Optional body `{ limit?: 1–5000 (default 1000, new reviews to extract), recluster?: bool }`. Returns `{ status, extract, cluster }`, each `{ run_id, status: ok/error/skipped, items, input_tokens, output_tokens, error }`. 409 if already running for the app |
| GET | `/api/apps/{id}/summary?from=&to=&store=` | For the filter slice (`from`/`to` inclusive dates, UTC; `store` = `play` / `appstore`): `{ app, filters, totals { reviews, analysed, avg_rating, first_review, last_review }, sentiment { positive, neutral, negative }, monthly [{ month, reviews, avg_rating, analysed, positive, neutral, negative }], themes { pain, positive, request: [{ id, label, description, example_phrases, review_count }] }, generic { pain, positive, request }, themes_updated_at }`. Theme counts are recomputed for the slice; generic themes are only counted |
| GET | `/api/themes/{id}/reviews?from=&to=&store=` | `{ theme, reviews: [{ id, store, rating, title, body, app_version, country, review_date, sentiment, phrases }] }` — the original reviews behind a theme, same filters as the summary; `phrases` are that review's extracted phrases of the theme's type |
| GET | `/api/compare?type=pain` | Stored topic × app matrix: `{ type, apps [{ id, name, analysed }], groups [{ id, label, description, apps_count, total_reviews, cells { app_id: { review_count, share, themes } } }], built_at, unmatched_themes, stale }` — sorted by apps sharing the topic, then reviews |
| POST | `/api/compare/refresh?type=` | Rebuild the comparison for one type (or all three without `type`); logged as `compare` runs; 409 if already rebuilding |
| GET | `/api/compare/groups/{id}` | Topic summary: `{ group, apps_count, review_count, apps: [{ app_id, name, review_count, share, app_analysed, avg_rating, app_avg_rating, sentiment, first_review, last_review, themes: [{ id, label, description, review_count, example_phrases }] }] }` — per app, the reviews behind the topic, their average rating vs the app's overall, sentiment, date range and the app's themes in the topic |
| GET | `/api/compare/groups/{id}/reviews?app_id=` | Original reviews behind one cell (same shape as theme reviews) |
| GET | `/api/runs?app_id=` | Recent runs with token usage |
| GET | `/api/export/markdown?app_id=` | Markdown file for the Obsidian vault (YAML frontmatter; themes, counts and phrases — no raw review text). With `app_id`: that app's report; without: the cross-app comparison. Returns the file itself (`Content-Disposition: attachment`), not the envelope; errors use the envelope |

## Frontend pages

- **Apps** — list of target apps with review / analysed counts, add/edit/delete, "Fetch" and "Analyse" buttons with progress (analysis polls `/api/runs`) and last-run status
- **App detail** — one filter row (date range: all time / last 30 / 90 days / 12 months / custom; store: all / Play / App Store), kept in the URL; stat tiles (reviews, average rating, % analysed, % negative); sentiment as one stacked bar; average rating by month (line) and sentiment by month (100% stacked columns); top 10 pain points / positives / requests (horizontal bars, count at the bar end, generic themes noted but not ranked); click a bar or label → side panel with the original reviews. Every chart has a table view.
- **Compare** — tabs for pain points / positives / requests; topics × apps table with cells shaded on a one-hue scale by share (count shown too); topics shared by ≥2 apps highlighted with a "Shared by N apps" badge and an "only shared" filter; apps with < 30 analysed reviews flagged as a small sample; click a topic → summary panel (per app: share, rating vs the app's overall, sentiment, date range, the app's themes with example phrases, and its reviews on demand); click a cell → side panel with its reviews; Build / Rebuild button and a notice when the comparison is stale; Export Markdown (also on App detail)
- Every page: loading spinners, error states with retry, empty states with guidance; unknown addresses and missing apps show a not-found page; a render error shows a message with Reload instead of a blank page; the header's API status re-checks every 30 s and on tab focus

Sentiment colors: green = positive, gray = neutral, red = negative — always in that order with gray between green and red (green vs red alone is not colour-blind safe), and always with text labels. This is why sentiment is a stacked bar, not a pie (a pie puts red next to green).
