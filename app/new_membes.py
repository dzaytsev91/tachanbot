import telebot

bot = telebot.TeleBot("KATY_BOT_TOKEN", parse_mode=None)


@bot.message_handler(content_types=["new_chat_members"])
def hello(message):
    for new_user in message.new_chat_members:
        user_id = new_user.id
        user_name = new_user.first_name
        mention = "[" + user_name + "](tg://user?id=" + str(user_id) + ")"
        bot.send_message(
            message.chat.id,
            reply_to_message_id=message.id,
            text="Добро пожаловать в чат {}!\n Пожалуйста не забудь проголосовать в опросе :) \n https://t.me/c/2062868616/107".format(
                mention
            ),
            parse_mode="Markdown",
        )


bot.infinity_polling()
