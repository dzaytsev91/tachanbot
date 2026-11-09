from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import date

import telebot

from app.cron_jobs.periods import local_now, previous_week
from app.database.create_db_connection import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MINIMUM_MEMES_COUNT = 5
TOP_PLACES = 3
REWARDS = ["🥇", "🥈", "🥉"]
CLOWN = "🤡"
BOSS_TITLE = "Dank boss"
DEFAULT_ADMIN_TITLE = "дух"
# Telegram only lets the bot demote an admin when every right is False
ADMIN_RIGHTS = (
    "can_post_messages",
    "can_invite_users",
    "can_pin_messages",
    "can_manage_chat",
    "can_manage_video_chats",
    "can_manage_voice_chats",
    "can_manage_topics",
)
ADMIN_STATUSES = ("administrator", "creator")


@dataclass
class Config:
    bot_token: str
    memes_chat_id: int
    flood_thread_id: int
    memes_thread_id: int
    chat_creator_id: int
    db_path: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            memes_chat_id=int(os.environ["MEMES_CHAT_ID"]),
            flood_thread_id=int(os.environ["FLOOD_THREAD_ID"]),
            memes_thread_id=int(os.environ["MEMES_THREAD_ID"]),
            chat_creator_id=int(os.getenv("CHAT_CREATOR_ID", "43529628")),
            db_path=os.getenv("DB_PATH", "memes.db"),
        )


@dataclass
class MemeStats:
    user_id: int
    username: str
    aml: float
    total_up_votes: int
    total_count: int

    @property
    def has_enough_memes(self) -> bool:
        return self.total_count >= MINIMUM_MEMES_COUNT


