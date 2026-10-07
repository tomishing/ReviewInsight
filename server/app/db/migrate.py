"""Apply migrations/*.sql in filename order, each once, each in its own transaction."""

import logging
from pathlib import Path

from psycopg_pool import ConnectionPool

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_LOCK_ID = 7_315_001  # arbitrary; serialises concurrent server starts

log = logging.getLogger("uvicorn.error")


def run_migrations(pool: ConnectionPool) -> list[str]:
    applied_now: list[str] = []
    with pool.connection() as conn:
        # Autocommit so each conn.transaction() below is a real transaction, not a savepoint.
        conn.autocommit = True
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                     filename TEXT PRIMARY KEY,
                     applied_at TIMESTAMPTZ DEFAULT now()
                   )"""
            )
            done = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
                    )
                log.info("Applied migration %s", path.name)
                applied_now.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
            conn.autocommit = False  # hand the connection back to the pool as found
    return applied_now
