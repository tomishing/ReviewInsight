"""Google Play review fetcher (unofficial google-play-scraper)."""

import time
from datetime import datetime

from google_play_scraper import Sort, reviews
from pydantic import BaseModel

PAGE_SIZE = 100
PAGE_DELAY_S = 1.0


class FetchedReview(BaseModel):
    store: str
    store_review_id: str
    rating: int | None
    title: str | None
    body: str
    app_version: str | None
    country: str
    review_date: datetime | None


def fetch_play_reviews(
    play_id: str, count: int = 200, lang: str = "en", country: str = "ca"
) -> list[FetchedReview]:
    """Fetch up to `count` newest reviews, paginating with the continuation token."""
    out: list[FetchedReview] = []
    token = None
    while len(out) < count:
        batch, token = reviews(
            play_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=min(PAGE_SIZE, count - len(out)),
            continuation_token=token,
        )
        for r in batch:
            body = (r.get("content") or "").strip()
            if not body:
                continue
            out.append(
                FetchedReview(
                    store="play",
                    store_review_id=r["reviewId"],
                    rating=r.get("score"),
                    title=None,
                    body=body,
                    app_version=r.get("reviewCreatedVersion"),
                    country=country,
                    review_date=r.get("at"),
                )
            )
        if not batch or token is None or token.token is None:
            break
        time.sleep(PAGE_DELAY_S)
    return out[:count]
