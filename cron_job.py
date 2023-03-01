import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int);"
)


def getKey(x):
    return [x[1], -x[2]]


def main():
    chat_id = -1001621587072
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT * FROM posts WHERE created_at > ?"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    rows.sort(key=getKey)
    first, second, third = None, None, None
    for row in reversed(rows):
        if first is None:
            bot.send_message(chat_id, "🥇", reply_to_message_id=row[4])
            first = 1
            continue
        if second is None:
            bot.send_message(chat_id, "🥈", reply_to_message_id=row[4])
            second = 1
            continue
        if third is None:
            bot.send_message(chat_id, "🥉", reply_to_message_id=row[4])
            third = 1
            continue
        return


if __name__ == "__main__":
    main()
