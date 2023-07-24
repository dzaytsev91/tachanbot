import json
import os
import random
import sqlite3
from datetime import datetime, timedelta
from sqlite3 import IntegrityError

import cachetools
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import telebot
from telebot import types

matplotlib.use("agg")
matplotlib.rc("figure", figsize=(20, 5))
ttl_cache = cachetools.TTLCache(maxsize=128, ttl=100)
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), skip_pending=True)
bot.set_my_commands(
    [
        telebot.types.BotCommand("/topicid", "print topic id"),
        telebot.types.BotCommand("/chatid", "print chat id"),
        telebot.types.BotCommand("/statistic", "show memes statistic"),
        telebot.types.BotCommand("/myaml", "show memes statistic"),
    ]
)
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_chat_link_id = int(os.getenv("MEMES_CHAT_LINK_ID", 1))

all_threads_ids = [memes_thread_id, flood_thread_id]

conn = sqlite3.connect("memes.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS memes_posts_v2 (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, user_id int, username string, old_hat_votes int, flood_thread_message_id int, memes_thread_message_id int);"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS user_messages (user_id int, message_id int, message_thread_id int, created_at timestamp);"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS users (user_id int, username string, active bool, joined_date timestamp);"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS user_votes (user_id int, meme_id int, constraint user_votes_pk unique (user_id, meme_id));"
)


def generate_markup(
    meme_message_id: int,
    username: str,
    up_votes: int = 0,
    down_votes: int = 0,
    old_hat_votes: int = 0,
):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "👍 " + (str(up_votes) if up_votes else ""),
            callback_data="vote_up|" + str(meme_message_id),
        ),
        types.InlineKeyboardButton(
            "👎 " + (str(down_votes) if down_votes else ""),
            callback_data="vote_down|" + str(meme_message_id),
        ),
        types.InlineKeyboardButton(
            username + "🪗 " + (str(old_hat_votes) if old_hat_votes else ""),
            callback_data="vote_old_hat|" + str(meme_message_id),
        ),
    )

    return markup


def save_meme_to_db(
    message, flood_thread_message_id: int, memes_thread_message_id: int
):
    query = "INSERT INTO memes_posts_v2 (id, created_at, message_id, up_votes, down_votes, old_hat_votes, user_id, username, flood_thread_message_id, memes_thread_message_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
    cursor = conn.cursor()
    cursor.execute(
        query,
        (
            message.id,
            datetime.now(),
            message.id,
            0,
            0,
            0,
            message.from_user.id,
            message.from_user.first_name,
            flood_thread_message_id,
            memes_thread_message_id,
        ),
    )
    conn.commit()


@bot.callback_query_handler(func=lambda call: call.data.startswith("vote"))
def vote_pressed(call: types.CallbackQuery):
    action = call.data.split("|")[0]
    meme_message_id = int(call.data.split("|")[1])

    cursor = conn.cursor()
    query = "INSERT INTO user_votes (user_id, meme_id) VALUES(?, ?);"

    try:
        cursor.execute(query, (call.from_user.id, meme_message_id))
    except IntegrityError:
        conn.commit()
        bot.answer_callback_query(
            call.id, "Иди другие мемы оценивай, " + call.from_user.first_name
        )
        return

    query = "select up_votes, down_votes, old_hat_votes, username, flood_thread_message_id, memes_thread_message_id from memes_posts_v2 WHERE id = ?;"
    meme_stats = conn.execute(query, (meme_message_id,)).fetchall()
    (
        up_votes,
        down_votes,
        old_hat_votes,
        username,
        flood_thread_message_id,
        memes_thread_message_id,
    ) = (
        meme_stats[0] if len(meme_stats) > 0 else (0, 0, 0, "", 0, 0)
    )

    if action == "vote_up":
        up_votes += 1
    elif action == "vote_down":
        down_votes += 1
    elif action == "vote_old_hat":
        old_hat_votes += 1

    query = "UPDATE memes_posts_v2 SET up_votes=?, down_votes=?, old_hat_votes=? WHERE id = ?;"
    conn.execute(query, (up_votes, down_votes, old_hat_votes, meme_message_id))
    conn.commit()

    markup = generate_markup(
        meme_message_id, username, up_votes, down_votes, old_hat_votes
    )

    for message_id in [flood_thread_message_id, memes_thread_message_id]:
        bot.edit_message_caption(
            caption=call.message.caption or " ",
            chat_id=call.message.chat.id,
            message_id=message_id,
            reply_markup=markup,
        )


