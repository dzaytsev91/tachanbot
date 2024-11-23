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
        hash_id: str,
):
    query = "INSERT INTO memes_posts_v2 (id, created_at, message_id, up_votes, down_votes, old_hat_votes, user_id, username, flood_thread_message_id, memes_thread_message_id, channel_message_id, hash, channel_up_votes, channel_down_votes) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
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
            hash_id,
            0,
            0,
        ),
    )
    conn.commit()


def meme_vote_pressed(
        bot, call: types.CallbackQuery, conn, memes_chat_link_id, external_channel_message
):
    pressed_from_channel = False
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

    query = "select up_votes, down_votes, old_hat_votes, username, flood_thread_message_id, memes_thread_message_id, channel_message_id, channel_up_votes, channel_down_votes from memes_posts_v2 WHERE id = ?;"
    meme_stats = conn.execute(query, (meme_message_id,)).fetchall()
    (
        up_votes,
        down_votes,
        old_hat_votes,
        username,
        flood_thread_message_id,
        memes_thread_message_id,
        channel_message_id,
        channel_up_votes,
        channel_down_votes,
    ) = meme_stats[0] if len(meme_stats) > 0 else (0, 0, 0, "", 0, 0, 0, 0, 0, 0, 0)

    if action == "vote_up":
        up_votes += 1
    elif action == "vote_down":
        down_votes += 1
    if action == "vote_channel_up":
        pressed_from_channel = True
        channel_up_votes += 1
    elif action == "vote_channel_down":
        pressed_from_channel = True
        channel_down_votes += 1

    elif action == "vote_old_hat":
        old_hat_votes += 1

    query = "UPDATE memes_posts_v2 SET up_votes=?, down_votes=?, old_hat_votes=?, channel_up_votes=?, channel_down_votes=?  WHERE id = ?;"
    conn.execute(query, (up_votes, down_votes, old_hat_votes, channel_up_votes, channel_down_votes, meme_message_id))
    conn.commit()

    markup_inner = generate_markup(
        meme_message_id, username, up_votes, down_votes, old_hat_votes, "vote"
    )

    markup_external_channel = generate_markup(
        meme_message_id, username, up_votes + channel_up_votes, down_votes + channel_down_votes, old_hat_votes,
        "vote_channel"
    )

    for thread_message_id in [flood_thread_message_id, memes_thread_message_id]:
        if pressed_from_channel:
            continue
        bot.edit_message_caption(
            caption=call.message.caption or " ",
            chat_id=memes_chat_link_id,
            message_id=thread_message_id,
            reply_markup=markup_inner,
        )

    bot.edit_message_caption(
        caption=call.message.caption or " ",
        chat_id=external_channel_message,
        message_id=channel_message_id,
        reply_markup=markup_external_channel,
    )


def is_duplicate_by_hash(conn, image_hash) -> int:
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT memes_thread_message_id FROM memes_posts_v2 WHERE hash = '{}'".format(
            image_hash
        )
    ).fetchall()
    if len(rows) > 0:
        return rows[0][0]
    return 0
