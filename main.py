import os
import random
import sqlite3
from datetime import datetime

import cachetools
import telebot

ttl_cache = cachetools.TTLCache(maxsize=128, ttl=100)
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), skip_pending=True)
bot.set_my_commands(
    [
        telebot.types.BotCommand("/topicid", "print topic id"),
        telebot.types.BotCommand("/chatid", "print chat id"),
    ]
)
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS posts (hash string, message_id int, message_thread_id int);"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS memes_posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, user_id int);"
)


def update_votes(data):
    cursor = conn.cursor()
    query = "INSERT INTO memes_posts (id, up_votes, down_votes) VALUES(?, ?, ?) ON CONFLICT(id) DO UPDATE SET up_votes={up_votes}, down_votes={down_votes};".format(
        up_votes=data.options[0].voter_count, down_votes=data.options[1].voter_count
    )
    cursor.execute(
        query, (data.id, data.options[0].voter_count, data.options[1].voter_count)
    )
    conn.commit()


@bot.poll_handler(update_votes)
def create_pool(message):
    poll_data = bot.send_poll(
        message.chat.id,
        " ",
        ["👍", "👎"],
        message_thread_id=message.message_thread_id,
    )
    query = "INSERT INTO memes_posts (id, created_at, message_id, up_votes, down_votes, user_id) VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
    cursor = conn.cursor()
    cursor.execute(
        query,
        (poll_data.poll.id, datetime.now(), message.id, 0, 0, message.from_user.id),
    )
    conn.commit()


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
def send_rand_photo(message):
    if message.message_thread_id != memes_thread_id:
        if message.text.lower() == "нет":
            bot.send_message(
                message.chat.id,
                "Пидора ответ",
                reply_to_message_id=message.id,
                message_thread_id=message.message_thread_id,
            )
        return
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
        or message.voice
        or message.location
        or message.contact
    ):
        bot.delete_message(message.chat.id, message.id)
    else:
        proccess_photo_mem(message)
        if message.media_group_id:
            if not ttl_cache.get(message.media_group_id):
                ttl_cache[message.media_group_id] = 1
                create_pool(message)
        else:
            create_pool(message)


@bot.message_handler(commands=["topicid"])
def get_topic_id(message):
    return bot.send_message(
        message.chat.id,
        "here is topic id: {}".format(message.message_thread_id),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )


@bot.message_handler(commands=["chatid"])
def get_chat_id(message):
    return bot.send_message(
        message.chat.id,
        "here is chat id: {}".format(message.chat.id),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )


def proccess_photo_mem(message):
    if not message.photo:
        return
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
        animation="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWEwY2MwY2Q0MTU2Mjg0OWZiNzk0NmY0ZDQ5MWNjMzczODI1YWFmZiZjdD1n/FeAs1kvsWP4OvWa9zt/giphy-downsized-large.gif",
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
