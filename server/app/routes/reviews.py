"""Fetch new reviews from both stores, deduplicated on (store, store_review_id)."""

import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.pool import get_pool
from app.envelope import ok
from app.fetchers.appstore import fetch_appstore_reviews
from app.fetchers.models import FetchedReview
from app.fetchers.play import fetch_play_reviews
from app.routes.apps import get_app_row

router = APIRouter(prefix="/api", tags=["reviews"])

INSERT_REVIEWS = """
INSERT INTO reviews (app_id, store, store_review_id, rating, title, body, app_version, country, review_date)
SELECT %s, store, id, rating, title, body, version, country, review_date
  FROM unnest(%s::text[], %s::text[], %s::smallint[], %s::text[], %s::text[], %s::text[],
              %s::text[], %s::timestamptz[])
       AS t(store, id, rating, title, body, version, country, review_date)
ON CONFLICT (store, store_review_id) DO NOTHING
"""


_ID_LABEL = {"play": "Play ID", "appstore": "App Store ID"}


class FetchIn(BaseModel):
    count: int = Field(500, ge=1, le=2000, description="max reviews per store")
    country: str | None = Field(None, pattern=r"^[a-z]{2}$")


def _insert(app_id: int, rows: list[FetchedReview]) -> int:
    """Insert reviews, skipping ones already stored; returns the number inserted."""
    if not rows:
        return 0
    cols = list(
        zip(
            *[
                (
                    r.store,
                    r.store_review_id,
                    r.rating,
                    r.title,
                    r.body,
                    r.app_version,
                    r.country,
                    r.review_date,
                )
                for r in rows
            ]
        )
    )
    with get_pool().connection() as conn:
        cur = conn.execute(INSERT_REVIEWS, (app_id, *map(list, cols)))
        return cur.rowcount


def _known_ids(app_id: int, store: str) -> set[str]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            "SELECT store_review_id FROM reviews WHERE app_id = %s AND store = %s", (app_id, store)
        ).fetchall()
    return {r["store_review_id"] for r in rows}


@router.post("/apps/{app_id}/fetch")
def fetch_reviews(app_id: int, body: FetchIn | None = None) -> dict[str, Any]:
    body = body or FetchIn()
    app = get_app_row(app_id)
    country = body.country or os.getenv("DEFAULT_COUNTRY", "ca")
    lang = os.getenv("DEFAULT_LANG", "en")

    jobs: dict[str, Callable[[set[str]], list[FetchedReview]]] = {}
    if app["play_id"]:
        jobs["play"] = lambda known: fetch_play_reviews(
            app["play_id"], body.count, lang, country, known_ids=known
        )
    if app["appstore_id"]:
        jobs["appstore"] = lambda known: fetch_appstore_reviews(
            app["appstore_id"], body.count, country, known_ids=known
        )
    if not jobs:
        raise HTTPException(400, "App has no Play ID or App Store ID")

    with get_pool().connection() as conn:
        run_id = conn.execute(
            "INSERT INTO analysis_runs (app_id, kind) VALUES (%s, 'fetch') RETURNING id", (app_id,)
        ).fetchone()["id"]

    # One store failing must not stop the other.
    stores: dict[str, dict[str, Any]] = {}
    for store, job in jobs.items():
        try:
            known = _known_ids(app_id, store)
            # Stopping at an already-stored page is only safe once we hold `count` reviews;
            # otherwise a larger `count` would never reach older reviews.
            fetched = job(known if len(known) >= body.count else None)
            if not fetched and not known:  # both stores answer an unknown ID with an empty list
                raise LookupError(f"no reviews found; check the {_ID_LABEL[store]}")
            stores[store] = {
                "fetched": len(fetched),
                "inserted": _insert(app_id, fetched),
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            stores[store] = {"fetched": 0, "inserted": 0, "error": f"{type(e).__name__}: {e}"}

    failed = [s for s, r in stores.items() if r["error"]]
    status = "error" if len(failed) == len(stores) else "partial" if failed else "ok"
    error = "; ".join(f"{s}: {stores[s]['error']}" for s in failed) or None
    inserted = sum(r["inserted"] for r in stores.values())
    with get_pool().connection() as conn:
        conn.execute(
            """UPDATE analysis_runs SET status = %s, items = %s, error = %s, finished_at = now()
               WHERE id = %s""",
            (status, inserted, error, run_id),
        )
    return ok({"run_id": run_id, "status": status, "inserted": inserted, "stores": stores})