class TitleManager:
    """Manages the 'Dank boss' title rotation between weekly winners."""

    def __init__(self, conn: sqlite3.Connection, bot: telebot.TeleBot, chat_id: int):
        self._conn = conn
        self._bot = bot
        self._chat_id = chat_id
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dank_boss_titles (
                user_id    INTEGER PRIMARY KEY,
                old_title  TEXT,
                assigned_at TEXT,
                old_tag    TEXT DEFAULT '',
                promoted   INTEGER DEFAULT 0
            )
            """
        )
        columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(dank_boss_titles)")
        }
        if "old_tag" not in columns:
            self._conn.execute(
                "ALTER TABLE dank_boss_titles ADD COLUMN old_tag TEXT DEFAULT ''"
            )
        if "promoted" not in columns:
            self._conn.execute(
                "ALTER TABLE dank_boss_titles ADD COLUMN promoted INTEGER DEFAULT 0"
            )
        self._conn.commit()

    def restore_previous_titles(
        self,
        exclude_user_id: int | None = None,
        honored_user_ids: frozenset[int] = frozenset(),
    ):
        rows = self._conn.execute(
            "SELECT user_id, old_title, old_tag, promoted FROM dank_boss_titles"
        ).fetchall()

        failures: list[Exception] = []
        for user_id, old_title, old_tag, promoted in rows:
            if user_id == exclude_user_id:
                continue
            try:
                status = self._bot.get_chat_member(self._chat_id, user_id).status
                if status in ADMIN_STATUSES:
                    if not promoted:
                        self._bot.set_chat_administrator_custom_title(
                            self._chat_id, user_id, old_title or ""
                        )
                    elif user_id in honored_user_ids:
                        # Finished in the top 3 again, so stays an admin like
                        # the other medalists
                        self._bot.set_chat_administrator_custom_title(
                            self._chat_id, user_id, DEFAULT_ADMIN_TITLE
                        )
                    else:
                        self._bot.promote_chat_member(
                            self._chat_id,
                            user_id,
                            **{right: False for right in ADMIN_RIGHTS},
                        )
                        status = "member"
                if promoted and old_tag and status in ("member", "restricted"):
                    self._bot.set_chat_member_tag(self._chat_id, user_id, old_tag)
            except Exception as error:
                logger.exception("Failed to restore title for user %d", user_id)
                failures.append(error)
            else:
                self._conn.execute(
                    "DELETE FROM dank_boss_titles WHERE user_id = ?", (user_id,)
                )
                self._conn.commit()

        if failures:
            raise RuntimeError(
                f"Failed to restore {len(failures)} previous title(s)"
            ) from failures[0]

    def save_title(self, user_id: int) -> bool:
        existing = self._conn.execute(
            "SELECT 1 FROM dank_boss_titles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            return False

        try:
            member = self._bot.get_chat_member(self._chat_id, user_id)
        except Exception:
            logger.exception("Failed to get old title for user %d", user_id)
            raise
        is_admin = member.status in ADMIN_STATUSES
        # A regular member has a tag instead of an admin title (Bot API 9.5),
        # and the bot promotes them for the week
        old_title = (member.custom_title or "") if is_admin else ""
        old_tag = "" if is_admin else (getattr(member, "tag", None) or "")
        self._conn.execute(
            "INSERT INTO dank_boss_titles"
            " (user_id, old_title, assigned_at, old_tag, promoted)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                old_title,
                local_now().date().isoformat(),
                old_tag,
                int(not is_admin),
            ),
        )
        self._conn.commit()
        return True


class MemeRatingBot:
    WEEKLY_STATS_QUERY = """
        SELECT user_id,
               username,
               ROUND(
                   CAST(SUM(up_votes) - SUM(down_votes) AS REAL)
                   / CAST(COUNT(*) AS REAL),
                   3
               ) AS aml,
               SUM(up_votes),
               COUNT(*)
        FROM memes_posts_v2
        WHERE created_at >= ? AND created_at < ?
        GROUP BY user_id, username
        ORDER BY aml DESC, user_id ASC
    """

    def __init__(
        self,
        config: Config,
        bot: telebot.TeleBot | None = None,
        conn: sqlite3.Connection | None = None,
    ):
        self._config = config
        self._bot = bot or telebot.TeleBot(config.bot_token)
        self._conn = conn or init_db(config.db_path)
        self._owns_connection = conn is None
        self._titles = TitleManager(self._conn, self._bot, config.memes_chat_id)

    def _send_flood(self, text: str):
        self._bot.send_message(
            self._config.memes_chat_id,
            text,
            message_thread_id=self._config.flood_thread_id,
            parse_mode="Markdown",
        )

    def _fetch_weekly_stats(self, start: date, end: date) -> list[MemeStats]:
        rows = self._conn.execute(
            self.WEEKLY_STATS_QUERY, (start.isoformat(), end.isoformat())
        ).fetchall()
        return [MemeStats(*row) for row in rows]

    def _promote_to_admin(self, user_id: int, username: str):
        member = self._bot.get_chat_member(self._config.memes_chat_id, user_id)
        if member.status in ADMIN_STATUSES:
            return
        self._bot.promote_chat_member(
            self._config.memes_chat_id,
            user_id,
            **{right: True for right in ADMIN_RIGHTS},
        )
        self._bot.set_chat_administrator_custom_title(
            self._config.memes_chat_id, user_id, DEFAULT_ADMIN_TITLE
        )
        self._bot.send_message(
            self._config.memes_chat_id,
            f"Чествуем новых админов! [{username}](tg://user?id={user_id})",
        )

    def _assign_boss_title(self, winner: MemeStats):
        if winner.user_id == self._config.chat_creator_id:
            self._send_flood(
                f"Нельзя присвоить титул создателю чата, присвой себе сам "
                f"[{winner.username}](tg://user?id={winner.user_id})"
            )
            return

        # Save the old title or tag first: a member's tag is unreadable once
        # the bot promotes them
        self._titles.save_title(winner.user_id)
        self._promote_to_admin(winner.user_id, winner.username)
        try:
            self._bot.set_chat_administrator_custom_title(
                chat_id=self._config.memes_chat_id,
                user_id=winner.user_id,
                custom_title=BOSS_TITLE,
            )
        except Exception:
            logger.exception("Failed to assign boss title to user %d", winner.user_id)
            raise

        self._send_flood(
            f"Почет и уважение новому босу данка на эту неделю! "
            f"[{winner.username}](tg://user?id={winner.user_id})"
        )

    def _format_user_line(self, stats: MemeStats, reward: str) -> str:
        return (
            f"[{stats.username}](tg://user?id={stats.user_id})"
            f" - {stats.aml} - {reward}"
            f" (total up votes {stats.total_up_votes},"
            f" total memes count {stats.total_count})"
        )

    def run(self, start: date | None = None, end: date | None = None):
        if start is None or end is None:
            period = previous_week()
            start, end = period.start, period.end
        all_stats = self._fetch_weekly_stats(start, end)
        if not all_stats:
            logger.info("No meme stats for this week")
            self._titles.restore_previous_titles()
            return

        ranked_lines: list[str] = []
        unranked_lines: list[str] = []
        failures: list[Exception] = []
        reward_idx = 0
        winner: MemeStats | None = None
        honored_user_ids: set[int] = set()

        for stats in all_stats:
            if not stats.has_enough_memes:
                unranked_lines.append(self._format_user_line(stats, CLOWN))
                continue

            if reward_idx < TOP_PLACES:
                reward = REWARDS[reward_idx]
                reward_idx += 1
                honored_user_ids.add(stats.user_id)
                if winner is None:
                    # Promoted in _assign_boss_title once the old title is saved
                    winner = stats
                else:
                    try:
                        self._promote_to_admin(stats.user_id, stats.username)
                    except Exception as error:
                        logger.exception("Failed to promote user %d", stats.user_id)
                        failures.append(error)
            else:
                reward = CLOWN
            ranked_lines.append(self._format_user_line(stats, reward))

        message_parts = ["AML - Average Meme Likes\n"]
        message_parts.extend(ranked_lines)
        message_parts.append(
            f"\n\n\nПользователи у которых <{MINIMUM_MEMES_COUNT} мемов "
            f"в неделю не участвуют в рейтинге\n"
        )
        message_parts.extend(unranked_lines)

        self._send_flood("\n".join(message_parts))

        # Last week's boss loses the title even when nobody qualifies this week
        try:
            self._titles.restore_previous_titles(
                exclude_user_id=winner.user_id if winner else None,
                honored_user_ids=frozenset(honored_user_ids),
            )
        except Exception as error:  # noqa: BLE001 - aggregate Telegram failures
            failures.append(error)

        if winner:
            try:
                self._assign_boss_title(winner)
            except Exception as error:  # noqa: BLE001 - aggregate Telegram failures
                failures.append(error)

        if failures:
            raise RuntimeError(
                f"AML report completed with {len(failures)} Telegram failure(s)"
            ) from failures[0]

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()


def main():
    config = Config.from_env()
    rating_bot = MemeRatingBot(config)
    try:
        rating_bot.run()
    finally:
        rating_bot.close()


if __name__ == "__main__":
    main()
