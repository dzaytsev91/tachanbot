import sqlite3
from datetime import date

import telebot

from app.config import AppConfig
from app.cron_jobs.periods import previous_week
from app.database.create_db_connection import init_db


def send_top_memes(
    bot: telebot.TeleBot,
    conn: sqlite3.Connection,
    chat_id: int,
    thread_id: int,
    start: date,
    end: date,
) -> None:
    query = "SELECT * FROM memes_posts_v2 WHERE created_at >= ? AND created_at < ? ORDER BY up_votes DESC, down_votes ASC, created_at ASC LIMIT 3"
    rows = conn.execute(query, (start.isoformat(), end.isoformat())).fetchall()
    stack = ["🥉", "🥈", "🥇"]
    for row in rows:
        bot.send_message(
            chat_id,
            stack.pop(),
            reply_to_message_id=row[9],
            message_thread_id=thread_id,
        )


def main() -> None:
    config = AppConfig.from_env()
    bot = telebot.TeleBot(config.bot_token)
    conn = init_db(config.db_path)
    period = previous_week()
    try:
        send_top_memes(
            bot,
            conn,
            config.memes_chat_id,
            config.memes_thread_id,
            period.start,
            period.end,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
