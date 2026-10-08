"""Fetch new reviews from both stores, deduplicated on (store, store_review_id)."""

import os
from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.pool import get_pool
from app.envelope import ok
from app.fetchers.appstore import fetch_appstore_reviews
from app.fetchers.models import FetchedReview
from app.fetchers.play import fetch_play_reviews
from app.routes.apps import get_app_row
from app.routes.summary import REVIEW_FILTER, Store, filter_params

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
        except LookupError as e:  # our own "check the ID" message: show it as written
            stores[store] = {"fetched": 0, "inserted": 0, "error": str(e)}
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


@router.get("/themes/{theme_id}/reviews")
def theme_reviews(
    theme_id: int,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    store: Store | None = None,
) -> dict[str, Any]:
    """The original reviews behind a theme (optionally the same filter slice as the summary)."""
    with get_pool().connection() as conn:
        theme = conn.execute(
            """SELECT id, app_id, type, label, description, generic, review_count, example_phrases
                 FROM themes WHERE id = %s""",
            (theme_id,),
        ).fetchone()
        if theme is None:
            raise HTTPException(404, f"Theme {theme_id} not found")
        field = {"pain": "pain_points", "positive": "positives", "request": "requests"}[
            theme["type"]
        ]
        rows = conn.execute(
            f"""SELECT r.id, r.store, r.rating, r.title, r.body, r.app_version, r.country,
                       r.review_date, ra.sentiment, ra.{field} AS phrases
                  FROM themes t
                  CROSS JOIN LATERAL unnest(t.review_ids) AS rid
                  JOIN reviews r ON r.id = rid AND {REVIEW_FILTER}
                  LEFT JOIN review_analysis ra ON ra.review_id = r.id
                 WHERE t.id = %(theme_id)s
                 ORDER BY r.review_date DESC NULLS LAST, r.id DESC""",
            {"theme_id": theme_id, **filter_params(store, from_, to)},
        ).fetchall()
    return ok({"theme": theme, "reviews": rows})
