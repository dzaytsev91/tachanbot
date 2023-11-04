from main import bot, memes_thread_id


@bot.message_handler(commands=["chatid"])
def get_chat_id(message):
    if message.message_thread_id == memes_thread_id:
        bot.delete_message(message.chat.id, message.id)
        return
    return bot.send_message(
        message.chat.id,
        "here is chat id: {}".format(message.chat.id),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )
