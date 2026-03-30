from __future__ import annotations

import os
import sqlite3
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import telebot
from dateutil.relativedelta import relativedelta, MO

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MINIMUM_MEMES_COUNT = 5
TOP_PLACES = 3
REWARDS = ["🥇", "🥈", "🥉"]
CLOWN = "🤡"
BOSS_TITLE = "Dank boss"
DEFAULT_ADMIN_TITLE = "дух"


@dataclass
class Config:
    bot_token: str
    memes_chat_id: int
    flood_thread_id: int
    memes_thread_id: int
    chat_creator_id: int
    db_path: str

    @classmethod
    def from_env(cls) -> "Config":
        project_root = Path(__file__).resolve().parents[2]
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            memes_chat_id=int(os.environ["MEMES_CHAT_ID"]),
            flood_thread_id=int(os.getenv("FLOOD_THREAD_ID", "1")),
            memes_thread_id=int(os.getenv("MEMES_THREAD_ID", "1")),
            chat_creator_id=43529628,
            db_path=str(project_root / "memes.db"),
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
                assigned_at TEXT
            )
            """
        )
        self._conn.commit()

    def _get_custom_title(self, user_id: int) -> str:
        try:
            member = self._bot.get_chat_member(self._chat_id, user_id)
            return member.custom_title or ""
        except Exception:
            logger.exception("Failed to get custom title for user %d", user_id)
            return ""

    def restore_previous_titles(self, exclude_user_id: int | None = None):
        rows = self._conn.execute(
            "SELECT user_id, old_title FROM dank_boss_titles"
        ).fetchall()

        for user_id, old_title in rows:
            if user_id == exclude_user_id:
                continue
            try:
                member = self._bot.get_chat_member(self._chat_id, user_id)
                if member.status in ("administrator", "creator"):
                    self._bot.set_chat_administrator_custom_title(
                        self._chat_id, user_id, old_title or ""
                    )
            except Exception:
                logger.exception("Failed to restore title for user %d", user_id)
            finally:
                self._conn.execute(
                    "DELETE FROM dank_boss_titles WHERE user_id = ?", (user_id,)
                )
                self._conn.commit()

    def save_title(self, user_id: int) -> bool:
        existing = self._conn.execute(
            "SELECT 1 FROM dank_boss_titles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            return False

        old_title = self._get_custom_title(user_id)
        self._conn.execute(
            "INSERT INTO dank_boss_titles (user_id, old_title, assigned_at) VALUES (?, ?, ?)",
            (user_id, old_title, date.today().isoformat()),
        )
        self._conn.commit()
        return True

    def rollback_save(self, user_id: int):
        self._conn.execute("DELETE FROM dank_boss_titles WHERE user_id = ?", (user_id,))
        self._conn.commit()


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
        WHERE created_at > ?
        GROUP BY user_id, username
        ORDER BY aml DESC
    """

    def __init__(self, config: Config):
        self._config = config
        self._bot = telebot.TeleBot(config.bot_token)
        self._conn = sqlite3.connect(config.db_path, check_same_thread=False)
        self._titles = TitleManager(self._conn, self._bot, config.memes_chat_id)

    def _send_flood(self, text: str):
        self._bot.send_message(
            self._config.memes_chat_id,
            text,
            message_thread_id=self._config.flood_thread_id,
            parse_mode="Markdown",
        )

    def _fetch_weekly_stats(self) -> list[MemeStats]:
        last_monday = date.today() + relativedelta(weekday=MO(-2))
        rows = self._conn.execute(self.WEEKLY_STATS_QUERY, (last_monday,)).fetchall()
        return [MemeStats(*row) for row in rows]

    def _promote_to_admin(self, user_id: int, username: str):
        member = self._bot.get_chat_member(self._config.memes_chat_id, user_id)
        if member.status == "administrator":
            return
        self._bot.promote_chat_member(
            self._config.memes_chat_id,
            user_id,
            can_post_messages=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_chat=True,
            can_manage_video_chats=True,
            can_manage_voice_chats=True,
            can_manage_topics=True,
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

        self._titles.restore_previous_titles(exclude_user_id=winner.user_id)
        saved = self._titles.save_title(winner.user_id)
        try:
            self._bot.set_chat_administrator_custom_title(
                chat_id=self._config.memes_chat_id,
                user_id=winner.user_id,
                custom_title=BOSS_TITLE,
            )
        except Exception as err:
            if saved:
                self._titles.rollback_save(winner.user_id)
            self._send_flood(f"Ошибка, error: {err}")
            return

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

    def run(self):
        all_stats = self._fetch_weekly_stats()
        if not all_stats:
            logger.info("No meme stats for this week")
            return

        ranked_lines: list[str] = []
        unranked_lines: list[str] = []
        reward_idx = 0
        winner: MemeStats | None = None

        for stats in all_stats:
            if not stats.has_enough_memes:
                unranked_lines.append(self._format_user_line(stats, CLOWN))
                continue

            if reward_idx < TOP_PLACES:
                reward = REWARDS[reward_idx]
                reward_idx += 1
                if winner is None:
                    winner = stats
                try:
                    self._promote_to_admin(stats.user_id, stats.username)
                except Exception:
                    logger.exception("Failed to promote user %d", stats.user_id)
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

        if winner:
            self._assign_boss_title(winner)


def main():
    config = Config.from_env()
    MemeRatingBot(config).run()


if __name__ == "__main__":
    main()
