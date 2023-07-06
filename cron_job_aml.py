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
    query = "SELECT user_id,username, CAST(SUM(up_votes) as float) / CAST(COUNT(*) as float) FROM memes_posts WHERE created_at > ? GROUP BY user_id, username ORDER BY CAST(SUM(up_votes) as float) / CAST(COUNT(*) as float) DESC"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    msg = []
    stack = ["🥉", "🥈", "🥇"]
    for row in rows:
        user_id, username, aml = row
        reward = "🤡"
        if stack:
            reward = stack.pop()
        msg.append(
            "[{username}](tg://user?id={user_id}) AML - {aml} - {reward}".format(
                username=username,
                user_id=user_id,
                aml=aml,
                reward=reward,
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
