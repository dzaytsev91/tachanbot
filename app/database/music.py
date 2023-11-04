from datetime import datetime
from sqlite3 import IntegrityError

from app.utils.markup import generate_markup
from telebot import types


def save_music_to_db(
    message,
    conn,
    author_name: str,
    author_id: int,
    flood_thread_message_id: int,
    music_thread_message_id: int,
):
    query = "INSERT INTO music_posts (id, created_at, message_id, up_votes, down_votes, old_hat_votes, user_id, username, flood_thread_message_id, music_thread_message_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING;"
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
            author_id,
            author_name,
            flood_thread_message_id,
            music_thread_message_id,
        ),
    )
    conn.commit()


def music_vote_process(bot, call: types.CallbackQuery, conn, channel_chat_id: int):
    action = call.data.split("|")[0]
    message_id = int(call.data.split("|")[1])

    cursor = conn.cursor()
    query = "INSERT INTO music_votes (user_id, music_id) VALUES(?, ?);"

    try:
        cursor.execute(query, (call.from_user.id, message_id))
    except IntegrityError:
        conn.commit()
        bot.answer_callback_query(
            call.id, "Иди другие песни оценивай, " + call.from_user.first_name
        )
        return

    query = "select up_votes, down_votes, old_hat_votes, username, flood_thread_message_id, music_thread_message_id from music_posts WHERE id = ?;"
    music_stats = conn.execute(query, (message_id,)).fetchall()
    (
        up_votes,
        down_votes,
        old_hat_votes,
        username,
        flood_thread_message_id,
        music_thread_message_id,
    ) = music_stats[0] if len(music_stats) > 0 else (0, 0, 0, "", 0, 0)

    if action == "music_vote_up":
        up_votes += 1
    elif action == "music_vote_down":
        down_votes += 1
    elif action == "music_vote_old_hat":
        old_hat_votes += 1

    query = (
        "UPDATE music_posts SET up_votes=?, down_votes=?, old_hat_votes=? WHERE id = ?;"
    )
    conn.execute(query, (up_votes, down_votes, old_hat_votes, message_id))
    conn.commit()

    markup = generate_markup(
        message_id, username, up_votes, down_votes, old_hat_votes, "music_vote"
    )

    for thread_message_id in [flood_thread_message_id, music_thread_message_id]:
        bot.edit_message_caption(
            caption=call.message.caption or " ",
            chat_id=channel_chat_id,
            message_id=thread_message_id,
            reply_markup=markup,
        )
