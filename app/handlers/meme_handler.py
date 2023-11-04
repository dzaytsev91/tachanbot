from app.database.meme import save_meme_to_db
from app.utils.markup import generate_markup


def process_meme(bot, conn, message, memes_thread_id, flood_thread_id):
    markup = generate_markup(
        message.id, message.from_user.first_name, callback_prefix="vote"
    )

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
        conn,
        message,
        flood_thread_message.message_id,
        memes_thread_message.message_id,
    )
    bot.delete_message(message.chat.id, message.id)
