from app.database.meme import save_meme_to_db
from app.utils.markup import generate_markup


def process_meme(
    bot, conn, message, memes_thread_id, flood_thread_id, external_channel_chat_id
):
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

    external_channel_message = bot.copy_message(
        chat_id=external_channel_chat_id,
        from_chat_id=message.chat.id,
        message_id=message.id,
        disable_notification=True,
    )

    save_meme_to_db(
        conn,
        message,
        flood_thread_message.message_id,
        memes_thread_message.message_id,
        external_channel_message.message_id,
    )
    bot.delete_message(message.chat.id, message.id)

    for thread_message_id in [memes_thread_message, flood_thread_message]:
        bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=thread_message_id.message_id,
            reply_markup=markup,
        )
