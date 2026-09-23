import logging
import sqlite3
from datetime import datetime, timedelta

import telebot

from app.config import AppConfig
from app.cron_jobs.periods import local_now
from app.database.create_db_connection import init_db

logger = logging.getLogger(__name__)


def send_inactive_users(
    bot: telebot.TeleBot,
    conn: sqlite3.Connection,
    chat_id: int,
    thread_id: int,
    cutoff: datetime,
) -> None:
    query = "SELECT u.user_id, u.username FROM users u LEFT JOIN user_messages um ON um.user_id=u.user_id AND um.created_at > ? WHERE um.message_id is NULL AND u.active=1"
    rows = conn.execute(query, (cutoff.isoformat(sep=" "),)).fetchall()
    msg = ["Список вуаеристов\n"]
    for row in rows:
        user_id, username = row
        try:
            user_data = bot.get_chat_member(chat_id, user_id)
        except Exception:
            logger.exception("Failed to inspect chat member %d", user_id)
            continue
        if user_data.status == "administrator":
            continue
        msg.append(f"[{username}](tg://user?id={user_id}) {user_id}")
    if len(msg) == 1:
        return
    bot.send_message(
        chat_id,
        "\n".join(msg),
        message_thread_id=thread_id,
        parse_mode="Markdown",
    )


def main() -> None:
    config = AppConfig.from_env()
    bot = telebot.TeleBot(config.bot_token)
    conn = init_db(config.db_path)
    try:
        send_inactive_users(
            bot,
            conn,
            config.memes_chat_id,
            config.flood_thread_id,
            local_now().replace(tzinfo=None) - timedelta(days=14),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
