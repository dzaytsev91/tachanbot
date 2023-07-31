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
    query = "SELECT * FROM memes_posts_v2 WHERE created_at > ? ORDER BY up_votes DESC, down_votes DESC, created_at ASC LIMIT 3"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    stack = ["🥉", "🥈", "🥇"]
    for row in rows:
        bot.send_message(
            memes_chat_id,
            stack.pop(),
            reply_to_message_id=row[9],
            message_thread_id=memes_thread_id,
        )


if __name__ == "__main__":
    main()
