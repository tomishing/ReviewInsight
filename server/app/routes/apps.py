"""Apps CRUD."""

from typing import Any

from fastapi import APIRouter, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field, field_validator

from app.db.pool import get_pool
from app.envelope import ok

router = APIRouter(prefix="/api/apps", tags=["apps"])

# Review counts, analysed count, last successful fetch and the latest run of any kind.
APP_SELECT = """
SELECT a.id, a.name, a.play_id, a.appstore_id, a.notes, a.created_at,
       count(r.id) FILTER (WHERE r.store = 'play')     AS play_reviews,
       count(r.id) FILTER (WHERE r.store = 'appstore') AS appstore_reviews,
       count(ra.review_id)                             AS analysed_reviews,
       (SELECT max(finished_at) FROM analysis_runs
         WHERE app_id = a.id AND kind = 'fetch' AND status IN ('ok', 'partial')) AS last_fetched_at,
       (SELECT row_to_json(x) FROM (
          SELECT id, kind, status, items, error, started_at, finished_at
            FROM analysis_runs WHERE app_id = a.id
           ORDER BY started_at DESC, id DESC LIMIT 1) x)                       AS last_run
  FROM apps a
  LEFT JOIN reviews r          ON r.app_id = a.id
  LEFT JOIN review_analysis ra ON ra.review_id = r.id
"""


class AppIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    play_id: str | None = None
    appstore_id: str | None = None
    notes: str | None = None

    @field_validator("name", "play_id", "appstore_id", "notes", mode="before")
    @classmethod
    def blank_to_none(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("appstore_id")
    @classmethod
    def numeric_appstore_id(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.removeprefix("id")
            if not v.isdigit():
                raise ValueError("App Store ID must be numeric, e.g. 1459319842")
        return v


class AppPatch(AppIn):
    name: str | None = Field(default=None, min_length=1, max_length=200)  # type: ignore[assignment]


def get_app_row(app_id: int) -> dict[str, Any]:
    with get_pool().connection() as conn:
        row = conn.execute(APP_SELECT + " WHERE a.id = %s GROUP BY a.id", (app_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"App {app_id} not found")
    return row


def _duplicate(e: errors.UniqueViolation) -> HTTPException:
    field = "Play ID" if "play_id" in str(e) else "App Store ID"
    return HTTPException(409, f"Another app already uses this {field}")


@router.get("")
def list_apps() -> dict[str, Any]:
    with get_pool().connection() as conn:
        rows = conn.execute(APP_SELECT + " GROUP BY a.id ORDER BY lower(a.name)").fetchall()
    return ok(rows)


@router.get("/{app_id}")
def get_app(app_id: int) -> dict[str, Any]:
    return ok(get_app_row(app_id))


@router.post("", status_code=201)
def create_app(body: AppIn) -> dict[str, Any]:
    if not body.play_id and not body.appstore_id:
        raise HTTPException(422, "Give at least a Play ID or an App Store ID")
    try:
        with get_pool().connection() as conn:
            new_id = conn.execute(
                """INSERT INTO apps (name, play_id, appstore_id, notes)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (body.name, body.play_id, body.appstore_id, body.notes),
            ).fetchone()["id"]
    except errors.UniqueViolation as e:
        raise _duplicate(e) from None
    return ok(get_app_row(new_id))


@router.put("/{app_id}")
def update_app(app_id: int, body: AppPatch) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(422, "name cannot be empty")
    current = get_app_row(app_id)
    merged = {k: changes.get(k, current[k]) for k in ("play_id", "appstore_id")}
    if not merged["play_id"] and not merged["appstore_id"]:
        raise HTTPException(422, "An app needs at least a Play ID or an App Store ID")
    if changes:
        cols = ", ".join(f"{k} = %({k})s" for k in changes)  # keys come from AppPatch fields
        try:
            with get_pool().connection() as conn:
                conn.execute(f"UPDATE apps SET {cols} WHERE id = %(id)s", {**changes, "id": app_id})
        except errors.UniqueViolation as e:
            raise _duplicate(e) from None
    return ok(get_app_row(app_id))


@router.delete("/{app_id}")
def delete_app(app_id: int) -> dict[str, Any]:
    with get_pool().connection() as conn:
        deleted = conn.execute("DELETE FROM apps WHERE id = %s RETURNING id", (app_id,)).fetchone()
    if deleted is None:
        raise HTTPException(404, f"App {app_id} not found")
    return ok({"id": app_id, "deleted": True})
