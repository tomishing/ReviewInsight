# ReviewInsight

A personal tool that reads Google Play and App Store reviews of competing budgeting apps and turns them into **pain points**, **positive points**, **feature requests** and **sentiment over time** — to guide the design of **PopNickel** (see `../FinancialApp/specification.md`).

It runs locally with Docker: a React UI, a FastAPI server, and PostgreSQL. Reviews are analysed with Claude.

- **Apps** — the competitors you track; fetch their reviews and analyse them.
- **App detail** — sentiment, rating and sentiment by month, and the top themes; click a theme to read the reviews behind it.
- **Compare** — the same topics across apps; pain points shared by several competitors are opportunities for PopNickel.
- **Export** — Markdown reports (per app, or the comparison) for the Obsidian vault.

`SPEC.md` has the details (data sources, schema, pipeline, API, pages); `CLAUDE.md` the project conventions.

## Requirements

- Docker with Docker Compose
- An Anthropic API key (for analysis; fetching reviews works without one)
- Optional, for the standalone script: Python 3.12

## Setup

```sh
cp .env.example .env
```

Then edit `.env`:

| Variable | What to set |
| --- | --- |
| `POSTGRES_PASSWORD` | **Required.** Generate one: `openssl rand -hex 16` |
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `PORT`, `CLIENT_PORT`, `DB_PORT` | Host ports (default 4000 / 3000 / 5432). Change them if another project uses them, and keep `VITE_API_URL` in sync with `PORT` |
| `EXTRACT_MODEL`, `CLUSTER_MODEL` | Optional. Default `claude-haiku-4-5`; `CLUSTER_MODEL` defaults to `EXTRACT_MODEL` |
| `DEFAULT_COUNTRY`, `DEFAULT_LANG` | Store country / language for fetching (default `ca` / `en`) |

## Run

```sh
docker compose up --build
```

Open <http://localhost:3000> (or your `CLIENT_PORT`). The database schema and the six seed apps are created automatically on first start. All three services listen on `127.0.0.1` only.

Stop with `Ctrl+C` or `docker compose down`. Data lives in the `pgdata` volume and survives restarts; `docker compose down -v` deletes it.

## Using it

1. **Apps** → **Fetch** downloads the newest reviews from both stores (up to 500 per store; later fetches only add new ones).
2. **Analyse** sends reviews that haven't been analysed yet to Claude in batches of 50, then groups the extracted phrases into themes. Progress shows in the row. Already-analysed reviews are never sent again.
3. Click an app for its **detail** page. Filter by date range and store; the filters are kept in the URL.
4. **Compare** → **Build comparison** groups every app's themes into shared topics (needs at least two analysed apps). After an app is analysed again, the page offers a **Rebuild**.
5. **Export Markdown** on the detail or Compare page downloads a report with YAML frontmatter, ready for the vault. Reports contain themes, counts and short phrases — no raw review text.

### Cost

Measured with `claude-haiku-4-5`: about **$0.25 per 1,000 reviews** analysed (extraction plus clustering). Rebuilding the comparison sends only theme labels and costs well under a cent. Each run's token usage is logged (`GET /api/runs`).

To try another model, set `EXTRACT_MODEL` in `.env` and restart the server (`docker compose up -d server`). Reviews already analysed keep their results.

## Standalone script (Phase 1)

Analyses one Google Play app without the database or UI and prints a Markdown report:

```sh
python3.12 -m venv server/.venv
server/.venv/bin/pip install -r server/requirements.txt
server/.venv/bin/python server/scripts/analyse_app.py com.monarchmoney.mobile --count 200 -o monarch.md
```

It reads `ANTHROPIC_API_KEY` from `.env`. See `--help` for options.

## Development

- **Hot reload**: the containers mount `client/` and `server/app/`, so edits apply immediately (Vite HMR, `uvicorn --reload`).
- **Dependencies**: after changing `client/package.json`, run `docker compose up --build -V` (`-V` recreates the `node_modules` volume from the new image). After changing `server/requirements.txt`, `docker compose up --build`.
- **Database changes**: add a new file in `server/app/db/migrations/` (`005_….sql`); it runs once on the next server start. Never edit an applied migration.
- **Python style**: `ruff check server && ruff format server`.
- **Running server code on the host** (e.g. scripts against the database): `.env`'s `DATABASE_URL` points at `localhost:${DB_PORT}`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `required variable POSTGRES_PASSWORD is missing a value` | Set `POSTGRES_PASSWORD` in `.env` |
| `port is already allocated` | Another project uses the port. Change `PORT` / `CLIENT_PORT` / `DB_PORT` (and `VITE_API_URL`) in `.env` |
| The header says **API down** | The server isn't running or is restarting: `docker compose ps`, `docker compose logs server` |
| Server logs `password authentication failed` after changing `POSTGRES_PASSWORD` | Postgres only reads it when the volume is first created. Change it in the database too: `docker compose exec db psql -U reviewinsight -c "ALTER USER reviewinsight PASSWORD '<new>'"` |
| Analyse fails with an authentication error | Check `ANTHROPIC_API_KEY` in `.env`, then `docker compose up -d server` |
| "Analysis is already running for this app" | One analysis per app at a time; wait for the current one to finish |
| Fetch says "no reviews found; check the Play ID" | The store ID is wrong, or the app has no reviews in `DEFAULT_COUNTRY` |

## Data sources

Both are unofficial: `google-play-scraper` for Google Play, and Apple's customer-reviews RSS feed for the App Store (at most ~500 recent reviews per country). The fetchers wait 1 s between pages. This is for personal research — don't redistribute raw review text.
