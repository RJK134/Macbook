"""Postgres connection helpers using psycopg 3."""

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .config import database_url


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    """Yield a Postgres connection that auto-closes."""
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def execute(sql: str, params: tuple | dict | None = None) -> int:
    """Execute INSERT/UPDATE/DELETE and return rows affected."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def upsert_many(
    sql: str,
    rows: list[tuple],
) -> int:
    """Bulk execute parameterised SQL across many rows. Returns total rowcount."""
    if not rows:
        return 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
            conn.commit()
            return cur.rowcount


def start_scraper_run(name: str) -> str:
    """Insert a scraper_runs row with status='running' and return its id."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scraper_runs (scraper_name, status) "
                "VALUES (%s, 'running') RETURNING id",
                (name,),
            )
            run_id = cur.fetchone()["id"]
            conn.commit()
            return str(run_id)


def finish_scraper_run(
    run_id: str,
    status: str,
    fetched: int = 0,
    inserted: int = 0,
    updated: int = 0,
    skipped: int = 0,
    error: str | None = None,
    log_path: str | None = None,
) -> None:
    execute(
        """
        UPDATE scraper_runs
        SET finished_at = NOW(),
            status = %s,
            items_fetched = %s,
            items_inserted = %s,
            items_updated = %s,
            items_skipped = %s,
            error_message = %s,
            raw_log_path = %s
        WHERE id = %s
        """,
        (status, fetched, inserted, updated, skipped, error, log_path, run_id),
    )
