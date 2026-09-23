from __future__ import annotations

import logging

import telebot

from app.config import AppConfig
from app.cron_jobs.cron_job import send_top_memes
from app.cron_jobs.cron_job_aml import Config as AmlConfig
from app.cron_jobs.cron_job_aml import MemeRatingBot
from app.cron_jobs.cron_job_old_hats import send_old_hat_winner
from app.cron_jobs.job_runner import run_once
from app.cron_jobs.periods import previous_week
from app.database.create_db_connection import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    config = AppConfig.from_env()
    bot = telebot.TeleBot(config.bot_token)
    conn = init_db(config.db_path)
    period = previous_week()
    aml_config = AmlConfig(
        bot_token=config.bot_token,
        memes_chat_id=config.memes_chat_id,
        flood_thread_id=config.flood_thread_id,
        memes_thread_id=config.memes_thread_id,
        chat_creator_id=config.chat_creator_id,
        db_path=config.db_path,
    )
    rating_bot = MemeRatingBot(aml_config, bot=bot, conn=conn)
    jobs = [
        (
            "weekly-top-memes",
            lambda: send_top_memes(
                bot,
                conn,
                config.memes_chat_id,
                config.memes_thread_id,
                period.start,
                period.end,
            ),
        ),
        ("weekly-aml", lambda: rating_bot.run(period.start, period.end)),
        (
            "weekly-old-hat",
            lambda: send_old_hat_winner(
                bot,
                conn,
                config.memes_chat_id,
                config.flood_thread_id,
                period.start,
                period.end,
            ),
        ),
    ]

    failures = 0
    try:
        for job_name, action in jobs:
            try:
                run_once(conn, job_name, period.key, action)
            except Exception:
                failures += 1
                logger.exception("Weekly report section failed: %s", job_name)
    finally:
        conn.close()

    if failures:
        raise SystemExit(f"{failures} weekly report section(s) failed")


if __name__ == "__main__":
    main()
