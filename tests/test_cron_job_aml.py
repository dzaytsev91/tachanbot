from __future__ import annotations

import sqlite3
import sys
import types
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import app.cron_jobs.cron_job_aml as mod


_real_telebot = sys.modules.get("telebot")
if _real_telebot is None:
    _fake = types.ModuleType("telebot")
    _fake.TeleBot = MagicMock
    sys.modules["telebot"] = _fake

_IS_REFACTORED = hasattr(mod, "MemeRatingBot")

CHAT_ID = -100123
FLOOD_THREAD_ID = 1
CHAT_CREATOR_ID = 43529628
MINIMUM_MEMES = getattr(mod, "MINIMUM_MEMES_COUNT", None) or getattr(
    mod, "minimum_memes_count", 5
)


def _make_member(status: str = "member", custom_title: str = "") -> MagicMock:
    m = MagicMock()
    m.status = status
    m.custom_title = custom_title
    return m


def _recent_date() -> str:
    """A date guaranteed to fall within the 'last week' query window."""
    return date.today().isoformat()


def _old_date() -> str:
    """A date guaranteed to fall outside the query window."""
    return (date.today() - timedelta(days=30)).isoformat()


def _seed_memes(conn: sqlite3.Connection, rows: list[tuple]):
    """Insert rows into memes_posts_v2.
    Each row: (user_id, username, up_votes, down_votes, created_at).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memes_posts_v2 (
            user_id    INTEGER,
            username   TEXT,
            up_votes   INTEGER,
            down_votes INTEGER,
            created_at TEXT
        )
    """
    )
    conn.executemany("INSERT INTO memes_posts_v2 VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()


def _seed_boss_titles(conn: sqlite3.Connection, rows: list[tuple]):
    """Insert rows into dank_boss_titles.
    Each row: (user_id, old_title, assigned_at).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dank_boss_titles (
            user_id     INTEGER PRIMARY KEY,
            old_title   TEXT,
            assigned_at TEXT
        )
    """
    )
    conn.executemany("INSERT INTO dank_boss_titles VALUES (?, ?, ?)", rows)
    conn.commit()


def _collect_texts(mock_bot: MagicMock) -> list[str]:
    """Extract all text arguments from send_message calls."""
    texts = []
    for c in mock_bot.send_message.call_args_list:
        # positional: send_message(chat_id, text, ...)
        if len(c.args) >= 2:
            texts.append(c.args[1])
        elif "text" in c.kwargs:
            texts.append(c.kwargs["text"])
    return texts


