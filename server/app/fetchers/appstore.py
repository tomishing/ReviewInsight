"""App Store review fetcher (Apple customer-reviews RSS JSON feed, ~500 most recent per country)."""

import time
from datetime import datetime
from typing import Any

import httpx

from app.fetchers.models import FetchedReview

FEED_URL = "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
MAX_PAGES = 10  # Apple serves at most 10 pages of 50
PAGE_DELAY_S = 1.0


def _label(entry: dict[str, Any], key: str) -> str | None:
    value = entry.get(key)
    return value.get("label") if isinstance(value, dict) else None


def _parse_entry(e: dict[str, Any], country: str) -> FetchedReview | None:
    review_id = _label(e, "id")
    body = (_label(e, "content") or "").strip()
    if not review_id or not body or "im:rating" not in e:  # skip app-metadata entries
        return None
    rating = _label(e, "im:rating")
    updated = _label(e, "updated")
    return FetchedReview(
        store="appstore",
        store_review_id=review_id,
        rating=int(rating) if rating and rating.isdigit() else None,
        title=_label(e, "title"),
        body=body,
        app_version=_label(e, "im:version"),
        country=country,
        review_date=datetime.fromisoformat(updated) if updated else None,
    )


def fetch_appstore_reviews(
    appstore_id: str,
    count: int = 500,
    country: str = "ca",
    known_ids: set[str] | None = None,
) -> list[FetchedReview]:
    """Fetch up to `count` newest reviews; stops early once a whole page is in `known_ids`."""
    out: list[FetchedReview] = []
    with httpx.Client(timeout=20, headers={"User-Agent": "ReviewInsight/0.1"}) as client:
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                time.sleep(PAGE_DELAY_S)
            url = FEED_URL.format(country=country, page=page, app_id=appstore_id)
            resp = client.get(url)
            if resp.status_code == 400 and page > 1:  # past the last page
                break
            resp.raise_for_status()
            entries = resp.json().get("feed", {}).get("entry", [])
            if isinstance(entries, dict):  # a single entry is not wrapped in a list
                entries = [entries]
            batch = [r for e in entries if (r := _parse_entry(e, country))]
            if not batch:
                break
            out.extend(batch)
            if len(out) >= count:
                break
            if known_ids is not None and all(r.store_review_id in known_ids for r in batch):
                break
    return out[:count]
