import logging
import time
from io import BytesIO

import imagehash
import requests
from PIL import Image
from telebot.apihelper import ApiException, ApiTelegramException

from app.database.meme import save_meme_to_db
from app.utils.markup import generate_markup

logger = logging.getLogger(__name__)


def _image_hash(bot, message):
    for attempt in range(3):
        try:
            image_url = bot.get_file_url(message.photo[-1].file_id)
            response = requests.get(image_url, timeout=(5, 15))
            response.raise_for_status()
            return str(imagehash.average_hash(Image.open(BytesIO(response.content))))
        except (requests.RequestException, ApiException) as error:
            # Never log the exception text: Telegram file URLs contain the bot token.
            logger.warning(
                "Meme chat=%s message=%s stage=image_hash attempt=%s error=%s",
                message.chat.id,
                message.id,
                attempt + 1,
                type(error).__name__,
            )
            if attempt < 2:
                time.sleep(attempt + 1)
    return ""


def _delete_original(bot, message):
    for attempt in range(3):
        try:
            bot.delete_message(message.chat.id, message.id, timeout=15)
            return
        except ApiTelegramException as error:
            if (
                error.error_code == 400
                and "message to delete not found" in error.description.lower()
            ):
                return
            raise
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def process_meme(
    bot,
    conn,
    message,
    memes_thread_id,
    flood_thread_id,
    external_channel_chat_id,
    memes_chat_id,
):
    stage = "image_hash"
    copies = {}
    try:
        image_hash = _image_hash(bot, message) if message.photo else ""
        markup_inner = generate_markup(
            message.id, message.from_user.first_name, callback_prefix="vote"
        )
        markup_external_channel = generate_markup(
            message.id, message.from_user.first_name, callback_prefix="vote_channel"
        )

        for stage, chat_id, thread_id, markup in (
            ("copy_memes", message.chat.id, memes_thread_id, markup_inner),
            ("copy_flood", message.chat.id, flood_thread_id, markup_inner),
            ("copy_channel", external_channel_chat_id, None, markup_external_channel),
        ):
            # A timeout can mean the copy exists but its response was lost. No retry.
            copied = bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_thread_id=thread_id,
                message_id=message.id,
                disable_notification=True,
                reply_markup=markup,
                timeout=15,
            )
            copies[stage] = copied.message_id

        stage = "save_database"
        save_meme_to_db(
            conn,
            message,
            copies["copy_flood"],
            copies["copy_memes"],
            copies["copy_channel"],
            image_hash,
        )
        stage = "delete_original"
        _delete_original(bot, message)
    except (requests.RequestException, ApiException) as error:
        logger.error(
            "Meme chat=%s message=%s stage=%s copies=%s error=%s code=%s",
            message.chat.id,
            message.id,
            stage,
            copies,
            type(error).__name__,
            getattr(error, "error_code", None),
        )
        text = (
            "Мем опубликован, но удалить исходник не удалось. Не отправляйте его повторно."
            if stage == "delete_original"
            else "Не удалось завершить обработку мема. Возможны частичные копии; "
            "не отправляйте его повторно до проверки администратором."
        )
        text += f"\nИсходное сообщение: {message.id}."
        try:
            bot.send_message(
                message.chat.id,
                text,
                message_thread_id=memes_thread_id,
                timeout=15,
            )
        except (requests.RequestException, ApiException) as notification_error:
            logger.error(
                "Meme chat=%s message=%s stage=notify_failure error=%s",
                message.chat.id,
                message.id,
                type(notification_error).__name__,
            )
