import random


def process_left_member(message, bot, conn):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET active=0 WHERE user_id=?",
        (message.from_user.id,),
    )

    conn.commit()
    bot.send_message(
        message.chat.id,
        random.choice(
            [
                "Ну и пиздуй",
                "Аривидерчи",
                "Адьос",
                "Чао-какао",
                "Оревуар",
                "Ассаламу алейкум, брат",
            ]
        ),
        reply_to_message_id=message.message_id,
    )
