import os
import random
import sqlite3
from datetime import datetime

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), skip_pending=True)
bot.set_my_commands(
    [
        telebot.types.BotCommand("/topicid", "print topic id"),
    ]
)
memes_thread_id = int(os.getenv("MEMES_THREAD_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID"))

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS posts (hash string, message_id int, message_thread_id int);"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS memes_posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int);"
)


@bot.message_handler(content_types=["photo", "video"])
def send_rand_photo(message):
    if message.message_thread_id != memes_thread_id:
        return
    poll_data = bot.send_poll(
        message.chat.id,
        "Норм?",
        ["👍", "👎"],
        message_thread_id=message.message_thread_id,
    )
    query = "INSERT INTO memes_posts (id, created_at, message_id, up_votes, down_votes) VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
    cursor = conn.cursor()
    cursor.execute(query, (poll_data.poll.id, datetime.now(), poll_data.id - 1, 0, 0))
    conn.commit()


@bot.message_handler(commands=["topicid"])
def get_topic_id(message):
    return bot.send_message(
        message.chat.id,
        "here is topic id: {}".format(message.message_thread_id),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )


@bot.message_handler(
    content_types=[
        "text",
        "animation",
        "audio",
        "document",
        "photo",
        "sticker",
        "video",
        "video_note",
        "voice",
        "location",
        "contact",
    ]
)
def check_duplicate_post(message):
    if message.message_thread_id == memes_thread_id:
        bot.forward_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_thread_id=flood_thread_id,
            message_id=message.id,
            disable_notification=True,
        )
        if (
            message.text
            or message.sticker
            or message.video_note
            or message.voice
            or message.location
            or message.contact
        ):
            bot.delete_message(message.chat.id, message.id)
        elif message.photo:
            proccess_photo_mem(message)


def proccess_photo_mem(message):
    for photo in message.photo:
        res = conn.execute(
            "SELECT message_id FROM posts WHERE hash = '{}' AND message_thread_id = {}".format(
                photo.file_unique_id, message.message_thread_id
            )
        ).fetchone()
        if res:
            bot.send_message(
                message.chat.id,
                "Баян, ептыть",
                reply_to_message_id=res[0],
                message_thread_id=message.message_thread_id,
            )
            return
        else:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO posts (hash, message_id, message_thread_id) VALUES(?, ?, ?)",
                (photo.file_unique_id, message.id, message.message_thread_id),
            )
            conn.commit()


@bot.message_handler(content_types=["new_chat_members"])
def hello(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    mention = "[" + user_name + "](tg://user?id=" + str(user_id) + ")"
    bot_msg = "WelCUM CUMрад, {}".format(mention)
    bot.send_animation(
        message.chat.id,
        animation="CgACAgIAAx0CbVDbgwADPWQC7678gaLotBps8NtMHFdk7V5XAALJAgACWQAB8Evsy1CFaR2Cti4E",
        caption=bot_msg,
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["left_chat_member"])
def goodbye(message):
    bot.send_message(
        message.chat.id,
        random.choice(
            [
                "Ну и пиздуй",
                "Аривидерчи",
                "Адьос",
                "Чао-какао",
                "Оревуар",
                "Ассаламу алейкум, брат",
            ]
        ),
        reply_to_message_id=message.message_id,
    )


def main():
    bot.infinity_polling(allowed_updates=telebot.util.update_types)


if __name__ == "__main__":
    main()
