"""Store listing details: rating, price, in-app purchases, ads.

Google Play via google-play-scraper; App Store via the iTunes Lookup API plus the in-app
purchase list embedded in the apps.apple.com page (unofficial; returns None if it changes).
"""

import json
import re

import httpx
from google_play_scraper import app as play_app
from google_play_scraper.exceptions import NotFoundError
from pydantic import BaseModel

LOOKUP_URL = "https://itunes.apple.com/lookup"
PAGE_URL = "https://apps.apple.com/{country}/app/id{app_id}"
# The page serialises its data as JSON; the IAP list follows this annotation title.
IAP_MARKER = re.compile(r'"title":"In-App Purchases","summary":"[^"]*","items":')
HAS_IAP = re.compile(r'"hasInAppPurchases":(true|false)')
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


class InAppItem(BaseModel):
    name: str
    price: str  # as shown, e.g. "$18.49"
    amount: float | None  # parsed from price, for sorting


class StoreInfo(BaseModel):
    url: str | None
    rating: float | None
    rating_count: int | None
    histogram: list[int] | None  # 1★..5★ counts (Play only)
    installs: str | None  # e.g. "1,000,000+" (Play only)
    price: float  # 0 = free to download
    currency: str | None
    offers_iap: bool | None
    iap_range: str | None  # e.g. "$18.99 - $149.99 per item" (Play only)
    iap_items: list[InAppItem] | None  # named purchases (App Store only)
    contains_ads: bool | None  # Play only


def _amount(price: str) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", price)
    return float(m.group().replace(",", "")) if m else None


def fetch_play_info(play_id: str, lang: str = "en", country: str = "ca") -> StoreInfo:
    try:
        d = play_app(play_id, lang=lang, country=country)
    except NotFoundError:
        raise LookupError("app not found; check the Play ID") from None
    return StoreInfo(
        url=d.get("url"),
        rating=d.get("score"),
        rating_count=d.get("ratings"),
        histogram=d.get("histogram"),
        installs=d.get("installs"),
        price=d.get("price") or 0,
        currency=d.get("currency"),
        offers_iap=d.get("offersIAP"),
        iap_range=d.get("inAppProductPrice"),
        iap_items=None,
        contains_ads=d.get("containsAds"),
    )


def _parse_iap(html: str) -> list[InAppItem] | None:
    m = IAP_MARKER.search(html)
    if not m:
        return None
    try:
        items, _ = json.JSONDecoder().raw_decode(html, m.end())
    except ValueError:
        return None
    seen: set[tuple[str, str]] = set()
    out: list[InAppItem] = []
    for it in items:
        if it.get("$kind") != "textPair":  # skips the "Learn More" button
            continue
        key = (it.get("leadingText") or "", it.get("trailingText") or "")
        if key in seen or not all(key):  # Apple repeats items per offer
            continue
        seen.add(key)
        out.append(InAppItem(name=key[0], price=key[1], amount=_amount(key[1])))
    return sorted(out, key=lambda i: (i.amount is None, i.amount))


def fetch_appstore_info(appstore_id: str, country: str = "ca") -> StoreInfo:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        resp = client.get(LOOKUP_URL, params={"id": appstore_id, "country": country})
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            raise LookupError(f"app not found in the {country} store; check the App Store ID")
        d = results[0]
        iap_items, offers_iap = None, None
        try:
            page = client.get(
                PAGE_URL.format(country=country, app_id=appstore_id),
                headers={"User-Agent": BROWSER_UA},
            )
            page.raise_for_status()
            iap_items = _parse_iap(page.text)
            if has := HAS_IAP.search(page.text):
                offers_iap = has.group(1) == "true"
            elif iap_items is not None:
                offers_iap = bool(iap_items)
        except httpx.HTTPError:
            pass  # the in-app list is a best-effort extra
    return StoreInfo(
        url=d.get("trackViewUrl"),
        rating=d.get("averageUserRating"),
        rating_count=d.get("userRatingCount"),
        histogram=None,
        installs=None,
        price=d.get("price") or 0,
        currency=d.get("currency"),
        offers_iap=offers_iap,
        iap_range=None,
        iap_items=iap_items,
        contains_ads=None,
    )