# ---------------------------------------------------------------------------
# Execution wrapper — hides the old-vs-new difference from every test.
# ---------------------------------------------------------------------------
def _run_main(
    conn: sqlite3.Connection,
    mock_bot: MagicMock,
    chat_creator_id: int = CHAT_CREATOR_ID,
):
    """Call main() with the given db connection and mocked bot.

    Patches differ depending on whether we have the old or new code.
    """
    if _IS_REFACTORED:
        # New code: construct MemeRatingBot, inject conn + bot, call run().
        cfg = mod.Config(
            bot_token="fake",
            memes_chat_id=CHAT_ID,
            flood_thread_id=FLOOD_THREAD_ID,
            memes_thread_id=1,
            chat_creator_id=chat_creator_id,
            db_path=":memory:",
        )
        bot_obj = mod.MemeRatingBot.__new__(mod.MemeRatingBot)
        bot_obj._config = cfg
        bot_obj._bot = mock_bot
        bot_obj._conn = conn
        bot_obj._titles = mod.TitleManager(conn, mock_bot, CHAT_ID)
        bot_obj.run()
    else:
        # Old code: patch module-level globals, call main().
        with patch.object(mod, "bot", mock_bot), patch.object(
            mod, "conn", conn
        ), patch.object(mod, "memes_chat_id", CHAT_ID), patch.object(
            mod, "flood_thread_id", FLOOD_THREAD_ID
        ), patch.object(mod, "chat_creator", chat_creator_id):
            mod.main()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestNoData(unittest.TestCase):
    """When there are no memes, the bot should stay quiet (or send an
    empty rating — both are acceptable)."""

    def test_no_memes_no_crash(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE memes_posts_v2 (
                user_id INT, username TEXT, up_votes INT,
                down_votes INT, created_at TEXT
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE dank_boss_titles (
                user_id INT PRIMARY KEY, old_title TEXT, assigned_at TEXT
            )
        """
        )
        conn.commit()
        mock_bot = MagicMock()
        mock_bot.get_chat_member.return_value = _make_member()
        _run_main(conn, mock_bot)
        # No crash is the assertion.  The old code still sends a (mostly
        # empty) rating message; the new code sends nothing.  Both are fine.
        conn.close()


class TestRatingMessage(unittest.TestCase):
    """The weekly rating message should contain the AML header, medals,
    and a separator for low-meme users."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE dank_boss_titles (
                user_id INT PRIMARY KEY, old_title TEXT, assigned_at TEXT
            )
        """
        )
        self.conn.commit()
        self.mock_bot = MagicMock()
        self.mock_bot.get_chat_member.return_value = _make_member(
            status="administrator"
        )
        self.today = _recent_date()

    def tearDown(self):
        self.conn.close()

    def _rating_text(self) -> str:
        texts = _collect_texts(self.mock_bot)
        for t in texts:
            if "AML" in t:
                return t
        self.fail("No rating message with 'AML' header found")

    def test_contains_aml_header(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        self.assertIn("AML - Average Meme Likes", self._rating_text())

    def test_top3_get_medals(self):
        rows = []
        for uid, name, ups in [(1, "a", 20), (2, "b", 15), (3, "c", 10)]:
            rows += [(uid, name, ups, 1, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        text = self._rating_text()
        self.assertIn("🥇", text)
        self.assertIn("🥈", text)
        self.assertIn("🥉", text)

    def test_users_below_minimum_shown_separately(self):
        # One user with enough memes, one without.
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        rows += [(2, "bob", 10, 0, self.today)]  # only 1 meme
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        text = self._rating_text()
        self.assertIn("alice", text)
        self.assertIn("bob", text)
        # Bob should be in the low-memes section (after the separator).
        sep_pos = text.find("не уча")  # works for both "учавствуют" and "участвуют"
        bob_pos = text.find("bob")
        self.assertGreater(
            bob_pos, sep_pos, "Low-meme user should appear after the separator"
        )

    def test_fourth_place_gets_clown(self):
        rows = []
        for uid, name, ups in [(1, "a", 20), (2, "b", 15), (3, "c", 10), (4, "d", 5)]:
            rows += [(uid, name, ups, 1, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        text = self._rating_text()
        # "d" should have the clown emoji
        d_line = [l for l in text.split("\n") if "[d]" in l]  # noqa
        self.assertTrue(d_line, "User 'd' line not found")
        self.assertIn("🤡", d_line[0])

    def test_old_data_excluded(self):
        rows = [(1, "alice", 10, 0, _old_date())] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        texts = _collect_texts(self.mock_bot)
        # Either no message at all or the rating has no user lines.
        for t in texts:
            self.assertNotIn("alice", t)


class TestPromotion(unittest.TestCase):
    """Top-3 non-admin users should be promoted."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE dank_boss_titles (
                user_id INT PRIMARY KEY, old_title TEXT, assigned_at TEXT
            )
        """
        )
        self.conn.commit()
        self.mock_bot = MagicMock()
        self.today = _recent_date()

    def tearDown(self):
        self.conn.close()

    def test_promotes_non_admin(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        self.mock_bot.get_chat_member.return_value = _make_member(status="member")
        _run_main(self.conn, self.mock_bot)
        self.mock_bot.promote_chat_member.assert_called()

    def test_skips_existing_admin(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        self.mock_bot.get_chat_member.return_value = _make_member(
            status="administrator"
        )
        _run_main(self.conn, self.mock_bot)
        self.mock_bot.promote_chat_member.assert_not_called()


class TestBossTitle(unittest.TestCase):
    """The #1 user should receive the 'Dank boss' title."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE dank_boss_titles (
                user_id INT PRIMARY KEY, old_title TEXT, assigned_at TEXT
            )
        """
        )
        self.conn.commit()
        self.mock_bot = MagicMock()
        self.mock_bot.get_chat_member.return_value = _make_member(
            status="administrator", custom_title="old title"
        )
        self.today = _recent_date()

    def tearDown(self):
        self.conn.close()

    def test_sets_dank_boss_title(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        # set_chat_administrator_custom_title should have been called
        # with "Dank boss" for the winner.
        calls = self.mock_bot.set_chat_administrator_custom_title.call_args_list
        boss_calls = [
            c for c in calls if "Dank boss" in (list(c.args) + list(c.kwargs.values()))
        ]
        self.assertTrue(boss_calls, "Expected 'Dank boss' title to be set")

    def test_celebration_message_sent(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        texts = _collect_texts(self.mock_bot)
        self.assertTrue(
            any("Почет и уважение" in t for t in texts), "Expected celebration message"
        )

    def test_saves_old_title_to_db(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        row = self.conn.execute(
            "SELECT old_title FROM dank_boss_titles WHERE user_id = 1"
        ).fetchone()
        self.assertIsNotNone(row, "Old title should be saved in DB")

    def test_restores_previous_boss_title(self):
        # Previous boss exists in DB.
        _seed_boss_titles(self.conn, [(99, "previous king", "2025-01-01")])
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot)
        # Previous boss row should be cleaned up.
        row = self.conn.execute(
            "SELECT 1 FROM dank_boss_titles WHERE user_id = 99"
        ).fetchone()
        self.assertIsNone(row, "Previous boss should be removed from DB")

    def test_skips_chat_creator(self):
        rows = [(CHAT_CREATOR_ID, "creator", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)
        _run_main(self.conn, self.mock_bot, chat_creator_id=CHAT_CREATOR_ID)
        # Should NOT set "Dank boss" title.
        calls = self.mock_bot.set_chat_administrator_custom_title.call_args_list
        boss_calls = [
            c for c in calls if "Dank boss" in (list(c.args) + list(c.kwargs.values()))
        ]
        self.assertFalse(
            boss_calls, "'Dank boss' should NOT be set for the chat creator"
        )
        # Should send the "can't assign to creator" message.
        texts = _collect_texts(self.mock_bot)
        self.assertTrue(
            any("Нельзя присвоить титул создателю" in t for t in texts),
            "Expected creator-skip message",
        )

    def test_rollback_on_title_error(self):
        """If setting the Dank boss title fails, the saved old title
        should be rolled back from the DB."""
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)

        def _side_effect(*args, **kwargs):
            title = ""
            if args:
                # positional: (chat_id, user_id, title)
                title = args[2] if len(args) > 2 else ""
            title = kwargs.get("custom_title", title)
            if title == "Dank boss":
                raise Exception("API fail")

        self.mock_bot.set_chat_administrator_custom_title.side_effect = _side_effect
        _run_main(self.conn, self.mock_bot)

        row = self.conn.execute(
            "SELECT 1 FROM dank_boss_titles WHERE user_id = 1"
        ).fetchone()
        self.assertIsNone(row, "Old title row should be rolled back after error")

    def test_error_message_on_title_failure(self):
        rows = [(1, "alice", 10, 0, self.today)] * MINIMUM_MEMES
        _seed_memes(self.conn, rows)

        def _side_effect(*args, **kwargs):
            title = ""
            if args:
                title = args[2] if len(args) > 2 else ""
            title = kwargs.get("custom_title", title)
            if title == "Dank boss":
                raise Exception("API fail")

        self.mock_bot.set_chat_administrator_custom_title.side_effect = _side_effect
        _run_main(self.conn, self.mock_bot)

        texts = _collect_texts(self.mock_bot)
        self.assertTrue(
            any("Ошибка" in t or "error" in t.lower() for t in texts),
            "Expected error message when title assignment fails",
        )


if __name__ == "__main__":
    unittest.main()
