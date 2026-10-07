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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    run_migrations(open_pool())
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CLIENT_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None}


def fail(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"data": None, "error": message})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return fail(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return fail(422, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))


@app.get("/api/health")
def health() -> dict[str, Any]:
    with get_pool().connection() as conn:
        conn.execute("SELECT 1")
    return ok({"status": "ok", "db": "ok"})
