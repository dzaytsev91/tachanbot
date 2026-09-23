import sqlite3
from datetime import date

import telebot

from app.config import AppConfig
from app.cron_jobs.periods import previous_week
from app.database.create_db_connection import init_db


def send_old_hat_winner(
    bot: telebot.TeleBot,
    conn: sqlite3.Connection,
    chat_id: int,
    thread_id: int,
    start: date,
    end: date,
) -> None:
    query = "SELECT user_id, MAX(username), SUM(old_hat_votes) FROM memes_posts_v2 WHERE created_at >= ? AND created_at < ? GROUP BY user_id ORDER BY SUM(old_hat_votes) DESC LIMIT 1"
    row = conn.execute(query, (start.isoformat(), end.isoformat())).fetchone()
    if row is None:
        return
    user_id, username, old_hat_votes = row
    msg = (
        f"Звание главное баяниста этой недели получает "
        f"[{username}](tg://user?id={user_id}) - 🪗 {old_hat_votes}"
        "\nГоните его насмехайтесь над ним"
    )
    bot.send_message(
        chat_id,
        msg,
        message_thread_id=thread_id,
        parse_mode="Markdown",
    )


def main() -> None:
    config = AppConfig.from_env()
    bot = telebot.TeleBot(config.bot_token)
    conn = init_db(config.db_path)
    period = previous_week()
    try:
        send_old_hat_winner(
            bot,
            conn,
            config.memes_chat_id,
            config.flood_thread_id,
            period.start,
            period.end,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
