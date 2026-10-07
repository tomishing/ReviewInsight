"""psycopg connection pool singleton."""

import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        pool = ConnectionPool(
            url,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            # Test connections on checkout so a database restart doesn't fail the next request.
            check=ConnectionPool.check_connection,
            open=False,
        )
        try:
            pool.open(wait=True, timeout=30)
        except Exception:
            pool.close()  # stop its background reconnect workers
            raise
        _pool = pool  # only keep it once it opened successfully
    return _pool


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("database pool is not open")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
