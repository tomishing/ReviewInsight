"""{ data, error } response envelope."""

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None}


def fail(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"data": None, "error": message})
