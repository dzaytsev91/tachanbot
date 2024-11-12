import os
import re
import logging
from pathlib import Path

from yt_dlp import YoutubeDL

from app.database.music import save_music_to_db
from app.utils.markup import generate_markup

log = logging.getLogger(__name__)

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
                info = ydl.extract_info(youtube_link, download=True)
            except Exception as err:
                bot.delete_message(message.chat.id, temp_msg.id)
                bot.send_message(
                    message.chat.id,
                    message_thread_id=message.message_thread_id,
                    text=err,
                )
                return
            log.info("video duration: {}".format(info.get("duration", 0)))
            if info.get("duration", 1000) > 600:
                bot.delete_message(message.chat.id, temp_msg.id)
                bot.send_message(
                    message.chat.id,
                    message_thread_id=message.message_thread_id,
                    text="Видео длинее 10 минут не поддерживается",
                )
                return
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

        bot.edit_message_reply_markup(
            chat_id=music_message.chat.id,
            message_id=music_message.id,
            reply_markup=markup,
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
