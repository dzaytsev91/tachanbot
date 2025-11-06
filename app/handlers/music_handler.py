import os
import re
import logging
from pathlib import Path

from yt_dlp import YoutubeDL

from app.database.music import save_music_to_db
from app.utils.markup import generate_markup

log = logging.getLogger(__name__)

# Platform-specific user agents
USER_AGENTS = {
    'default': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
}

ydl_opts = {
    "format": "bestaudio/best",
    "retries": 5,
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
    'noplaylist': True,
    'quiet': True,
    'no_warnings': False,
    'merge_output_format': 'mp4',
    'http_headers': {'User-Agent': USER_AGENTS['default']},
    'extractor_retries': 3,
    'fragment_retries': 3,
    'ignoreerrors': False,
}

youtube_re = r"http(?:s?)://(?:www\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w\-\_]*)(&(amp;)?‌​[\w\?‌​=]*)?"


def handle_audio_messages(bot, conn, message, flood_thread_id):
    if message.audio:
        return
    elif message.text and re.search(youtube_re, message.text):
        youtube_link = re.search(youtube_re, message.text)[0]
        author_name = message.from_user.first_name
        author_id = message.from_user.id
        bot.delete_message(message.chat.id, message.id)
        temp_msg = bot.send_message(
            message.chat.id,
            text="Downloading song 🎶",
            message_thread_id=message.message_thread_id,
        )
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(youtube_link, download=False)
            except Exception as err:
                bot.delete_message(message.chat.id, temp_msg.id)
                bot.send_message(
                    message.chat.id,
                    message_thread_id=message.message_thread_id,
                    text=err,
                )
                return
            log.info("video link: {},  duration: {}".format(youtube_link, info.get("duration", 0)))
            if info.get('availability') == 'subscriber_only':
                bot.delete_message(message.chat.id, temp_msg.id)
                bot.edit_message_text(
                    chat_id=message.chat_id,
                    message_thread_id=message.message_thread_id,
                    text="Это видео только для подписчиков. Бот не может его скачать без авторизации."
                )
                return
            if info.get("duration", 1000) > 600:
                bot.delete_message(message.chat.id, temp_msg.id)
                bot.send_message(
                    message.chat.id,
                    message_thread_id=message.message_thread_id,
                    text="Видео длинее 10 минут не поддерживается",
                )
                return
            info = ydl.extract_info(youtube_link, download=True)
            filename = ydl.prepare_filename(info)
            new_filename = str(Path(filename).with_suffix(".mp3"))

        bot.delete_message(message.chat.id, temp_msg.id)
        music_message = bot.send_audio(
            message.chat.id,
            audio=open(new_filename, "rb"),
            message_thread_id=message.message_thread_id,
            caption=message.from_user.first_name,
        )

        markup = generate_markup(
            music_message.id, author_name, callback_prefix="music_vote"
        )

        flood_thread_message = bot.copy_message(
            chat_id=music_message.chat.id,
            from_chat_id=music_message.chat.id,
            message_thread_id=flood_thread_id,
            message_id=music_message.id,
            disable_notification=True,
            reply_markup=markup,
        )

        save_music_to_db(
            music_message,
            conn,
            author_name,
            author_id,
            flood_thread_message.message_id,
            music_message.message_id,
        )
        os.remove(new_filename)

        for thread_message_id in [music_message, flood_thread_message]:
            bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=thread_message_id.message_id,
                reply_markup=markup,
            )
