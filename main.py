import os
import sqlite3
from datetime import datetime

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int);"
)


def test(data):
    cursor = conn.cursor()
    query = "INSERT INTO posts (id, up_votes, down_votes) VALUES(?, ?, ?) ON CONFLICT(id) DO UPDATE SET up_votes={up_votes}, down_votes={down_votes};".format(
        up_votes=data.options[0].voter_count, down_votes=data.options[1].voter_count
    )
    cursor.execute(
        query, (data.id, data.options[0].voter_count, data.options[1].voter_count)
    )
    conn.commit()


@bot.message_handler(content_types=["photo", "video"])
@bot.poll_handler(test)
def send_rand_photo(message):
    poll_data = bot.send_poll(message.chat.id, "Норм?", ["👍", "👎"])
    query = "INSERT INTO posts (id, created_at, message_id, up_votes, down_votes) VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
    cursor = conn.cursor()
    cursor.execute(query, (poll_data.poll.id, datetime.now(), poll_data.id - 1, 0, 0))
    conn.commit()


def main():
    bot.infinity_polling(allowed_updates=telebot.util.update_types)


if __name__ == "__main__":
    main()
