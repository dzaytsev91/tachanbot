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
    query = "SELECT user_id, SUM(up_votes), SUM(down_votes) FROM memes_posts WHERE created_at > ? GROUP BY user_id ORDER BY 2 DESC,3 DESC LIMIT 3"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    for row in rows:
        user_id, up_votes, down_votes = row
        msg = (
            "["
            + user_id
            + "](tg://user?id="
            + str(user_id)
            + ") 👍 {}, 👎 {}".format(up_votes, down_votes)
        )
        bot.send_message(
            memes_chat_id,
            msg,
            message_thread_id=flood_thread_id,
        )
        return


if __name__ == "__main__":
    main()
