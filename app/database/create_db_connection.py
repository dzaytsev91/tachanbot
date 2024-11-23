import sqlite3


def init_db(db_name: str):
    conn = sqlite3.connect(db_name, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memes_posts_v2 (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, user_id int, username string, old_hat_votes int, flood_thread_message_id int, memes_thread_message_id int, channel_message_id int, hash string, channel_up_votes int, channel_down_votes int);"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_messages (user_id int, message_id int, message_thread_id int, created_at timestamp);"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (user_id int, username string, active bool, joined_date timestamp);"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_votes (user_id int, meme_id int, constraint user_votes_pk unique (user_id, meme_id));"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS music_votes (user_id int, music_id int, constraint user_music_votes_pk unique (user_id, music_id));"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS music_posts (id integer PRIMARY KEY, up_votes int, down_votes int, created_at timestamp,message_id int, user_id int, username string, old_hat_votes int, flood_thread_message_id int, music_thread_message_id int);"
    )
    return conn
