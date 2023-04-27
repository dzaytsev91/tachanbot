import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS memes_posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, old_hat_votes int);"
)


def main():
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT * FROM memes_posts WHERE created_at > ? ORDER BY up_votes DESC, down_votes DESC, created_at ASC LIMIT 3"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    stack = ["🥉", "🥈", "🥇"]
    for row in rows:
        bot.send_message(
            memes_chat_id,
            stack.pop(),
            reply_to_message_id=row[4],
            message_thread_id=memes_thread_id,
        )


if __name__ == "__main__":
    main()
