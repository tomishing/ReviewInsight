"""Analysis (extract + cluster) and the run log."""

import os
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.analysis.cluster import cluster_all
from app.analysis.extract import (
    DEFAULT_MODEL,
    ReviewExtraction,
    ReviewInput,
    Usage,
    extract_reviews,
)
from app.db.pool import get_pool
from app.envelope import ok
from app.routes.apps import get_app_row

router = APIRouter(prefix="/api", tags=["analysis"])

_LOCK_NS = 2  # advisory-lock namespace for "analysis running for app X"
_client: anthropic.Anthropic | None = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _models() -> tuple[str, str]:
    extract_model = os.getenv("EXTRACT_MODEL") or DEFAULT_MODEL
    return extract_model, os.getenv("CLUSTER_MODEL") or extract_model


class AnalyseIn(BaseModel):
    limit: int = Field(1000, ge=1, le=5000, description="max new reviews to extract this run")
    recluster: bool = Field(False, description="re-cluster even if no new reviews were analysed")


# --- run log helpers ---------------------------------------------------------------------


def _start_run(app_id: int, kind: str) -> int:
    with get_pool().connection() as conn:
        return conn.execute(
            "INSERT INTO analysis_runs (app_id, kind) VALUES (%s, %s) RETURNING id", (app_id, kind)
        ).fetchone()["id"]


def _update_run(
    run_id: int, items: int, usage: Usage, status: str | None = None, error: str | None = None
) -> None:
    """Record progress; with `status`, also close the run."""
    with get_pool().connection() as conn:
        conn.execute(
            """UPDATE analysis_runs
                  SET items = %s, input_tokens = %s, output_tokens = %s,
                      status = coalesce(%s, status), error = %s,
                      finished_at = CASE WHEN %s::text IS NULL THEN NULL ELSE now() END
                WHERE id = %s""",
            (items, usage.input_tokens, usage.output_tokens, status, error, status, run_id),
        )


def _run_result(run_id: int | None, status: str, items: int, usage: Usage, error: str | None):
    return {
        "run_id": run_id,
        "status": status,
        "items": items,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "error": error,
    }


# --- steps -------------------------------------------------------------------------------


def _extract(app_id: int, app_name: str, limit: int, model: str) -> dict[str, Any]:
    """Extract reviews that have no review_analysis row yet; each batch is saved as it completes."""
    with get_pool().connection() as conn:
        rows = conn.execute(
            """SELECT r.id, r.rating, r.title, r.body
                 FROM reviews r LEFT JOIN review_analysis ra ON ra.review_id = r.id
                WHERE r.app_id = %s AND ra.review_id IS NULL
                ORDER BY r.review_date DESC NULLS LAST, r.id DESC
                LIMIT %s""",
            (app_id, limit),
        ).fetchall()
    usage = Usage()
    if not rows:
        return _run_result(None, "skipped", 0, usage, "no unanalysed reviews")

    run_id = _start_run(app_id, "extract")
    saved = 0

    def save(results: list[ReviewExtraction], _done: int, _total: int) -> None:
        nonlocal saved
        with get_pool().connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """INSERT INTO review_analysis
                     (review_id, sentiment, pain_points, positives, requests, model)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (review_id) DO NOTHING""",
                [
                    (
                        int(r.review_id),
                        r.sentiment,
                        Jsonb(r.pain_points),
                        Jsonb(r.positives),
                        Jsonb(r.requests),
                        model,
                    )
                    for r in results
                ],
            )
            saved += cur.rowcount
        _update_run(run_id, saved, usage)

    inputs = [
        ReviewInput(review_id=str(r["id"]), rating=r["rating"], title=r["title"], body=r["body"])
        for r in rows
    ]
    try:
        extract_reviews(_anthropic(), model, app_name, inputs, usage, on_batch=save)
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
        _update_run(run_id, saved, usage, "error", error)
        return _run_result(run_id, "error", saved, usage, error)
    _update_run(run_id, saved, usage, "ok")
    return _run_result(run_id, "ok", saved, usage, None)


