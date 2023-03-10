import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS memes_posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int);"
)


def getKey(x):
    return [x[1], -x[2]]


def main():
    chat_id = -1001834015619
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT * FROM memes_posts WHERE created_at > ?"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    rows.sort(key=getKey)
    first, second, third = None, None, None
    for row in reversed(rows):
        if first is None:
            bot.send_message(
                chat_id,
                "🥇",
                reply_to_message_id=row[4],
                message_thread_id=flood_thread_id,
            )
            first = 1
            continue
        if second is None:
            bot.send_message(
                chat_id,
                "🥈",
                reply_to_message_id=row[4],
                message_thread_id=flood_thread_id,
            )
            second = 1
            continue
        if third is None:
            bot.send_message(
                chat_id,
                "🥉",
                reply_to_message_id=row[4],
                message_thread_id=flood_thread_id,
            )
            third = 1
            continue
        return


if __name__ == "__main__":
    main()
