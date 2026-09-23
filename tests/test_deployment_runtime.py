from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import AppConfig
from app.cron_jobs import weekly_report
from app.cron_jobs.backup_database import BACKUPS_TO_KEEP, create_backup
from app.cron_jobs.cron_job import send_top_memes
from app.cron_jobs.cron_job_message_count import send_inactive_users
from app.cron_jobs.cron_job_old_hats import send_old_hat_winner
from app.cron_jobs.job_runner import run_once
from app.cron_jobs.periods import current_week_key, previous_week
from app.database.create_db_connection import init_db

VALID_ENV = {
    "BOT_TOKEN": "test-token",
    "MEMES_CHAT_ID": "-1001",
    "MEMES_THREAD_ID": "10",
    "FLOOD_THREAD_ID": "11",
    "MUSIC_THREAD_ID": "12",
    "EXTERNAL_CHANNEL_CHAT_ID": "-1002",
}


class TestConfig(unittest.TestCase):
    def test_loads_required_values_and_defaults(self):
        with patch.dict(os.environ, VALID_ENV, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(config.memes_chat_id, -1001)
        self.assertEqual(config.chat_creator_id, 43529628)
        self.assertEqual(config.db_path, "memes.db")

    def test_missing_secret_fails_fast(self):
        env = VALID_ENV | {"BOT_TOKEN": ""}
        with (
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(ValueError, "BOT_TOKEN is required"),
        ):
            AppConfig.from_env()

    def test_invalid_id_fails_fast(self):
        env = VALID_ENV | {"MEMES_CHAT_ID": "not-an-id"}
        with (
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(ValueError, "MEMES_CHAT_ID must be an integer"),
        ):
            AppConfig.from_env()


class TestDatabase(unittest.TestCase):
    def test_initializes_migrations_and_runtime_pragmas(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "memes.db"
            conn = init_db(str(path))
            try:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertIn("memes_posts_v2", tables)
                self.assertIn("job_runs", tables)
                self.assertEqual(
                    conn.execute("PRAGMA journal_mode").fetchone()[0], "wal"
                )
                self.assertEqual(
                    conn.execute("PRAGMA busy_timeout").fetchone()[0], 10000
                )
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[
                        0
                    ],
                    1,
                )
            finally:
                conn.close()

            reopened = init_db(str(path))
            try:
                self.assertEqual(
                    reopened.execute(
                        "SELECT COUNT(*) FROM schema_migrations"
                    ).fetchone()[0],
                    1,
                )
            finally:
                reopened.close()

    def test_migrates_an_existing_database_without_losing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memes.db"
            legacy = sqlite3.connect(path)
            legacy.execute("CREATE TABLE users (user_id int, username text)")
            legacy.execute("INSERT INTO users VALUES (1, 'alice')")
            legacy.commit()
            legacy.close()

            conn = init_db(str(path))
            try:
                self.assertEqual(
                    conn.execute(
                        "SELECT username FROM users WHERE user_id=1"
                    ).fetchone(),
                    ("alice",),
                )
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT name FROM sqlite_master WHERE name='job_runs'"
                    ).fetchone()
                )
            finally:
                conn.close()


class TestPeriods(unittest.TestCase):
    def test_previous_week_uses_closed_open_monday_boundaries(self):
        period = previous_week(date(2026, 9, 23))
        self.assertEqual(period.start, date(2026, 9, 14))
        self.assertEqual(period.end, date(2026, 9, 21))
        self.assertEqual(period.key, "2026-09-14_2026-09-21")

    def test_current_week_key_is_stable_through_week(self):
        self.assertEqual(current_week_key(date(2026, 9, 21)), "2026-09-21")
        self.assertEqual(current_week_key(date(2026, 9, 27)), "2026-09-21")