def _cluster(app_id: int, model: str) -> dict[str, Any]:
    """Cluster all analysed reviews of the app; replaces its themes in one transaction."""
    with get_pool().connection() as conn:
        rows = conn.execute(
            """SELECT ra.review_id, ra.sentiment, ra.pain_points, ra.positives, ra.requests
                 FROM review_analysis ra JOIN reviews r ON r.id = ra.review_id
                WHERE r.app_id = %s""",
            (app_id,),
        ).fetchall()
    usage = Usage()
    if not rows:
        return _run_result(None, "skipped", 0, usage, "no analysed reviews")

    run_id = _start_run(app_id, "cluster")
    extractions = [
        ReviewExtraction(
            review_id=str(r["review_id"]),
            sentiment=r["sentiment"],
            pain_points=r["pain_points"],
            positives=r["positives"],
            requests=r["requests"],
        )
        for r in rows
    ]
    try:
        themes = cluster_all(_anthropic(), model, extractions, usage)
        all_themes = [t for ts in themes.values() for t in ts]
        with get_pool().connection() as conn, conn.transaction():
            conn.execute("DELETE FROM themes WHERE app_id = %s", (app_id,))
            conn.cursor().executemany(
                """INSERT INTO themes (app_id, type, label, description, generic,
                                       review_count, review_ids, example_phrases)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        app_id,
                        t.type,
                        t.label,
                        t.description,
                        t.generic,
                        t.review_count,
                        [int(i) for i in t.review_ids],
                        t.example_phrases,
                    )
                    for t in all_themes
                ],
            )
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
        _update_run(run_id, 0, usage, "error", error)
        return _run_result(run_id, "error", 0, usage, error)
    _update_run(run_id, len(all_themes), usage, "ok")
    return _run_result(run_id, "ok", len(all_themes), usage, None)


# --- routes ------------------------------------------------------------------------------


@router.post("/apps/{app_id}/analyse")
def analyse(app_id: int, body: AnalyseIn | None = None) -> dict[str, Any]:
    body = body or AnalyseIn()
    app = get_app_row(app_id)
    extract_model, cluster_model = _models()

    # One analysis per app at a time (a double click would otherwise pay twice).
    with get_pool().connection() as lock_conn:
        lock_conn.autocommit = True
        if not lock_conn.execute(
            "SELECT pg_try_advisory_lock(%s, %s) AS got", (_LOCK_NS, app_id)
        ).fetchone()["got"]:
            lock_conn.autocommit = False
            raise HTTPException(409, "Analysis is already running for this app")
        try:
            extract = _extract(app_id, app["name"], body.limit, extract_model)
            with get_pool().connection() as conn:
                has_themes = conn.execute(
                    "SELECT EXISTS (SELECT 1 FROM themes WHERE app_id = %s) AS x", (app_id,)
                ).fetchone()["x"]
            if extract["status"] == "error":
                cluster = _run_result(None, "skipped", 0, Usage(), "extraction failed")
            elif extract["items"] or not has_themes or body.recluster:
                cluster = _cluster(app_id, cluster_model)
            else:
                cluster = _run_result(None, "skipped", 0, Usage(), "no new reviews analysed")
        finally:
            lock_conn.execute("SELECT pg_advisory_unlock(%s, %s)", (_LOCK_NS, app_id))
            lock_conn.autocommit = False

    status = "error" if "error" in (extract["status"], cluster["status"]) else "ok"
    return ok({"status": status, "extract": extract, "cluster": cluster})


@router.get("/runs")
def list_runs(app_id: int | None = None, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """SELECT r.*, a.name AS app_name
                 FROM analysis_runs r JOIN apps a ON a.id = r.app_id
                WHERE %(app_id)s::int IS NULL OR r.app_id = %(app_id)s
                ORDER BY r.started_at DESC, r.id DESC
                LIMIT %(limit)s""",
            {"app_id": app_id, "limit": limit},
        ).fetchall()
    return ok(rows)
