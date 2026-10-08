"""Cross-app comparison: theme groups × apps."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException

from app.analysis.compare import ThemeRef, group_themes
from app.analysis.extract import Usage
from app.db.pool import get_pool
from app.envelope import ok
from app.routes.analysis import _anthropic, _models, _run_result, _start_run, _update_run
from app.routes.summary import REVIEW_FILTER, filter_params

router = APIRouter(prefix="/api/compare", tags=["compare"])

ThemeType = Literal["pain", "positive", "request"]
TYPES: tuple[ThemeType, ...] = ("pain", "positive", "request")
_LOCK_NS = 3  # advisory-lock namespace for "comparison being rebuilt"
_FIELD = {"pain": "pain_points", "positive": "positives", "request": "requests"}


def build_matrix(theme_type: ThemeType) -> dict[str, Any]:
    """The stored comparison for one type, plus whether it is out of date."""
    with get_pool().connection() as conn:
        apps = conn.execute(
            """SELECT a.id, a.name,
                      (SELECT count(*) FROM review_analysis ra JOIN reviews r ON r.id = ra.review_id
                        WHERE r.app_id = a.id) AS analysed
                 FROM apps a
                WHERE EXISTS (SELECT 1 FROM themes t
                               WHERE t.app_id = a.id AND t.type = %s AND NOT t.generic)
                ORDER BY lower(a.name)""",
            (theme_type,),
        ).fetchall()
        # Distinct reviews per (group, app): a review in two themes of one group counts once.
        cells = conn.execute(
            """SELECT g.id AS group_id, t.app_id, count(DISTINCT rid) AS review_count,
                      json_agg(DISTINCT jsonb_build_object(
                        'id', t.id, 'label', t.label, 'review_count', t.review_count)) AS themes
                 FROM compare_groups g
                 JOIN compare_group_themes gt ON gt.group_id = g.id
                 JOIN themes t ON t.id = gt.theme_id
                 CROSS JOIN LATERAL unnest(t.review_ids) AS rid
                WHERE g.type = %s
                GROUP BY g.id, t.app_id""",
            (theme_type,),
        ).fetchall()
        groups = conn.execute(
            "SELECT id, label, description FROM compare_groups WHERE type = %s", (theme_type,)
        ).fetchall()
        meta = conn.execute(
            """SELECT (SELECT max(created_at) FROM compare_groups WHERE type = %(t)s) AS built_at,
                      (SELECT count(*) FROM themes t
                        WHERE t.type = %(t)s AND NOT t.generic
                          AND NOT EXISTS (SELECT 1 FROM compare_group_themes gt
                                           WHERE gt.theme_id = t.id)) AS unmatched""",
            {"t": theme_type},
        ).fetchone()

    analysed = {a["id"]: a["analysed"] for a in apps}
    by_group: dict[int, dict[int, dict[str, Any]]] = {}
    for c in cells:
        n = analysed.get(c["app_id"]) or 0
        by_group.setdefault(c["group_id"], {})[c["app_id"]] = {
            "review_count": c["review_count"],
            "share": round(c["review_count"] / n, 4) if n else 0,
            "themes": sorted(c["themes"], key=lambda t: -t["review_count"]),
        }
    rows = []
    for g in groups:
        g_cells = by_group.get(g["id"])
        if not g_cells:  # every member theme was replaced by re-clustering
            continue
        rows.append(
            {
                **g,
                "apps_count": len(g_cells),
                "total_reviews": sum(c["review_count"] for c in g_cells.values()),
                "cells": {str(app_id): cell for app_id, cell in g_cells.items()},
            }
        )
    # By reach, then by review volume (shares from tiny samples, e.g. 1 of 5 reviews, shouldn't lead).
    rows.sort(key=lambda r: (-r["apps_count"], -r["total_reviews"], r["label"]))
    return {
        "type": theme_type,
        "apps": apps,
        "groups": rows,
        "built_at": meta["built_at"],
        "unmatched_themes": meta["unmatched"],
        "stale": meta["unmatched"] > 0,
    }


@router.get("")
def compare(type: ThemeType = "pain") -> dict[str, Any]:  # noqa: A002 — matches ?type=
    return ok(build_matrix(type))


def _rebuild(theme_type: ThemeType, model: str) -> dict[str, Any]:
    with get_pool().connection() as conn:
        themes = [
            ThemeRef(**r)
            for r in conn.execute(
                """SELECT t.id AS theme_id, a.name AS app_name, t.label, t.description
                     FROM themes t JOIN apps a ON a.id = t.app_id
                    WHERE t.type = %s AND NOT t.generic
                    ORDER BY lower(a.name), t.review_count DESC""",
                (theme_type,),
            ).fetchall()
        ]
    usage = Usage()
    if not themes:
        with get_pool().connection() as conn:
            conn.execute("DELETE FROM compare_groups WHERE type = %s", (theme_type,))
        return _run_result(None, "skipped", 0, usage, "no themes to compare")

    run_id = _start_run(None, "compare")
    try:
        groups = group_themes(_anthropic(), model, theme_type, themes, usage)
        with get_pool().connection() as conn, conn.transaction():
            conn.execute("DELETE FROM compare_groups WHERE type = %s", (theme_type,))
            for g in groups:
                gid = conn.execute(
                    """INSERT INTO compare_groups (type, label, description)
                       VALUES (%s, %s, %s) RETURNING id""",
                    (theme_type, g.label, g.description),
                ).fetchone()["id"]
                conn.cursor().executemany(
                    """INSERT INTO compare_group_themes (group_id, theme_id) VALUES (%s, %s)
                       ON CONFLICT DO NOTHING""",
                    [(gid, tid) for tid in g.theme_ids],
                )
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
        _update_run(run_id, 0, usage, "error", error)
        return _run_result(run_id, "error", 0, usage, error)
    _update_run(run_id, len(groups), usage, "ok")
    return _run_result(run_id, "ok", len(groups), usage, None)


@router.post("/refresh")
def refresh(type: ThemeType | None = None) -> dict[str, Any]:  # noqa: A002
    """Rebuild the comparison for one type (or all three) with the clustering model."""
    _, model = _models()
    results: dict[str, Any] = {}
    with get_pool().connection() as lock_conn:
        lock_conn.autocommit = True
        if not lock_conn.execute(
            "SELECT pg_try_advisory_lock(%s, 0) AS got", (_LOCK_NS,)
        ).fetchone()["got"]:
            lock_conn.autocommit = False
            raise HTTPException(409, "The comparison is already being rebuilt")
        try:
            for t in [type] if type else TYPES:
                results[t] = _rebuild(t, model)
        finally:
            lock_conn.execute("SELECT pg_advisory_unlock(%s, 0)", (_LOCK_NS,))
            lock_conn.autocommit = False
    status = "error" if any(r["status"] == "error" for r in results.values()) else "ok"
    return ok({"status": status, "runs": results})


@router.get("/groups/{group_id}/reviews")
def group_reviews(group_id: int, app_id: int) -> dict[str, Any]:
    """The original reviews behind one cell: one app's themes in one group."""
    with get_pool().connection() as conn:
        group = conn.execute(
            "SELECT id, type, label, description FROM compare_groups WHERE id = %s", (group_id,)
        ).fetchone()
        if group is None:
            raise HTTPException(404, f"Comparison group {group_id} not found")
        app = conn.execute("SELECT name FROM apps WHERE id = %s", (app_id,)).fetchone()
        if app is None:
            raise HTTPException(404, f"App {app_id} not found")
        rows = conn.execute(
            f"""SELECT DISTINCT ON (r.review_date, r.id)
                       r.id, r.store, r.rating, r.title, r.body, r.app_version, r.country,
                       r.review_date, ra.sentiment, ra.{_FIELD[group["type"]]} AS phrases
                  FROM compare_group_themes gt
                  JOIN themes t ON t.id = gt.theme_id AND t.app_id = %(app_id)s
                  CROSS JOIN LATERAL unnest(t.review_ids) AS rid
                  JOIN reviews r ON r.id = rid AND {REVIEW_FILTER}
                  LEFT JOIN review_analysis ra ON ra.review_id = r.id
                 WHERE gt.group_id = %(group_id)s
                 ORDER BY r.review_date DESC NULLS LAST, r.id DESC""",
            {"group_id": group_id, "app_id": app_id, **filter_params(None, None, None)},
        ).fetchall()
    theme = {**group, "label": f"{group['label']} — {app['name']}", "app_id": app_id}
    return ok({"theme": theme, "reviews": rows})
