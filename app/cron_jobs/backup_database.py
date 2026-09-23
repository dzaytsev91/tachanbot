from __future__ import annotations

import logging
import sqlite3
import tempfile
from datetime import datetime
from fcntl import LOCK_EX, flock
from pathlib import Path

from app.config import AppConfig
from app.cron_jobs.periods import local_now
from app.database.create_db_connection import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKUPS_TO_KEEP = 14


def create_backup(
    source: sqlite3.Connection,
    backup_dir: str | Path,
    now: datetime | None = None,
) -> Path:
    destination_dir = Path(backup_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or local_now()).strftime("%Y%m%d-%H%M%S")
    destination = destination_dir / f"memes-{timestamp}.db"

    with (destination_dir / ".backup.lock").open("a+") as lock_file:
        flock(lock_file, LOCK_EX)
        with tempfile.NamedTemporaryFile(
            dir=destination_dir, prefix=".memes-", suffix=".tmp", delete=False
        ) as temporary_file:
            temporary = Path(temporary_file.name)
        try:
            target = sqlite3.connect(temporary)
            try:
                source.backup(target)
                result = target.execute("PRAGMA integrity_check").fetchone()
                if result != ("ok",):
                    raise RuntimeError(f"SQLite integrity check failed: {result}")
            finally:
                target.close()
        except (OSError, RuntimeError, sqlite3.Error):
            temporary.unlink(missing_ok=True)
            raise

        temporary.replace(destination)
        backups = sorted(destination_dir.glob("memes-*.db"), reverse=True)
        for old_backup in backups[BACKUPS_TO_KEEP:]:
            old_backup.unlink()
    return destination


def main() -> None:
    config = AppConfig.from_env()
    conn = init_db(config.db_path)
    try:
        destination = create_backup(conn, config.backup_dir)
    finally:
        conn.close()
    logger.info("Created verified SQLite backup: %s", destination)


if __name__ == "__main__":
    main()
