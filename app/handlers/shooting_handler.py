import random
import time
from datetime import datetime, timedelta


def start_shooting(message, bot, conn, memes_chat_link_id):
    test_mode = "тест" in message.text.lower()
    two_weeks_ago = datetime.now() - timedelta(days=14)
    query = "SELECT u.user_id, u.username from user_messages um join users u ON u.user_id = um.user_id AND u.joined_date < ? group by um.user_id having  max(created_at) < ?;"
    rows = conn.execute(query, (two_weeks_ago, two_weeks_ago)).fetchall()
    msg = ["Список вуаеристов на расстрел\n"]
    users_to_shoot = []
    for row in rows:
        user_id, username = row
        user_data = bot.get_chat_member(memes_chat_link_id, user_id)
        if user_data.status == "administrator":
            continue
        msg.append(
            "{username} - {user_id}".format(
                username=username,
                user_id=user_id,
            )
        )
        users_to_shoot.append([username, user_id])
    if len(users_to_shoot) < 1:
        bot.send_message(
            memes_chat_link_id,
            "Всех неверных уже расстреляли",
            message_thread_id=message.message_thread_id,
            parse_mode="Markdown",
        )
        return

    bot.send_message(
        memes_chat_link_id,
        "\n".join(msg),
        message_thread_id=message.message_thread_id,
        parse_mode="Markdown",
    )
    time.sleep(1)

    bot.send_message(
        memes_chat_link_id,
        "Заряжаем пистолет 🔫",
        message_thread_id=message.message_thread_id,
        parse_mode="Markdown",
    )
    target_to_shot = random.choice(users_to_shoot)
    time.sleep(1)
    msg = "Кара пала на - [{username}](tg://user?id={user_id}) {user_id}".format(
        username=target_to_shot[0], user_id=target_to_shot[1]
    )
    bot.send_message(
        memes_chat_link_id,
        msg,
        message_thread_id=message.message_thread_id,
        parse_mode="Markdown",
    )
    if test_mode:
        bot.send_message(
            memes_chat_link_id,
            "Попался холостой патрон",
            message_thread_id=message.message_thread_id,
            parse_mode="Markdown",
        )
    else:
        bot.ban_chat_member(
            memes_chat_link_id,
            target_to_shot[1],
        )
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET active=0 WHERE user_id=?",
            (target_to_shot[1],),
        )
        conn.commit()
