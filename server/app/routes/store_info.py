"""Store listing details per app (rating, price, in-app purchases, ads) and a derived revenue model."""

import os
import re
import time
from typing import Any

from fastapi import APIRouter
from psycopg.types.json import Jsonb

from app.db.pool import get_pool
from app.envelope import ok
from app.fetchers.storeinfo import StoreInfo, fetch_appstore_info, fetch_play_info
from app.routes.apps import get_app_row

router = APIRouter(prefix="/api", tags=["store-info"])

APP_DELAY_S = 1.0  # between apps when refreshing all

# In-app purchase names → plan kind (App Store names like "Cashew Pro Yearly", "1 Month Subscription").
PLAN_PATTERNS = {
    "monthly": re.compile(r"month", re.I),
    "yearly": re.compile(r"(?<![2-9]-)(?<![2-9] )year|annual", re.I),  # not "3-Year"
    "lifetime": re.compile(r"lifetime|forever", re.I),
}
SUBSCRIPTION = re.compile(r"month|year|annual|week|subscri", re.I)

SELECT_INFO = """
SELECT a.id, a.name, a.play_id, a.appstore_id,
       (SELECT json_object_agg(s.store, json_build_object(
                 'data', s.data, 'error', s.error, 'fetched_at', s.fetched_at))
          FROM store_info s WHERE s.app_id = a.id) AS stores
  FROM apps a
"""


def _plans(items: list[dict[str, Any]]) -> dict[str, str | None]:
    """Cheapest price per plan kind, from named App Store purchases."""
    out: dict[str, str | None] = {}
    for kind, pattern in PLAN_PATTERNS.items():
        matches = [i for i in items if pattern.search(i["name"]) and i["amount"] is not None]
        out[kind] = min(matches, key=lambda i: i["amount"])["price"] if matches else None
    return out


def revenue_model(play: dict[str, Any] | None, appstore: dict[str, Any] | None) -> dict[str, Any]:
    """Derive a revenue-model label from whatever the stores report."""
    infos = [i for i in (play, appstore) if i]
    items = (appstore or {}).get("iap_items") or []
    paid = any(i["price"] > 0 for i in infos)
    iap = any(i["offers_iap"] for i in infos)
    ads = any(i["contains_ads"] for i in infos)
    plans = _plans(items)
    subscription = any(SUBSCRIPTION.search(i["name"]) for i in items)
    lifetime = plans["lifetime"] is not None

    parts = []
    if subscription:
        parts.append("subscription")
    if lifetime:
        parts.append("lifetime purchase")
    if iap and not parts:  # in-app purchases of unknown kind (e.g. Play only)
        parts.append("in-app purchases")
    if ads:
        parts.append("ads")
    if not infos:
        label = None
    else:
        base = "Paid" if paid else "Freemium" if parts and parts != ["ads"] else "Free"
        label = " · ".join([base, " + ".join(parts)]) if parts else base
    return {
        "label": label,
        "paid": paid,
        "in_app_purchases": iap,
        "subscription": subscription,
        "lifetime": lifetime,
        "ads": ads,
        "plans": plans,
    }


def _shape(row: dict[str, Any]) -> dict[str, Any]:
    stores = row.pop("stores") or {}
    row["play"] = stores.get("play")
    row["appstore"] = stores.get("appstore")
    data = {s: (row[s] or {}).get("data") for s in ("play", "appstore")}
    row["revenue_model"] = revenue_model(data["play"], data["appstore"])
    return row


def _save(app_id: int, store: str, info: StoreInfo | None, error: str | None) -> None:
    with get_pool().connection() as conn:
        # A failed refresh keeps the last good data and records the error next to it.
        conn.execute(
            """INSERT INTO store_info (app_id, store, data, error, fetched_at)
               VALUES (%s, %s, %s, %s, now())
               ON CONFLICT (app_id, store) DO UPDATE
                 SET data = COALESCE(EXCLUDED.data, store_info.data),
                     error = EXCLUDED.error,
                     fetched_at = CASE WHEN EXCLUDED.data IS NULL THEN store_info.fetched_at
                                       ELSE now() END""",
            (app_id, store, Jsonb(info.model_dump()) if info else None, error),
        )


def refresh_app(app: dict[str, Any]) -> dict[str, str | None]:
    """Refresh both stores of one app; one store failing doesn't stop the other."""
    country = os.getenv("DEFAULT_COUNTRY", "ca")
    lang = os.getenv("DEFAULT_LANG", "en")
    jobs = {}
    if app["play_id"]:
        jobs["play"] = lambda: fetch_play_info(app["play_id"], lang, country)
    if app["appstore_id"]:
        jobs["appstore"] = lambda: fetch_appstore_info(app["appstore_id"], country)
    errors: dict[str, str | None] = {}
    for store, job in jobs.items():
        try:
            _save(app["id"], store, job(), None)
            errors[store] = None
        except LookupError as e:
            errors[store] = str(e)
        except Exception as e:  # noqa: BLE001
            errors[store] = f"{type(e).__name__}: {e}"
        if errors[store]:
            _save(app["id"], store, None, errors[store])
    return errors


@router.get("/store-info")
def list_store_info() -> dict[str, Any]:
    with get_pool().connection() as conn:
        rows = conn.execute(SELECT_INFO + " ORDER BY lower(a.name)").fetchall()
    return ok({"country": os.getenv("DEFAULT_COUNTRY", "ca"), "apps": [_shape(r) for r in rows]})


@router.post("/store-info/refresh")
def refresh_all() -> dict[str, Any]:
    with get_pool().connection() as conn:
        apps = conn.execute("SELECT id, play_id, appstore_id FROM apps ORDER BY id").fetchall()
    errors = {}
    for n, app in enumerate(apps):
        if n:
            time.sleep(APP_DELAY_S)
        errors[app["id"]] = refresh_app(app)
    return ok({"refreshed": len(apps), "errors": errors})


@router.post("/apps/{app_id}/store-info/refresh")
def refresh_one(app_id: int) -> dict[str, Any]:
    errors = refresh_app(get_app_row(app_id))
    with get_pool().connection() as conn:
        row = conn.execute(SELECT_INFO + " WHERE a.id = %s", (app_id,)).fetchone()
    return ok({**_shape(row), "errors": errors})
