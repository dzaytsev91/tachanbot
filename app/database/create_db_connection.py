import sqlite3
from collections.abc import Callable
from pathlib import Path


def _create_initial_schema(conn: sqlite3.Connection) -> None:
    statements = [
        "CREATE TABLE IF NOT EXISTS memes_posts_v2 (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, user_id int, username string, old_hat_votes int, flood_thread_message_id int, memes_thread_message_id int, channel_message_id int, hash string, channel_up_votes int, channel_down_votes int)",
        "CREATE TABLE IF NOT EXISTS user_messages (user_id int, message_id int, message_thread_id int, created_at timestamp)",
        "CREATE TABLE IF NOT EXISTS users (user_id int, username string, active bool, joined_date timestamp)",
        "CREATE TABLE IF NOT EXISTS user_votes (user_id int, meme_id int, constraint user_votes_pk unique (user_id, meme_id))",
        "CREATE TABLE IF NOT EXISTS music_votes (user_id int, music_id int, constraint user_music_votes_pk unique (user_id, music_id))",
        "CREATE TABLE IF NOT EXISTS music_posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, user_id int, username string, old_hat_votes int, flood_thread_message_id int, music_thread_message_id int)",
        "CREATE TABLE IF NOT EXISTS dank_boss_titles (user_id int PRIMARY KEY, old_title string, assigned_at timestamp)",
        """CREATE TABLE IF NOT EXISTS job_runs (
            job_name text NOT NULL,
            period text NOT NULL,
            status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
            started_at timestamp NOT NULL,
            finished_at timestamp,
            error text,
            PRIMARY KEY (job_name, period)
        )""",
    ]
    for statement in statements:
        conn.execute(statement)


MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (1, _create_initial_schema),
)


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    for version, migration in MIGRATIONS:
        if version in applied:
            continue
        with conn:
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
            )


def init_db(db_name: str) -> sqlite3.Connection:
    if db_name != ":memory:" and not db_name.startswith("file:"):
        Path(db_name).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_name,
        timeout=10,
        check_same_thread=False,
        uri=db_name.startswith("file:"),
    )
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    _migrate(conn)
    return conn
