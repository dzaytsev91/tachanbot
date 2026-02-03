import os
import sqlite3
from datetime import date

import telebot
from dateutil.relativedelta import relativedelta, MO

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
memes_chat_id = int(os.getenv("MEMES_CHAT_ID"))
flood_thread_id = int(os.getenv("FLOOD_THREAD_ID", 1))
memes_thread_id = int(os.getenv("MEMES_THREAD_ID", 1))
chat_creator = 43529628
minimum_memes_count = 5
db_path = os.path.join(
    os.path.abspath(__file__).rsplit(os.sep, maxsplit=3)[0], "memes.db"
)
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS dank_boss_titles (user_id int PRIMARY KEY, old_title string, assigned_at timestamp);"
)


def restore_previous_boss_title(new_boss_user_id):
    rows = conn.execute("SELECT user_id, old_title FROM dank_boss_titles").fetchall()
    if not rows:
        return
    for previous_boss_id, old_title in rows:
        if new_boss_user_id and previous_boss_id == new_boss_user_id:
            continue
        try:
            member = bot.get_chat_member(memes_chat_id, previous_boss_id)
            if member.status in ("administrator", "creator"):
                bot.set_chat_administrator_custom_title(
                    memes_chat_id, previous_boss_id, old_title or ""
                )
        except Exception as err:
            print(err)
        finally:
            conn.execute(
                "DELETE FROM dank_boss_titles WHERE user_id = ?",
                (previous_boss_id,),
            )
            conn.commit()


def save_boss_old_title(user_id):
    row = conn.execute(
        "SELECT user_id FROM dank_boss_titles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row:
        return False
    try:
        member = bot.get_chat_member(memes_chat_id, user_id)
        old_title = member.custom_title or ""
    except Exception as err:
        print(err)
        old_title = ""
    conn.execute(
        "INSERT OR REPLACE INTO dank_boss_titles (user_id, old_title, assigned_at) VALUES(?, ?, ?);",
        (user_id, old_title, date.today()),
    )
    conn.commit()
    return True


def main():
    today = date.today()
    last_monday = today + relativedelta(weekday=MO(-2))
    query = "SELECT user_id, username, ROUND(CAST((SUM(up_votes) - SUM(down_votes)) as float) / CAST(COUNT(*) as float), 3),  SUM(up_votes), COUNT(*) FROM memes_posts_v2 WHERE created_at > ? GROUP BY user_id, username ORDER BY ROUND(CAST((SUM(up_votes) - SUM(down_votes)) as float) / CAST(COUNT(*) as float), 3) DESC"
    rows = conn.execute(query, (last_monday,)).fetchall()
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
                            username,
                            user_id,
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
    saved_title = False
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
            restore_previous_boss_title(gold_user_id)
            saved_title = save_boss_old_title(gold_user_id)
            bot.set_chat_administrator_custom_title(
                chat_id=memes_chat_id,
                user_id=gold_user_id,
                custom_title="Dank boss",
            )
    except Exception as err:
        if gold_user_id and gold_user_id != chat_creator and saved_title:
            conn.execute(
                "DELETE FROM dank_boss_titles WHERE user_id = ?",
                (gold_user_id,),
            )
            conn.commit()
        bot.send_message(
            memes_chat_id,
            "Ошибка, error: {}".format(err),
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
