"""Google Play review fetcher (unofficial google-play-scraper)."""

import time
from datetime import timezone

from google_play_scraper import Sort, reviews

from app.fetchers.models import FetchedReview

PAGE_SIZE = 100
PAGE_DELAY_S = 1.0


def fetch_play_reviews(
    play_id: str,
    count: int = 200,
    lang: str = "en",
    country: str = "ca",
    known_ids: set[str] | None = None,
) -> list[FetchedReview]:
    """Fetch up to `count` newest reviews, paginating with the continuation token.

    Stops early once a whole page is already in `known_ids` (incremental fetch).
    """
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
        page: list[FetchedReview] = []
        for r in batch:
            body = (r.get("content") or "").strip()
            if not body:  # rating-only reviews are never stored
                continue
            page.append(
                FetchedReview(
                    store="play",
                    store_review_id=r["reviewId"],
                    rating=r.get("score"),
                    title=None,
                    body=body,
                    app_version=r.get("reviewCreatedVersion"),
                    country=country,
                    # the scraper returns naive *local* time (datetime.fromtimestamp)
                    review_date=r["at"].astimezone(timezone.utc) if r.get("at") else None,
                )
            )
        out.extend(page)
        if known_ids is not None and page and all(r.store_review_id in known_ids for r in page):
            break
        if not batch or token is None or token.token is None:
            break
        time.sleep(PAGE_DELAY_S)
    return out[:count]
