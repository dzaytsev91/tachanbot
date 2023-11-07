from datetime import date
from dateutil.relativedelta import relativedelta, MO


def process_my_aml(bot, message, conn, memes_thread_id):
    if message.message_thread_id == memes_thread_id:
        bot.delete_message(message.chat.id, message.id)
        return
    today = date.today()
    last_monday = today + relativedelta(weekday=MO(-1))
    query = "SELECT ROUND(CAST((SUM(up_votes) - SUM(down_votes)) as float) / CAST(COUNT(*) as float), 3), COUNT(*) FROM memes_posts_v2 WHERE created_at > ? AND user_id = ? ORDER BY ROUND(CAST((SUM(up_votes) - SUM(down_votes)) as float) / CAST(COUNT(*) as float), 3) / CAST(COUNT(*) as float) DESC"
    aml = conn.execute(query, (last_monday, str(message.from_user.id))).fetchone()
    return bot.send_message(
        message.chat.id,
        "Your aml is: {}".format(aml),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )
