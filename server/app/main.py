"""FastAPI entry point. All responses use the { data, error } envelope."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db.migrate import run_migrations
from app.db.pool import close_pool, get_pool, open_pool
from app.envelope import fail, ok
from app.routes import analysis, apps, reviews, summary


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    pool = open_pool()
    run_migrations(pool)
    with pool.connection() as conn:  # runs cut off by a restart would otherwise stay 'running'
        conn.execute(
            """UPDATE analysis_runs SET status = 'error', error = 'Interrupted by server restart',
                      finished_at = now() WHERE status = 'running'"""
        )
    yield
    close_pool()


app = FastAPI(title="ReviewInsight API", lifespan=lifespan)


# Catch-all as middleware (not an exception handler) so it runs inside CORSMiddleware
# and 500 responses still carry CORS headers the browser can read.
@app.middleware("http")
async def unhandled_error(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001
        return fail(500, f"{type(exc).__name__}: {exc}")


_origin = os.getenv("CLIENT_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    # The browser treats localhost and 127.0.0.1 as different origins; accept both.
    allow_origins=list(
        {
            _origin,
            _origin.replace("://localhost", "://127.0.0.1"),
            _origin.replace("://127.0.0.1", "://localhost"),
        }
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return fail(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return fail(422, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


app.include_router(apps.router)
app.include_router(reviews.router)
app.include_router(analysis.router)
app.include_router(summary.router)


@app.get("/api/health")
def health() -> dict[str, Any]:
    with get_pool().connection() as conn:
        conn.execute("SELECT 1")
    return ok({"status": "ok", "db": "ok"})
