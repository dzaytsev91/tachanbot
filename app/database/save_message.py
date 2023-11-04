from datetime import datetime


def save_message(message, conn):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_messages (user_id, message_id, message_thread_id, created_at) VALUES(?, ?, ?, ?) ON CONFLICT DO NOTHING",
        (
            message.from_user.id,
            message.id,
            message.message_thread_id,
            datetime.now(),
        ),
    )
    conn.commit()
