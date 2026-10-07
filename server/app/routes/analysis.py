"""Run log (fetch now; extract / cluster in Phase 5)."""

from typing import Any

from fastapi import APIRouter, Query

from app.db.pool import get_pool
from app.envelope import ok

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/runs")
def list_runs(app_id: int | None = None, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """SELECT r.*, a.name AS app_name
                 FROM analysis_runs r JOIN apps a ON a.id = r.app_id
                WHERE %(app_id)s::int IS NULL OR r.app_id = %(app_id)s
                ORDER BY r.started_at DESC, r.id DESC
                LIMIT %(limit)s""",
            {"app_id": app_id, "limit": limit},
        ).fetchall()
    return ok(rows)