class TestJobRunner(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_successful_job_runs_only_once(self):
        action = MagicMock()
        self.assertTrue(run_once(self.conn, "report", "week-1", action))
        self.assertFalse(run_once(self.conn, "report", "week-1", action))
        action.assert_called_once_with()
        self.assertEqual(
            self.conn.execute(
                "SELECT status FROM job_runs WHERE job_name='report'"
            ).fetchone(),
            ("succeeded",),
        )

    def test_failed_job_is_recorded_and_not_automatically_retried(self):
        action = MagicMock(side_effect=RuntimeError("telegram failed"))
        with self.assertRaisesRegex(RuntimeError, "telegram failed"):
            run_once(self.conn, "report", "week-1", action)
        self.assertFalse(run_once(self.conn, "report", "week-1", action))
        action.assert_called_once_with()
        status, error = self.conn.execute(
            "SELECT status, error FROM job_runs WHERE job_name='report'"
        ).fetchone()
        self.assertEqual(status, "failed")
        self.assertEqual(error, "telegram failed")


class TestReports(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.bot = MagicMock()
        self.start = date(2026, 9, 14)
        self.end = date(2026, 9, 21)

    def tearDown(self):
        self.conn.close()

    def _insert_meme(
        self,
        meme_id: int,
        created_at: str,
        up_votes: int,
        down_votes: int,
        old_hat_votes: int = 0,
        user_id: int = 1,
        username: str = "alice",
    ) -> None:
        self.conn.execute(
            """INSERT INTO memes_posts_v2
               (id, up_votes, down_votes, created_at, user_id, username,
                old_hat_votes, memes_thread_message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meme_id,
                up_votes,
                down_votes,
                created_at,
                user_id,
                username,
                old_hat_votes,
                meme_id + 100,
            ),
        )
        self.conn.commit()

    def test_top_memes_respects_boundaries_and_prefers_fewer_downvotes(self):
        self._insert_meme(1, "2026-09-13", 100, 0)
        self._insert_meme(2, "2026-09-14", 10, 5)
        self._insert_meme(3, "2026-09-15", 10, 1)
        self._insert_meme(4, "2026-09-21", 200, 0)

        send_top_memes(self.bot, self.conn, -1, 10, self.start, self.end)

        replies = [
            call.kwargs["reply_to_message_id"]
            for call in self.bot.send_message.call_args_list
        ]
        self.assertEqual(replies, [103, 102])
        self.assertEqual(
            [call.args[1] for call in self.bot.send_message.call_args_list],
            ["🥇", "🥈"],
        )

    def test_old_hat_report_is_quiet_without_memes(self):
        send_old_hat_winner(self.bot, self.conn, -1, 10, self.start, self.end)
        self.bot.send_message.assert_not_called()

    def test_inactive_report_skips_admins_and_unavailable_members(self):
        self.conn.executemany(
            "INSERT INTO users (user_id, username, active) VALUES (?, ?, 1)",
            [(1, "alice"), (2, "admin"), (3, "gone")],
        )
        self.conn.commit()
        member = MagicMock()
        member.status = "member"
        admin = MagicMock()
        admin.status = "administrator"
        self.bot.get_chat_member.side_effect = [member, admin, RuntimeError("gone")]

        send_inactive_users(
            self.bot,
            self.conn,
            -1,
            10,
            datetime.now(timezone.utc) - timedelta(days=14),
        )

        text = self.bot.send_message.call_args.args[1]
        self.assertIn("alice", text)
        self.assertNotIn("admin", text)
        self.assertNotIn("gone", text)

    def test_inactive_report_is_quiet_when_everyone_is_active(self):
        self.conn.execute("INSERT INTO users VALUES (1, 'alice', 1, NULL)")
        self.conn.execute(
            "INSERT INTO user_messages VALUES (1, 100, 1, ?)",
            (datetime.now(timezone.utc).isoformat(sep=" "),),
        )
        self.conn.commit()

        send_inactive_users(
            self.bot,
            self.conn,
            -1,
            10,
            datetime.now(timezone.utc) - timedelta(days=14),
        )
        self.bot.send_message.assert_not_called()


class TestBackup(unittest.TestCase):
    def test_backup_is_consistent_and_old_copies_are_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            source = init_db(str(Path(directory) / "memes.db"))
            source.execute("INSERT INTO users VALUES (1, 'alice', 1, NULL)")
            source.commit()
            backup_dir = Path(directory) / "backups"

            try:
                for day in range(BACKUPS_TO_KEEP + 2):
                    create_backup(
                        source,
                        backup_dir,
                        datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=day),
                    )
            finally:
                source.close()

            backups = sorted(backup_dir.glob("memes-*.db"))
            self.assertEqual(len(backups), BACKUPS_TO_KEEP)
            self.assertEqual(backups[0].name, "memes-20260903-000000.db")
            restored = sqlite3.connect(backups[-1])
            try:
                self.assertEqual(
                    restored.execute("SELECT username FROM users").fetchone(),
                    ("alice",),
                )
                self.assertEqual(
                    restored.execute("PRAGMA integrity_check").fetchone(), ("ok",)
                )
            finally:
                restored.close()

    def test_failed_backup_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = MagicMock()
            source.backup.side_effect = sqlite3.DatabaseError("read failed")
            backup_dir = Path(directory) / "backups"

            with self.assertRaisesRegex(sqlite3.DatabaseError, "read failed"):
                create_backup(
                    source,
                    backup_dir,
                    datetime(2026, 9, 1, tzinfo=timezone.utc),
                )

            self.assertEqual(list(backup_dir.iterdir()), [])


class TestWeeklyReportOrchestrator(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.directory.name) / "memes.db")
        self.config = AppConfig(
            bot_token="test-token",
            memes_chat_id=-1001,
            memes_thread_id=10,
            flood_thread_id=11,
            music_thread_id=12,
            external_channel_chat_id=-1002,
            chat_creator_id=1,
            db_path=self.db_path,
            backup_dir=str(Path(self.directory.name) / "backups"),
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_sections_are_each_run_once(self):
        with (
            patch.object(weekly_report.AppConfig, "from_env", return_value=self.config),
            patch.object(weekly_report.telebot, "TeleBot", return_value=MagicMock()),
            patch.object(weekly_report, "send_top_memes") as top,
            patch.object(weekly_report.MemeRatingBot, "run") as aml,
            patch.object(weekly_report, "send_old_hat_winner") as old_hat,
        ):
            weekly_report.main()
            weekly_report.main()

        top.assert_called_once()
        aml.assert_called_once()
        old_hat.assert_called_once()
        conn = init_db(self.db_path)
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM job_runs WHERE status='succeeded'"
                ).fetchone()[0],
                3,
            )
        finally:
            conn.close()

    def test_one_section_failure_does_not_block_the_others(self):
        with (
            patch.object(weekly_report.AppConfig, "from_env", return_value=self.config),
            patch.object(weekly_report.telebot, "TeleBot", return_value=MagicMock()),
            patch.object(
                weekly_report,
                "send_top_memes",
                side_effect=RuntimeError("telegram unavailable"),
            ) as top,
            patch.object(weekly_report.MemeRatingBot, "run") as aml,
            patch.object(weekly_report, "send_old_hat_winner") as old_hat,
            self.assertRaisesRegex(SystemExit, "1 weekly report section"),
        ):
            weekly_report.main()

        top.assert_called_once()
        aml.assert_called_once()
        old_hat.assert_called_once()
        conn = init_db(self.db_path)
        try:
            statuses = dict(conn.execute("SELECT job_name, status FROM job_runs"))
            self.assertEqual(statuses["weekly-top-memes"], "failed")
            self.assertEqual(statuses["weekly-aml"], "succeeded")
            self.assertEqual(statuses["weekly-old-hat"], "succeeded")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
