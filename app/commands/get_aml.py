from datetime import datetime, timedelta

from main import bot, memes_thread_id, conn


@bot.message_handler(commands=["myaml"])
def get_my_aml(message):
    if message.message_thread_id == memes_thread_id:
        bot.delete_message(message.chat.id, message.id)
        return
    seven_days_ago = datetime.now() - timedelta(days=7)
    query = "SELECT ROUND(CAST((SUM(up_votes) - SUM(down_votes)) as float) / CAST(COUNT(*) as float), 3), COUNT(*) FROM memes_posts_v2 WHERE created_at > ? AND user_id = ? ORDER BY ROUND(CAST((SUM(up_votes) - SUM(down_votes)) as float) / CAST(COUNT(*) as float), 3) / CAST(COUNT(*) as float) DESC"
    aml = conn.execute(query, (seven_days_ago, str(message.from_user.id))).fetchone()
    return bot.send_message(
        message.chat.id,
        "Your aml is: {}".format(aml),
        reply_to_message_id=message.id,
        message_thread_id=message.message_thread_id,
    )
