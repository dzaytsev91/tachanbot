import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))

db_path = os.path.join(
    os.path.normpath(__file__).rsplit(os.sep, maxsplit=3)[0], "memes.db"
)
conn = sqlite3.connect(db_path, check_same_thread=False)


def main():
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT user_id, MAX(username), count(*) FROM memes_posts_v2 WHERE created_at > ? GROUP BY user_id ORDER BY 3 DESC, 3 DESC LIMIT 3"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    msg = ["Количество сброшенных мемов\n"]
    stack = ["🥉", "🥈", "🥇"]
    for row in rows:
        user_id, username, memes_count = row
        message = "[{username}](tg://user?id={user_id}) {memes_count} - {medal}".format(
            username=username,
            user_id=user_id,
            memes_count=memes_count,
            medal=stack.pop(),
        )
        msg.append(message)
    bot.send_message(
        memes_chat_id,
        "\n".join(msg),
        message_thread_id=flood_thread_id,
        parse_mode="Markdown",
    )


if __name__ == "__main__":
    main()
