import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))
chat_creator = 43529628

conn = sqlite3.connect("memes.db", check_same_thread=False)


def main():
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT user_id,username, ROUND(CAST(SUM(up_votes) as float) / CAST(COUNT(*) as float), 3), SUM(up_votes), COUNT(*) FROM memes_posts WHERE created_at > ? GROUP BY user_id, username ORDER BY CAST(SUM(up_votes) as float) / CAST(COUNT(*) as float) DESC"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    msg = ["AML - Average Meme Likes\n"]
    stack = ["🥉", "🥈", "🥇"]
    gold_user_id = None
    gold_username = None
    low_memes_count = []
    for row in rows:
        user_id, username, aml, total_up_votes, total_count = row
        reward = "🤡"
        if stack and total_count > 10:
            reward = stack.pop()
            if not gold_user_id and not gold_username:
                gold_username = username
                gold_user_id = user_id
        message = "[{username}](tg://user?id={user_id}) - {aml} - {reward} (total up votes {total_up_votes}, total memes count {total_count})".format(
            username=username,
            user_id=user_id,
            aml=aml,
            reward=reward,
            total_up_votes=total_up_votes,
            total_count=total_count,
        )
        if total_count <= 10:
            low_memes_count.append(message)
        else:
            msg.append(message)

    msg.append(
        "\n\n\nПользователи у которых <10 мемов в неделю не учавствуют в рейтинге\n\n"
    )
    for message in low_memes_count:
        msg.append(message)

    bot.send_message(
        memes_chat_id,
        "\n".join(msg),
        message_thread_id=flood_thread_id,
        parse_mode="Markdown",
    )
    if not gold_user_id:
        return

    try:
        if gold_user_id == chat_creator:
            bot.send_message(
                memes_chat_id,
                "Нельзя присвоить титул создателю чата, присвой себе сам [{}](tg://user?id={})".format(
                    gold_username, gold_user_id
                ),
                parse_mode="Markdown",
            )
        else:
            bot.set_chat_administrator_custom_title(
                chat_id=memes_chat_id,
                user_id=gold_user_id,
                custom_title="Dank boss",
            )
    except Exception as err:
        print(err)
        bot.send_message(
            memes_chat_id,
            "Опять криворукий разраб меня писал, ошибка",
            parse_mode="Markdown",
        )
    bot.send_message(
        memes_chat_id,
        "Почет и уважение новому босу данка на эту неделю! [{}](tg://user?id={})".format(
            gold_username, gold_user_id
        ),
        parse_mode="Markdown",
    )


if __name__ == "__main__":
    main()