@bot.message_handler(commands=["topicid"])
def get_topic_id(message):
    return bot.send_message(
        message.chat.id,
        "here is topic id: {}".format(message.message_thread_id),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )


@bot.message_handler(commands=["myaml"])
def get_my_aml(message):
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT ROUND(CAST(SUM(up_votes) as float) / CAST(COUNT(*) as float), 3), SUM(up_votes), COUNT(*) FROM memes_posts_v2 WHERE created_at > ? AND user_id = ? ORDER BY CAST(SUM(up_votes) as float) / CAST(COUNT(*) as float) DESC"
    aml = conn.execute(query, (seven_days_ago, str(message.from_user.id))).fetchone()
    return bot.send_message(
        message.chat.id,
        "Your aml is: {}".format(aml),
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


@bot.message_handler(commands=["statistic"])
def get_statistic(message):
    seven_days_ago = datetime.now() - timedelta(days=14)
    query = "select date(created_at), count(*) from memes_posts_v2 WHERE created_at > ? group by date(created_at) order by date(created_at);"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    date_time = []
    data = []
    for row in rows:
        date_time.append(row[0])
        data.append(row[1])

    date_time = pd.to_datetime(date_time)
    df = pd.DataFrame()
    df["value"] = data
    df = df.set_index(date_time)
    plt.plot(df, **{"marker": "o"})
    plt.gcf().autofmt_xdate()
    plt.title("Memes count")
    plt.grid()
    plt.savefig("test.png", dpi=300)
    plt.close()
    with open("test.png", "rb") as f:
        content = f.read()
    return bot.send_photo(
        message.chat.id,
        message_thread_id=message.message_thread_id,
        photo=content,
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
def handle_message(message):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_messages (user_id, message_id, message_thread_id, created_at) VALUES(?, ?, ?, ?) ON CONFLICT DO NOTHING",
        (
            message.from_user.id,
            message.id,
            message.message_thread_id,
            datetime.now(),
        ),
    )
    conn.commit()
    if message.message_thread_id != memes_thread_id:
        return

    if (
        message.text
        or message.sticker
        or message.voice
        or message.location
        or message.contact
    ):
        bot.delete_message(message.chat.id, message.id)
    else:
        markup = generate_markup(message.id, message.from_user.first_name)

        memes_thread_message = bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_thread_id=memes_thread_id,
            message_id=message.id,
            disable_notification=True,
            reply_markup=markup,
        )

        flood_thread_message = bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_thread_id=flood_thread_id,
            message_id=message.id,
            disable_notification=True,
            reply_markup=markup,
        )

        save_meme_to_db(
            message, flood_thread_message.message_id, memes_thread_message.message_id
        )
        bot.delete_message(message.chat.id, message.id)


@bot.message_handler(content_types=["new_chat_members"])
def hello(message):
    for new_user in message.new_chat_members:
        user_id = new_user.id
        user_name = new_user.first_name
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
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, username, active, joined_date) VALUES(?, ?, ?, ?) ON CONFLICT DO UPDATE SET active=1",
            (
                user_id,
                user_name,
                True,
                datetime.now(),
            ),
        )
        conn.commit()


@bot.message_handler(content_types=["left_chat_member"])
def goodbye(message):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET active=0 WHERE user_id=?",
        (message.from_user.id,),
    )
    conn.commit()
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
