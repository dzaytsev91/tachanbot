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
    bot.send_message(
        memes_chat_id,
        "Господа и господессы забываем проголосовать https://t.me/c/1621587072/3098/29322",
        message_thread_id=flood_thread_id,
        parse_mode="Markdown",
    )


if __name__ == "__main__":
    main()
