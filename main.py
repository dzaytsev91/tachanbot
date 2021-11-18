import os

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))


@bot.message_handler(content_types=['photo','video'])
def send_rand_photo(message):
    bot.send_poll(message.chat.id, "Норм?", ['👍', "👎"])


def main():
    bot.infinity_polling(allowed_updates=telebot.util.update_types)


if __name__ == '__main__':
    main()
