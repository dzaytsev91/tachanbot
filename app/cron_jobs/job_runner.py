from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_once(
    conn: sqlite3.Connection,
    job_name: str,
    period: str,
    action: Callable[[], None],
) -> bool:
    """Run an externally visible job at most once for a reporting period.

    A claim is retained after failures because Telegram does not offer an
    idempotency key: automatically retrying could send duplicate messages or
    repeat administrative actions. Failed jobs can be consciously reset in the
    database after their effects have been inspected.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with conn:
            conn.execute(
                "INSERT INTO job_runs (job_name, period, status, started_at) VALUES (?, ?, 'running', ?)",
                (job_name, period, now),
            )
    except sqlite3.IntegrityError:
        logger.info(
            "Skipping %s for %s: the period is already claimed", job_name, period
        )
        return False

    try:
        action()
    except Exception as error:
        with conn:
            conn.execute(
                "UPDATE job_runs SET status = 'failed', finished_at = ?, error = ? WHERE job_name = ? AND period = ?",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    str(error)[:2000],
                    job_name,
                    period,
                ),
            )
        raise

    with conn:
        conn.execute(
            "UPDATE job_runs SET status = 'succeeded', finished_at = ? WHERE job_name = ? AND period = ?",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                job_name,
                period,
            ),
        )
    return True
