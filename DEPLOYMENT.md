# Dokploy deployment

Deploy `docker-compose.dokploy.yml` as a Docker Compose service. The bot uses
Telegram long polling, so it must run with exactly one replica and does not need
a domain or an exposed port.

## Environment

Set these values in the Compose environment editor:

```env
BOT_TOKEN=...
MEMES_CHAT_ID=...
MEMES_THREAD_ID=...
FLOOD_THREAD_ID=...
MUSIC_THREAD_ID=...
EXTERNAL_CHANNEL_CHAT_ID=...
CHAT_CREATOR_ID=43529628
TZ=Europe/Moscow
```

`DB_PATH` and `BACKUP_DIR` are set by the Compose file. Do not change
`COMPOSE_PROJECT_NAME`; Dokploy uses it to locate the service for scheduled
Compose jobs.

## Existing database cutover

Do not deploy over an existing bot by starting with an empty named volume. The
old `memes.db` contains meme history, votes, users, and saved administrator
titles. Before the first production start:

1. Disable the old schedules and stop the old polling bot so only one instance
   can consume Telegram updates.
2. Create a consistent SQLite snapshot with the SQLite backup API, or copy the
   database only after a clean shutdown. Do not copy a live `.db` while ignoring
   its `-wal` file.
3. Determine the timezone used by historical naïve timestamps. New writes use
   `Europe/Moscow`; convert historical timestamps once if the old runtime used a
   different timezone.
4. Import the snapshot as `/data/memes.db` in the `tachanbot_data` volume and
   make `/data` recursively writable by UID `10001`.
5. Before starting the bot, run `PRAGMA integrity_check` and compare row counts
   for `memes_posts_v2`, `user_votes`, `users`, and `dank_boss_titles` with the
   source snapshot.
6. Start the bot first. Enable the new schedules only after confirming whether
   the old scheduler already published the current reporting period.

For a deliberately fresh installation, record that no database import is
required before allowing the empty volume to initialize.

## Scheduled Compose jobs

Create jobs for the `bot` service and select the `Europe/Moscow` timezone:

| Name | Schedule | Command |
| --- | --- | --- |
| Weekly report | `0 9 * * 1` | `python -m app.cron_jobs.weekly_report` |
| Inactive users | `15 9 * * 1` | `python -m app.cron_jobs.inactive_users` |
| SQLite backup | `0 3 * * *` | `python -m app.cron_jobs.backup_database` |

Weekly report sections and the inactive-users report claim their reporting
period in `job_runs` before contacting Telegram. Re-running the same schedule
therefore does not duplicate messages or administrative actions. Inspect a
failed run before deleting its `job_runs` row for a deliberate retry.

The backup job creates a consistent online SQLite backup, verifies it, and
keeps the latest 14 local copies. Configure a Dokploy named-volume backup to
S3-compatible storage as protection against loss of the server itself.
