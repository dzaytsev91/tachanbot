from datetime import datetime, timedelta
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("agg")
matplotlib.rc("figure", figsize=(20, 5))


def process_statistic(bot, message, conn, memes_thread_id):
    if message.message_thread_id == memes_thread_id:
        bot.delete_message(message.chat.id, message.id)
        return
    seven_days_ago = datetime.now() - timedelta(days=14)
    query = "select date(created_at), count(*) from memes_posts_v2 WHERE created_at > ? group by date(created_at) order by date(created_at);"
    rows = conn.execute(query, (seven_days_ago,)).fetchall()
    date_time = []
    data = []
    for row in rows:
        date_time.append(row[0])
        data.append(row[1])

    date_time = pd.to_datetime(date_time)
    df = pd.DataFrame()
    df["value"] = data
    df = df.set_index(date_time)
    plt.plot(df, **{"marker": "o"})
    plt.gcf().autofmt_xdate()
    plt.title("Memes count")
    plt.grid()
    plt.savefig("test.png", dpi=300)
    plt.close()
    with open("test.png", "rb") as f:
        content = f.read()
    return bot.send_photo(
        message.chat.id,
        message_thread_id=message.message_thread_id,
        photo=content,
    )
