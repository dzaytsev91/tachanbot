import telebot

from app.commands.get_aml import process_my_aml
from app.commands.get_chat_id import process_chat_id
from app.commands.get_statistic import process_statistic
from app.commands.get_topic_id import process_topic_id
from app.config import AppConfig
from app.database.create_db_connection import init_db
from app.database.meme import meme_vote_pressed
from app.database.music import music_vote_process
from app.database.save_message import save_message
from app.handlers.left_chat_handler import process_left_member
from app.handlers.meme_handler import process_meme
from app.handlers.music_handler import handle_audio_messages
from app.handlers.new_member_handler import process_new_member

still_worthy = [43529628, 163181560, 678126582, 211291464, 374984530]


def create_bot(config: AppConfig):
    bot = telebot.TeleBot(config.bot_token, skip_pending=True)
    conn = init_db(config.db_path)
    bot.set_my_commands(
        [
            telebot.types.BotCommand("/topicid", "print topic id"),
            telebot.types.BotCommand("/chatid", "print chat id"),
            telebot.types.BotCommand("/statistic", "show memes statistic"),
            telebot.types.BotCommand("/myaml", "show memes statistic"),
        ]
    )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("vote"))
    def vote_pressed(call: telebot.types.CallbackQuery):
        meme_vote_pressed(
            bot,
            call,
            conn,
            config.memes_chat_id,
            config.external_channel_chat_id,
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("music_vote"))
    def music_vote_pressed(call: telebot.types.CallbackQuery):
        music_vote_process(bot, call, conn, config.memes_chat_id)

    @bot.message_handler(commands=["myaml"])
    def get_my_aml(message):
        process_my_aml(bot, message, conn, config.memes_thread_id)

    @bot.message_handler(commands=["chatid"])
    def get_chat_id(message):
        process_chat_id(bot, message, config.memes_thread_id)

    @bot.message_handler(content_types=["new_chat_members"])
    def hello(message):
        process_new_member(message, bot, conn)

    @bot.message_handler(commands=["statistic"])
    def get_statistic(message):
        process_statistic(bot, message, conn, config.memes_thread_id)

    @bot.message_handler(commands=["topicid"])
    def get_topic_id(message):
        process_topic_id(bot, message, config.memes_thread_id)

    @bot.message_handler(content_types=["left_chat_member"])
    def goodbye(message):
        process_left_member(message, bot, conn)

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
            return
        if message.message_thread_id == config.music_thread_id:
            handle_audio_messages(bot, conn, message, config.flood_thread_id)
            return

        if message.message_thread_id != config.memes_thread_id:
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
            process_meme(
                bot,
                conn,
                message,
                config.memes_thread_id,
                config.flood_thread_id,
                config.external_channel_chat_id,
                config.memes_chat_id,
            )

    return bot, conn


def main():
    config = AppConfig.from_env()
    bot, conn = create_bot(config)
    try:
        bot.infinity_polling(allowed_updates=telebot.util.update_types)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
