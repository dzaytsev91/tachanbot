import telebot

bot = telebot.TeleBot('2130478122:AAHE1jvoTMKc3hGbPbzonFiyND86k_hc2Pg')


@bot.message_handler(content_types=['photo','video'])
def send_rand_photo(message):
    bot.send_poll(message.chat.id, "Норм?", ['👍', "👎"])


def main():
    bot.infinity_polling(allowed_updates=telebot.util.update_types)


if __name__ == '__main__':
    main()
