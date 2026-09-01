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
    "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
}

COOKIES_FILE = "cookies.txt"
cookies_available = os.path.exists(COOKIES_FILE)

ydl_opts = {
    # Pick the best audio stream; FFmpegExtractAudio converts it to MP3 below.
    # A plain "bestaudio/best" selector plus full DASH/HLS manifests is the most
    # reliable setup — restricting formats (ext filters, disabled manifests) makes
    # yt-dlp fail with "Requested format is not available" on many videos.
    "format": "bestaudio/best",
    "retries": 10,
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
    "noplaylist": True,
    "quiet": False,
    "no_warnings": False,
    # Enhanced headers specifically for audio streams
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Range": "bytes=0-",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "DNT": "1",
    },
    "extractor_retries": 5,
    "fragment_retries": 10,
    "skip_unavailable_fragments": True,
    "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
    # Use external downloader
    "external_downloader": "aria2c",
    "external_downloader_args": [
        "--max-connection-per-server=16",
        "--split=16",
        "--min-split-size=1M",
        "--header=Accept: */*",
        "--header=Accept-Language: en-US,en;q=0.9",
        "--header=Sec-Fetch-Mode: cors",
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

        new_filename = None
        try:
            # Check if cookies are available and log it
            if os.path.exists(COOKIES_FILE):
                log.info("Using cookies for YouTube download")
            else:
                log.warning("No cookies file found, downloading without authentication")

            with YoutubeDL(ydl_opts) as ydl:
                try:
                    # First, get info without downloading
                    info = ydl.extract_info(youtube_link, download=False)
                except Exception as err:
                    bot.delete_message(message.chat.id, temp_msg.id)
                    error_msg = f"Error getting video info: {str(err)}"
                    if "Sign in to confirm you're not a bot" in str(err):
                        error_msg += "\n\nYouTube is requiring authentication. Please provide cookies.txt file."
                    bot.send_message(
                        message.chat.id,
                        message_thread_id=message.message_thread_id,
                        text=error_msg,
                    )
                    return

                log.info(
                    "video link: {}, duration: {}".format(
                        youtube_link, info.get("duration", 0)
                    )
                )

                # Check video restrictions
                if info.get("availability") == "subscriber_only":
                    bot.delete_message(message.chat.id, temp_msg.id)
                    bot.send_message(
                        message.chat.id,
                        message_thread_id=message.message_thread_id,
                        text="Это видео только для подписчиков. Бот не может его скачать без авторизации.",
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

                # Now download with retry
                try:
                    info = ydl.extract_info(youtube_link, download=True)
                    filename = ydl.prepare_filename(info)
                    new_filename = str(Path(filename).with_suffix(".mp3"))

                    # Verify file exists and has content
                    if not os.path.exists(new_filename):
                        raise FileNotFoundError("Downloaded file not found")

                    if os.path.getsize(new_filename) == 0:
                        raise ValueError("Downloaded file is empty")

                except Exception as download_err:
                    bot.delete_message(message.chat.id, temp_msg.id)
                    error_msg = f"Download failed: {str(download_err)}"
                    if "403" in str(download_err):
                        error_msg += (
                            "\n\nAccess denied by YouTube. Try adding valid cookies."
                        )
                    bot.send_message(
                        message.chat.id,
                        message_thread_id=message.message_thread_id,
                        text=error_msg,
                    )
                    return

            # Send the audio file
            bot.delete_message(message.chat.id, temp_msg.id)
            with open(new_filename, "rb") as audio_file:
                music_message = bot.send_audio(
                    message.chat.id,
                    audio=audio_file,
                    message_thread_id=message.message_thread_id,
                    caption=author_name,
                    title=info.get("title", "Unknown Title")[
                        :64
                    ],  # Telegram title limit
                    performer=info.get("uploader", "Unknown Artist")[:64],
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

        except Exception as e:
            log.error(f"Unexpected error: {str(e)}")
            bot.delete_message(message.chat.id, temp_msg.id)
            bot.send_message(
                message.chat.id,
                message_thread_id=message.message_thread_id,
                text="Произошла ошибка при обработке видео",
            )
        finally:
            # Clean up downloaded file
            if new_filename and os.path.exists(new_filename):
                try:
                    os.remove(new_filename)
                except Exception as cleanup_err:
                    log.error(f"Error cleaning up file: {cleanup_err}")
