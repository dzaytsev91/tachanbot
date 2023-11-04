import os

import telebot

from app.database.create_db_connection import init_db
from app.database.meme import meme_vote_pressed
from app.database.music import music_vote_process
from app.database.save_message import save_message
from app.handlers.left_chat_handler import process_left_member
from app.handlers.meme_handler import process_meme
from app.handlers.music_handler import handle_audio_messages
from app.handlers.new_member_handler import process_new_member

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), skip_pending=True)
bot.set_my_commands(
    [
        telebot.types.BotCommand("/topicid", "print topic id"),
        telebot.types.BotCommand("/chatid", "print chat id"),
        telebot.types.BotCommand("/statistic", "show memes statistic"),
        telebot.types.BotCommand("/myaml", "show memes statistic"),
    ]
)
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_chat_link_id = int(os.getenv("MEMES_CHAT_ID", 1))
channel_chat_id = int(os.getenv("CHANNEL_CHAT_ID", -1001871336301))
music_thread_id = int(os.getenv("MUSIC_THREAD_ID", 2))

still_worthy = [43529628, 163181560, 678126582, 211291464, 374984530]

all_threads_ids = [memes_thread_id, flood_thread_id]

conn = init_db("memes.db")


@bot.callback_query_handler(func=lambda call: call.data.startswith("vote"))
def vote_pressed(call: telebot.types.CallbackQuery):
    meme_vote_pressed(bot, call, conn, memes_chat_link_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("music_vote"))
def music_vote_pressed(call: telebot.types.CallbackQuery):
    music_vote_process(bot, call, conn, channel_chat_id)


@bot.message_handler(
    content_types=[
        "text",
        "animation",
        "audio",
        "document",
        "photo",
        "sticker",
        "video",
        "video_note",
        "voice",
        "location",
        "contact",
    ]
)
def handle_message(message):
    save_message(message, conn)
    if (
        message.text
        and message.from_user.id in still_worthy
        and "варфоломеевскую ночь" in message.text.lower()
    ):
        # start_shooting(message)
        return
    if message.message_thread_id == music_thread_id:
        handle_audio_messages(bot, conn, message, flood_thread_id)
        return

    if message.message_thread_id != memes_thread_id:
        return

    if (
        message.text
        or message.sticker
        or message.voice
        or message.location
        or message.contact
    ):
        bot.delete_message(message.chat.id, message.id)
    else:
        process_meme(bot, conn, message, memes_thread_id, flood_thread_id)


@bot.message_handler(content_types=["new_chat_members"])
def hello(message):
    process_new_member(message, bot, conn)


@bot.message_handler(content_types=["left_chat_member"])
def goodbye(message):
    process_left_member(message, bot, conn)


def main():
    bot.infinity_polling(allowed_updates=telebot.util.update_types)


if __name__ == "__main__":
    main()
