import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))

conn = sqlite3.connect("memes.db", check_same_thread=False)


def main():
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT u.user_id, u.username FROM users u LEFT JOIN user_messages um ON um.user_id=u.user_id AND um.created_at > ? WHERE um.message_id is NULL AND u.active=1"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    msg = ["Users who have 0 posts in the last 7 days\n"]
    for row in rows:
        user_id, username = row
        msg.append(
            "[{username}](tg://user?id={user_id}))".format(
                username=username,
                user_id=user_id,
            )
        )
    bot.send_message(
        memes_chat_id,
        "\n".join(msg),
        message_thread_id=flood_thread_id,
        parse_mode="Markdown",
    )


if __name__ == "__main__":
    main()
