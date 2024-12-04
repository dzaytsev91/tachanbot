from io import BytesIO

import imagehash
import requests
from PIL import Image

from app.database.meme import save_meme_to_db, is_duplicate_by_hash
from app.utils.markup import generate_markup


def process_meme(
        bot,
        conn,
        message,
        memes_thread_id,
        flood_thread_id,
        external_channel_chat_id,
        memes_chat_id,
):
    image_hash = ""
    if message.photo:
        file_id = message.photo[-1].file_id
        image_url = bot.get_file_url(file_id)
        image_bytes = BytesIO(requests.get(image_url).content)
        image_hash = str(imagehash.average_hash(Image.open(image_bytes)))
        duplicate_message_id = is_duplicate_by_hash(conn, image_hash)
        if duplicate_message_id:
            bot.delete_message(message.chat.id, message.id)
            user_id = message.from_user.id
            user_name = message.from_user.first_name
            mention = "[" + user_name + "](tg://user?id=" + str(user_id) + ")"
            bot.send_message(
                chat_id=message.chat.id,
                message_thread_id=flood_thread_id,
                text="{} уже [было](https://t.me/c/{}/{}/{})".format(
                    mention,
                    str(memes_chat_id)[4:],
                    memes_thread_id,
                    duplicate_message_id,
                ),
                parse_mode="Markdown",
            )
            return

    markup_inner = generate_markup(
        message.id, message.from_user.first_name, callback_prefix="vote"
    )
    markup_external_channel = generate_markup(
        message.id, message.from_user.first_name, callback_prefix="vote_channel"
    )

    memes_thread_message = bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_thread_id=memes_thread_id,
        message_id=message.id,
        disable_notification=True,
        reply_markup=markup_inner,
    )

    flood_thread_message = bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_thread_id=flood_thread_id,
        message_id=message.id,
        disable_notification=True,
        reply_markup=markup_inner,
    )

    external_channel_message = bot.copy_message(
        chat_id=external_channel_chat_id,
        from_chat_id=message.chat.id,
        message_id=message.id,
        disable_notification=True,
        reply_markup=markup_external_channel,
    )

    save_meme_to_db(
        conn,
        message,
        flood_thread_message.message_id,
        memes_thread_message.message_id,
        external_channel_message.message_id,
        image_hash,
    )
    bot.delete_message(message.chat.id, message.id)

    for thread_message_id in [memes_thread_message, flood_thread_message]:
        bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=thread_message_id.message_id,
            reply_markup=markup_inner,
        )

    bot.edit_message_reply_markup(
        chat_id=external_channel_chat_id,
        message_id=external_channel_message.message_id,
        reply_markup=markup_external_channel,
    )
