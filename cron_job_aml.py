import os
import sqlite3
from datetime import datetime, timedelta

import telebot

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))
chat_creator = 43529628
minimum_memes_count = 10
conn = sqlite3.connect("memes.db", check_same_thread=False)


def main():
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT ROUND(CAST((SUM(up_votes) - SUM(down_votes) - SUM(old_hat_votes)) as float) / CAST(COUNT(*) as float), 3), COUNT(*) FROM memes_posts_v2 WHERE created_at > ? AND user_id = ? ORDER BY ROUND(CAST((SUM(up_votes) - SUM(down_votes) - SUM(old_hat_votes)) as float) / CAST(COUNT(*) as float), 3) / CAST(COUNT(*) as float) DESC"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    msg = ["AML - Average Meme Likes\n"]
    stack = ["🥉", "🥈", "🥇"]
    gold_user_id = None
    gold_username = None
    low_memes_count = []
    for row in rows:
        user_id, username, aml, total_up_votes, total_count = row
        reward = "🤡"
        if stack and total_count >= minimum_memes_count:
            reward = stack.pop()
            if not gold_user_id and not gold_username:
                gold_username = username
                gold_user_id = user_id
            try:
                user_data = bot.get_chat_member(memes_chat_id, user_id)
                if user_data.status != "administrator":
                    bot.promote_chat_member(
                        memes_chat_id,
                        user_id,
                        can_post_messages=True,
                        can_invite_users=True,
                        can_pin_messages=True,
                        can_manage_chat=True,
                        can_manage_video_chats=True,
                        can_manage_voice_chats=True,
                        can_manage_topics=True,
                    )
                    bot.set_chat_administrator_custom_title(
                        memes_chat_id, user_id, "дух"
                    )
                    bot.send_message(
                        memes_chat_id,
                        "Чествуем новых админов! [{}](tg://user?id={})".format(
                            username, user_id
                        ),
                    )
            except Exception as err:
                print(err)
        message = "[{username}](tg://user?id={user_id}) - {aml} - {reward} (total up votes {total_up_votes}, total memes count {total_count})".format(
            username=username,
            user_id=user_id,
            aml=aml,
            reward=reward,
            total_up_votes=total_up_votes,
            total_count=total_count,
        )
        if total_count < minimum_memes_count:
            low_memes_count.append(message)
        else:
            msg.append(message)

    msg.append(
        "\n\n\nПользователи у которых <{} мемов в неделю не учавствуют в рейтинге\n\n".format(
            minimum_memes_count
        )
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
                message_thread_id=flood_thread_id,
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
            message_thread_id=flood_thread_id,
            parse_mode="Markdown",
        )
    bot.send_message(
        memes_chat_id,
        "Почет и уважение новому босу данка на эту неделю! [{}](tg://user?id={})".format(
            gold_username, gold_user_id
        ),
        message_thread_id=flood_thread_id,
        parse_mode="Markdown",
    )


if __name__ == "__main__":
    main()
