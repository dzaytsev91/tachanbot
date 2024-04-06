from datetime import datetime
from sqlite3 import IntegrityError

from app.utils.markup import generate_markup
from telebot import types


def save_meme_to_db(
    conn,
    message,
    flood_thread_message_id: int,
    memes_thread_message_id: int,
    channel_message_id: int,
):
    query = "INSERT INTO memes_posts_v2 (id, created_at, message_id, up_votes, down_votes, old_hat_votes, user_id, username, flood_thread_message_id, memes_thread_message_id, channel_message_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
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
            channel_message_id,
        ),
    )
    conn.commit()


def meme_vote_pressed(bot, call: types.CallbackQuery, conn, memes_chat_link_id, external_channel_message):
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

    query = "select up_votes, down_votes, old_hat_votes, username, flood_thread_message_id, memes_thread_message_id, channel_message_id from memes_posts_v2 WHERE id = ?;"
    meme_stats = conn.execute(query, (meme_message_id,)).fetchall()
    (
        up_votes,
        down_votes,
        old_hat_votes,
        username,
        flood_thread_message_id,
        memes_thread_message_id,
        channel_message_id,
    ) = meme_stats[0] if len(meme_stats) > 0 else (0, 0, 0, "", 0, 0, 0, 0, 0)

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
        meme_message_id, username, up_votes, down_votes, old_hat_votes, "vote"
    )

    for thread_message_id in [flood_thread_message_id, memes_thread_message_id]:
        bot.edit_message_caption(
            caption=call.message.caption or " ",
            chat_id=memes_chat_link_id,
            message_id=thread_message_id,
            reply_markup=markup,
        )
    bot.edit_message_caption(
        caption=call.message.caption or " ",
        chat_id=external_channel_message,
        message_id=channel_message_id,
        reply_markup=markup,
    )
