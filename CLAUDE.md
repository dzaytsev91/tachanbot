# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run tests
make test
# or
python -m unittest discover -s tests

# Run a single test file
python -m unittest tests/test_cron_job_aml.py

# Format code
make format
# or
ruff format .

# Lint
ruff check .

# Run the bot locally (source env vars first)
source creds_dev.env
python main.py

# Run a cron job manually
source creds_dev.env
python app/cron_jobs/cron_job_aml.py
```

## Environment Variables

Required at runtime (see `creds_dev.env` for dev values):
- `BOT_TOKEN` — Telegram bot token
- `MEMES_CHAT_ID` — ID of the main Telegram group
- `MEMES_THREAD_ID` — Topic thread ID for memes
- `FLOOD_THREAD_ID` — Topic thread ID for general chat
- `MUSIC_THREAD_ID` — Topic thread ID for music
- `EXTERNAL_CHANNEL_CHAT_ID` — External channel where memes are reposted

## Architecture

**`main.py`** — Bot entry point. Registers all handlers and runs `infinity_polling`. Reads thread/chat IDs from env vars at startup and passes them into handler functions.

**`app/database/create_db_connection.py`** — `init_db()` creates the SQLite schema on first run. The `memes.db` file lives at the project root and is mounted as a Docker volume. Tables: `memes_posts_v2`, `user_votes`, `user_messages`, `users`, `music_posts`, `music_votes`, `dank_boss_titles`.

**`app/handlers/`** — Message handling logic:
- `meme_handler.py` — Receives media in the memes thread, computes perceptual image hash for duplicate detection, copies the message to both memes thread and flood thread plus the external channel, saves to DB, deletes the original.
- `music_handler.py` — Detects YouTube links in the music thread, downloads as MP3 via `yt-dlp` (requires `aria2c` and optionally `cookies.txt`), sends as audio, copies to flood thread with voting buttons.

**`app/commands/`** — Slash command handlers (`/statistic`, `/myaml`, `/chatid`, `/topicid`).

**`app/cron_jobs/`** — Standalone scripts meant to be run on a schedule (not imported by `main.py`):
- `cron_job_aml.py` — Weekly AML (Average Meme Likes) report. Calculates `(up_votes - down_votes) / count` per user for the past week, posts a ranked leaderboard to the flood thread, promotes top-3 to admin, assigns the "Dank boss" custom title to the winner (saves and restores previous titles via `dank_boss_titles` table). Requires ≥5 memes (`MINIMUM_MEMES_COUNT`) to qualify for ranking.
- `cron_job.py` — Posts medal emoji replies on the top-3 memes of the last 7 days.
- `cron_job_likes.py`, `cron_job_old_hats.py`, `cron_job_message_count.py` — Other scheduled tasks.

**`app/utils/markup.py`** — `generate_markup()` builds the inline keyboard (👍/👎/🪗 buttons). The callback data format is `{prefix}_{action}|{message_id}` (e.g. `vote_up|42`).

## Voting Architecture

Each meme is stored once in `memes_posts_v2` with three message IDs: `memes_thread_message_id`, `flood_thread_message_id`, and `channel_message_id`. When a vote button is pressed, the handler updates vote counts and re-renders the markup on all three message copies. Channel votes (`vote_channel_*`) are tracked separately but displayed as combined totals on the channel copy.

## Pre-commit / CI

Pre-commit runs `ruff` (lint + format) and standard file checks. Install hooks with `make pre-commit`.
