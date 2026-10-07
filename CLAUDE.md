# CLAUDE.md — ReviewInsight

## Purpose

Personal tool to analyse Google Play and App Store reviews of competitor budgeting apps, to guide the design of **PopNickel** (household expense app — see `../FinancialApp/specification.md`).

For each app, extract from the user's perspective:
- **Pain points** — complaints, bugs, frustrations
- **Positive points** — what users love
- **Feature requests** — what users ask for
- **Sentiment** — positive / neutral / negative, and trend over time

Single user, runs locally with Docker. No sign-up, no payments, no public hosting.

**Read `SPEC.md`** for target apps, data sources, database schema, analysis pipeline, API design, and frontend pages. Read it before starting any phase.

## Tech stack

### Frontend
- **React 18** + Vite (HMR dev server)
- **Tailwind CSS** for styling
- **React Router v6** for navigation
- **Zustand** for state management
- **Recharts** for data visualization
- **date-fns** for date manipulation

### Backend
- **Python 3.12** + **FastAPI** (same as PopNickel)
- **PostgreSQL 17** with **psycopg 3** (connection pool singleton)
- **Pydantic** for request validation and LLM-output validation
- **CORS** enabled for the client origin
- **google-play-scraper** (Python) — Google Play reviews
- **httpx** — Apple RSS customer-reviews JSON feed
- **anthropic** SDK — `claude-haiku-4-5` for per-review extraction; stronger model only for theme clustering if needed

### Infrastructure
- **Docker** + **Docker Compose** (3 services: `db`, `server`, `client`)
- Environment-based configuration (`.env`, never committed; `.env.example` provided)

## Project structure

```
review-insight/
├── client/                 # React frontend
│   ├── src/
│   │   ├── api/           # fetch wrappers for API endpoints
│   │   ├── components/    # LoadingSpinner, ErrorState, EmptyState, charts
│   │   ├── pages/         # Apps, AppDetail, Compare
│   │   ├── store/         # Zustand stores (apps, summary, themes)
│   │   ├── App.jsx        # Router setup
│   │   └── index.css      # Tailwind imports
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── server/                # FastAPI
│   ├── app/
│   │   ├── routes/       # apps, reviews, analysis, summary, compare, export
│   │   ├── fetchers/     # play.py, appstore.py
│   │   ├── analysis/     # extract.py, cluster.py, prompts.py
│   │   ├── db/           # pool singleton + migrations/*.sql
│   │   └── main.py       # FastAPI app entry
│   ├── scripts/          # analyse_app.py (Phase 1 MVP)
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml    # 3 services + pgdata volume
├── .env.example
├── CLAUDE.md
└── SPEC.md
```

Ports: client `3000`, API `4000`, Postgres `5432`.

## Environment variables

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — database config; `POSTGRES_PASSWORD` is required (no default), generate with `openssl rand -hex 16`
- `DATABASE_URL` — connection string for the server
- `ANTHROPIC_API_KEY` — Claude API
- `EXTRACT_MODEL` — per-review extraction model, default `claude-haiku-4-5`
- `CLUSTER_MODEL` — theme clustering model, defaults to `EXTRACT_MODEL`
- `DEFAULT_COUNTRY=ca`, `DEFAULT_LANG=en`
- `VITE_API_URL` — default `http://localhost:4000`
- `PORT` — server port, default `4000`
- `CLIENT_PORT`, `DB_PORT` — host ports for client / Postgres, bound to 127.0.0.1 only, default `3000` / `5432` (change if taken; keep `VITE_API_URL` in sync with `PORT`)

## Development phases

Build one phase at a time; run and check before moving on.

1. **Script MVP** — `server/scripts/analyse_app.py <play_id>`: fetch → extract → cluster → print Markdown report. No DB, no UI.
2. **Scaffold** — `client/` (Vite React + Tailwind) and `server/` (FastAPI), Docker Compose with 3 services, `.env.example`.
3. **Database** — `001_init.sql` migration, auto-run on server start; psycopg pool singleton; seed apps.
4. **Fetchers** — Play and App Store fetchers + `/fetch` route with dedupe.
5. **Analysis** — extract + cluster + `/analyse` route, run logging.
6. **Frontend: Apps + App detail pages**.
7. **Compare page + Markdown export**.
8. **Polish** — error / loading / empty states, README.

## Conventions

- Python: type hints, Pydantic models for all LLM output, `ruff` formatting.
- All SQL uses parameterized queries.
- React: functional components, one Zustand store per resource.
- If a change alters the schema, API, or pages, update `SPEC.md` in the same step.
- Keep it simple — personal research tool, not a product.
