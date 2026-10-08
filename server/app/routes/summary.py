"""Per-app summary: totals, sentiment, monthly trend, top themes — all for one filter slice."""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query

from app.db.pool import get_pool
from app.envelope import ok
from app.routes.apps import get_app_row

router = APIRouter(prefix="/api", tags=["summary"])

Store = Literal["play", "appstore"]

# Reusable filter on a `reviews r` row. `to` is inclusive (whole day, UTC).
REVIEW_FILTER = """
      (%(store)s::text IS NULL OR r.store = %(store)s)
  AND (%(from)s::date IS NULL OR r.review_date >= %(from)s::date)
  AND (%(to)s::date IS NULL OR r.review_date < %(to)s::date + 1)
"""


def filter_params(store: Store | None, from_: date | None, to: date | None) -> dict[str, Any]:
    return {"store": store, "from": from_, "to": to}


@router.get("/apps/{app_id}/summary")
def summary(
    app_id: int,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    store: Store | None = None,
) -> dict[str, Any]:
    app = get_app_row(app_id)
    p = {"app_id": app_id, **filter_params(store, from_, to)}
    with get_pool().connection() as conn:
        conn.execute("SET LOCAL timezone = 'UTC'")  # month buckets in UTC
        totals = conn.execute(
            f"""SELECT count(*) AS reviews,
                       count(ra.review_id) AS analysed,
                       round(avg(r.rating), 2)::float AS avg_rating,
                       count(*) FILTER (WHERE ra.sentiment = 'positive') AS positive,
                       count(*) FILTER (WHERE ra.sentiment = 'neutral')  AS neutral,
                       count(*) FILTER (WHERE ra.sentiment = 'negative') AS negative,
                       min(r.review_date) AS first_review, max(r.review_date) AS last_review
                  FROM reviews r LEFT JOIN review_analysis ra ON ra.review_id = r.id
                 WHERE r.app_id = %(app_id)s AND {REVIEW_FILTER}""",
            p,
        ).fetchone()
        monthly = conn.execute(
            f"""SELECT to_char(date_trunc('month', r.review_date), 'YYYY-MM') AS month,
                       count(*) AS reviews,
                       round(avg(r.rating), 2)::float AS avg_rating,
                       count(ra.review_id) AS analysed,
                       count(*) FILTER (WHERE ra.sentiment = 'positive') AS positive,
                       count(*) FILTER (WHERE ra.sentiment = 'neutral')  AS neutral,
                       count(*) FILTER (WHERE ra.sentiment = 'negative') AS negative
                  FROM reviews r LEFT JOIN review_analysis ra ON ra.review_id = r.id
                 WHERE r.app_id = %(app_id)s AND r.review_date IS NOT NULL AND {REVIEW_FILTER}
                 GROUP BY 1 ORDER BY 1""",
            p,
        ).fetchall()
        # Theme counts are recomputed for the slice: reviews behind the theme that match the filter.
        theme_rows = conn.execute(
            f"""SELECT t.id, t.type, t.label, t.description, t.generic, t.example_phrases,
                       count(r.id) AS review_count
                  FROM themes t
                  CROSS JOIN LATERAL unnest(t.review_ids) AS rid
                  JOIN reviews r ON r.id = rid AND {REVIEW_FILTER}
                 WHERE t.app_id = %(app_id)s
                 GROUP BY t.id
                 ORDER BY review_count DESC, t.label""",
            p,
        ).fetchall()
        themes_updated_at = conn.execute(
            "SELECT max(created_at) AS at FROM themes WHERE app_id = %s", (app_id,)
        ).fetchone()["at"]

    themes: dict[str, list[dict[str, Any]]] = {"pain": [], "positive": [], "request": []}
    generic: dict[str, int] = {"pain": 0, "positive": 0, "request": 0}
    for t in theme_rows:
        if t["generic"]:
            generic[t["type"]] += t["review_count"]
        else:
            themes[t["type"]].append({k: t[k] for k in t if k not in ("type", "generic")})

    sentiment = {k: totals.pop(k) for k in ("positive", "neutral", "negative")}
    return ok(
        {
            "app": app,
            "filters": {"from": from_, "to": to, "store": store},
            "totals": totals,
            "sentiment": sentiment,
            "monthly": monthly,
            "themes": themes,
            "generic": generic,
            "themes_updated_at": themes_updated_at,
        }
    )
