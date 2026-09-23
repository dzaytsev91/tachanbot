from __future__ import annotations

from datetime import timedelta

import telebot

from app.config import AppConfig
from app.cron_jobs.cron_job_message_count import send_inactive_users
from app.cron_jobs.job_runner import run_once
from app.cron_jobs.periods import current_week_key, local_now
from app.database.create_db_connection import init_db


def main() -> None:
    config = AppConfig.from_env()
    bot = telebot.TeleBot(config.bot_token)
    conn = init_db(config.db_path)
    try:
        run_once(
            conn,
            "inactive-users",
            current_week_key(),
            lambda: send_inactive_users(
                bot,
                conn,
                config.memes_chat_id,
                config.flood_thread_id,
                local_now().replace(tzinfo=None) - timedelta(days=14),
            ),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
